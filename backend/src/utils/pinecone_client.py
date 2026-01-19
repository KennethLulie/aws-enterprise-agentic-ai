"""
Pinecone vector store client wrapper for RAG operations.

This module provides a wrapper around the Pinecone Python client for vector
store operations in the RAG pipeline. It supports:
- Batch upsert with automatic chunking (100 vectors per batch)
- Query with metadata filtering
- Delete-before-upsert pattern for safe re-indexing
- Connection pooling and retry logic

The client is designed for the parent/child chunking architecture where:
- Child chunks (256 tokens) are embedded and stored as vectors
- Parent text (1024 tokens) is stored in metadata for LLM context
- Both child_text and child_text_raw are stored for embedding and citation

Vector Format (10-K Documents):
    {
        "id": "AAPL_10K_2024_parent_5_child_2",
        "values": [0.1, 0.2, ...],  # 1024 floats (Titan v2)
        "metadata": {
            "document_id": "AAPL_10K_2024",
            "document_type": "10k",
            "parent_id": "AAPL_10K_2024_parent_5",
            "parent_text": "Full 1024-token context...",
            "child_text": "Enriched 256-token text...",
            "child_text_raw": "Original text for citations...",
            ...
        }
    }

Metadata Size Consideration:
    - Pinecone metadata limit: 40KB per vector
    - 1024 tokens ≈ 4KB text (well under limit)
    - Both parent_text and child_text fit safely

Usage:
    from src.utils.pinecone_client import PineconeClient

    client = PineconeClient()

    # Upsert vectors for a document (delete-before-upsert)
    result = client.upsert_document("AAPL_10K_2024", vectors)

    # Query with filter
    results = client.query(embedding, top_k=10, filter={"ticker": "AAPL"})

    # Get index stats
    stats = client.get_stats()

Reference:
    - Pinecone Python client: https://docs.pinecone.io/docs/python-client
    - backend.mdc for Python patterns
    - RAG_IMPROVEMENTS_DELTA.md for architecture details
"""

from __future__ import annotations

import time
from typing import Any

import structlog
from pydantic import SecretStr
from tenacity import (
    RetryCallState,
    retry,
    stop_after_attempt,
    wait_exponential,
)

from src.config.settings import get_settings

# Configure structured logger
logger = structlog.get_logger(__name__)


# =============================================================================
# Retry Configuration
# =============================================================================

# Define which exceptions are retryable (transient/network errors)
# We avoid retrying on validation errors or client-side issues
RETRYABLE_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    OSError,  # Network errors
)


def _is_retryable_pinecone_error(retry_state: RetryCallState) -> bool:
    """
    Determine if a Pinecone exception is retryable.

    This function is used by tenacity's retry decorator to decide whether
    to retry after an exception.

    Retries on:
    - Network/connection errors
    - Rate limiting (429)
    - Server errors (5xx)

    Does NOT retry on:
    - Validation errors (400)
    - Authentication errors (401, 403)
    - Not found errors (404)

    Args:
        retry_state: The tenacity RetryCallState containing exception info.

    Returns:
        True if the exception should be retried, False otherwise.
    """
    exception = retry_state.outcome.exception() if retry_state.outcome else None
    if exception is None:
        return False

    # Check for common retryable exception types
    if isinstance(exception, RETRYABLE_EXCEPTIONS):
        return True

    # Check for Pinecone-specific errors by examining the message
    error_str = str(exception).lower()
    retryable_patterns = [
        "rate limit",
        "throttl",
        "timeout",
        "connection",
        "503",
        "502",
        "504",
        "internal server",
        "service unavailable",
    ]
    return any(pattern in error_str for pattern in retryable_patterns)


# =============================================================================
# Constants
# =============================================================================

# Batch size for upsert operations (Pinecone recommendation)
DEFAULT_UPSERT_BATCH_SIZE = 100

# Retry settings
MAX_RETRIES = 3
MIN_RETRY_WAIT = 1  # seconds
MAX_RETRY_WAIT = 10  # seconds

# Rate limiting - delay between batch operations to avoid throttling
BATCH_DELAY_SECONDS = 0.1  # 100ms between batches

# Expected embedding dimension (Titan v2 default)
EXPECTED_DIMENSION = 1024

# Metadata size limit (Pinecone limit is 40KB, we use 38KB for safety margin)
MAX_METADATA_BYTES = 38 * 1024  # 38KB

# Fields that contain large text and should be checked for size
LARGE_TEXT_FIELDS = ["parent_text", "child_text", "child_text_raw"]


# =============================================================================
# Custom Exceptions
# =============================================================================


class PineconeClientError(Exception):
    """Base exception for Pinecone client operations."""

    pass


class PineconeConnectionError(PineconeClientError):
    """Error connecting to Pinecone."""

    pass


class PineconeValidationError(PineconeClientError):
    """Error during vector validation (dimension, metadata size, etc.)."""

    pass


class PineconeUpsertError(PineconeClientError):
    """Error during vector upsert."""

    pass


class PineconeQueryError(PineconeClientError):
    """Error during vector query."""

    pass


class PineconeDeleteError(PineconeClientError):
    """Error during vector deletion."""

    pass


# =============================================================================
# PineconeClient Class
# =============================================================================


class PineconeClient:
    """
    Pinecone vector store client for RAG operations.

    This client wraps the Pinecone Python SDK and provides:
    - Lazy connection initialization
    - Batch upsert with automatic chunking
    - Delete-before-upsert pattern for safe re-indexing
    - Query with metadata filtering
    - Retry logic for transient failures

    Attributes:
        api_key: Pinecone API key.
        index_name: Name of the Pinecone index.
        environment: Pinecone environment/region.

    Example:
        client = PineconeClient()

        # Upsert vectors for a document
        vectors = [
            {"id": "doc1_chunk1", "values": [...], "metadata": {...}},
            {"id": "doc1_chunk2", "values": [...], "metadata": {...}},
        ]
        result = client.upsert_document("doc1", vectors)

        # Query
        results = client.query(embedding, top_k=5, filter={"ticker": "AAPL"})
    """

    def __init__(
        self,
        api_key: str | SecretStr | None = None,
        index_name: str | None = None,
        environment: str | None = None,
    ) -> None:
        """
        Initialize the Pinecone client.

        Args:
            api_key: Pinecone API key (str or SecretStr). If not provided, loaded from settings.
            index_name: Pinecone index name. If not provided, loaded from settings.
            environment: Pinecone environment. If not provided, loaded from settings.

        Raises:
            PineconeConnectionError: If API key is not available.
        """
        settings = get_settings()

        # Get API key from parameter or settings
        # Handle both str and SecretStr for flexibility
        if api_key:
            if isinstance(api_key, SecretStr):
                self._api_key = api_key.get_secret_value()
            else:
                self._api_key = api_key
        elif settings.pinecone_api_key:
            self._api_key = settings.pinecone_api_key.get_secret_value()
        else:
            raise PineconeConnectionError(
                "Pinecone API key not provided. Set PINECONE_API_KEY in .env"
            )

        self._index_name = index_name or settings.pinecone_index_name
        self._environment = environment or settings.pinecone_environment

        # Lazy initialization
        self._client: Any = None
        self._index: Any = None

        self._log = logger.bind(
            component="pinecone_client",
            index_name=self._index_name,
            environment=self._environment,
        )
        self._log.info("pinecone_client_initialized")

    # =========================================================================
    # Validation Methods
    # =========================================================================

    def _validate_vector_dimension(
        self, vectors: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Validate that vectors have the expected dimension.

        Checks the first vector's dimension against EXPECTED_DIMENSION.
        If mismatch, raises PineconeValidationError with clear message.

        Args:
            vectors: List of vector dicts to validate.

        Returns:
            The same list (pass-through for chaining).

        Raises:
            PineconeValidationError: If dimension doesn't match expected.
        """
        if not vectors:
            return vectors

        first_vector = vectors[0]
        values = first_vector.get("values", [])

        if len(values) != EXPECTED_DIMENSION:
            raise PineconeValidationError(
                f"Vector dimension mismatch: got {len(values)}, "
                f"expected {EXPECTED_DIMENSION} (Bedrock Titan). "
                f"Check that you're using the correct embedding model."
            )

        return vectors

    def _validate_metadata_size(
        self, vectors: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """
        Validate metadata size doesn't exceed Pinecone's 40KB limit.

        Vectors with oversized metadata are logged and excluded.

        Args:
            vectors: List of vector dicts to validate.

        Returns:
            Tuple of (valid_vectors, skipped_vectors).
        """
        import json

        valid = []
        skipped = []

        for vector in vectors:
            metadata = vector.get("metadata", {})

            # Estimate metadata size (JSON serialization)
            try:
                metadata_bytes = len(json.dumps(metadata).encode("utf-8"))
            except (TypeError, ValueError):
                # Can't serialize - skip this vector
                self._log.error(
                    "metadata_serialization_failed",
                    vector_id=vector.get("id"),
                )
                skipped.append(vector)
                continue

            if metadata_bytes > MAX_METADATA_BYTES:
                self._log.warning(
                    "metadata_size_exceeded",
                    vector_id=vector.get("id"),
                    metadata_bytes=metadata_bytes,
                    limit_bytes=MAX_METADATA_BYTES,
                    large_fields={
                        field: len(str(metadata.get(field, "")).encode("utf-8"))
                        for field in LARGE_TEXT_FIELDS
                        if field in metadata
                    },
                )
                skipped.append(vector)
            else:
                valid.append(vector)

        if skipped:
            self._log.warning(
                "vectors_skipped_for_size",
                skipped_count=len(skipped),
                valid_count=len(valid),
            )

        return valid, skipped

    def _sanitize_filter(self, filter: dict[str, Any] | None) -> dict[str, Any] | None:
        """
        Sanitize query filter by removing None values.

        Pinecone doesn't handle None values in filters well.
        This removes them to prevent query errors.

        Args:
            filter: The filter dict to sanitize.

        Returns:
            Sanitized filter with None values removed, or None if empty.
        """
        if not filter:
            return None

        # Remove None values (shallow - doesn't handle nested dicts)
        sanitized = {k: v for k, v in filter.items() if v is not None}

        if not sanitized:
            return None

        # Log if we removed anything
        removed_keys = set(filter.keys()) - set(sanitized.keys())
        if removed_keys:
            self._log.debug(
                "filter_sanitized",
                removed_keys=list(removed_keys),
            )

        return sanitized

    def _get_client(self) -> Any:
        """
        Get or create the Pinecone client.

        Returns:
            Pinecone client instance.

        Raises:
            PineconeConnectionError: If client creation fails.
        """
        if self._client is None:
            try:
                from pinecone import Pinecone

                self._client = Pinecone(api_key=self._api_key)
                self._log.debug("pinecone_client_created")
            except Exception as e:
                self._log.error("pinecone_client_creation_failed", error=str(e))
                raise PineconeConnectionError(
                    f"Failed to create Pinecone client: {e}"
                ) from e
        return self._client

    def _get_index(self) -> Any:
        """
        Get or create the Pinecone index reference.

        Returns:
            Pinecone Index instance.

        Raises:
            PineconeConnectionError: If index connection fails.
        """
        if self._index is None:
            try:
                client = self._get_client()
                self._index = client.Index(self._index_name)
                self._log.debug("pinecone_index_connected", index=self._index_name)
            except Exception as e:
                self._log.error(
                    "pinecone_index_connection_failed",
                    index=self._index_name,
                    error=str(e),
                )
                raise PineconeConnectionError(
                    f"Failed to connect to index '{self._index_name}': {e}"
                ) from e
        return self._index

    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=MIN_RETRY_WAIT, max=MAX_RETRY_WAIT),
        retry=_is_retryable_pinecone_error,
        reraise=True,
    )
    def upsert_vectors(
        self,
        vectors: list[dict[str, Any]],
        batch_size: int = DEFAULT_UPSERT_BATCH_SIZE,
        skip_validation: bool = False,
    ) -> dict[str, Any]:
        """
        Upsert vectors to Pinecone in batches.

        Vectors are automatically split into batches of batch_size for
        efficient upsert. Each batch is followed by a small delay to
        avoid throttling.

        Validation (unless skip_validation=True):
        - Checks vector dimension matches EXPECTED_DIMENSION (1024 for Titan v2)
        - Checks metadata size < 40KB (Pinecone limit)
        - Vectors failing validation are skipped with warnings

        Args:
            vectors: List of vector dictionaries with format:
                {
                    "id": str,
                    "values": list[float],
                    "metadata": dict (optional)
                }
            batch_size: Number of vectors per batch. Defaults to 100.
            skip_validation: If True, skip dimension and size validation.
                Use only if you've pre-validated vectors.

        Returns:
            Dict with upsert statistics:
            {
                "upserted_count": int,
                "batch_count": int,
                "skipped_count": int  # Vectors that failed validation
            }

        Raises:
            PineconeUpsertError: If upsert fails.
            PineconeValidationError: If vector dimension is wrong.

        Example:
            vectors = [
                {"id": "doc1_chunk1", "values": [...], "metadata": {...}},
            ]
            result = client.upsert_vectors(vectors)
        """
        if not vectors:
            return {"upserted_count": 0, "batch_count": 0, "skipped_count": 0}

        skipped_count = 0

        if not skip_validation:
            # Validate dimension (raises on mismatch)
            self._validate_vector_dimension(vectors)

            # Validate metadata size (filters out oversized)
            vectors, skipped = self._validate_metadata_size(vectors)
            skipped_count = len(skipped)

            if not vectors:
                self._log.warning(
                    "all_vectors_skipped",
                    skipped_count=skipped_count,
                    reason="metadata_size_exceeded",
                )
                return {
                    "upserted_count": 0,
                    "batch_count": 0,
                    "skipped_count": skipped_count,
                }

        index = self._get_index()
        total_upserted = 0
        batch_count = 0

        self._log.info(
            "upsert_started",
            total_vectors=len(vectors),
            batch_size=batch_size,
        )

        try:
            # Process in batches
            for i in range(0, len(vectors), batch_size):
                batch = vectors[i : i + batch_size]
                batch_count += 1

                # Convert to Pinecone format (tuples or dicts work)
                # Using dict format for clarity
                index.upsert(vectors=batch)
                total_upserted += len(batch)

                self._log.debug(
                    "batch_upserted",
                    batch_num=batch_count,
                    batch_size=len(batch),
                    total_so_far=total_upserted,
                )

                # Small delay between batches to avoid throttling
                if i + batch_size < len(vectors):
                    time.sleep(BATCH_DELAY_SECONDS)

            self._log.info(
                "upsert_completed",
                total_upserted=total_upserted,
                batch_count=batch_count,
                skipped_count=skipped_count,
            )

            return {
                "upserted_count": total_upserted,
                "batch_count": batch_count,
                "skipped_count": skipped_count,
            }

        except Exception as e:
            self._log.error(
                "upsert_failed",
                error=str(e),
                upserted_before_error=total_upserted,
                skipped_count=skipped_count,
            )
            raise PineconeUpsertError(f"Failed to upsert vectors: {e}") from e

    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=MIN_RETRY_WAIT, max=MAX_RETRY_WAIT),
        retry=_is_retryable_pinecone_error,
        reraise=True,
    )
    def query(
        self,
        vector: list[float],
        top_k: int = 10,
        filter: dict[str, Any] | None = None,
        include_metadata: bool = True,
        include_values: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Query Pinecone for similar vectors.

        Returns parent_text for LLM context and child_text_raw for citations
        in the metadata of each result.

        Args:
            vector: Query embedding vector (1024 floats for Titan v2).
            top_k: Number of results to return. Defaults to 10.
            filter: Optional metadata filter dict. Uses Pinecone filter syntax.
            include_metadata: Include metadata in results. Defaults to True.
            include_values: Include vector values in results. Defaults to False.

        Returns:
            List of match dictionaries:
            [
                {
                    "id": str,
                    "score": float,
                    "metadata": {
                        "parent_text": str,  # 1024-token context for LLM
                        "child_text_raw": str,  # Original text for citation
                        ...
                    }
                }
            ]

        Raises:
            PineconeQueryError: If query fails.

        Example:
            results = client.query(
                embedding,
                top_k=5,
                filter={"ticker": "AAPL", "fiscal_year": 2024}
            )
        """
        index = self._get_index()

        # Sanitize filter (remove None values that can cause errors)
        sanitized_filter = self._sanitize_filter(filter)

        self._log.debug(
            "query_started",
            top_k=top_k,
            has_filter=sanitized_filter is not None,
        )

        try:
            response = index.query(
                vector=vector,
                top_k=top_k,
                filter=sanitized_filter,
                include_metadata=include_metadata,
                include_values=include_values,
            )

            # Convert response to list of dicts
            results = []
            for match in response.matches:
                result = {
                    "id": match.id,
                    "score": match.score,
                }
                if include_metadata and match.metadata:
                    result["metadata"] = dict(match.metadata)
                if include_values and match.values:
                    result["values"] = list(match.values)
                results.append(result)

            self._log.debug(
                "query_completed",
                num_results=len(results),
                top_score=results[0]["score"] if results else None,
            )

            return results

        except Exception as e:
            self._log.error("query_failed", error=str(e))
            raise PineconeQueryError(f"Failed to query vectors: {e}") from e

    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=MIN_RETRY_WAIT, max=MAX_RETRY_WAIT),
        retry=_is_retryable_pinecone_error,
        reraise=True,
    )
    def delete_by_metadata(
        self,
        filter: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Delete vectors matching a metadata filter.

        This is used in the delete-before-upsert pattern to remove
        existing vectors for a document before re-indexing.

        Args:
            filter: Metadata filter dict. Must include at least one field.
                Example: {"document_id": "AAPL_10K_2024"}

        Returns:
            Dict with deletion info (may be empty for serverless).

        Raises:
            PineconeDeleteError: If deletion fails.

        Example:
            client.delete_by_metadata({"document_id": "AAPL_10K_2024"})
        """
        if not filter:
            raise PineconeDeleteError("Filter cannot be empty for delete operation")

        index = self._get_index()

        self._log.info(
            "delete_started",
            filter=filter,
        )

        try:
            # Pinecone serverless uses delete with filter
            # Note: This deletes ALL vectors matching the filter
            # Response is None for serverless indexes, so we don't capture it
            index.delete(filter=filter)

            self._log.info(
                "delete_completed",
                filter=filter,
            )

            return {"deleted": True, "filter": filter}

        except Exception as e:
            self._log.error("delete_failed", error=str(e), filter=filter)
            raise PineconeDeleteError(f"Failed to delete vectors: {e}") from e

    def upsert_document(
        self,
        document_id: str,
        vectors: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Safely upsert vectors for a document using delete-before-upsert pattern.

        This method first deletes any existing vectors for the document_id,
        then upserts the new vectors. This prevents duplicate vectors when
        re-indexing a document.

        Args:
            document_id: Unique document identifier (used as filter).
            vectors: List of vector dictionaries to upsert.

        Returns:
            Dict with operation statistics:
            {
                "document_id": str,
                "deleted": bool,
                "upserted_count": int,
                "batch_count": int
            }

        Raises:
            PineconeUpsertError: If upsert fails.
            PineconeDeleteError: If deletion fails.

        Example:
            result = client.upsert_document("AAPL_10K_2024", vectors)
        """
        # Early return if no vectors to upsert (don't delete existing data!)
        if not vectors:
            self._log.warning(
                "upsert_document_empty",
                document_id=document_id,
                message="No vectors provided, skipping upsert",
            )
            return {
                "document_id": document_id,
                "deleted": False,
                "upserted_count": 0,
                "batch_count": 0,
                "skipped_count": 0,
            }

        self._log.info(
            "upsert_document_started",
            document_id=document_id,
            vector_count=len(vectors),
        )

        # Step 1: Delete existing vectors for this document
        deleted = False
        try:
            self.delete_by_metadata({"document_id": document_id})
            deleted = True
        except PineconeDeleteError as e:
            # Log but continue - document might not exist yet
            self._log.warning(
                "delete_before_upsert_failed",
                document_id=document_id,
                error=str(e),
            )

        # Step 2: Upsert new vectors
        upsert_result = self.upsert_vectors(vectors)

        result = {
            "document_id": document_id,
            "deleted": deleted,
            **upsert_result,
        }

        self._log.info(
            "upsert_document_completed",
            **result,
        )

        return result

    def get_stats(self) -> dict[str, Any]:
        """
        Get index statistics.

        Returns:
            Dict with index stats:
            {
                "total_vector_count": int,
                "dimension": int,
                "index_fullness": float (0.0-1.0),
                "namespaces": dict
            }

        Raises:
            PineconeClientError: If stats retrieval fails.

        Example:
            stats = client.get_stats()
            print(f"Total vectors: {stats['total_vector_count']}")
        """
        index = self._get_index()

        try:
            stats = index.describe_index_stats()

            result = {
                "total_vector_count": stats.total_vector_count,
                "dimension": stats.dimension,
                "index_fullness": getattr(stats, "index_fullness", 0.0),
                "namespaces": dict(stats.namespaces) if stats.namespaces else {},
            }

            self._log.debug("stats_retrieved", **result)

            return result

        except Exception as e:
            self._log.error("stats_retrieval_failed", error=str(e))
            raise PineconeClientError(f"Failed to get index stats: {e}") from e

    def verify_connection(self) -> dict[str, Any]:
        """
        Verify Pinecone connection and index accessibility.

        Performs a test query to ensure the index is accessible and
        returns connection status.

        Returns:
            Dict with connection status:
            {
                "connected": bool,
                "index_name": str,
                "dimension": int,
                "total_vectors": int
            }

        Example:
            status = client.verify_connection()
            if status["connected"]:
                print(f"Connected to index with {status['total_vectors']} vectors")
        """
        try:
            stats = self.get_stats()

            return {
                "connected": True,
                "index_name": self._index_name,
                "dimension": stats["dimension"],
                "total_vectors": stats["total_vector_count"],
            }

        except Exception as e:
            self._log.error("connection_verification_failed", error=str(e))
            return {
                "connected": False,
                "index_name": self._index_name,
                "error": str(e),
            }


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    "PineconeClient",
    "PineconeClientError",
    "PineconeConnectionError",
    "PineconeValidationError",
    "PineconeUpsertError",
    "PineconeQueryError",
    "PineconeDeleteError",
    "DEFAULT_UPSERT_BATCH_SIZE",
    "EXPECTED_DIMENSION",
    "MAX_METADATA_BYTES",
]
