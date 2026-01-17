"""
Vision Language Model (VLM) extractor for document processing.

This module provides VLM-based extraction from PDF documents using
AWS Bedrock Claude Vision. It converts PDF pages to images and uses
Claude's vision capabilities to extract structured data from:
- 10-K SEC filings (financial statements, risk factors, segment data)
- Reference documents (news, research, policies)

The extractor is designed for the RAG pipeline, producing structured
JSON that can be stored in PostgreSQL and indexed in vector stores.

Usage:
    from src.ingestion.vlm_extractor import VLMExtractor

    extractor = VLMExtractor()
    result = await extractor.extract_document(
        pdf_path=Path("documents/apple_10k_2024.pdf"),
        doc_type="10k"
    )

Cost Notes:
    - Claude Vision ~$0.003/image input + $0.015/1K output tokens
    - ~$0.03-0.05 per page typical for 10-K pages
    - ~$0.02-0.03 per page for reference documents

Reference:
    - backend.mdc for Python patterns
    - agent.mdc for Bedrock integration patterns
    - AWS Bedrock Claude documentation
    - pdf2image documentation: https://pdf2image.readthedocs.io/
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
from pathlib import Path
from typing import Any

import structlog
from botocore.exceptions import ClientError
from PIL import Image
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config.settings import get_settings

# Configure structured logger
logger = structlog.get_logger(__name__)

# =============================================================================
# Constants
# =============================================================================

# Default VLM model for document extraction
# NOTE: Claude 3.5 Sonnet V2 was deprecated Oct 2025, shutdown Feb 2026
# Using Claude Sonnet 4.5 (released Sep 2025) - the current recommended model
# To verify available models: aws bedrock list-foundation-models --query "modelSummaries[?contains(modelId, 'claude')]"
DEFAULT_VLM_MODEL_ID = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"

# Fallback model if primary not available
FALLBACK_VLM_MODEL_ID = "anthropic.claude-3-5-sonnet-20241022-v2:0"  # Deprecated but may still work until Feb 2026

# PDF to image conversion settings
DEFAULT_DPI = 150  # Balance between quality and file size
DEFAULT_IMAGE_FORMAT = "JPEG"  # Good compression, supported by Claude Vision

# Retry settings for Bedrock API calls
MAX_RETRIES = 3
MIN_RETRY_WAIT = 2  # seconds
MAX_RETRY_WAIT = 10  # seconds

# Max tokens for Claude response
MAX_TOKENS = 4096

# Rate limiting - delay between page extractions to avoid throttling
PAGE_DELAY_SECONDS = 0.5  # Half second between pages

# Image size limits for Bedrock
MAX_IMAGE_DIMENSION = 4096  # Max pixels on any side
MAX_IMAGE_SIZE_BYTES = (
    5 * 1024 * 1024
)  # 5MB max (Bedrock limit is ~20MB, use 5MB for safety)


# =============================================================================
# Extraction Prompts
# =============================================================================

EXTRACTION_PROMPT_10K = """You are extracting structured data from a 10-K SEC filing page.

Extract ALL content from this page and return as JSON with these keys:

{
  "page_number": <int>,
  "section": "<section name, e.g., 'Item 1A: Risk Factors', 'Item 8: Financial Statements'>",
  "content_type": "<narrative|table|mixed>",
  "text": "<all narrative text on this page>",
  "tables": [
    {
      "table_name": "<descriptive name>",
      "table_type": "<income_statement|balance_sheet|cash_flow|segment_revenue|geographic_revenue|other>",
      "headers": ["Column1", "Column2", ...],
      "rows": [
        {"label": "Revenue", "values": {"2024": "394328", "2023": "383285"}},
        ...
      ]
    }
  ],
  "financial_metrics": {
    "fiscal_year": <int or null if not on this page>,
    "revenue": <number in millions or null>,
    "cost_of_revenue": <number in millions or null>,
    "gross_profit": <number in millions or null>,
    "operating_expenses": <number in millions or null>,
    "operating_income": <number in millions or null>,
    "net_income": <number in millions or null>,
    "total_assets": <number in millions or null>,
    "total_liabilities": <number in millions or null>,
    "total_equity": <number in millions or null>,
    "cash_and_equivalents": <number in millions or null>,
    "long_term_debt": <number in millions or null>,
    "gross_margin": <percentage as decimal, e.g., 46.5 for 46.5%, or null>,
    "operating_margin": <percentage as decimal or null>,
    "net_margin": <percentage as decimal or null>,
    "earnings_per_share": <number or null>,
    "diluted_eps": <number or null>,
    "currency": "USD"
  },
  "segment_data": [
    {"segment_name": "iPhone", "revenue": 200583, "fiscal_year": 2024, "percentage_of_total": 50.8}
  ],
  "geographic_data": [
    {"region": "Americas", "revenue": 167045, "fiscal_year": 2024, "percentage_of_total": 42.3}
  ],
  "risk_factors": [
    {"category": "Supply Chain", "title": "Manufacturing concentration in Asia", "summary": "Significant manufacturing operations concentrated in Asia Pacific region pose supply chain disruption risks", "severity": "high"}
  ],
  "cross_references": ["Note 12", "See Item 7"]
}

IMPORTANT EXTRACTION RULES:
1. For financial tables: Parse EVERY row, preserve column headers for year identification
2. For numbers: Remove $ and commas, convert 'million'/'billion' to raw millions (e.g., '$394.3 billion' → 394300)
3. If a metric spans multiple years, include ALL years found
4. For segment/geographic data: Only extract if this page contains segment or geographic revenue breakdowns. Calculate percentage_of_total if total revenue is available on the page
5. Set fields to null if not present on THIS page (will be consolidated later)
6. For risk factors: Only extract from Item 1A pages, categorize by type (Supply Chain, Regulatory, Competition, Macroeconomic, Technology, Legal), include a brief summary (1-2 sentences)
7. For segment_data and geographic_data: Include percentage_of_total as a decimal (e.g., 50.8 for 50.8%)

Return ONLY valid JSON, no markdown code blocks or explanatory text."""

EXTRACTION_PROMPT_REFERENCE = """You are extracting content from a reference document (news article, research report, or policy document).

Extract ALL content from this page and return as JSON:

{
  "page_number": <int>,
  "document_type": "<news|research|policy|other>",
  "content_type": "<narrative|table|mixed>",
  "text": "<all text content>",
  "headline": "<main headline if this is page 1, else null>",
  "publication_date": "<YYYY-MM-DD if found, else null>",
  "source": "<publication name if found, e.g., 'Reuters', 'Financial Times'>",
  "key_claims": [
    {"claim": "<factual assertion that could be verified>", "entities": ["Entity1", "Entity2"]}
  ],
  "entities_mentioned": ["Apple", "Tim Cook", "China", ...],
  "tables": [
    {
      "table_name": "<descriptive name>",
      "table_type": "<other>",
      "headers": ["Column1", "Column2", ...],
      "rows": [
        {"label": "Row1", "values": {"Col1": "value1", "Col2": "value2"}}
      ]
    }
  ],
  "cross_references": []
}

EXTRACTION RULES:
1. Extract ALL claims that could be verified against official sources (10-Ks, earnings reports)
2. Identify entities: companies, people, locations, financial metrics, dates
3. For key_claims: Focus on numerical claims and assertions about company performance

Return ONLY valid JSON, no markdown code blocks or explanatory text."""


# =============================================================================
# Exceptions
# =============================================================================


class VLMExtractionError(Exception):
    """Base exception for VLM extraction errors."""

    pass


class PDFConversionError(VLMExtractionError):
    """Error during PDF to image conversion."""

    pass


class BedrockInvocationError(VLMExtractionError):
    """Error invoking Bedrock API."""

    pass


class JSONParsingError(VLMExtractionError):
    """Error parsing JSON response from LLM."""

    pass


# =============================================================================
# VLMExtractor Class
# =============================================================================


class VLMExtractor:
    """
    Vision Language Model extractor for document processing.

    Uses AWS Bedrock Claude Vision to extract structured data from PDF
    documents. Supports different extraction prompts for different
    document types (10-K filings vs reference documents).

    Attributes:
        model_id: Bedrock model ID for Claude Vision.
        _client: Boto3 Bedrock Runtime client (lazy initialized).

    Example:
        extractor = VLMExtractor()
        result = await extractor.extract_document(
            pdf_path=Path("apple_10k.pdf"),
            doc_type="10k"
        )
        print(result["pages"][0]["financial_metrics"])
    """

    def __init__(
        self,
        model_id: str = DEFAULT_VLM_MODEL_ID,
        fallback_model_id: str = FALLBACK_VLM_MODEL_ID,
    ) -> None:
        """
        Initialize the VLM extractor.

        Args:
            model_id: Bedrock model ID for Claude Vision.
                Defaults to Claude Sonnet 4.5 (the latest as of Jan 2026).
            fallback_model_id: Fallback model if primary is unavailable.
        """
        self.model_id = model_id
        self.fallback_model_id = fallback_model_id
        self._client: Any = None
        self._log = logger.bind(model_id=model_id)
        self._log.info("vlm_extractor_initialized")

    def _get_client(self) -> Any:
        """
        Get or create the Bedrock Runtime client.

        Returns:
            Boto3 Bedrock Runtime client.

        Raises:
            BedrockInvocationError: If client creation fails.
        """
        if self._client is None:
            try:
                import boto3

                settings = get_settings()
                self._client = boto3.client(
                    "bedrock-runtime",
                    region_name=settings.aws_region,
                )
                self._log.debug("bedrock_client_created", region=settings.aws_region)
            except Exception as e:
                self._log.error("bedrock_client_creation_failed", error=str(e))
                raise BedrockInvocationError(
                    f"Failed to create Bedrock client: {e}"
                ) from e
        return self._client

    async def verify_model_access(self, check_fallback: bool = True) -> dict[str, Any]:
        """
        Verify that the configured Bedrock model is accessible.

        Use this before starting batch extraction to catch permission
        issues early. Will check both primary and fallback models if configured.

        Args:
            check_fallback: If True, also verify fallback model (default True).

        Returns:
            Dict with status and model info for accessible models.

        Raises:
            BedrockInvocationError: If no model is accessible.
        """
        self._log.info(
            "verifying_model_access",
            primary_model=self.model_id,
            fallback_model=self.fallback_model_id,
        )

        import boto3

        settings = get_settings()
        bedrock = boto3.client("bedrock", region_name=settings.aws_region)

        async def _check_model(model_id: str) -> dict[str, Any] | None:
            """Check a single model and return info if accessible."""
            try:
                # Extract model identifier for API call (remove version suffix)
                model_identifier = model_id.split(":")[0]

                response = await asyncio.to_thread(
                    bedrock.get_foundation_model,
                    modelIdentifier=model_identifier,
                )

                model_details = response.get("modelDetails", {})
                input_modalities = model_details.get("inputModalities", [])

                if "IMAGE" not in input_modalities:
                    self._log.warning(
                        "model_no_vision_support",
                        model_id=model_id,
                        modalities=input_modalities,
                    )
                    return None

                return {
                    "model_id": model_id,
                    "model_name": model_details.get("modelName"),
                    "supports_vision": True,
                    "modalities": input_modalities,
                }
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                self._log.warning(
                    "model_not_accessible",
                    model_id=model_id,
                    error_code=error_code,
                )
                return None
            except Exception as e:
                self._log.warning(
                    "model_check_failed",
                    model_id=model_id,
                    error=str(e),
                )
                return None

        # Check primary model
        primary_result = await _check_model(self.model_id)

        # Check fallback if requested and different from primary
        fallback_result = None
        if (
            check_fallback
            and self.fallback_model_id
            and self.fallback_model_id != self.model_id
        ):
            fallback_result = await _check_model(self.fallback_model_id)

        # Determine best available model
        if primary_result:
            self._log.info(
                "model_access_verified",
                model_id=self.model_id,
                model_name=primary_result.get("model_name"),
            )
            return {
                "status": "ok",
                "active_model": self.model_id,
                "primary": primary_result,
                "fallback": fallback_result,
            }
        elif fallback_result:
            self._log.warning(
                "using_fallback_model",
                primary_model=self.model_id,
                fallback_model=self.fallback_model_id,
            )
            # Switch to fallback model
            self.model_id = self.fallback_model_id
            return {
                "status": "ok_fallback",
                "active_model": self.fallback_model_id,
                "primary": None,
                "fallback": fallback_result,
                "note": "Primary model not accessible, using fallback",
            }
        else:
            # Neither model accessible
            raise BedrockInvocationError(
                f"No Claude Vision model accessible.\n\n"
                f"Tried:\n"
                f"  - Primary: {self.model_id}\n"
                f"  - Fallback: {self.fallback_model_id}\n\n"
                f"To fix this:\n"
                f"1. Go to AWS Console → Amazon Bedrock → Model access\n"
                f"2. Request access to a Claude model with vision (e.g., Claude Sonnet 4.5)\n"
                f"3. Wait for access to be granted\n\n"
                f"To see available models, run:\n"
                f"  aws bedrock list-foundation-models --query "
                f"\"modelSummaries[?contains(modelId, 'claude')].{{id:modelId,name:modelName}}\""
            )

    def _check_poppler_installed(self) -> None:
        """
        Check if poppler-utils is installed on the system.

        Raises:
            PDFConversionError: If poppler is not installed.
        """
        import shutil

        if shutil.which("pdftoppm") is None:
            raise PDFConversionError(
                "poppler-utils is not installed. This is required for PDF processing.\n\n"
                "Install with:\n"
                "  Ubuntu/Debian (WSL): sudo apt-get install poppler-utils\n"
                "  macOS: brew install poppler\n"
                "  Windows: Download from https://github.com/oschwartz10612/poppler-windows/releases\n\n"
                "After installing, restart your terminal and try again."
            )

    def _get_pdf_page_count(self, pdf_path: Path) -> int:
        """
        Get the total number of pages in a PDF without loading all images.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            Number of pages in the PDF.
        """
        try:
            from pdf2image import pdfinfo_from_path

            info = pdfinfo_from_path(str(pdf_path))
            return info.get("Pages", 0)
        except Exception:
            # Fallback: just return 0, will be determined during iteration
            return 0

    def _pdf_page_to_image(
        self, pdf_path: Path, page_num: int, dpi: int = DEFAULT_DPI
    ) -> Image.Image:
        """
        Convert a single PDF page to a PIL Image object.

        Memory-efficient: only loads one page at a time.

        Args:
            pdf_path: Path to the PDF file.
            page_num: Page number (1-indexed).
            dpi: Resolution for image conversion (default 150).

        Returns:
            PIL Image object for the page.

        Raises:
            PDFConversionError: If PDF conversion fails.
        """
        try:
            from pdf2image import convert_from_path

            # Convert only the single page (first_page and last_page are 1-indexed)
            images = convert_from_path(
                pdf_path,
                dpi=dpi,
                fmt=DEFAULT_IMAGE_FORMAT.lower(),
                first_page=page_num,
                last_page=page_num,
            )
            if not images:
                raise PDFConversionError(f"Failed to extract page {page_num} from PDF")
            return images[0]
        except ImportError as e:
            raise PDFConversionError(
                "pdf2image not available. Install with: pip install pdf2image "
                "and ensure poppler-utils is installed on your system."
            ) from e
        except Exception as e:
            raise PDFConversionError(
                f"Failed to convert page {page_num} to image: {e}"
            ) from e

    def _pdf_to_images(
        self, pdf_path: Path, dpi: int = DEFAULT_DPI
    ) -> list[Image.Image]:
        """
        Convert PDF pages to PIL Image objects.

        Note: This method loads ALL pages into memory at once.
        For memory-efficient processing, use _pdf_page_to_image() for single pages.

        Args:
            pdf_path: Path to the PDF file.
            dpi: Resolution for image conversion (default 150).

        Returns:
            List of PIL Image objects, one per page.

        Raises:
            PDFConversionError: If PDF conversion fails.
        """
        self._log.info(
            "pdf_to_images_started",
            pdf_path=str(pdf_path),
            dpi=dpi,
        )

        if not pdf_path.exists():
            raise PDFConversionError(f"PDF file not found: {pdf_path}")

        # Check poppler is installed first
        self._check_poppler_installed()

        try:
            from pdf2image import convert_from_path

            images = convert_from_path(
                pdf_path,
                dpi=dpi,
                fmt=DEFAULT_IMAGE_FORMAT.lower(),
            )
            self._log.info(
                "pdf_to_images_completed",
                pdf_path=str(pdf_path),
                page_count=len(images),
            )
            return images
        except ImportError as e:
            raise PDFConversionError(
                "pdf2image not available. Install with: pip install pdf2image "
                "and ensure poppler-utils is installed on your system."
            ) from e
        except Exception as e:
            self._log.error(
                "pdf_to_images_failed",
                pdf_path=str(pdf_path),
                error=str(e),
            )
            raise PDFConversionError(f"Failed to convert PDF to images: {e}") from e

    def _resize_image_if_needed(self, image: Image.Image) -> Image.Image:
        """
        Resize image if it exceeds Bedrock's size limits.

        Args:
            image: PIL Image object.

        Returns:
            Resized image (or original if within limits).
        """
        width, height = image.size

        # Check if resize needed for dimensions
        if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
            # Calculate new size maintaining aspect ratio
            if width > height:
                new_width = MAX_IMAGE_DIMENSION
                new_height = int(height * (MAX_IMAGE_DIMENSION / width))
            else:
                new_height = MAX_IMAGE_DIMENSION
                new_width = int(width * (MAX_IMAGE_DIMENSION / height))

            self._log.debug(
                "resizing_image",
                original_size=(width, height),
                new_size=(new_width, new_height),
            )
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

        return image

    def _encode_image(self, image: Image.Image) -> tuple[str, str]:
        """
        Encode a PIL Image to base64 string.

        Resizes image if needed and adjusts quality to stay under size limits.

        Args:
            image: PIL Image object.

        Returns:
            Tuple of (base64_string, media_type).
        """
        # Resize if dimensions too large
        image = self._resize_image_if_needed(image)

        # Convert to RGB if necessary (for PNG with transparency)
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")

        # Try encoding with decreasing quality until size is acceptable
        quality = 85
        while quality >= 30:
            buffer = io.BytesIO()
            image.save(buffer, format=DEFAULT_IMAGE_FORMAT, quality=quality)
            buffer.seek(0)
            image_bytes = buffer.getvalue()

            if len(image_bytes) <= MAX_IMAGE_SIZE_BYTES:
                break

            self._log.debug(
                "reducing_image_quality",
                current_quality=quality,
                size_bytes=len(image_bytes),
            )
            quality -= 10

        if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
            self._log.warning(
                "image_still_large_after_compression",
                size_bytes=len(image_bytes),
                max_bytes=MAX_IMAGE_SIZE_BYTES,
            )

        base64_string = base64.standard_b64encode(image_bytes).decode("utf-8")
        media_type = f"image/{DEFAULT_IMAGE_FORMAT.lower()}"
        return base64_string, media_type

    def _get_extraction_prompt(self, doc_type: str, page_num: int) -> str:
        """
        Get the appropriate extraction prompt for document type.

        Args:
            doc_type: Document type ("10k" or "reference").
            page_num: Current page number (1-indexed).

        Returns:
            Extraction prompt string.
        """
        base_prompt = (
            EXTRACTION_PROMPT_10K
            if doc_type.lower() == "10k"
            else EXTRACTION_PROMPT_REFERENCE
        )
        return f"This is page {page_num}.\n\n{base_prompt}"

    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=MIN_RETRY_WAIT, max=MAX_RETRY_WAIT),
        retry=retry_if_exception_type((BedrockInvocationError,)),
        reraise=True,
    )
    async def _extract_page(
        self,
        image: Image.Image,
        page_num: int,
        doc_type: str,
    ) -> dict[str, Any]:
        """
        Extract structured data from a single page image.

        Uses Claude Vision via Bedrock Converse API to analyze the
        image and extract structured data according to the document type.

        Args:
            image: PIL Image of the page.
            page_num: Page number (1-indexed).
            doc_type: Document type ("10k" or "reference").

        Returns:
            Extracted data as a dictionary.

        Raises:
            BedrockInvocationError: If Bedrock API call fails.
            JSONParsingError: If response cannot be parsed as JSON.
        """
        log = self._log.bind(page_num=page_num, doc_type=doc_type)
        log.info("page_extraction_started")

        # Encode image
        base64_image, media_type = self._encode_image(image)

        # Get extraction prompt
        prompt = self._get_extraction_prompt(doc_type, page_num)

        # Build Converse API request
        client = self._get_client()

        try:
            # Prepare request parameters
            request_params = {
                "modelId": self.model_id,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "image": {
                                    "format": DEFAULT_IMAGE_FORMAT.lower(),
                                    "source": {
                                        "bytes": base64.standard_b64decode(
                                            base64_image
                                        ),
                                    },
                                },
                            },
                            {
                                "text": prompt,
                            },
                        ],
                    }
                ],
                "inferenceConfig": {
                    "maxTokens": MAX_TOKENS,
                    "temperature": 0.0,  # Deterministic for extraction
                },
            }

            # Use Converse API for Claude Vision
            # Run synchronous boto3 call in thread pool to avoid blocking event loop
            response = await asyncio.to_thread(
                client.converse,
                **request_params,
            )

            # Extract text from response
            output = response.get("output", {})
            message = output.get("message", {})
            content_blocks = message.get("content", [])

            response_text = ""
            for block in content_blocks:
                if "text" in block:
                    response_text += block["text"]

            # Log token usage for cost tracking
            usage = response.get("usage", {})
            log.info(
                "page_extraction_response_received",
                input_tokens=usage.get("inputTokens", 0),
                output_tokens=usage.get("outputTokens", 0),
            )

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))

            if error_code == "ThrottlingException":
                log.warning("bedrock_throttled", error=str(e))
                raise BedrockInvocationError(f"Bedrock throttled: {e}") from e

            # Try fallback model if primary model fails with access/not found errors
            if error_code in (
                "AccessDeniedException",
                "ResourceNotFoundException",
                "ValidationException",
            ):
                if self.model_id != self.fallback_model_id and self.fallback_model_id:
                    log.warning(
                        "primary_model_unavailable_trying_fallback",
                        primary_model=self.model_id,
                        fallback_model=self.fallback_model_id,
                        error_code=error_code,
                        error_message=error_message,
                    )
                    # Update request to use fallback model
                    request_params["modelId"] = self.fallback_model_id
                    try:
                        response = await asyncio.to_thread(
                            client.converse,
                            **request_params,
                        )
                        # If successful, switch to fallback for future requests
                        self.model_id = self.fallback_model_id
                        log.info(
                            "switched_to_fallback_model",
                            model_id=self.fallback_model_id,
                        )

                        # Extract text from fallback response
                        output = response.get("output", {})
                        message = output.get("message", {})
                        content_blocks = message.get("content", [])

                        response_text = ""
                        for block in content_blocks:
                            if "text" in block:
                                response_text += block["text"]

                        # Log token usage
                        usage = response.get("usage", {})
                        log.info(
                            "fallback_response_received",
                            input_tokens=usage.get("inputTokens", 0),
                            output_tokens=usage.get("outputTokens", 0),
                        )
                    except Exception as fallback_e:
                        log.error(
                            "fallback_model_also_failed",
                            error=str(fallback_e),
                        )
                        raise BedrockInvocationError(
                            f"Both primary and fallback models failed. "
                            f"Primary error: {error_message}. Fallback error: {fallback_e}"
                        ) from e
                else:
                    raise BedrockInvocationError(
                        f"Model {self.model_id} not available: {error_message}\n"
                        f"To check available models: aws bedrock list-foundation-models "
                        f"--query \"modelSummaries[?contains(modelId, 'claude')]\""
                    ) from e
            else:
                log.error(
                    "bedrock_invocation_failed", error=str(e), error_code=error_code
                )
                raise BedrockInvocationError(f"Bedrock invocation failed: {e}") from e
        except Exception as e:
            log.error("bedrock_invocation_failed", error=str(e))
            raise BedrockInvocationError(f"Bedrock invocation failed: {e}") from e

        # Parse JSON response
        try:
            # Clean up response - remove markdown code blocks if present
            cleaned_response = response_text.strip()
            if cleaned_response.startswith("```json"):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.startswith("```"):
                cleaned_response = cleaned_response[3:]
            if cleaned_response.endswith("```"):
                cleaned_response = cleaned_response[:-3]
            cleaned_response = cleaned_response.strip()

            result = json.loads(cleaned_response)

            # Ensure page_number is set
            result["page_number"] = page_num

            log.info("page_extraction_completed", page_num=page_num)
            return result

        except json.JSONDecodeError as e:
            log.error(
                "json_parsing_failed",
                error=str(e),
                raw_response=response_text[:500],  # Log first 500 chars for debugging
            )
            # Return a minimal structure with the raw text for manual review
            return {
                "page_number": page_num,
                "section": "unknown",
                "content_type": "narrative",
                "text": response_text,
                "tables": [],
                "financial_metrics": {},
                "segment_data": [],
                "geographic_data": [],
                "risk_factors": [],
                "cross_references": [],
                "_parsing_error": str(e),
                "_raw_response": response_text[:1000],
            }

    async def extract_document(
        self,
        pdf_path: Path,
        doc_type: str = "10k",
        start_page: int | None = None,
        end_page: int | None = None,
        memory_efficient: bool = True,
    ) -> dict[str, Any]:
        """
        Extract structured data from a PDF document.

        Converts the PDF to images and processes each page with
        Claude Vision to extract structured data.

        Args:
            pdf_path: Path to the PDF file.
            doc_type: Document type - "10k" for SEC 10-K filings,
                "reference" for news/research/policy documents.
            start_page: Optional starting page (1-indexed, inclusive).
            end_page: Optional ending page (1-indexed, inclusive).
            memory_efficient: If True, load one page at a time (recommended).
                If False, load all pages into memory at once.

        Returns:
            Dictionary containing:
            - document_path: Path to source document
            - doc_type: Document type
            - total_pages: Total pages in document
            - pages_processed: Number of pages processed
            - pages: List of extracted page data
            - consolidated_metrics: Merged financial metrics (for 10-K)
            - errors: List of any errors encountered

        Raises:
            PDFConversionError: If PDF cannot be converted to images.
            VLMExtractionError: If extraction fails completely.

        Example:
            result = await extractor.extract_document(
                pdf_path=Path("apple_10k.pdf"),
                doc_type="10k",
                start_page=50,  # Start from financial statements
                end_page=80,
            )
        """
        log = self._log.bind(
            pdf_path=str(pdf_path),
            doc_type=doc_type,
        )
        log.info("document_extraction_started")

        # Check PDF exists
        if not pdf_path.exists():
            raise PDFConversionError(f"PDF file not found: {pdf_path}")

        # Check poppler is installed
        self._check_poppler_installed()

        # Get total page count
        total_pages = self._get_pdf_page_count(pdf_path)
        if total_pages == 0:
            # Fallback: load all pages to count (less efficient)
            log.warning("could_not_get_page_count_efficiently")
            images = self._pdf_to_images(pdf_path)
            total_pages = len(images)
            memory_efficient = False  # Already loaded, might as well use them
        else:
            images = None

        # Determine page range
        start_idx = (start_page - 1) if start_page else 0
        end_idx = end_page if end_page else total_pages

        # Validate range
        start_idx = max(0, min(start_idx, total_pages - 1))
        end_idx = max(start_idx + 1, min(end_idx, total_pages))

        log.info(
            "page_range_determined",
            total_pages=total_pages,
            start_page=start_idx + 1,
            end_page=end_idx,
            memory_efficient=memory_efficient,
        )

        # Process pages
        pages_data: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []

        for idx in range(start_idx, end_idx):
            page_num = idx + 1
            try:
                # Get image for this page
                if memory_efficient or images is None:
                    # Load single page (memory efficient)
                    image = self._pdf_page_to_image(pdf_path, page_num)
                else:
                    # Use pre-loaded images
                    image = images[idx]

                page_data = await self._extract_page(
                    image=image,
                    page_num=page_num,
                    doc_type=doc_type,
                )
                pages_data.append(page_data)

                # Clear image from memory if we loaded it individually
                if memory_efficient:
                    del image

                # Add delay between pages to avoid rate limiting
                if idx < end_idx - 1:  # Don't delay after last page
                    await asyncio.sleep(PAGE_DELAY_SECONDS)

            except VLMExtractionError as e:
                log.error(
                    "page_extraction_failed",
                    page_num=page_num,
                    error=str(e),
                )
                errors.append(
                    {
                        "page_number": page_num,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    }
                )

        # Consolidate financial metrics (for 10-K documents)
        consolidated_metrics = {}
        if doc_type.lower() == "10k":
            consolidated_metrics = self._consolidate_financial_metrics(pages_data)

        result = {
            "document_path": str(pdf_path),
            "doc_type": doc_type,
            "total_pages": total_pages,
            "pages_processed": len(pages_data),
            "pages": pages_data,
            "consolidated_metrics": consolidated_metrics,
            "errors": errors,
        }

        log.info(
            "document_extraction_completed",
            pages_processed=len(pages_data),
            error_count=len(errors),
        )

        return result

    def _consolidate_financial_metrics(
        self,
        pages_data: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Consolidate financial metrics from all pages.

        Merges financial metrics found across multiple pages,
        taking the most recent non-null value for each metric.

        Args:
            pages_data: List of extracted page data.

        Returns:
            Consolidated financial metrics dictionary.
        """
        consolidated: dict[str, Any] = {
            "fiscal_years": [],
            "revenue_by_year": {},
            "cost_of_revenue_by_year": {},
            "gross_profit_by_year": {},
            "operating_expenses_by_year": {},
            "operating_income_by_year": {},
            "net_income_by_year": {},
            "total_assets_by_year": {},
            "total_liabilities_by_year": {},
            "total_equity_by_year": {},
            "cash_by_year": {},
            "debt_by_year": {},
            "gross_margin_by_year": {},
            "operating_margin_by_year": {},
            "net_margin_by_year": {},
            "eps_by_year": {},
            "diluted_eps_by_year": {},
            "currency": "USD",
            "all_segments": [],
            "all_geographic": [],
            "all_risk_factors": [],
        }

        for page in pages_data:
            metrics = page.get("financial_metrics", {})

            # Extract fiscal year
            fiscal_year = metrics.get("fiscal_year")
            if fiscal_year and fiscal_year not in consolidated["fiscal_years"]:
                consolidated["fiscal_years"].append(fiscal_year)

            # Map metrics by year
            if fiscal_year:
                year_str = str(fiscal_year)
                metric_mappings = [
                    ("revenue", "revenue_by_year"),
                    ("cost_of_revenue", "cost_of_revenue_by_year"),
                    ("gross_profit", "gross_profit_by_year"),
                    ("operating_expenses", "operating_expenses_by_year"),
                    ("operating_income", "operating_income_by_year"),
                    ("net_income", "net_income_by_year"),
                    ("total_assets", "total_assets_by_year"),
                    ("total_liabilities", "total_liabilities_by_year"),
                    ("total_equity", "total_equity_by_year"),
                    ("cash_and_equivalents", "cash_by_year"),
                    ("long_term_debt", "debt_by_year"),
                    ("gross_margin", "gross_margin_by_year"),
                    ("operating_margin", "operating_margin_by_year"),
                    ("net_margin", "net_margin_by_year"),
                    ("earnings_per_share", "eps_by_year"),
                    ("diluted_eps", "diluted_eps_by_year"),
                ]
                for metric_key, consolidated_key in metric_mappings:
                    value = metrics.get(metric_key)
                    if value is not None:
                        if consolidated_key not in consolidated:
                            consolidated[consolidated_key] = {}
                        consolidated[consolidated_key][year_str] = value

            # Collect segment data
            segments = page.get("segment_data", [])
            for segment in segments:
                if segment not in consolidated["all_segments"]:
                    consolidated["all_segments"].append(segment)

            # Collect geographic data
            geographic = page.get("geographic_data", [])
            for geo in geographic:
                if geo not in consolidated["all_geographic"]:
                    consolidated["all_geographic"].append(geo)

            # Collect risk factors
            risks = page.get("risk_factors", [])
            for risk in risks:
                if risk not in consolidated["all_risk_factors"]:
                    consolidated["all_risk_factors"].append(risk)

        # Sort fiscal years
        consolidated["fiscal_years"].sort(reverse=True)

        return consolidated


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    "VLMExtractor",
    "VLMExtractionError",
    "PDFConversionError",
    "BedrockInvocationError",
    "JSONParsingError",
    "DEFAULT_VLM_MODEL_ID",
    "FALLBACK_VLM_MODEL_ID",
]
