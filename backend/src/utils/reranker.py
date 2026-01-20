"""
Cross-encoder reranking using AWS Bedrock Nova Lite.

This module provides LLM-based relevance scoring to rerank retrieval results.
Unlike bi-encoder embeddings which encode query and document separately,
cross-encoder reranking considers both together for more accurate relevance.

Architecture:
    RRF Results → CrossEncoderReranker → Top-K Most Relevant
                          ↓
              Nova Lite scores each (query, doc) pair

Why Reranking:
    - Bi-encoders optimize for retrieval speed, not precision
    - Cross-encoders understand query-document interaction
    - 20-25% precision improvement on top results
    - Filters false positives from initial retrieval

Pipeline Position:
    Dense Search → RRF Fusion → KG Boost → **Reranker** → Compressor → LLM
                                              ↑
                                        This module

Usage:
    from src.utils.reranker import CrossEncoderReranker

    reranker = CrossEncoderReranker()

    # Rerank RRF results
    top_results = await reranker.rerank(
        query="What are NVIDIA's supply chain risks?",
        results=rrf_results,  # From rrf_fusion()
        top_k=5
    )

    # Each result has relevance_score (1-10) from LLM
    for r in top_results:
        print(f"{r['id']}: relevance={r['relevance_score']}, rrf={r['rrf_score']}")

Note:
    This module preserves `kg_evidence` and `sources` from input results,
    which are critical for LLM explainability downstream.

Reference:
    - PHASE_2B_HOW_TO_GUIDE.md Section 10.1
    - backend.mdc for Python patterns
    - DEVELOPMENT_REFERENCE.md for Nova Lite model ID
"""

from __future__ import annotations

import asyncio
import json
import re
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

# Default Nova Lite model for reranking (fast, cheap)
DEFAULT_MODEL_ID = "amazon.nova-lite-v1:0"

# Retry configuration for transient errors
MAX_RETRIES = 3
MIN_RETRY_WAIT = 1  # seconds
MAX_RETRY_WAIT = 10  # seconds

# Default reranking parameters
DEFAULT_TOP_K = 5
DEFAULT_CANDIDATES = 15

# Maximum document length to send to LLM (tokens ≈ chars/4)
MAX_DOCUMENT_CHARS = 2000  # ~500 tokens

# Default score when LLM response is unparseable
DEFAULT_RELEVANCE_SCORE = 5

# Maximum concurrent LLM calls (avoid rate limiting)
MAX_CONCURRENT_CALLS = 5


# =============================================================================
# Exceptions
# =============================================================================


class RerankerError(Exception):
    """Base exception for reranking operations."""

    pass


class RerankerModelError(RerankerError):
    """Raised when LLM invocation fails."""

    pass


# =============================================================================
# Cross-Encoder Reranker
# =============================================================================


class CrossEncoderReranker:
    """
    Reranks retrieval results using LLM-based relevance scoring.

    Uses Nova Lite to score query-document relevance on a 1-10 scale.
    Documents are then sorted by relevance score and top-K returned.

    Attributes:
        model_id: Bedrock model ID for Nova Lite.

    Example:
        reranker = CrossEncoderReranker()

        results = await reranker.rerank(
            query="NVIDIA supply chain risks",
            results=rrf_results,
            top_k=5
        )

        # Results sorted by relevance_score, with original scores preserved
        for r in results:
            print(f"{r['id']}: relevance={r['relevance_score']}")
    """

    def __init__(
        self,
        model_id: str = DEFAULT_MODEL_ID,
    ) -> None:
        """
        Initialize the reranker.

        Args:
            model_id: Bedrock model ID for relevance scoring.
                Defaults to amazon.nova-lite-v1:0.
        """
        self.model_id = model_id
        self._client: Any = None
        self._log = logger.bind(component="reranker", model_id=model_id)

        self._log.info("reranker_initialized")

    def _get_client(self) -> Any:
        """
        Get or create the Bedrock runtime client.

        Returns:
            boto3 Bedrock runtime client.

        Raises:
            RerankerError: If client creation fails.
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
                raise RerankerError(f"Failed to create Bedrock client: {e}") from e
        return self._client

    def _build_relevance_prompt(self, query: str, document: str) -> str:
        """
        Build the relevance scoring prompt.

        Args:
            query: The user's search query.
            document: The document text to score.

        Returns:
            Formatted prompt string.
        """
        # Truncate document if too long
        if len(document) > MAX_DOCUMENT_CHARS:
            document = document[:MAX_DOCUMENT_CHARS] + "..."

        return f"""Rate the relevance of this document to the query on a scale of 1-10.
Only respond with a single number.

Query: {query}

Document: {document}

Relevance score (1-10):"""

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
            RerankerModelError: If model invocation fails.
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
                    "maxTokens": 10,  # Only need a single number
                    "temperature": 0.0,  # Deterministic for scoring
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
                text = content[0].get("text", "")
                return text.strip()

            raise RerankerModelError(f"Unexpected response format: {response_body}")

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            self._log.error(
                "nova_lite_invocation_failed",
                error_code=error_code,
                error=str(e),
            )
            raise

    def _parse_score(self, response: str) -> float:
        """
        Parse numeric score from LLM response.

        Args:
            response: Raw LLM response text.

        Returns:
            Parsed score (1-10), or DEFAULT_RELEVANCE_SCORE if unparseable.
        """
        # Extract first number from response
        match = re.search(r"\b(\d+(?:\.\d+)?)\b", response)
        if match:
            try:
                score = float(match.group(1))
                # Clamp to valid range
                return max(1.0, min(10.0, score))
            except ValueError:
                pass

        self._log.warning(
            "score_parse_failed",
            response=response[:50],
            using_default=DEFAULT_RELEVANCE_SCORE,
        )
        return DEFAULT_RELEVANCE_SCORE

    async def score_relevance(self, query: str, document: str) -> float:
        """
        Score relevance of a single document to a query.

        Args:
            query: The user's search query.
            document: The document text to score.

        Returns:
            Relevance score from 1-10.

        Example:
            score = await reranker.score_relevance(
                query="NVIDIA risks",
                document="NVIDIA faces supply chain challenges..."
            )
            print(f"Relevance: {score}/10")
        """
        prompt = self._build_relevance_prompt(query, document)

        try:
            response = await self._invoke_nova_lite(prompt)
            return self._parse_score(response)
        except Exception as e:
            self._log.error(
                "relevance_scoring_failed",
                error=str(e),
                using_default=DEFAULT_RELEVANCE_SCORE,
            )
            return DEFAULT_RELEVANCE_SCORE

    async def rerank(
        self,
        query: str,
        results: list[dict[str, Any]],
        top_k: int = DEFAULT_TOP_K,
    ) -> list[dict[str, Any]]:
        """
        Rerank results by LLM-scored relevance.

        Scores each result's relevance to the query, sorts by score,
        and returns the top-K most relevant. Preserves all original
        fields including kg_evidence and sources.

        Args:
            query: The user's search query.
            results: List of result dicts from RRF fusion. Expected fields:
                - id: Document/chunk identifier
                - metadata: Dict with parent_text or text field
                - rrf_score: (optional) Score from RRF fusion
                - kg_evidence: (optional) Evidence from KG boost
                - sources: (optional) List of retrieval sources
            top_k: Number of top results to return. Defaults to 5.

        Returns:
            List of top-K results sorted by relevance_score (descending).
            Each result contains all original fields plus:
            - relevance_score: LLM-assigned score (1-10)

        Example:
            reranked = await reranker.rerank(
                query="NVIDIA supply chain",
                results=rrf_results,
                top_k=5
            )
        """
        if not results:
            self._log.debug("rerank_empty_input")
            return []

        # Limit candidates to avoid excessive LLM calls
        candidates = results[:DEFAULT_CANDIDATES]

        self._log.debug(
            "rerank_started",
            query=query[:50],
            candidates=len(candidates),
            top_k=top_k,
        )

        # Semaphore to limit concurrent LLM calls (avoid rate limiting)
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_CALLS)

        # Score all candidates with controlled concurrency
        async def score_result(result: dict[str, Any]) -> tuple[dict[str, Any], float]:
            """Score a single result and return (result, score) tuple."""
            metadata = result.get("metadata", {})
            # Prefer parent_text (full context), fall back to text/child_text
            document = (
                metadata.get("parent_text")
                or metadata.get("text")
                or metadata.get("child_text")
                or ""
            )

            if not document:
                self._log.warning(
                    "rerank_missing_text",
                    result_id=result.get("id"),
                )
                return (result, DEFAULT_RELEVANCE_SCORE)

            # Use semaphore to limit concurrent LLM calls
            async with semaphore:
                score = await self.score_relevance(query, document)
            return (result, score)

        # Run all scoring tasks with controlled concurrency
        scored_results = await asyncio.gather(*[score_result(r) for r in candidates])

        # Sort by relevance score descending
        sorted_results = sorted(scored_results, key=lambda x: x[1], reverse=True)

        # Build output with all fields preserved
        reranked_results: list[dict[str, Any]] = []
        for original_result, score in sorted_results[:top_k]:
            reranked = {
                "id": original_result.get("id"),
                "relevance_score": score,
                "rrf_score": original_result.get("rrf_score", 0),
                "metadata": original_result.get("metadata", {}),
            }

            # PRESERVE kg_evidence from KG boost step (critical for explainability)
            if "kg_evidence" in original_result:
                reranked["kg_evidence"] = original_result["kg_evidence"]

            # PRESERVE sources list (tracks retrieval provenance)
            if "sources" in original_result:
                reranked["sources"] = original_result["sources"]

            reranked_results.append(reranked)

        self._log.info(
            "rerank_complete",
            query=query[:50],
            candidates_scored=len(candidates),
            returned=len(reranked_results),
            top_score=reranked_results[0]["relevance_score"] if reranked_results else 0,
        )

        return reranked_results


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    "CrossEncoderReranker",
    "RerankerError",
    "RerankerModelError",
]
