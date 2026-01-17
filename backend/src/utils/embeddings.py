"""
Bedrock Titan embeddings utility for text vectorization.

This module provides a wrapper around AWS Bedrock's Titan embedding model
for generating text embeddings used in RAG (Retrieval-Augmented Generation)
pipelines. It supports single text and batch embedding operations with
proper error handling, retry logic, and cost tracking.

The embeddings are used for:
- Indexing documents in vector stores (Pinecone, ChromaDB)
- Semantic search over document collections
- Finding similar documents for RAG context

Usage:
    from src.utils.embeddings import BedrockEmbeddings

    embeddings = BedrockEmbeddings()

    # Single text embedding
    vector = await embeddings.embed_text("What is NVIDIA's revenue?")

    # Batch embedding
    vectors = await embeddings.embed_batch([
        "Document chunk 1...",
        "Document chunk 2...",
        "Document chunk 3...",
    ])

Cost Notes:
    - Titan embeddings: ~$0.0001 per 1K tokens (~$0.10 per 1M tokens)
    - Batch processing reduces overhead but not per-token cost
    - Token usage is logged for cost tracking

Reference:
    - AWS Bedrock Titan documentation
    - backend.mdc for Python patterns
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections import OrderedDict
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

# Default Titan embedding model
DEFAULT_EMBEDDING_MODEL_ID = "amazon.titan-embed-text-v1"

# Embedding dimensions by model
MODEL_DIMENSIONS = {
    "amazon.titan-embed-text-v1": 1536,
    "amazon.titan-embed-text-v2:0": 1024,  # v2 supports variable dimensions, default is 1024
}

# Default batch size for processing multiple texts
DEFAULT_BATCH_SIZE = 25

# Max tokens for Titan embedding input (approximately 8K tokens)
# We use character limit as a proxy - ~4 chars per token average
MAX_INPUT_CHARS = 25000  # ~6250 tokens, leaving buffer

# Retry settings
MAX_RETRIES = 3
MIN_RETRY_WAIT = 1  # seconds
MAX_RETRY_WAIT = 10  # seconds

# Rate limiting - delay between batch requests to avoid throttling
BATCH_DELAY_SECONDS = 0.1  # 100ms between batches

# Cache settings
DEFAULT_CACHE_SIZE = 1000  # Max number of embeddings to cache in memory


# =============================================================================
# Custom Exceptions
# =============================================================================


class EmbeddingError(Exception):
    """Base exception for embedding operations."""

    pass


class EmbeddingModelError(EmbeddingError):
    """Error related to the embedding model itself."""

    pass


class EmbeddingInputError(EmbeddingError):
    """Error related to invalid input text."""

    pass


# =============================================================================
# BedrockEmbeddings Class
# =============================================================================


class BedrockEmbeddings:
    """
    Wrapper for AWS Bedrock Titan embeddings.

    This class provides methods for generating text embeddings using
    Amazon Titan embedding models via AWS Bedrock. It handles:
    - Single text embedding
    - Batch embedding with configurable batch sizes
    - Text normalization and truncation
    - Retry logic for transient failures
    - Token usage logging for cost tracking

    Attributes:
        model_id: The Bedrock model ID for embeddings.
        dimension: The embedding dimension for the configured model.

    Example:
        embeddings = BedrockEmbeddings()

        # Single embedding
        vector = await embeddings.embed_text("Hello world")
        print(f"Dimension: {len(vector)}")  # 1536

        # Batch embedding
        texts = ["Text 1", "Text 2", "Text 3"]
        vectors = await embeddings.embed_batch(texts)
        print(f"Generated {len(vectors)} embeddings")
    """

    def __init__(
        self,
        model_id: str | None = None,
        cache_size: int = DEFAULT_CACHE_SIZE,
    ) -> None:
        """
        Initialize the Bedrock embeddings client.

        Args:
            model_id: Bedrock model ID for embeddings. Defaults to
                amazon.titan-embed-text-v1 from settings or constant.
            cache_size: Maximum number of embeddings to cache in memory.
                Set to 0 to disable caching. Defaults to 1000.
        """
        settings = get_settings()

        # Use provided model_id, fall back to settings, then to default
        self.model_id = (
            model_id
            or getattr(settings, "bedrock_embedding_model_id", None)
            or DEFAULT_EMBEDDING_MODEL_ID
        )

        self._client: Any = None
        self._log = logger.bind(model_id=self.model_id)
        self._total_tokens_used = 0

        # In-memory LRU cache for repeated embeddings
        self._cache_size = cache_size
        self._cache: OrderedDict[str, list[float]] = OrderedDict()
        self._cache_hits = 0
        self._cache_misses = 0

        self._log.info(
            "bedrock_embeddings_initialized",
            cache_enabled=cache_size > 0,
            cache_size=cache_size,
        )

    def _get_client(self) -> Any:
        """
        Get or create the Bedrock Runtime client.

        Returns:
            Boto3 Bedrock Runtime client.

        Raises:
            EmbeddingModelError: If client creation fails.
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
                raise EmbeddingModelError(
                    f"Failed to create Bedrock client: {e}"
                ) from e
        return self._client

    def get_dimension(self) -> int:
        """
        Get the embedding dimension for the configured model.

        Returns:
            int: The number of dimensions in the embedding vector.
                - 1536 for amazon.titan-embed-text-v1
                - 1024 for amazon.titan-embed-text-v2 (default)
        """
        return MODEL_DIMENSIONS.get(self.model_id, 1536)

    def _get_cache_key(self, text: str) -> str:
        """
        Generate a cache key for the given text.

        Uses SHA-256 hash of the normalized text to create a fixed-length key.

        Args:
            text: The normalized text to hash.

        Returns:
            Hex string of the SHA-256 hash.
        """
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _get_from_cache(self, text: str) -> list[float] | None:
        """
        Get an embedding from the cache if available.

        Args:
            text: The normalized text to look up.

        Returns:
            The cached embedding, or None if not cached.
        """
        if self._cache_size == 0:
            return None

        cache_key = self._get_cache_key(text)
        if cache_key in self._cache:
            # Move to end (most recently used)
            self._cache.move_to_end(cache_key)
            self._cache_hits += 1
            return self._cache[cache_key]

        self._cache_misses += 1
        return None

    def _add_to_cache(self, text: str, embedding: list[float]) -> None:
        """
        Add an embedding to the cache.

        Uses LRU eviction when cache is full.

        Args:
            text: The normalized text.
            embedding: The embedding vector to cache.
        """
        if self._cache_size == 0:
            return

        cache_key = self._get_cache_key(text)

        # If already in cache, update and move to end
        if cache_key in self._cache:
            self._cache.move_to_end(cache_key)
            self._cache[cache_key] = embedding
            return

        # Evict oldest if at capacity
        while len(self._cache) >= self._cache_size:
            self._cache.popitem(last=False)

        self._cache[cache_key] = embedding

    def _normalize_text(self, text: str) -> str:
        """
        Normalize input text for embedding.

        Performs the following normalizations:
        - Strip leading/trailing whitespace
        - Replace multiple whitespace with single space
        - Truncate to max input characters

        Args:
            text: The input text to normalize.

        Returns:
            Normalized text string.

        Raises:
            EmbeddingInputError: If text is empty after normalization.
        """
        if not text:
            raise EmbeddingInputError("Input text cannot be empty")

        # Strip and normalize whitespace
        normalized = " ".join(text.split())

        if not normalized:
            raise EmbeddingInputError("Input text is empty after normalization")

        # Truncate if too long
        if len(normalized) > MAX_INPUT_CHARS:
            self._log.warning(
                "text_truncated",
                original_length=len(normalized),
                truncated_length=MAX_INPUT_CHARS,
            )
            normalized = normalized[:MAX_INPUT_CHARS]

        return normalized

    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=MIN_RETRY_WAIT, max=MAX_RETRY_WAIT),
        retry=retry_if_exception_type((ClientError,)),
        reraise=True,
    )
    async def _invoke_model(self, text: str) -> list[float]:
        """
        Invoke the Bedrock embedding model for a single text.

        This method is decorated with retry logic to handle transient
        failures like throttling.

        Args:
            text: The text to embed (should be pre-normalized).

        Returns:
            List of floats representing the embedding vector.

        Raises:
            EmbeddingModelError: If the model invocation fails.
        """
        client = self._get_client()

        # Prepare request body
        body = json.dumps({"inputText": text})

        try:
            # Run synchronous boto3 call in thread pool
            response = await asyncio.to_thread(
                client.invoke_model,
                modelId=self.model_id,
                body=body,
                contentType="application/json",
                accept="application/json",
            )

            # Parse response
            response_body = json.loads(response["body"].read())
            embedding = response_body.get("embedding")

            if not embedding:
                raise EmbeddingModelError(f"No embedding in response: {response_body}")

            # Track token usage for cost estimation
            # Titan returns inputTextTokenCount in the response
            token_count = response_body.get("inputTextTokenCount", 0)
            self._total_tokens_used += token_count

            self._log.debug(
                "embedding_generated",
                dimension=len(embedding),
                input_tokens=token_count,
            )

            return embedding

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))

            if error_code == "ThrottlingException":
                self._log.warning(
                    "bedrock_throttled",
                    error_code=error_code,
                    error_message=error_message,
                )
                raise  # Let tenacity retry

            self._log.error(
                "bedrock_invocation_failed",
                error_code=error_code,
                error_message=error_message,
            )
            raise EmbeddingModelError(
                f"Bedrock invocation failed: {error_code} - {error_message}"
            ) from e

        except json.JSONDecodeError as e:
            self._log.error("response_parse_failed", error=str(e))
            raise EmbeddingModelError(f"Failed to parse response: {e}") from e

        except Exception as e:
            self._log.error("embedding_generation_failed", error=str(e))
            raise EmbeddingModelError(f"Embedding generation failed: {e}") from e

    async def embed_text(self, text: str) -> list[float]:
        """
        Generate an embedding for a single text.

        This method normalizes the input text and generates an embedding
        vector using the configured Bedrock model. Results are cached
        to avoid redundant API calls for repeated texts.

        Args:
            text: The text to embed.

        Returns:
            List of floats representing the embedding vector (1536 dimensions
            for Titan v1, 1024 for Titan v2).

        Raises:
            EmbeddingInputError: If the input text is invalid.
            EmbeddingModelError: If embedding generation fails.

        Example:
            embeddings = BedrockEmbeddings()
            vector = await embeddings.embed_text("What is NVIDIA's revenue?")
            print(f"Vector dimension: {len(vector)}")
        """
        normalized = self._normalize_text(text)

        # Check cache first
        cached = self._get_from_cache(normalized)
        if cached is not None:
            self._log.debug("embedding_cache_hit", text_length=len(normalized))
            return cached

        # Generate new embedding
        embedding = await self._invoke_model(normalized)

        # Cache the result
        self._add_to_cache(normalized, embedding)

        return embedding

    async def embed_batch(
        self,
        texts: list[str],
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> list[list[float]]:
        """
        Generate embeddings for a batch of texts.

        Processes texts in batches to improve efficiency and avoid
        overwhelming the API. Each batch is processed with a small
        delay to prevent throttling.

        Args:
            texts: List of texts to embed.
            batch_size: Number of texts to process per batch. Defaults to 25.
                Smaller batches are safer for rate limiting.

        Returns:
            List of embedding vectors, one per input text.

        Raises:
            EmbeddingInputError: If any input text is invalid.
            EmbeddingModelError: If embedding generation fails.

        Example:
            embeddings = BedrockEmbeddings()
            texts = [
                "Document chunk 1...",
                "Document chunk 2...",
                "Document chunk 3...",
            ]
            vectors = await embeddings.embed_batch(texts, batch_size=10)
            print(f"Generated {len(vectors)} embeddings")
        """
        if not texts:
            return []

        # Normalize all texts first
        normalized_texts = [self._normalize_text(text) for text in texts]

        self._log.info(
            "batch_embedding_started",
            total_texts=len(texts),
            batch_size=batch_size,
        )

        results: list[list[float]] = []

        # Process in batches
        for i in range(0, len(normalized_texts), batch_size):
            batch = normalized_texts[i : i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(normalized_texts) + batch_size - 1) // batch_size

            self._log.debug(
                "processing_batch",
                batch_num=batch_num,
                total_batches=total_batches,
                batch_size=len(batch),
            )

            # Process each text in the batch
            # Note: Titan doesn't support true batch API, so we process individually
            # but group them logically for progress tracking
            for text in batch:
                embedding = await self._invoke_model(text)
                results.append(embedding)

            # Small delay between batches to avoid throttling
            if i + batch_size < len(normalized_texts):
                await asyncio.sleep(BATCH_DELAY_SECONDS)

        self._log.info(
            "batch_embedding_completed",
            total_embeddings=len(results),
            total_tokens=self._total_tokens_used,
        )

        return results

    def get_total_tokens_used(self) -> int:
        """
        Get the total number of tokens processed.

        This can be used for cost estimation. Titan embeddings cost
        approximately $0.0001 per 1K tokens.

        Returns:
            Total tokens processed since initialization.

        Example:
            embeddings = BedrockEmbeddings()
            await embeddings.embed_batch(texts)
            tokens = embeddings.get_total_tokens_used()
            estimated_cost = tokens / 1000 * 0.0001
            print(f"Estimated cost: ${estimated_cost:.4f}")
        """
        return self._total_tokens_used

    def reset_token_counter(self) -> None:
        """
        Reset the token usage counter.

        Useful for tracking costs across different operations or batches.
        """
        self._total_tokens_used = 0
        self._log.debug("token_counter_reset")

    def get_cache_stats(self) -> dict[str, int | float]:
        """
        Get cache statistics.

        Returns:
            Dict with cache hits, misses, size, max_size (int), and hit_rate (float).

        Example:
            stats = embeddings.get_cache_stats()
            print(f"Cache hit rate: {stats['hit_rate']:.1%}")
        """
        total = self._cache_hits + self._cache_misses
        hit_rate = self._cache_hits / total if total > 0 else 0.0

        return {
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "size": len(self._cache),
            "max_size": self._cache_size,
            "hit_rate": hit_rate,
        }

    def clear_cache(self) -> None:
        """
        Clear the embedding cache.

        Useful when documents are updated and embeddings need to be regenerated.
        """
        self._cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0
        self._log.debug("embedding_cache_cleared")

    async def verify_model_access(self) -> dict[str, Any]:
        """
        Verify that the embedding model is accessible.

        Performs a test embedding to ensure the model is available
        and credentials are valid.

        Returns:
            Dict with status, model info, and test embedding dimension.

        Raises:
            EmbeddingModelError: If model access fails.

        Example:
            embeddings = BedrockEmbeddings()
            status = await embeddings.verify_model_access()
            if status["accessible"]:
                print(f"Model ready, dimension: {status['dimension']}")
        """
        self._log.info("verifying_model_access", model_id=self.model_id)

        try:
            # Test with a simple embedding
            test_embedding = await self.embed_text("test")

            return {
                "accessible": True,
                "model_id": self.model_id,
                "dimension": len(test_embedding),
                "expected_dimension": self.get_dimension(),
            }

        except Exception as e:
            self._log.error("model_access_verification_failed", error=str(e))
            raise EmbeddingModelError(f"Failed to verify model access: {e}") from e


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    "BedrockEmbeddings",
    "EmbeddingError",
    "EmbeddingModelError",
    "EmbeddingInputError",
    "DEFAULT_EMBEDDING_MODEL_ID",
    "DEFAULT_CACHE_SIZE",
]
