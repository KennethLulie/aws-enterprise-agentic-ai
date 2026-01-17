"""
Semantic chunking module for document text processing.

This module provides semantic-aware text chunking using spaCy for sentence
boundary detection. Unlike fixed-size chunking, semantic chunking respects
linguistic boundaries (sentences, paragraphs) to preserve context and
improve retrieval quality.

The chunker is designed for the RAG pipeline, producing chunks that:
- Never split mid-sentence
- Respect paragraph boundaries when possible
- Include configurable overlap for context continuity
- Track source page numbers for citation

Usage:
    from src.ingestion.semantic_chunking import SemanticChunker

    chunker = SemanticChunker(max_tokens=512, overlap_tokens=50)

    # Chunk a single text
    chunks = chunker.chunk_text("Long document text...")

    # Chunk extracted document pages
    chunks = chunker.chunk_document(pages)

Reference:
    - spaCy documentation: https://spacy.io/
    - backend.mdc for Python patterns
"""

from __future__ import annotations

from typing import Any

import structlog

# Configure structured logger
logger = structlog.get_logger(__name__)

# =============================================================================
# Constants
# =============================================================================

# Default chunk configuration
DEFAULT_MAX_TOKENS = 512
DEFAULT_OVERLAP_TOKENS = 50

# Token estimation constants
# For most English text: ~4 characters per token or ~1.3 tokens per word
# Using words-based estimation as specified in requirements
TOKENS_PER_WORD = 1.3

# spaCy model name
SPACY_MODEL = "en_core_web_sm"

# Maximum sentence length before forcing a split (prevents runaway sentences)
MAX_SENTENCE_TOKENS = 200

# Maximum text length to process at once (characters)
# Prevents very slow processing; larger texts are chunked page-by-page
MAX_TEXT_LENGTH = 100_000


# =============================================================================
# Custom Exceptions
# =============================================================================


class ChunkingError(Exception):
    """Base exception for chunking operations."""

    pass


class SpaCyLoadError(ChunkingError):
    """Error loading spaCy model."""

    pass


# =============================================================================
# SemanticChunker Class
# =============================================================================


class SemanticChunker:
    """
    Semantic text chunker using spaCy for sentence boundary detection.

    This chunker creates overlapping chunks that respect sentence and
    paragraph boundaries, improving retrieval quality in RAG systems.

    Attributes:
        max_tokens: Maximum tokens per chunk (default 512).
        overlap_tokens: Token overlap between consecutive chunks (default 50).

    Example:
        chunker = SemanticChunker(max_tokens=512, overlap_tokens=50)

        # Chunk text
        chunks = chunker.chunk_text("Document content...")

        # Chunk document pages (from VLM extraction)
        chunks = chunker.chunk_document(pages)
        # Returns: [{"text": "...", "token_count": 487, "start_page": 1, ...}]
    """

    def __init__(
        self,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
    ) -> None:
        """
        Initialize the semantic chunker.

        Args:
            max_tokens: Maximum tokens per chunk. Defaults to 512.
            overlap_tokens: Token overlap between chunks. Defaults to 50.
                Set to 0 for no overlap.

        Raises:
            ValueError: If overlap_tokens >= max_tokens.
            SpaCyLoadError: If spaCy model cannot be loaded.
        """
        if overlap_tokens >= max_tokens:
            raise ValueError(
                f"overlap_tokens ({overlap_tokens}) must be less than "
                f"max_tokens ({max_tokens})"
            )

        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        self._nlp: Any = None
        self._log = logger.bind(
            max_tokens=max_tokens,
            overlap_tokens=overlap_tokens,
        )
        self._log.info("semantic_chunker_initialized")

    def _get_nlp(self) -> Any:
        """
        Lazy-load the spaCy NLP model.

        Returns:
            spaCy Language model.

        Raises:
            SpaCyLoadError: If model cannot be loaded.
        """
        if self._nlp is None:
            try:
                import spacy

                # Load the small English model
                # Disable components we don't need for sentence detection
                self._nlp = spacy.load(
                    SPACY_MODEL,
                    disable=["ner", "lemmatizer"],
                )
                self._log.debug("spacy_model_loaded", model=SPACY_MODEL)
            except OSError as e:
                self._log.error(
                    "spacy_model_load_failed",
                    model=SPACY_MODEL,
                    error=str(e),
                )
                raise SpaCyLoadError(
                    f"Failed to load spaCy model '{SPACY_MODEL}'. "
                    f"Run: python -m spacy download {SPACY_MODEL}"
                ) from e
        return self._nlp

    def _count_tokens(self, text: str) -> int:
        """
        Approximate token count for text.

        Uses a word-based approximation (~1.3 tokens per word) which is
        reasonably accurate for English text with most tokenizers.

        Args:
            text: Text to count tokens for.

        Returns:
            Approximate token count.
        """
        if not text:
            return 0
        # Count words and multiply by tokens per word
        words = len(text.split())
        return max(1, int(words * TOKENS_PER_WORD))

    def _split_sentences(self, text: str) -> list[str]:
        """
        Split text into sentences using spaCy.

        Handles edge cases like abbreviations, numbers, and URLs
        better than simple regex-based splitting.

        Args:
            text: Text to split into sentences.

        Returns:
            List of sentence strings.
        """
        if not text or not text.strip():
            return []

        # Guard against very large text which causes slow processing
        if len(text) > MAX_TEXT_LENGTH:
            self._log.warning(
                "text_too_large_splitting",
                text_length=len(text),
                max_length=MAX_TEXT_LENGTH,
            )
            # Split into smaller chunks and process each
            return self._split_large_text(text)

        nlp = self._get_nlp()

        # Process with spaCy (handles sentence boundary detection)
        doc = nlp(text)

        sentences = []
        for sent in doc.sents:
            sent_text = sent.text.strip()
            if sent_text:
                # Handle very long sentences by splitting on punctuation
                if self._count_tokens(sent_text) > MAX_SENTENCE_TOKENS:
                    sub_sentences = self._split_long_sentence(sent_text)
                    sentences.extend(sub_sentences)
                else:
                    sentences.append(sent_text)

        return sentences

    def _split_large_text(self, text: str) -> list[str]:
        """
        Split very large text into manageable chunks for spaCy processing.

        Falls back to paragraph-based splitting when text exceeds
        MAX_TEXT_LENGTH to avoid slow spaCy processing.

        Args:
            text: Large text to split.

        Returns:
            List of sentence strings.
        """
        nlp = self._get_nlp()
        all_sentences: list[str] = []

        # Split on paragraph boundaries (double newlines)
        paragraphs = text.split("\n\n")

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if len(para) <= MAX_TEXT_LENGTH:
                # Process paragraph normally with spaCy
                doc = nlp(para)
                for sent in doc.sents:
                    sent_text = sent.text.strip()
                    if sent_text:
                        if self._count_tokens(sent_text) > MAX_SENTENCE_TOKENS:
                            all_sentences.extend(self._split_long_sentence(sent_text))
                        else:
                            all_sentences.append(sent_text)
            else:
                # Paragraph is still too large, split on single newlines
                lines = para.split("\n")
                for line in lines:
                    line = line.strip()
                    if line and len(line) <= MAX_TEXT_LENGTH:
                        doc = nlp(line)
                        for sent in doc.sents:
                            sent_text = sent.text.strip()
                            if sent_text:
                                all_sentences.append(sent_text)
                    elif line:
                        # Last resort: split by sentence-ending punctuation
                        import re

                        crude_sents = re.split(r"(?<=[.!?])\s+", line)
                        all_sentences.extend(
                            s.strip() for s in crude_sents if s.strip()
                        )

        return all_sentences

    def _split_long_sentence(self, sentence: str) -> list[str]:
        """
        Split a very long sentence into smaller parts.

        Used as a fallback for sentences that exceed MAX_SENTENCE_TOKENS.
        Splits on semicolons, colons, or em-dashes while preserving meaning.

        Args:
            sentence: Long sentence to split.

        Returns:
            List of sentence parts.
        """
        # Try splitting on common clause separators
        separators = ["; ", ": ", " - ", " — ", ", and ", ", or "]

        parts = [sentence]
        for sep in separators:
            new_parts = []
            for part in parts:
                if self._count_tokens(part) > MAX_SENTENCE_TOKENS:
                    sub_parts = part.split(sep)
                    if len(sub_parts) > 1:
                        # Re-add separator to all but last part
                        for i, sp in enumerate(sub_parts[:-1]):
                            new_parts.append(sp + sep.rstrip())
                        new_parts.append(sub_parts[-1])
                    else:
                        new_parts.append(part)
                else:
                    new_parts.append(part)
            parts = new_parts

        # Final fallback: hard split by words if still too long
        final_parts = []
        for part in parts:
            if self._count_tokens(part) > MAX_SENTENCE_TOKENS:
                words = part.split()
                current = []
                for word in words:
                    current.append(word)
                    if self._count_tokens(" ".join(current)) >= MAX_SENTENCE_TOKENS:
                        final_parts.append(" ".join(current))
                        current = []
                if current:
                    final_parts.append(" ".join(current))
            else:
                final_parts.append(part)

        return [p.strip() for p in final_parts if p.strip()]

    def chunk_text(self, text: str) -> list[str]:
        """
        Chunk text into semantically coherent pieces.

        The algorithm:
        1. Split text into paragraphs
        2. Split paragraphs into sentences
        3. Build chunks by adding sentences until max_tokens
        4. Include overlap from previous chunk
        5. Never split mid-sentence

        Args:
            text: Text to chunk.

        Returns:
            List of chunk strings.
        """
        if not text or not text.strip():
            return []

        # Split into sentences
        sentences = self._split_sentences(text)

        if not sentences:
            return []

        chunks: list[str] = []
        current_chunk: list[str] = []
        current_tokens = 0

        # Track sentences for overlap
        overlap_sentences: list[str] = []

        for sentence in sentences:
            sentence_tokens = self._count_tokens(sentence)

            # Check if adding this sentence exceeds max_tokens
            if current_tokens + sentence_tokens > self.max_tokens and current_chunk:
                # Save current chunk
                chunk_text = " ".join(current_chunk)
                chunks.append(chunk_text)

                # Calculate overlap: take sentences from end of current chunk
                overlap_sentences = self._get_overlap_sentences(
                    current_chunk, self.overlap_tokens
                )

                # Start new chunk with overlap
                current_chunk = overlap_sentences.copy()
                current_tokens = sum(self._count_tokens(s) for s in current_chunk)

            # Add sentence to current chunk
            current_chunk.append(sentence)
            current_tokens += sentence_tokens

        # Don't forget the last chunk
        if current_chunk:
            chunk_text = " ".join(current_chunk)
            # Only add if it's different from the last chunk
            if not chunks or chunk_text != chunks[-1]:
                chunks.append(chunk_text)

        self._log.debug(
            "text_chunked",
            input_length=len(text),
            num_sentences=len(sentences),
            num_chunks=len(chunks),
        )

        return chunks

    def _get_overlap_sentences(
        self, sentences: list[str], target_tokens: int
    ) -> list[str]:
        """
        Get sentences from the end to create overlap.

        Args:
            sentences: List of sentences.
            target_tokens: Target number of overlap tokens.

        Returns:
            List of sentences for overlap.
        """
        if not sentences or target_tokens <= 0:
            return []

        overlap: list[str] = []
        overlap_tokens = 0

        # Work backwards from the end
        for sentence in reversed(sentences):
            sentence_tokens = self._count_tokens(sentence)
            if overlap_tokens + sentence_tokens <= target_tokens:
                overlap.insert(0, sentence)
                overlap_tokens += sentence_tokens
            else:
                break

        return overlap

    def chunk_document(self, pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Chunk a document's pages into indexed chunks with metadata.

        Processes each page's text content and tracks source page numbers
        for citation purposes. Uses a sentence-level approach to ensure
        accurate page boundary tracking.

        Args:
            pages: List of page dictionaries from VLM extraction.
                Each page should have:
                - "page_number": int
                - "text": str (the page content)
                - Optional: "section": str

        Returns:
            List of chunk dictionaries with format:
            {
                "text": "The chunk content...",
                "token_count": 487,
                "start_page": 15,
                "end_page": 15,
                "chunk_index": 42,
                "section": "Item 1A: Risk Factors"  # if available
            }
        """
        if not pages:
            return []

        self._log.info("chunking_document", num_pages=len(pages))

        # First pass: extract sentences with page metadata
        # This preserves the page origin of each sentence
        all_sentences: list[tuple[str, int, str | None]] = (
            []
        )  # (text, page_num, section)
        current_section: str | None = None

        for page in pages:
            page_number = page.get("page_number", 0)
            page_text = page.get("text", "")
            section = page.get("section")

            if not page_text or not page_text.strip():
                continue

            # Track section (sections persist across pages)
            if section:
                current_section = section

            # Split page into sentences
            page_sentences = self._split_sentences(page_text)
            for sent in page_sentences:
                all_sentences.append((sent, page_number, current_section))

        if not all_sentences:
            self._log.info(
                "document_chunked",
                num_pages=len(pages),
                num_chunks=0,
            )
            return []

        # Second pass: build chunks with accurate page tracking
        all_chunks: list[dict[str, Any]] = []
        chunk_index = 0

        current_chunk_sentences: list[tuple[str, int, str | None]] = []
        current_tokens = 0

        for sentence_data in all_sentences:
            sent_text, page_num, section = sentence_data
            sent_tokens = self._count_tokens(sent_text)

            # Check if adding this sentence exceeds max_tokens
            if (
                current_tokens + sent_tokens > self.max_tokens
                and current_chunk_sentences
            ):
                # Finalize current chunk
                chunk_dict = self._build_chunk_dict(
                    current_chunk_sentences, chunk_index
                )
                all_chunks.append(chunk_dict)
                chunk_index += 1

                # Calculate overlap sentences
                overlap = self._get_overlap_from_sentences(
                    current_chunk_sentences, self.overlap_tokens
                )

                # Start new chunk with overlap
                current_chunk_sentences = overlap.copy()
                current_tokens = sum(
                    self._count_tokens(s[0]) for s in current_chunk_sentences
                )

            # Add sentence to current chunk
            current_chunk_sentences.append(sentence_data)
            current_tokens += sent_tokens

        # Finalize last chunk
        if current_chunk_sentences:
            chunk_dict = self._build_chunk_dict(current_chunk_sentences, chunk_index)
            # Avoid duplicate with previous chunk
            if not all_chunks or chunk_dict["text"] != all_chunks[-1]["text"]:
                all_chunks.append(chunk_dict)

        self._log.info(
            "document_chunked",
            num_pages=len(pages),
            num_chunks=len(all_chunks),
        )

        return all_chunks

    def _build_chunk_dict(
        self,
        sentences: list[tuple[str, int, str | None]],
        chunk_index: int,
    ) -> dict[str, Any]:
        """
        Build a chunk dictionary from a list of sentences with metadata.

        Args:
            sentences: List of (text, page_number, section) tuples.
            chunk_index: Index of this chunk in the document.

        Returns:
            Chunk dictionary with text, token_count, start_page, end_page,
            chunk_index, and optionally section.
        """
        # Combine sentence texts
        text = " ".join(s[0] for s in sentences)

        # Get page range from actual sentence origins
        page_numbers = [s[1] for s in sentences]
        start_page = min(page_numbers) if page_numbers else 0
        end_page = max(page_numbers) if page_numbers else 0

        # Use the most recent section
        section = None
        for s in reversed(sentences):
            if s[2]:
                section = s[2]
                break

        chunk_dict: dict[str, Any] = {
            "text": text,
            "token_count": self._count_tokens(text),
            "start_page": start_page,
            "end_page": end_page,
            "chunk_index": chunk_index,
        }
        if section:
            chunk_dict["section"] = section

        return chunk_dict

    def _get_overlap_from_sentences(
        self,
        sentences: list[tuple[str, int, str | None]],
        target_tokens: int,
    ) -> list[tuple[str, int, str | None]]:
        """
        Get sentences from the end for overlap, preserving metadata.

        Args:
            sentences: List of (text, page_number, section) tuples.
            target_tokens: Target number of overlap tokens.

        Returns:
            List of sentence tuples for overlap.
        """
        if not sentences or target_tokens <= 0:
            return []

        overlap: list[tuple[str, int, str | None]] = []
        overlap_tokens = 0

        for sent_data in reversed(sentences):
            sent_tokens = self._count_tokens(sent_data[0])
            if overlap_tokens + sent_tokens <= target_tokens:
                overlap.insert(0, sent_data)
                overlap_tokens += sent_tokens
            else:
                break

        return overlap


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    "SemanticChunker",
    "ChunkingError",
    "SpaCyLoadError",
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_OVERLAP_TOKENS",
]
