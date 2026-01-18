"""
Document processor for PDF extraction and indexing pipeline.

This module provides a high-level document processing layer that:
- Uses VLMExtractor to extract structured data from PDF documents
- Tracks processed documents via manifest (avoids re-processing)
- Consolidates financial data for SQL storage (10-K documents)
- Consolidates reference document data for RAG indexing

The processor is designed for batch processing with change detection,
cost tracking, and idempotent operations.

Usage:
    from src.ingestion.document_processor import DocumentProcessor
    from pathlib import Path

    processor = DocumentProcessor(
        raw_dir=Path("documents/raw"),
        extracted_dir=Path("documents/extracted")
    )

    # Process all documents
    results = await processor.process_all()

    # Process single document
    result = await processor.process_document(Path("documents/raw/AAPL_10K_2024.pdf"))

Reference:
    - backend.mdc for Python patterns
    - PHASE_2A_HOW_TO_GUIDE.md Section 5.2 for requirements
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import structlog

from src.ingestion.vlm_extractor import VLMExtractor, VLMExtractionError

# Configure structured logger
logger = structlog.get_logger(__name__)


# =============================================================================
# Exceptions
# =============================================================================


class DocumentProcessingError(Exception):
    """Base exception for document processing errors."""

    pass


class ManifestError(DocumentProcessingError):
    """Raised when manifest operations fail."""

    pass


# =============================================================================
# Constants
# =============================================================================

# Estimated cost per page (for tracking, actual varies)
ESTIMATED_COST_PER_PAGE_10K = 0.04  # USD, 10-K pages are more complex
ESTIMATED_COST_PER_PAGE_REFERENCE = 0.025  # USD, reference docs simpler


# =============================================================================
# Document Processor Class
# =============================================================================


class DocumentProcessor:
    """
    High-level document processor for VLM-based PDF extraction.

    Manages the end-to-end document processing workflow:
    1. Detects document type from filename
    2. Tracks processed documents via manifest.json
    3. Extracts data using VLMExtractor
    4. Consolidates financial data for SQL storage
    5. Saves extraction results as JSON

    The processor is idempotent - running multiple times only processes
    new or changed documents (unless --force is used).

    Attributes:
        raw_dir: Directory containing raw PDF files.
        extracted_dir: Directory for extracted JSON files.
        manifest: Dictionary tracking all processed documents.
    """

    def __init__(
        self,
        raw_dir: Path,
        extracted_dir: Path,
        vlm_extractor: VLMExtractor | None = None,
    ) -> None:
        """
        Initialize the document processor.

        Args:
            raw_dir: Directory containing raw PDF files to process.
            extracted_dir: Directory for extracted JSON output files.
            vlm_extractor: Optional VLMExtractor instance.
                If not provided, creates one with default settings.
        """
        self.raw_dir = Path(raw_dir)
        self.extracted_dir = Path(extracted_dir)
        self.vlm_extractor = vlm_extractor or VLMExtractor()

        # Create directories if they don't exist
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.extracted_dir.mkdir(parents=True, exist_ok=True)

        # Load or create manifest
        self.manifest = self._load_manifest()

        self._log = logger.bind(
            raw_dir=str(raw_dir),
            extracted_dir=str(extracted_dir),
        )
        self._log.info("document_processor_initialized")

    # =========================================================================
    # Document Type Detection
    # =========================================================================

    def _detect_doc_type(self, filename: str) -> Literal["10k", "reference"]:
        """
        Detect document type from filename pattern.

        Args:
            filename: Name of the PDF file.

        Returns:
            "10k" if filename contains "_10K_" (case insensitive),
            "reference" otherwise.
        """
        if re.search(r"_10K_", filename, re.IGNORECASE):
            return "10k"
        return "reference"

    def _get_document_id(self, pdf_path: Path) -> str:
        """
        Generate unique document ID from filename.

        Removes extension and special characters to create a clean ID.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            Document ID string (e.g., "AAPL_10K_2024").
        """
        # Remove extension and create clean ID
        stem = pdf_path.stem
        # Remove any characters that might cause issues
        doc_id = re.sub(r"[^\w\-]", "_", stem)
        return doc_id

    def _get_file_hash(self, pdf_path: Path) -> str:
        """
        Compute MD5 hash of file for change detection.

        Reads file in chunks to handle large files efficiently.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            MD5 hex digest string.
        """
        hash_md5 = hashlib.md5()
        with open(pdf_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    # =========================================================================
    # Manifest Management
    # =========================================================================

    def _load_manifest(self) -> dict[str, Any]:
        """
        Load or create the document manifest.

        The manifest tracks all processed documents, their hashes,
        extraction dates, costs, and indexing status.

        Returns:
            Manifest dictionary.
        """
        manifest_path = self.extracted_dir / "manifest.json"

        if manifest_path.exists():
            try:
                with open(manifest_path, encoding="utf-8") as f:
                    manifest = json.load(f)
                    logger.info(
                        "manifest_loaded",
                        document_count=len(manifest.get("documents", {})),
                    )
                    return manifest
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(
                    "manifest_load_failed_creating_new",
                    error=str(e),
                )

        # Create new manifest
        manifest = {
            "documents": {},
            "totals": {
                "documents_extracted": 0,
                "documents_indexed": 0,
                "total_extraction_cost_usd": 0.0,
                "last_updated": datetime.now(timezone.utc).isoformat(),
            },
        }
        return manifest

    def _save_manifest(self) -> None:
        """
        Persist manifest to disk.

        Writes manifest.json to the extracted directory with
        pretty formatting for human readability.
        """
        manifest_path = self.extracted_dir / "manifest.json"
        self.manifest["totals"]["last_updated"] = datetime.now(timezone.utc).isoformat()

        try:
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(self.manifest, f, indent=2, ensure_ascii=False)
            logger.debug("manifest_saved", path=str(manifest_path))
        except OSError as e:
            logger.error("manifest_save_failed", error=str(e))
            raise ManifestError(f"Failed to save manifest: {e}") from e

    def _update_manifest(
        self,
        doc_id: str,
        pdf_path: Path,
        extraction: dict[str, Any],
        cost: float,
    ) -> None:
        """
        Update manifest with extraction results.

        Args:
            doc_id: Document identifier.
            pdf_path: Path to source PDF.
            extraction: Extraction result dictionary.
            cost: Estimated extraction cost in USD.
        """
        file_stat = pdf_path.stat()

        self.manifest["documents"][doc_id] = {
            "source_file": pdf_path.name,
            "file_hash": self._get_file_hash(pdf_path),
            "file_size_bytes": file_stat.st_size,
            "extracted_at": datetime.now(timezone.utc).isoformat(),
            "page_count": extraction.get("total_pages", 0),
            "pages_processed": extraction.get("pages_processed", 0),
            "extraction_cost_usd": round(cost, 4),
            "doc_type": extraction.get("doc_type", "unknown"),
            "indexed_to_pinecone": False,
            "indexed_at": None,
            "chunk_count": None,
            "error_count": len(extraction.get("errors", [])),
        }

        # Update totals
        self.manifest["totals"]["documents_extracted"] = len(self.manifest["documents"])
        self.manifest["totals"]["total_extraction_cost_usd"] = round(
            sum(
                doc.get("extraction_cost_usd", 0)
                for doc in self.manifest["documents"].values()
            ),
            4,
        )

        self._save_manifest()
        logger.info(
            "manifest_updated",
            doc_id=doc_id,
            cost_usd=cost,
            total_docs=self.manifest["totals"]["documents_extracted"],
        )

    def should_process(
        self,
        pdf_path: Path,
        force: bool = False,
        if_changed: bool = False,
    ) -> bool:
        """
        Determine if document needs processing.

        Args:
            pdf_path: Path to the PDF file.
            force: If True, always process the document.
            if_changed: If True, process if content hash changed.

        Returns:
            True if document should be processed, False otherwise.

        Raises:
            DocumentProcessingError: If file doesn't exist and if_changed is True.
        """
        doc_id = self._get_document_id(pdf_path)

        # Force always processes
        if force:
            logger.debug("should_process_force", doc_id=doc_id)
            return True

        # Check manifest
        if doc_id not in self.manifest["documents"]:
            logger.debug("should_process_new", doc_id=doc_id)
            return True  # New document

        entry = self.manifest["documents"][doc_id]

        # If if_changed flag, check hash
        if if_changed:
            # Check file exists before trying to hash it
            if not pdf_path.exists():
                logger.warning(
                    "should_process_file_not_found",
                    doc_id=doc_id,
                    pdf_path=str(pdf_path),
                )
                raise DocumentProcessingError(
                    f"Cannot check if file changed - file not found: {pdf_path}"
                )
            current_hash = self._get_file_hash(pdf_path)
            if current_hash != entry.get("file_hash"):
                logger.info(
                    "should_process_changed",
                    doc_id=doc_id,
                    old_hash=entry.get("file_hash", "")[:8],
                    new_hash=current_hash[:8],
                )
                return True

        # Already processed and not changed
        if entry.get("extracted_at"):
            logger.debug(
                "should_process_skip",
                doc_id=doc_id,
                extracted_at=entry.get("extracted_at"),
            )
            return False

        return True

    # =========================================================================
    # Data Consolidation
    # =========================================================================

    def _consolidate_financial_data(
        self, pages: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Aggregate financial data scattered across multiple pages.

        Financial statements in 10-K filings often span 3-5 pages.
        This method consolidates all metrics into a SQL-ready structure.

        Args:
            pages: List of extracted page data dictionaries.

        Returns:
            Consolidated financial data dictionary with:
            - financial_metrics_by_year: Dict mapping year to metrics
            - segment_revenue: List of segment breakdowns
            - geographic_revenue: List of geographic breakdowns
            - risk_factors: List of identified risk factors
        """
        consolidated: dict[str, Any] = {
            "financial_metrics_by_year": {},  # {2024: {...}, 2023: {...}}
            "segment_revenue": [],
            "geographic_revenue": [],
            "risk_factors": [],
        }

        # Track seen segments/geo/risks for deduplication
        seen_segments: set[tuple[str, int]] = set()  # (name, year)
        seen_geo: set[tuple[str, int]] = set()  # (region, year)
        seen_risk_titles: set[str] = set()

        for page in pages:
            page_num = page.get("page_number", 0)

            # Aggregate financial metrics by fiscal year
            if metrics := page.get("financial_metrics"):
                year = metrics.get("fiscal_year")
                if year:
                    year_key = str(year)
                    if year_key not in consolidated["financial_metrics_by_year"]:
                        consolidated["financial_metrics_by_year"][year_key] = {
                            "fiscal_year": year,
                        }

                    # Merge non-null values (later pages may have more complete data)
                    for key, value in metrics.items():
                        if value is not None and key != "fiscal_year":
                            # Always update with non-null data (last value wins)
                            consolidated["financial_metrics_by_year"][year_key][
                                key
                            ] = value

            # Aggregate segment data (deduplicate by segment_name + fiscal_year)
            for segment in page.get("segment_data", []):
                if segment and segment.get("segment_name"):
                    seg_key = (
                        segment.get("segment_name", ""),
                        segment.get("fiscal_year", 0),
                    )
                    if seg_key not in seen_segments:
                        seen_segments.add(seg_key)
                        # Add source page for traceability
                        segment_copy = dict(segment)
                        segment_copy["source_page"] = page_num
                        consolidated["segment_revenue"].append(segment_copy)

            # Aggregate geographic data (deduplicate by region + fiscal_year)
            for geo in page.get("geographic_data", []):
                if geo and geo.get("region"):
                    geo_key = (
                        geo.get("region", ""),
                        geo.get("fiscal_year", 0),
                    )
                    if geo_key not in seen_geo:
                        seen_geo.add(geo_key)
                        geo_copy = dict(geo)
                        geo_copy["source_page"] = page_num
                        consolidated["geographic_revenue"].append(geo_copy)

            # Aggregate risk factors (deduplicate by title)
            for risk in page.get("risk_factors", []):
                if risk and risk.get("title"):
                    title = risk["title"]
                    if title not in seen_risk_titles:
                        seen_risk_titles.add(title)
                        risk_copy = dict(risk)
                        risk_copy["page_number"] = page_num
                        consolidated["risk_factors"].append(risk_copy)

        # Sort segments and geographic data by revenue descending
        consolidated["segment_revenue"].sort(
            key=lambda x: x.get("revenue", 0) or 0,
            reverse=True,
        )
        consolidated["geographic_revenue"].sort(
            key=lambda x: x.get("revenue", 0) or 0,
            reverse=True,
        )

        return consolidated

    def _consolidate_reference_data(
        self, pages: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Consolidate reference document data (news, research, policies).

        Args:
            pages: List of extracted page data dictionaries.

        Returns:
            Consolidated reference data dictionary with:
            - headline: Document headline/title
            - publication_date: Publication date
            - source: Source organization/publication
            - key_claims: List of key claims with entities
            - entities_mentioned: List of all entities mentioned
        """
        consolidated: dict[str, Any] = {
            "headline": None,
            "publication_date": None,
            "source": None,
            "source_type": None,
            "key_claims": [],
            "entities_mentioned": set(),
        }

        for page in pages:
            page_num = page.get("page_number", 0)

            # First page usually has headline/date/source
            if page_num == 1:
                consolidated["headline"] = page.get("headline") or page.get("title")
                consolidated["publication_date"] = page.get(
                    "publication_date"
                ) or page.get("date")
                consolidated["source"] = page.get("source") or page.get("publisher")
                # VLM extracts as "document_type" (news|research|policy|other)
                consolidated["source_type"] = (
                    page.get("source_type")
                    or page.get("document_type")
                    or page.get("document_subtype")
                )

            # Aggregate claims and entities from all pages
            for claim in page.get("key_claims", []):
                if claim:
                    if isinstance(claim, dict):
                        # Preserve all fields including 'entities' if present
                        claim_copy = dict(claim)
                    else:
                        # String claim - wrap in dict
                        claim_copy = {"claim": claim}
                    claim_copy["source_page"] = page_num
                    consolidated["key_claims"].append(claim_copy)

            # Collect entities from various possible fields
            entities = (
                page.get("entities_mentioned", [])
                or page.get("entities", [])
                or page.get("companies_mentioned", [])
            )
            for entity in entities:
                if entity:
                    consolidated["entities_mentioned"].add(entity)

        # Convert set to sorted list
        consolidated["entities_mentioned"] = sorted(consolidated["entities_mentioned"])

        return consolidated

    # =========================================================================
    # Document Processing
    # =========================================================================

    async def process_document(
        self,
        pdf_path: Path,
        force: bool = False,
        if_changed: bool = False,
    ) -> dict[str, Any]:
        """
        Process a single PDF document.

        Args:
            pdf_path: Path to the PDF file.
            force: If True, process even if already extracted.
            if_changed: If True, process only if content changed.

        Returns:
            Extraction result dictionary with consolidated data.

        Raises:
            DocumentProcessingError: If processing fails or file not found.
        """
        # Early validation - check file exists and is a file (not directory)
        if not pdf_path.exists():
            raise DocumentProcessingError(f"PDF file not found: {pdf_path}")
        if not pdf_path.is_file():
            raise DocumentProcessingError(f"Path is not a file: {pdf_path}")

        doc_id = self._get_document_id(pdf_path)
        doc_type = self._detect_doc_type(pdf_path.name)

        log = self._log.bind(
            doc_id=doc_id,
            doc_type=doc_type,
            pdf_path=str(pdf_path),
        )
        log.info("processing_document_started")

        # Check if should process
        if not self.should_process(pdf_path, force=force, if_changed=if_changed):
            log.info("processing_skipped")
            # Return cached result if available
            cached_path = self.extracted_dir / f"{doc_id}.json"
            if cached_path.exists():
                with open(cached_path, encoding="utf-8") as f:
                    return json.load(f)
            return {
                "document_id": doc_id,
                "skipped": True,
                "reason": "already_processed",
            }

        # Extract document
        start_time = datetime.now(timezone.utc)
        try:
            extraction = await self.vlm_extractor.extract_document(
                pdf_path=pdf_path,
                doc_type=doc_type,
            )
        except VLMExtractionError as e:
            log.error("extraction_failed", error=str(e))
            raise DocumentProcessingError(f"Failed to extract {doc_id}: {e}") from e

        # Consolidate data based on document type
        if doc_type == "10k":
            consolidated = self._consolidate_financial_data(extraction.get("pages", []))
        else:
            consolidated = self._consolidate_reference_data(extraction.get("pages", []))

        # Calculate estimated cost
        pages_processed = extraction.get("pages_processed", 0)
        if doc_type == "10k":
            cost = pages_processed * ESTIMATED_COST_PER_PAGE_10K
        else:
            cost = pages_processed * ESTIMATED_COST_PER_PAGE_REFERENCE

        # Build final result structure
        result: dict[str, Any] = {
            "document_id": doc_id,
            "document_type": doc_type,
            "filename": pdf_path.name,
            "extraction_date": start_time.isoformat(),
            "total_pages": extraction.get("total_pages", 0),
            "pages_processed": pages_processed,
            "pages": extraction.get("pages", []),
            "metadata": self._extract_metadata(extraction, doc_type, pdf_path),
            "consolidated": consolidated,
            "errors": extraction.get("errors", []),
            "estimated_cost_usd": round(cost, 4),
        }

        # Save extraction result
        output_path = self.save_extraction(doc_id, result)

        # Update manifest
        self._update_manifest(doc_id, pdf_path, extraction, cost)

        log.info(
            "processing_document_completed",
            pages_processed=pages_processed,
            cost_usd=cost,
            output_path=str(output_path),
        )

        return result

    def _extract_metadata(
        self,
        extraction: dict[str, Any],
        doc_type: str,
        pdf_path: Path,
    ) -> dict[str, Any]:
        """
        Extract metadata from the extraction result.

        Scans pages for company info, ticker, fiscal year, etc.

        Args:
            extraction: VLM extraction result.
            doc_type: Document type ("10k" or "reference").
            pdf_path: Source PDF path.

        Returns:
            Metadata dictionary.
        """
        metadata: dict[str, Any] = {}
        pages = extraction.get("pages", [])

        if doc_type == "10k":
            # Try to extract company info from early pages
            for page in pages[:5]:  # Usually in first few pages
                metrics = page.get("financial_metrics", {})
                if not metadata.get("company") and page.get("company"):
                    metadata["company"] = page["company"]
                if not metadata.get("ticker"):
                    # Try to extract ticker from filename
                    match = re.match(r"^([A-Z]{1,5})_", pdf_path.name)
                    if match:
                        metadata["ticker"] = match.group(1)
                if not metadata.get("fiscal_year") and metrics.get("fiscal_year"):
                    metadata["fiscal_year"] = metrics["fiscal_year"]
                if not metadata.get("sector") and page.get("sector"):
                    metadata["sector"] = page["sector"]

            # Delta Improvement: Extract company name from cover page text
            # VLM doesn't output a "company" field, but the name is in the text
            # Look for patterns like "NVIDIA CORPORATION" or "APPLE INC."
            if not metadata.get("company") and pages:
                first_page_text = pages[0].get("text", "")
                # Pattern: Company name in all caps followed by corp suffix
                # Common patterns: "NVIDIA CORPORATION", "APPLE INC.", "MICROSOFT CORPORATION"
                company_match = re.search(
                    r"\n([A-Z][A-Z\s&,\.]+(?:CORPORATION|CORP|INC|LLC|LTD|COMPANY|CO)\.?)\s*\n",
                    first_page_text[
                        :3000
                    ],  # Only search first 3000 chars of cover page
                    re.IGNORECASE,
                )
                if company_match:
                    # Clean up: Title case, fix common suffixes
                    company_name = company_match.group(1).strip()
                    # Convert "NVIDIA CORPORATION" to "NVIDIA Corporation"
                    company_name = company_name.title()
                    # Fix common suffix capitalization
                    for suffix in ["Llc", "Inc.", "Corp.", "Ltd.", "Co."]:
                        company_name = company_name.replace(
                            suffix, suffix.upper() if suffix == "Llc" else suffix
                        )
                    metadata["company"] = company_name
                    logger.debug(
                        "company_extracted_from_text",
                        company=metadata["company"],
                        document=pdf_path.name,
                    )
                else:
                    logger.warning(
                        "company_not_found_in_text",
                        document=pdf_path.name,
                    )

            # Defaults
            metadata.setdefault("document_type", "SEC 10-K Filing")

        else:  # reference
            # First page usually has metadata
            if pages:
                first_page = pages[0]
                metadata["headline"] = first_page.get("headline") or first_page.get(
                    "title"
                )
                metadata["publication_date"] = first_page.get(
                    "publication_date"
                ) or first_page.get("date")
                metadata["source"] = first_page.get("source") or first_page.get(
                    "publisher"
                )
                metadata["source_type"] = first_page.get("source_type", "news")

            # Try to extract entities mentioned across all pages
            entities = set()
            for page in pages:
                for entity in page.get("entities_mentioned", []):
                    if entity:
                        entities.add(entity)
            metadata["entities_mentioned"] = sorted(entities)

        return metadata

    def save_extraction(self, doc_id: str, extraction: dict[str, Any]) -> Path:
        """
        Save extraction results to JSON file.

        Args:
            doc_id: Document identifier.
            extraction: Extraction result dictionary.

        Returns:
            Path to saved JSON file.
        """
        output_path = self.extracted_dir / f"{doc_id}.json"

        def json_serializer(obj: Any) -> Any:
            """Custom JSON serializer for non-standard types."""
            if isinstance(obj, set):
                return sorted(obj)  # Convert sets to sorted lists
            if hasattr(obj, "isoformat"):  # datetime objects
                return obj.isoformat()
            return str(obj)  # Fallback to string for unknown types

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(
                extraction, f, indent=2, ensure_ascii=False, default=json_serializer
            )

        logger.debug("extraction_saved", doc_id=doc_id, path=str(output_path))
        return output_path

    async def process_all(
        self,
        doc_types: list[str] | None = None,
        force: bool = False,
        if_changed: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Process all PDF documents in the raw directory.

        Args:
            doc_types: Optional list of document types to process.
                Use ["10k"] or ["reference"] to filter. Default processes all.
            force: If True, process all documents even if already extracted.
            if_changed: If True, process only if content changed.

        Returns:
            List of extraction results.
        """
        log = self._log.bind(doc_types=doc_types, force=force, if_changed=if_changed)
        log.info("process_all_started")

        # Find all PDF files (filter out directories that might match the glob)
        pdf_files = [p for p in self.raw_dir.glob("*.pdf") if p.is_file()]

        if not pdf_files:
            log.warning("no_pdf_files_found", raw_dir=str(self.raw_dir))
            return []

        # Filter by document type if specified
        if doc_types:
            doc_types_lower = [dt.lower() for dt in doc_types]
            pdf_files = [
                pdf
                for pdf in pdf_files
                if self._detect_doc_type(pdf.name) in doc_types_lower
            ]

        log.info(
            "processing_batch",
            total_files=len(pdf_files),
            doc_types=doc_types,
        )

        results: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []

        for pdf_path in pdf_files:
            try:
                result = await self.process_document(
                    pdf_path=pdf_path,
                    force=force,
                    if_changed=if_changed,
                )
                results.append(result)
            except DocumentProcessingError as e:
                log.error(
                    "document_failed",
                    pdf_path=str(pdf_path),
                    error=str(e),
                )
                errors.append(
                    {
                        "file": pdf_path.name,
                        "error": str(e),
                    }
                )

        log.info(
            "process_all_completed",
            processed=len(results),
            errors=len(errors),
            total_cost_usd=self.manifest["totals"]["total_extraction_cost_usd"],
        )

        return results

    def get_manifest_summary(self) -> dict[str, Any]:
        """
        Get a summary of the manifest for reporting.

        Returns:
            Summary dictionary with document counts and costs.
        """
        docs = self.manifest.get("documents", {})

        by_type: dict[str, int] = {"10k": 0, "reference": 0}
        for doc in docs.values():
            doc_type = doc.get("doc_type", "unknown")
            if doc_type in by_type:
                by_type[doc_type] += 1

        return {
            "total_documents": len(docs),
            "documents_by_type": by_type,
            "total_pages_processed": sum(
                doc.get("pages_processed", 0) for doc in docs.values()
            ),
            "total_cost_usd": self.manifest["totals"]["total_extraction_cost_usd"],
            "documents_indexed": self.manifest["totals"]["documents_indexed"],
            "last_updated": self.manifest["totals"]["last_updated"],
        }


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    "DocumentProcessor",
    "DocumentProcessingError",
    "ManifestError",
]
