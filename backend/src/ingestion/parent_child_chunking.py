"""
Parent/child chunking module for hierarchical document processing.

This module implements a two-tier chunking strategy for RAG retrieval:
- Parent chunks: Large context windows (1024 tokens) stored for retrieval
- Child chunks: Small, precise chunks (256 tokens) used for embedding/search

The strategy addresses the classic RAG tradeoff:
- Small chunks = precise embedding matches but limited context
- Large chunks = rich context but imprecise matches

Solution: Embed small child chunks for search precision, but retrieve
the parent chunk text for LLM context. This gives the best of both worlds.

Architecture:
    Document Pages
         │
         ▼
    ┌─────────────────────────────────┐
    │  Parent Chunk (1024 tokens)     │
    │  - Non-overlapping              │
    │  - Section-aware boundaries     │
    │  - Stored for retrieval         │
    └─────────────────────────────────┘
         │
         ├─────────────────────┬─────────────────────┐
         ▼                     ▼                     ▼
    ┌──────────┐          ┌──────────┐          ┌──────────┐
    │  Child 0 │──overlap─│  Child 1 │──overlap─│  Child 2 │
    │ 256 tok  │          │ 256 tok  │          │ 256 tok  │
    └──────────┘          └──────────┘          └──────────┘
    (50-token overlap ONLY within same parent)

Key Design Decisions:
- Parents are NON-overlapping to avoid redundant storage
- Children have 50-token overlap WITHIN the same parent only
- Children do NOT overlap across parent boundaries
- Section boundaries force new parent (no mixing Item 1 with Item 1A)
- Parent text is stored in Pinecone metadata for retrieval
- Only children are embedded; parents are retrieved via parent_id

Usage:
    from src.ingestion.parent_child_chunking import ParentChildChunker

    chunker = ParentChildChunker(
        parent_tokens=1024,
        child_tokens=256,
        overlap_tokens=50
    )

    # Chunk a document into parents and children
    parents, children = chunker.chunk_document(
        document_id="AAPL_10K_2024",
        pages=[{"page_number": 1, "text": "...", "section": "Item 1A"}]
    )

    # parents: List of parent chunks with full text
    # children: List of child chunks with parent_id reference

Reference:
    - backend.mdc for Python patterns
    - semantic_chunking.py for sentence boundary logic
    - LangChain ParentDocumentRetriever concept
    - RAG_IMPROVEMENTS_DELTA.md for full architecture details
"""

from __future__ import annotations

from typing import Any

import structlog

from src.ingestion.semantic_chunking import SemanticChunker

# Configure structured logger
logger = structlog.get_logger(__name__)

# =============================================================================
# Constants
# =============================================================================

# Default parent chunk configuration
# 1024 tokens provides rich context for LLM response generation
DEFAULT_PARENT_TOKENS = 1024

# Default child chunk configuration
# 256 tokens provides high precision for embedding search
DEFAULT_CHILD_TOKENS = 256

# Default overlap between child chunks (within same parent only)
DEFAULT_OVERLAP_TOKENS = 50

# Token estimation constant (must match semantic_chunking.py)
TOKENS_PER_WORD = 1.3


# =============================================================================
# Custom Exceptions
# =============================================================================


class ParentChildChunkingError(Exception):
    """Exception for parent/child chunking operations."""

    pass


# =============================================================================
# ParentChildChunker Class
# =============================================================================


class ParentChildChunker:
    """
    Hierarchical document chunker using parent/child strategy.

    Creates large parent chunks (1024 tokens) for context retrieval and
    small child chunks (256 tokens) for precise embedding search. Children
    reference their parent via parent_id, enabling the RAG system to:
    1. Search over precise child embeddings
    2. Retrieve parent text for rich LLM context

    Attributes:
        parent_tokens: Maximum tokens per parent chunk (default 1024).
        child_tokens: Maximum tokens per child chunk (default 256).
        overlap_tokens: Token overlap between children (default 50).

    Example:
        chunker = ParentChildChunker(
            parent_tokens=1024,
            child_tokens=256,
            overlap_tokens=50
        )

        parents, children = chunker.chunk_document(
            document_id="AAPL_10K_2024",
            pages=extracted_pages
        )

        # Parents: [{
        #     "parent_id": "AAPL_10K_2024_parent_0",
        #     "document_id": "AAPL_10K_2024",
        #     "text": "Full parent text...",
        #     "token_count": 1024,
        #     "start_page": 15,
        #     "end_page": 16,
        #     "section": "Item 1A: Risk Factors",
        #     "parent_index": 0
        # }]

        # Children: [{
        #     "child_id": "AAPL_10K_2024_parent_0_child_0",
        #     "parent_id": "AAPL_10K_2024_parent_0",
        #     "document_id": "AAPL_10K_2024",
        #     "text": "Child text...",
        #     "token_count": 256,
        #     "start_page": 15,
        #     "end_page": 15,
        #     "section": "Item 1A: Risk Factors",
        #     "child_index": 0,
        #     "child_index_in_document": 0
        # }]
    """

    def __init__(
        self,
        parent_tokens: int = DEFAULT_PARENT_TOKENS,
        child_tokens: int = DEFAULT_CHILD_TOKENS,
        overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
    ) -> None:
        """
        Initialize the parent/child chunker.

        Args:
            parent_tokens: Maximum tokens per parent chunk. Defaults to 1024.
            child_tokens: Maximum tokens per child chunk. Defaults to 256.
            overlap_tokens: Token overlap between children within same parent.
                Defaults to 50. Set to 0 for no overlap.

        Raises:
            ValueError: If overlap_tokens >= child_tokens.
            ValueError: If child_tokens >= parent_tokens.
        """
        if overlap_tokens >= child_tokens:
            raise ValueError(
                f"overlap_tokens ({overlap_tokens}) must be less than "
                f"child_tokens ({child_tokens})"
            )

        if child_tokens >= parent_tokens:
            raise ValueError(
                f"child_tokens ({child_tokens}) must be less than "
                f"parent_tokens ({parent_tokens})"
            )

        self.parent_tokens = parent_tokens
        self.child_tokens = child_tokens
        self.overlap_tokens = overlap_tokens

        # Initialize SemanticChunker for parent creation (non-overlapping)
        # Uses spaCy for sentence boundary detection and section awareness
        self._parent_chunker = SemanticChunker(
            max_tokens=parent_tokens,
            overlap_tokens=0,  # Parents are non-overlapping
        )

        # Initialize SemanticChunker for child creation (with overlap)
        # Uses spaCy for sentence-aware splitting to maintain quality
        self._child_chunker = SemanticChunker(
            max_tokens=child_tokens,
            overlap_tokens=overlap_tokens,
        )

        # Flag to track if spaCy model has been shared between chunkers
        self._spacy_model_shared = False

        self._log = logger.bind(
            parent_tokens=parent_tokens,
            child_tokens=child_tokens,
            overlap_tokens=overlap_tokens,
        )
        self._log.info("parent_child_chunker_initialized")

    def _count_tokens(self, text: str) -> int:
        """
        Approximate token count for text.

        Uses the same formula as SemanticChunker for consistency:
        words * 1.3 tokens per word.

        Args:
            text: Text to count tokens for.

        Returns:
            Approximate token count.
        """
        if not text:
            return 0
        words = len(text.split())
        return max(1, int(words * TOKENS_PER_WORD))

    def chunk_document(
        self,
        document_id: str,
        pages: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """
        Chunk a document into parent and child chunks.

        The algorithm:
        1. Create parent chunks using SemanticChunker (section-aware, non-overlapping)
        2. For each parent, create overlapping child chunks

        Args:
            document_id: Unique identifier for the document (e.g., "AAPL_10K_2024").
            pages: List of page dictionaries from VLM extraction.
                Each page should have:
                - "page_number": int
                - "text": str (the page content)
                - Optional: "section": str

        Returns:
            Tuple of (parents, children) where:
            - parents: List of parent chunk dictionaries
            - children: List of child chunk dictionaries with parent_id references

        Raises:
            ParentChildChunkingError: If document_id is empty or pages is invalid.
        """
        if not document_id:
            raise ParentChildChunkingError("document_id cannot be empty")

        if not pages:
            self._log.info(
                "empty_document",
                document_id=document_id,
            )
            return [], []

        self._log.info(
            "chunking_document",
            document_id=document_id,
            num_pages=len(pages),
        )

        # Step 1: Create parent chunks
        parents = self._create_parent_chunks(document_id, pages)

        if not parents:
            self._log.info(
                "no_parent_chunks_created",
                document_id=document_id,
            )
            return [], []

        # Step 2: Create children from each parent
        all_children: list[dict[str, Any]] = []
        global_child_index = 0

        for parent in parents:
            children = self._create_children_from_parent(parent)

            # Assign global child index
            for child in children:
                child["child_index_in_document"] = global_child_index
                global_child_index += 1

            all_children.extend(children)

        # Log comprehensive summary (replaces per-chunk debug logging)
        avg_children_per_parent = len(all_children) / len(parents) if parents else 0
        self._log.info(
            "document_chunked",
            document_id=document_id,
            num_parents=len(parents),
            num_children=len(all_children),
            avg_children_per_parent=round(avg_children_per_parent, 1),
        )

        return parents, all_children

    def _create_parent_chunks(
        self,
        document_id: str,
        pages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Create parent chunks from document pages.

        Uses SemanticChunker with overlap=0 to create non-overlapping,
        section-aware parent chunks.

        Args:
            document_id: Unique document identifier.
            pages: List of page dictionaries from VLM extraction.

        Returns:
            List of parent chunk dictionaries.
        """
        # Use SemanticChunker to get section-aware chunks
        # This handles sentence boundaries and section transitions
        raw_chunks = self._parent_chunker.chunk_document(pages)

        # Share spaCy model with child chunker after first load (~12MB memory savings)
        # This is safe because both chunkers use the same model for sentence detection
        if not self._spacy_model_shared and self._parent_chunker._nlp is not None:
            self._child_chunker._nlp = self._parent_chunker._nlp
            self._spacy_model_shared = True
            self._log.debug("spacy_model_shared_between_chunkers")

        parents: list[dict[str, Any]] = []

        for idx, chunk in enumerate(raw_chunks):
            parent_id = f"{document_id}_parent_{idx}"

            parent = {
                "parent_id": parent_id,
                "document_id": document_id,
                "text": chunk["text"],
                "token_count": chunk["token_count"],
                "start_page": chunk["start_page"],
                "end_page": chunk["end_page"],
                "section": chunk.get("section"),
                "parent_index": idx,
            }
            parents.append(parent)

        # Log summary at info level, detailed stats at debug level
        # This reduces logging overhead for large documents
        if len(parents) > 0:
            avg_tokens = sum(p["token_count"] for p in parents) // len(parents)
            self._log.debug(
                "parent_chunks_created",
                document_id=document_id,
                num_parents=len(parents),
                avg_tokens_per_parent=avg_tokens,
            )

        return parents

    def _create_children_from_parent(
        self,
        parent: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        Create child chunks from a parent chunk.

        Children have overlap ONLY within the same parent. Children never
        overlap across parent boundaries to prevent context pollution.

        Args:
            parent: Parent chunk dictionary with text and metadata.

        Returns:
            List of child chunk dictionaries.
        """
        parent_text = parent.get("text", "")
        if not parent_text or not parent_text.strip():
            return []

        parent_id = parent["parent_id"]
        document_id = parent["document_id"]
        section = parent.get("section")
        start_page = parent.get("start_page", 0)
        end_page = parent.get("end_page", 0)

        # Use SemanticChunker for sentence-aware child splitting
        # This maintains quality by respecting sentence boundaries
        # The spaCy model is shared with parent chunker to save ~12MB memory
        child_texts = self._child_chunker.chunk_text(parent_text)

        if not child_texts:
            return []

        children: list[dict[str, Any]] = []

        # Pre-calculate token counts for O(n) page estimation instead of O(n²)
        child_token_counts = [self._count_tokens(text) for text in child_texts]
        parent_token_count = parent.get("token_count", 1)

        # Track cumulative tokens for page estimation
        cumulative_tokens = 0

        for idx, child_text in enumerate(child_texts):
            child_id = f"{parent_id}_child_{idx}"

            # Use cumulative token position for page estimation
            child_start_token = cumulative_tokens
            cumulative_tokens += child_token_counts[idx]

            # Estimate page position based on token position in parent
            if start_page == end_page:
                # Parent spans single page
                child_start_page = start_page
                child_end_page = end_page
            else:
                # Parent spans multiple pages - estimate child's page position
                # This is approximate; for exact page tracking, would need
                # sentence-level page metadata from parent creation
                total_pages = end_page - start_page + 1
                position_ratio = child_start_token / max(1, parent_token_count)
                page_offset = int(position_ratio * (total_pages - 1))
                child_start_page = start_page + page_offset
                child_end_page = min(
                    end_page,
                    child_start_page + 1,  # Child unlikely to span more than 2 pages
                )

            child = {
                "child_id": child_id,
                "parent_id": parent_id,
                "document_id": document_id,
                "text": child_text,
                "token_count": child_token_counts[idx],  # Use pre-calculated value
                "start_page": child_start_page,
                "end_page": child_end_page,
                "section": section,
                "child_index": idx,
                # child_index_in_document is set by caller
            }
            children.append(child)

        # Skip per-parent debug logging to reduce overhead for large documents
        # Summary stats are logged in chunk_document() at info level

        return children


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    "ParentChildChunker",
    "ParentChildChunkingError",
]
