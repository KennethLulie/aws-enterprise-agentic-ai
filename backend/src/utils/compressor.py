"""
Contextual compression using AWS Bedrock Nova Lite.

This module extracts only query-relevant sentences from retrieved passages,
reducing noise and context length for final LLM synthesis. It's the final
step before passing context to the answer generation LLM.

Architecture:
    Reranked Results → ContextualCompressor → Compressed Results → LLM
                              ↓
              Nova Lite extracts relevant sentences

Why Compression:
    - Removes tangential information from retrieved passages
    - Focuses LLM attention on relevant content only
    - Reduces token usage in synthesis step
    - Improves answer quality by filtering noise

Pipeline Position:
    Dense → RRF → KG Boost → Reranker → **Compressor** → Answer LLM
                                              ↑
                                        This module

Parent/Child Integration:
    - Compresses `parent_text` (1024 tokens) - the full context for LLM
    - Preserves `child_text_raw` unchanged - used for citation previews
    - Stores result in new `compressed_text` field
    - Short passages (<400 chars) skip compression

Usage:
    from src.utils.compressor import ContextualCompressor

    compressor = ContextualCompressor()

    # Compress a single passage
    compressed = await compressor.compress(
        query="What are Apple's supply chain risks?",
        passage="Apple Inc. reported revenue... Supply chain risks..."
    )

    # Compress batch of reranked results
    compressed_results = await compressor.compress_results(
        query="What are Apple's supply chain risks?",
        results=reranked_results
    )

Note:
    This module preserves `kg_evidence`, `sources`, and all metadata from
    input results, which are critical for LLM explainability downstream.

Reference:
    - PHASE_2B_HOW_TO_GUIDE.md Section 10b.1
    - RAG_README.md Query Pipeline Step 5
    - backend.mdc for Python patterns
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import structlog
from botocore.exceptions import ClientError
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

# Default Nova Lite model for compression (fast, cheap)
DEFAULT_MODEL_ID = "amazon.nova-lite-v1:0"

# Retry configuration for transient errors
MAX_RETRIES = 3
MIN_RETRY_WAIT = 1  # seconds
MAX_RETRY_WAIT = 10  # seconds

# Minimum passage length for compression (~100 tokens)
# Shorter passages are returned as-is
MIN_COMPRESSION_LENGTH = 400  # characters

# Maximum concurrent compression calls (avoid rate limiting)
MAX_CONCURRENT_CALLS = 5

# Maximum passage length to send to LLM (tokens ≈ chars/4)
# Parent chunks are ~1024 tokens = ~4096 chars
MAX_PASSAGE_CHARS = 4500  # ~1125 tokens, allows some buffer

# Sentinel value for irrelevant passages
NOT_RELEVANT = "NOT_RELEVANT"

# Minimum results to return even if all marked NOT_RELEVANT
# Prevents empty results when LLM is overly aggressive
# Set to 5 to match default top_k (users expect ~5 comprehensive results)
MIN_RESULTS_GUARANTEE = 5

# Maximum length for NOT_RELEVANT variation detection
# Legitimate extractions are typically >50 chars
NOT_RELEVANT_MAX_LENGTH = 50

# Common LLM paraphrases of NOT_RELEVANT
NOT_RELEVANT_PHRASES = (
    "no relevant",
    "not relevant",
    "none relevant",
    "nothing relevant",
    "no sentences",
    "none of the sentences",
    "couldn't find",
    "could not find",
    "no content",
    "cannot find",
    "unable to find",
)


# =============================================================================
# Exceptions
# =============================================================================


class CompressorError(Exception):
    """Base exception for compression operations."""

    pass


class CompressorModelError(CompressorError):
    """Raised when LLM invocation fails."""

    pass


# =============================================================================
# Contextual Compressor
# =============================================================================


class ContextualCompressor:
    """
    Extracts query-relevant sentences from passages using Nova Lite.

    Compresses retrieved passages to only the sentences that directly
    answer the query, reducing noise and token usage for final synthesis.

    Attributes:
        model_id: Bedrock model ID for Nova Lite.

    Example:
        compressor = ContextualCompressor()

        # Single passage
        compressed = await compressor.compress(
            query="Apple supply chain risks",
            passage="Apple reported $394B revenue. Supply chain risks in China..."
        )
        # Returns: "Supply chain risks in China..."

        # Batch processing
        results = await compressor.compress_results(query, reranked_results)
    """

    def __init__(
        self,
        model_id: str = DEFAULT_MODEL_ID,
    ) -> None:
        """
        Initialize the compressor.

        Args:
            model_id: Bedrock model ID for compression.
                Defaults to amazon.nova-lite-v1:0.
        """
        self.model_id = model_id
        self._client: Any = None
        self._log = logger.bind(component="compressor", model_id=model_id)

        self._log.info("compressor_initialized")

    def _is_not_relevant_response(self, response: str) -> bool:
        """
        Detect NOT_RELEVANT responses including LLM variations.

        LLMs don't always return exact "NOT_RELEVANT" - they may paraphrase.
        This catches common variations while avoiding false positives on
        legitimate extracted text.

        Heuristic: Short responses (<50 chars) containing negative relevance
        indicators are likely NOT_RELEVANT variations.

        Args:
            response: The LLM response text.

        Returns:
            True if response indicates no relevant content, False otherwise.
        """
        # Empty or whitespace-only response = no relevant content
        if not response or not response.strip():
            return True

        response_upper = response.upper()
        response_lower = response.lower()

        # Exact match (what we instructed)
        if NOT_RELEVANT in response_upper:
            return True

        # Short response heuristics (LLM paraphrasing)
        # Legitimate extracted text is usually >50 chars
        if len(response) < NOT_RELEVANT_MAX_LENGTH:
            for phrase in NOT_RELEVANT_PHRASES:
                if phrase in response_lower:
                    self._log.debug(
                        "not_relevant_variation_detected",
                        response=response[:50],
                        matched_phrase=phrase,
                    )
                    return True

        return False

    def _get_client(self) -> Any:
        """
        Get or create the Bedrock runtime client.

        Returns:
            boto3 Bedrock runtime client.

        Raises:
            CompressorError: If client creation fails.
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
                raise CompressorError(f"Failed to create Bedrock client: {e}") from e
        return self._client

    def _build_compression_prompt(self, query: str, passage: str) -> str:
        """
        Build the compression prompt.

        Args:
            query: The user's search query.
            passage: The passage text to compress.

        Returns:
            Formatted prompt string.
        """
        # Truncate passage if too long
        if len(passage) > MAX_PASSAGE_CHARS:
            passage = passage[:MAX_PASSAGE_CHARS] + "..."
            self._log.debug(
                "passage_truncated",
                original_length=len(passage),
                truncated_to=MAX_PASSAGE_CHARS,
            )

        return f"""Extract only the sentences from this passage that are directly relevant to answering the question.
Return only the relevant sentences, nothing else. If no sentences are relevant, return 'NOT_RELEVANT'.

Question: {query}

Passage: {passage}

Relevant sentences:"""

    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=MIN_RETRY_WAIT, max=MAX_RETRY_WAIT),
        retry=retry_if_exception_type((ClientError,)),
        reraise=True,
    )
    async def _invoke_nova_lite(self, prompt: str) -> str:
        """
        Invoke Nova Lite model with the given prompt.

        Args:
            prompt: The prompt to send to the model.

        Returns:
            Model response text.

        Raises:
            CompressorModelError: If model invocation fails.
        """
        client = self._get_client()

        # Nova Lite request format
        body = json.dumps(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": [{"text": prompt}],
                    }
                ],
                "inferenceConfig": {
                    "maxTokens": 500,  # Allow for multi-sentence extraction
                    "temperature": 0.0,  # Deterministic for extraction
                },
            }
        )

        try:
            response = await asyncio.to_thread(
                client.invoke_model,
                modelId=self.model_id,
                body=body,
                contentType="application/json",
                accept="application/json",
            )

            response_body = json.loads(response["body"].read())

            # Extract text from Nova response format
            output = response_body.get("output", {})
            message = output.get("message", {})
            content = message.get("content", [])

            if content and isinstance(content, list):
                text = content[0].get("text", "").strip()

                # Fix #3: Empty response should trigger graceful degradation
                if not text:
                    self._log.warning("compression_empty_response")
                    raise CompressorModelError("Empty response from Nova Lite")

                return text

            raise CompressorModelError(f"Unexpected response format: {response_body}")

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            self._log.error(
                "nova_lite_invocation_failed",
                error_code=error_code,
                error=str(e),
            )
            raise

    async def compress(self, query: str, passage: str) -> str:
        """
        Extract query-relevant sentences from a passage.

        Args:
            query: The user's search query.
            passage: The passage text to compress.

        Returns:
            Compressed text with only relevant sentences, or NOT_RELEVANT
            if no sentences are relevant.

        Example:
            compressed = await compressor.compress(
                query="Apple supply chain risks",
                passage="Apple reported revenue. Supply chain risks in China."
            )
            # Returns: "Supply chain risks in China."
        """
        # Skip compression for very short passages
        if len(passage) < MIN_COMPRESSION_LENGTH:
            self._log.debug(
                "compression_skipped_short",
                passage_length=len(passage),
                threshold=MIN_COMPRESSION_LENGTH,
            )
            return passage

        prompt = self._build_compression_prompt(query, passage)

        try:
            response = await self._invoke_nova_lite(prompt)

            # Fix #2: Check for NOT_RELEVANT response (including LLM variations)
            if self._is_not_relevant_response(response):
                self._log.debug("compression_not_relevant", query=query[:50])
                return NOT_RELEVANT

            # Return compressed text
            self._log.debug(
                "compression_complete",
                original_length=len(passage),
                compressed_length=len(response),
                reduction_pct=round((1 - len(response) / len(passage)) * 100, 1),
            )
            return response

        except Exception as e:
            self._log.error(
                "compression_failed",
                error=str(e),
                returning_original=True,
            )
            # On error, return original passage (graceful degradation)
            return passage

    async def compress_results(
        self,
        query: str,
        results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Compress parent_text for a batch of results.

        Extracts relevant sentences from each result's parent_text field,
        storing the compressed version in compressed_text. Preserves all
        other fields including kg_evidence, sources, and child_text_raw.

        Args:
            query: The user's search query.
            results: List of result dicts from reranking. Expected fields:
                - metadata.parent_text: Full context to compress
                - metadata.child_text_raw: Citation preview (preserved)
                - kg_evidence: (optional) KG evidence (preserved)
                - sources: (optional) Retrieval sources (preserved)

        Returns:
            List of results with compressed_text added. Results where
            compression returns NOT_RELEVANT are filtered out.

        Note:
            Modifies results in-place and adds compressed_text field.
            All original fields (kg_evidence, sources, metadata) are preserved.
        """
        if not results:
            self._log.debug("compress_results_empty_input")
            return []

        self._log.debug(
            "compress_results_started",
            query=query[:50],
            result_count=len(results),
        )

        # Semaphore to limit concurrent LLM calls
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_CALLS)

        async def compress_single(result: dict[str, Any]) -> dict[str, Any]:
            """Compress a single result with fallback to parent_text."""
            metadata = result.get("metadata", {})
            # Check both top-level and metadata for parent_text
            # (HybridRetriever may flatten fields to top level)
            parent_text = (
                result.get("parent_text")  # Top-level (HybridRetriever output)
                or metadata.get("parent_text")  # In metadata (reranker output)
                or metadata.get("text")
                or metadata.get("child_text")
                or ""
            )

            if not parent_text:
                self._log.warning(
                    "compress_missing_text",
                    result_id=result.get("id"),
                )
                # Keep result but with empty compressed_text
                result["compressed_text"] = ""
                return result

            # Skip compression for short passages
            if len(parent_text) < MIN_COMPRESSION_LENGTH:
                result["compressed_text"] = parent_text
                return result

            # Compress with rate limiting
            async with semaphore:
                compressed = await self.compress(query, parent_text)

            # Option C: Don't filter - use parent_text as fallback when NOT_RELEVANT
            # Compression should enhance, not eliminate documents the reranker validated
            if compressed == NOT_RELEVANT:
                self._log.debug(
                    "compress_not_relevant_using_parent",
                    result_id=result.get("id"),
                )
                # Use original parent_text instead of filtering out
                result["compressed_text"] = parent_text
                result["_compression_skipped"] = True  # Flag for debugging
                return result

            # Add compressed_text field (preserves all other fields)
            result["compressed_text"] = compressed
            return result

        # Process all results concurrently
        compressed_results = await asyncio.gather(
            *[compress_single(r) for r in results]
        )

        # Filter out None results (shouldn't happen, but defensive)
        valid_results: list[dict[str, Any]] = [r for r in compressed_results if r is not None]

        # Count how many used parent_text fallback (NOT_RELEVANT from LLM)
        skipped_count = sum(
            1 for r in valid_results if r.get("_compression_skipped")
        )

        self._log.info(
            "compress_results_complete",
            query=query[:50],
            input_count=len(results),
            output_count=len(valid_results),
            compression_skipped=skipped_count,
            compression_applied=len(valid_results) - skipped_count,
        )

        return valid_results


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    "ContextualCompressor",
    "CompressorError",
    "CompressorModelError",
    "NOT_RELEVANT",
]
