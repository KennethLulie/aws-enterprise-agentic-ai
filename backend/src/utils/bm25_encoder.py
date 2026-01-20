"""
BM25 sparse vector encoder for Pinecone hybrid search.

This module provides BM25-style sparse vector encoding for use with Pinecone's
hybrid search capability. It generates sparse vectors that complement dense
embeddings, enabling keyword-based matching alongside semantic search.

Sparse vectors improve recall for:
- Exact term matches that dense search might miss
- Technical terms and acronyms (EPS, P/E, NVIDIA)
- Proper nouns and ticker symbols

Architecture:
    Text → Tokenize → Remove Stopwords → Hash Tokens → TF Weights → Sparse Vector

Output Format (Pinecone sparse vector):
    {
        "indices": [token_hash_1, token_hash_2, ...],  # Positive integers
        "values": [weight_1, weight_2, ...]            # TF weights
    }

Usage:
    from src.utils.bm25_encoder import BM25Encoder

    encoder = BM25Encoder()

    # Encode a query
    sparse = encoder.encode("What is NVIDIA's EPS?")
    # Returns: {"indices": [12345, 67890, ...], "values": [0.69, 1.09, ...]}

    # Use with Pinecone query
    results = index.query(
        vector=dense_vector,
        sparse_vector=sparse,
        top_k=10,
    )

Reference:
    - Pinecone hybrid search: https://docs.pinecone.io/docs/hybrid-search
    - BM25 algorithm: https://en.wikipedia.org/wiki/Okapi_BM25
    - PHASE_2B_HOW_TO_GUIDE.md Section 7.1
    - backend.mdc for Python patterns
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from typing import TypedDict

import structlog

# Configure structured logger
logger = structlog.get_logger(__name__)


# =============================================================================
# Type Definitions
# =============================================================================


class SparseVector(TypedDict):
    """Pinecone sparse vector format."""

    indices: list[int]
    values: list[float]


# =============================================================================
# Constants
# =============================================================================

# Common English stopwords to filter out
# FINANCIAL DOMAIN OPTIMIZED:
# - Removed "per" (important for "earnings per share", "price per share")
# - Removed "year", "quarter", "annual" (important for financial periods)
# - Removed "total", "net", "gross" (important for financial metrics)
# - Kept minimal to preserve domain-specific terms
STOPWORDS: frozenset[str] = frozenset(
    {
        # Articles
        "a",
        "an",
        "the",
        # Prepositions (kept minimal - "per" intentionally excluded)
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "from",
        "as",
        # Conjunctions
        "and",
        "or",
        "but",
        "if",
        "then",
        # Pronouns
        "i",
        "you",
        "he",
        "she",
        "it",
        "we",
        "they",
        "this",
        "that",
        # Verbs (common, but keeping financial verbs like "increase", "decrease")
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "can",
        # Generic words (excluding financial terms)
        "not",
        "no",
        "yes",
        "so",
        "just",
        "also",
        "very",
        "more",
        "most",
        "some",
        "any",
        "each",
        "every",
        "both",
        "other",
        "such",
        "what",
        "which",
        "who",
        "how",
        "about",
        "into",
        "over",
        "after",
        "before",
        "between",
        "under",
        "again",
        "further",
        "once",
        # NOTE: Intentionally EXCLUDED from stopwords (kept as searchable terms):
        # - "per" (earnings per share, price per unit)
        # - "year", "quarter", "annual", "fiscal" (financial periods)
        # - "total", "net", "gross" (financial aggregations)
        # - "all", "many", "few" (could be relevant in financial context)
        # - "may", "might", "must" (important for risk disclosures)
    }
)

# Regex pattern for tokenization: split on non-alphanumeric characters
# Preserves numbers and allows alphanumeric tokens
TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9]+")

# Max index value for Pinecone (must be positive 32-bit integer)
MAX_INDEX = 2**31 - 1

# Minimum token length to include (filters single chars)
MIN_TOKEN_LENGTH = 2


# =============================================================================
# Custom Exceptions
# =============================================================================


class BM25EncoderError(Exception):
    """Base exception for BM25 encoder operations."""

    pass


# =============================================================================
# BM25 Encoder
# =============================================================================


class BM25Encoder:
    """
    BM25-style sparse vector encoder for Pinecone hybrid search.

    Generates sparse vectors using term frequency (TF) weighting. This is a
    simplified "TF-only" approach that works well for Pinecone hybrid search
    without requiring a pre-computed IDF corpus.

    Attributes:
        stopwords: Set of words to filter out during tokenization.
        min_token_length: Minimum token length to include.

    Example:
        >>> encoder = BM25Encoder()
        >>> sparse = encoder.encode("NVIDIA revenue growth Q4 2024")
        >>> print(sparse["indices"][:3])
        [1234567, 2345678, 3456789]
        >>> print(sparse["values"][:3])
        [0.693, 0.693, 0.693]
    """

    def __init__(
        self,
        stopwords: frozenset[str] | None = None,
        min_token_length: int = MIN_TOKEN_LENGTH,
    ) -> None:
        """
        Initialize BM25Encoder.

        Args:
            stopwords: Custom stopwords set. Defaults to built-in STOPWORDS.
            min_token_length: Minimum token length to include. Default 2.
        """
        self._stopwords = stopwords if stopwords is not None else STOPWORDS
        self._min_token_length = min_token_length

        logger.debug(
            "bm25_encoder_initialized",
            stopword_count=len(self._stopwords),
            min_token_length=self._min_token_length,
        )

    def _tokenize(self, text: str) -> list[str]:
        """
        Tokenize text into lowercase terms with stopword removal.

        Args:
            text: Input text to tokenize.

        Returns:
            List of filtered, lowercase tokens.

        Example:
            >>> encoder._tokenize("NVIDIA's Q4 Revenue Report")
            ['nvidia', 'q4', 'revenue', 'report']
        """
        # Extract alphanumeric tokens
        tokens = TOKEN_PATTERN.findall(text.lower())

        # Filter stopwords and short tokens
        filtered = [
            token
            for token in tokens
            if token not in self._stopwords and len(token) >= self._min_token_length
        ]

        return filtered

    def _hash_token(self, token: str) -> int:
        """
        Hash a token to a positive integer index for Pinecone.

        Uses MD5 for deterministic hashing across Python processes.
        Python's built-in hash() is randomized by default and would produce
        different values across process restarts, breaking sparse vector matching.

        Args:
            token: Token string to hash.

        Returns:
            Positive integer index in range [0, 2^31-1].

        Example:
            >>> encoder._hash_token("nvidia")
            1234567890  # Consistent hash for same token across all processes
        """
        # Use MD5 for deterministic cross-process hashing
        # Take first 4 bytes and convert to int, then modulo for Pinecone limits
        hash_bytes = hashlib.md5(token.encode("utf-8")).digest()
        return int.from_bytes(hash_bytes[:4], "big") % MAX_INDEX

    def _compute_tf(self, tokens: list[str]) -> dict[str, float]:
        """
        Compute term frequency weights for tokens.

        Uses log-normalized TF: log(1 + count) for smoother weighting.

        Args:
            tokens: List of tokens (may contain duplicates).

        Returns:
            Dict mapping tokens to their TF weights.

        Example:
            >>> encoder._compute_tf(["nvidia", "nvidia", "revenue"])
            {'nvidia': 1.0986, 'revenue': 0.6931}
        """
        counts = Counter(tokens)

        # Log-normalized TF: log(1 + count)
        # This dampens the effect of high-frequency terms
        return {token: math.log(1 + count) for token, count in counts.items()}

    def encode(self, text: str) -> SparseVector:
        """
        Encode text into a Pinecone-compatible sparse vector.

        Args:
            text: Input text to encode.

        Returns:
            SparseVector dict with 'indices' and 'values' lists.

        Raises:
            BM25EncoderError: If encoding fails.

        Example:
            >>> sparse = encoder.encode("What is NVIDIA's EPS for Q4?")
            >>> sparse
            {'indices': [123, 456, 789], 'values': [0.69, 0.69, 0.69]}
        """
        try:
            # Handle empty input
            if not text or not text.strip():
                logger.debug("bm25_encode_empty_input")
                return {"indices": [], "values": []}

            # Tokenize
            tokens = self._tokenize(text)

            if not tokens:
                logger.debug("bm25_encode_no_tokens", text_preview=text[:50])
                return {"indices": [], "values": []}

            # Compute TF weights
            tf_weights = self._compute_tf(tokens)

            # Build sparse vector
            indices: list[int] = []
            values: list[float] = []

            for token, weight in tf_weights.items():
                indices.append(self._hash_token(token))
                values.append(weight)

            logger.debug(
                "bm25_encoded",
                input_length=len(text),
                token_count=len(tokens),
                unique_tokens=len(tf_weights),
            )

            return {"indices": indices, "values": values}

        except Exception as e:
            logger.error("bm25_encode_failed", error=str(e), text_preview=text[:50])
            raise BM25EncoderError(f"Failed to encode text: {e}") from e

    def encode_batch(self, texts: list[str]) -> list[SparseVector]:
        """
        Encode multiple texts into sparse vectors.

        Args:
            texts: List of texts to encode.

        Returns:
            List of SparseVector dicts, one per input text.

        Example:
            >>> vectors = encoder.encode_batch(["NVIDIA Q4", "AMD revenue"])
            >>> len(vectors)
            2
        """
        return [self.encode(text) for text in texts]

    def fit(self, documents: list[str]) -> None:
        """
        Optional: Fit encoder on a document corpus.

        This is a placeholder for future IDF computation. Currently a no-op
        as we use TF-only weighting which doesn't require corpus statistics.

        Args:
            documents: List of documents to fit on.
        """
        # TF-only encoding doesn't require fitting
        # This method is here for API compatibility if we add IDF later
        logger.debug("bm25_fit_noop", document_count=len(documents))
