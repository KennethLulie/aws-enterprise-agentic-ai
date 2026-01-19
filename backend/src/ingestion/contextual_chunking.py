"""
Contextual enrichment module for RAG chunk enhancement.

This module implements Anthropic's Contextual Retrieval approach, which
prepends document-level context to each chunk before embedding. This
dramatically improves retrieval accuracy by giving the embedding model
the context needed to understand what "it" or "the company" refers to.

The Problem:
    Traditional RAG embeds chunks in isolation. A chunk like "Revenue increased
    15% YoY" loses critical context: Which company? Which fiscal year? What
    section of the document? The embedding captures "revenue increase" but
    not the business context.

The Solution:
    Prepend structured metadata as a prefix before embedding:
    "[10-K Filing] [Apple Inc. (AAPL)] [FY2024] [Item 7: MD&A] [Page 45 of 127]

    Revenue increased 15% YoY..."

    Now the embedding captures company, fiscal year, and section context,
    enabling queries like "Apple 2024 revenue" to match accurately.

Key Design Decisions:
    - Enrichment applied to CHILD chunks only (parents stored as-is for display)
    - Original text preserved in "text_raw" for citation display
    - Enriched text in "text" used for embedding
    - Token count updated to include prefix (~20-30 tokens overhead)
    - Document type determines prefix format (10-K vs news/reference)
    - Graceful fallbacks for missing metadata (never fail, just log warning)

Usage:
    from src.ingestion.contextual_chunking import ContextualEnricher

    enricher = ContextualEnricher()

    # Enrich a single child chunk
    enriched = enricher.enrich_chunk(child_chunk, document_metadata)

    # Enrich all children in batch
    enriched_children = enricher.enrich_children(children, document_metadata)

Reference:
    - Anthropic Contextual Retrieval: https://www.anthropic.com/news/contextual-retrieval
    - backend.mdc for Python patterns
    - RAG_IMPROVEMENTS_DELTA.md for architecture details
"""

from __future__ import annotations

from typing import Any

import structlog

# Configure structured logger
logger = structlog.get_logger(__name__)

# =============================================================================
# Constants
# =============================================================================

# Token estimation constant (must match semantic_chunking.py)
TOKENS_PER_WORD = 1.3

# Prefix templates for different document types
# These are structured to maximize embedding relevance for common queries

PREFIX_TEMPLATE_10K = (
    "[10-K Filing] [{company} ({ticker})] [FY{fiscal_year}] [{section}] "
    "[Page {start_page} of {total_pages}]\n\n"
)

PREFIX_TEMPLATE_REFERENCE = (
    "[{source_type}] [{source_name}] [{publication_date}] [{headline}]\n\n"
)

# Fallback values for missing metadata
FALLBACK_COMPANY = "Unknown Company"
FALLBACK_TICKER = "N/A"
FALLBACK_FISCAL_YEAR = "N/A"
FALLBACK_TOTAL_PAGES = "?"
FALLBACK_SOURCE_NAME = "Unknown Source"
FALLBACK_SOURCE_TYPE = "document"
FALLBACK_PUBLICATION_DATE = "Unknown Date"
FALLBACK_HEADLINE = ""
FALLBACK_SECTION = "Unknown Section"


# =============================================================================
# Custom Exceptions
# =============================================================================


class ContextualEnrichmentError(Exception):
    """Exception for contextual enrichment operations."""

    pass


# =============================================================================
# ContextualEnricher Class
# =============================================================================


class ContextualEnricher:
    """
    Contextual enrichment for RAG chunks using Anthropic's approach.

    This class prepends document-level context to chunks before embedding,
    improving retrieval accuracy by including company, fiscal year, and
    section information in the embedding space.

    The enrichment is applied to child chunks only. Parent chunks are
    stored as-is for display/citation purposes.

    Attributes:
        None (stateless enricher)

    Example:
        enricher = ContextualEnricher()

        # Document metadata for a 10-K filing
        metadata = {
            "document_type": "10k",
            "company": "Apple Inc.",
            "ticker": "AAPL",
            "fiscal_year": 2024,
            "total_pages": 127
        }

        # Enrich a child chunk
        child = {
            "text": "Revenue increased 15% YoY...",
            "section": "Item 7: MD&A",
            "start_page": 45,
            "token_count": 150
        }

        enriched = enricher.enrich_chunk(child, metadata)
        # enriched["text"] = "[10-K Filing] [Apple Inc. (AAPL)] [FY2024]..."
        # enriched["text_raw"] = "Revenue increased 15% YoY..."
    """

    def __init__(self) -> None:
        """Initialize the contextual enricher."""
        self._log = logger.bind(component="contextual_enricher")
        self._log.info("contextual_enricher_initialized")
        # Track which documents have had missing metadata warnings logged
        # to avoid spamming logs with the same warning for every chunk
        self._warned_metadata: set[tuple[str, str]] = set()

    def _count_tokens(self, text: str) -> int:
        """
        Approximate token count for text.

        Uses a word-based approximation (~1.3 tokens per word) which is
        reasonably accurate for English text with most tokenizers.
        Must match the formula in semantic_chunking.py for consistency.

        Args:
            text: Text to count tokens for.

        Returns:
            Approximate token count.
        """
        if not text:
            return 0
        words = len(text.split())
        return max(1, int(words * TOKENS_PER_WORD))

    def _get_prefix_10k(
        self,
        chunk: dict[str, Any],
        metadata: dict[str, Any],
    ) -> str:
        """
        Generate contextual prefix for 10-K document chunks.

        Format:
        "[10-K Filing] [Apple Inc. (AAPL)] [FY2024] [Item 7: MD&A] [Page 45 of 127]

        "

        Args:
            chunk: The chunk dictionary with text and metadata.
            metadata: Document-level metadata.

        Returns:
            Formatted prefix string.
        """
        # Extract with fallbacks - never fail on missing data
        # Use explicit None checks to handle falsy values like 0 correctly
        company = (
            metadata.get("company")
            if metadata.get("company") is not None
            else FALLBACK_COMPANY
        )
        ticker = (
            metadata.get("ticker")
            if metadata.get("ticker") is not None
            else FALLBACK_TICKER
        )
        fiscal_year = (
            metadata.get("fiscal_year")
            if metadata.get("fiscal_year") is not None
            else FALLBACK_FISCAL_YEAR
        )
        total_pages = (
            metadata.get("total_pages")
            if metadata.get("total_pages") is not None
            else FALLBACK_TOTAL_PAGES
        )

        # Section can come from chunk - use explicit None check
        section = (
            chunk.get("section")
            if chunk.get("section") is not None
            else FALLBACK_SECTION
        )

        # Page info from chunk
        start_page = chunk.get("start_page", "?")

        # Log warnings for missing critical metadata (once per document, not per chunk)
        doc_id = metadata.get("document_id", "unknown")
        if metadata.get("company") is None:
            warn_key = (doc_id, "company")
            if warn_key not in self._warned_metadata:
                self._warned_metadata.add(warn_key)
                self._log.warning(
                    "missing_metadata",
                    field="company",
                    document_type="10k",
                    document_id=doc_id,
                )
        if metadata.get("ticker") is None:
            warn_key = (doc_id, "ticker")
            if warn_key not in self._warned_metadata:
                self._warned_metadata.add(warn_key)
                self._log.warning(
                    "missing_metadata",
                    field="ticker",
                    document_type="10k",
                    document_id=doc_id,
                )

        return PREFIX_TEMPLATE_10K.format(
            company=company,
            ticker=ticker,
            fiscal_year=fiscal_year,
            section=section,
            start_page=start_page,
            total_pages=total_pages,
        )

    def _get_prefix_reference(
        self,
        chunk: dict[str, Any],
        metadata: dict[str, Any],
    ) -> str:
        """
        Generate contextual prefix for news/reference document chunks.

        Format:
        "[news] [Reuters] [2025-01-10] [Apple reports record Q4 earnings]

        "

        Args:
            chunk: The chunk dictionary with text and metadata.
            metadata: Document-level metadata.

        Returns:
            Formatted prefix string.
        """
        # Extract with fallbacks - never fail on missing data
        # Use explicit None checks to handle falsy values correctly
        source_type = (
            metadata.get("source_type")
            if metadata.get("source_type") is not None
            else FALLBACK_SOURCE_TYPE
        )
        source_name = (
            metadata.get("source_name")
            if metadata.get("source_name") is not None
            else FALLBACK_SOURCE_NAME
        )
        publication_date = (
            metadata.get("publication_date")
            if metadata.get("publication_date") is not None
            else FALLBACK_PUBLICATION_DATE
        )
        headline = metadata.get("headline")  # Can be None or empty, handled below

        # Log warnings for missing critical metadata (once per document)
        doc_id = metadata.get("document_id", "unknown")
        if metadata.get("source_name") is None:
            warn_key = (doc_id, "source_name")
            if warn_key not in self._warned_metadata:
                self._warned_metadata.add(warn_key)
                self._log.warning(
                    "missing_metadata",
                    field="source_name",
                    document_type="reference",
                    document_id=doc_id,
                )

        # If no headline, use simplified format without it
        if headline:
            return PREFIX_TEMPLATE_REFERENCE.format(
                source_type=source_type,
                source_name=source_name,
                publication_date=publication_date,
                headline=headline,
            )
        else:
            # Simplified format without headline
            return f"[{source_type}] [{source_name}] [{publication_date}]\n\n"

    def enrich_chunk(
        self,
        chunk: dict[str, Any],
        document_metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Enrich a single chunk with contextual prefix.

        Prepends document-level context to the chunk text for improved
        embedding quality. The original text is preserved in "text_raw"
        for citation display.

        Args:
            chunk: Chunk dictionary with at least "text" key.
            document_metadata: Document-level metadata with at least
                "document_type" key ("10k" or "reference").

        Returns:
            Enriched chunk dictionary with:
            - "text": Enriched text with prefix (for embedding)
            - "text_raw": Original text without prefix (for display)
            - "token_count": Updated count including prefix tokens

        Raises:
            ContextualEnrichmentError: If document_type is missing or invalid,
                or if chunk is not a dictionary.

        Example:
            enriched = enricher.enrich_chunk(
                {"text": "Revenue grew...", "section": "Item 7"},
                {"document_type": "10k", "company": "Apple", "ticker": "AAPL"}
            )
        """
        # Validate chunk is a dictionary
        if not isinstance(chunk, dict):
            raise ContextualEnrichmentError(
                f"chunk must be a dictionary, got {type(chunk).__name__}"
            )

        # Validate document_metadata is a dictionary
        if not isinstance(document_metadata, dict):
            raise ContextualEnrichmentError(
                f"document_metadata must be a dictionary, got {type(document_metadata).__name__}"
            )

        document_type = document_metadata.get("document_type")

        # Validate document_type exists and is a string
        if document_type is None:
            raise ContextualEnrichmentError(
                "document_type is required in document_metadata "
                "(must be '10k' or 'reference')"
            )

        if not isinstance(document_type, str):
            raise ContextualEnrichmentError(
                f"document_type must be a string, got {type(document_type).__name__}"
            )

        # Get original text
        original_text = chunk.get("text", "")

        # Ensure original_text is a string
        if not isinstance(original_text, str):
            original_text = str(original_text) if original_text is not None else ""

        if not original_text:
            self._log.warning("empty_chunk_text", chunk_index=chunk.get("chunk_index"))
            # Return chunk as-is with empty text_raw
            result = chunk.copy()
            result["text_raw"] = ""
            return result

        # Generate appropriate prefix based on document type
        if document_type.lower() == "10k":
            prefix = self._get_prefix_10k(chunk, document_metadata)
        else:
            # Treat everything else as reference (news, research, policy, etc.)
            prefix = self._get_prefix_reference(chunk, document_metadata)

        # Build enriched text
        enriched_text = prefix + original_text

        # Create result with both enriched and raw text
        result = chunk.copy()
        result["text"] = enriched_text
        result["text_raw"] = original_text

        # Update token count to include prefix
        result["token_count"] = self._count_tokens(enriched_text)

        self._log.debug(
            "chunk_enriched",
            document_type=document_type,
            original_tokens=self._count_tokens(original_text),
            enriched_tokens=result["token_count"],
            prefix_tokens=self._count_tokens(prefix),
        )

        return result

    def enrich_children(
        self,
        children: list[dict[str, Any]],
        document_metadata: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        Enrich multiple child chunks with contextual prefixes.

        Batch operation for enriching all children from a document.
        Each child gets the same document-level context prefix.

        Args:
            children: List of child chunk dictionaries.
            document_metadata: Document-level metadata.

        Returns:
            List of enriched child chunks.

        Raises:
            ContextualEnrichmentError: If document_type is missing.

        Example:
            enriched = enricher.enrich_children(
                children=[
                    {"text": "Revenue grew...", "section": "Item 7"},
                    {"text": "Operating expenses...", "section": "Item 7"},
                ],
                document_metadata={
                    "document_type": "10k",
                    "company": "Apple Inc.",
                    "ticker": "AAPL",
                    "fiscal_year": 2024,
                    "total_pages": 127
                }
            )
        """
        if not children:
            return []

        self._log.info(
            "enriching_children",
            num_children=len(children),
            document_type=document_metadata.get("document_type"),
        )

        enriched_children = [
            self.enrich_chunk(child, document_metadata) for child in children
        ]

        self._log.info(
            "children_enriched",
            num_enriched=len(enriched_children),
        )

        return enriched_children

    def clear_warning_cache(self) -> None:
        """
        Clear the cache of warned metadata fields.

        Call this when starting to process a new batch of documents
        to ensure warnings are logged again for each document.
        """
        self._warned_metadata.clear()


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    "ContextualEnricher",
    "ContextualEnrichmentError",
]
