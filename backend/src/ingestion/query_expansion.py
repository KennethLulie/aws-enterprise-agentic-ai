"""
Query expansion and analysis module for hybrid retrieval.

This module provides query expansion (generating alternative phrasings) and
complexity analysis (determining KG traversal depth) using AWS Bedrock Nova Lite.
Both tasks are performed in a single LLM call for cost efficiency.

Query Expansion:
    Generates alternative phrasings of a user query to improve retrieval recall.
    Different phrasings may match different relevant documents.

KG Complexity Analysis:
    Determines whether a query needs simple (1-hop) or complex (2-hop) Knowledge
    Graph traversal based on the query's semantic structure.

Architecture:
    Query → Nova Lite → JSON Response → QueryAnalysis
                         ↓
              variants + kg_complexity + reason

Usage:
    from src.ingestion.query_expansion import QueryExpander, QueryAnalysis

    expander = QueryExpander()

    # Get full analysis (variants + KG complexity)
    analysis = await expander.analyze("What are Apple's supply chain risks?")
    print(analysis.variants)        # ('original', 'alt1', 'alt2', 'alt3')
    print(analysis.kg_complexity)   # 'complex'
    print(analysis.use_2hop)        # True

    # Legacy method for just variants
    variants = await expander.expand("Tell me about NVIDIA")
    # ('Tell me about NVIDIA', 'NVIDIA Corporation overview', ...)

Reference:
    - PHASE_2B_HOW_TO_GUIDE.md Section 8.1
    - backend.mdc for Python patterns
    - DEVELOPMENT_REFERENCE.md for Nova Lite model ID
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
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

# Default Nova Lite model for query expansion (fast, cheap)
DEFAULT_MODEL_ID = "amazon.nova-lite-v1:0"

# Retry configuration for transient errors
MAX_RETRIES = 3
MIN_RETRY_WAIT = 1  # seconds
MAX_RETRY_WAIT = 10  # seconds

# Timeout for LLM calls
DEFAULT_TIMEOUT = 30.0  # seconds

# Maximum query length to prevent abuse
MAX_QUERY_LENGTH = 500

# Cache size for repeated queries
CACHE_SIZE = 100


# =============================================================================
# Data Classes
# =============================================================================


@dataclass(frozen=True)
class QueryAnalysis:
    """
    Result of query analysis: variants + KG complexity.

    Attributes:
        variants: Tuple of query variants (original + alternatives).
        kg_complexity: Either "simple" or "complex".
        complexity_reason: Brief explanation for the classification.

    Example:
        analysis = QueryAnalysis(
            variants=("Apple supply chain risks", "AAPL supplier risks", ...),
            kg_complexity="complex",
            complexity_reason="Query involves relationship between entities"
        )

        if analysis.use_2hop:
            # Use 2-hop KG traversal
            results = kg.find_related_entities(entity, hops=2)
    """

    variants: tuple[str, ...]
    kg_complexity: str
    complexity_reason: str

    @property
    def use_2hop(self) -> bool:
        """
        Convenience property for KG traversal decision.

        Returns:
            True if complex query requiring 2-hop traversal, False otherwise.
        """
        return self.kg_complexity == "complex"


# =============================================================================
# Exceptions
# =============================================================================


class QueryExpansionError(Exception):
    """Base exception for query expansion operations."""

    pass


class QueryAnalysisTimeoutError(QueryExpansionError):
    """Raised when query analysis times out."""

    pass


# =============================================================================
# Query Expander
# =============================================================================


class QueryExpander:
    """
    Expands queries and analyzes complexity using Nova Lite.

    This class generates alternative phrasings of user queries and determines
    whether they require simple or complex Knowledge Graph traversal. Both
    analyses are performed in a single LLM call for cost efficiency.

    Attributes:
        model_id: Bedrock model ID for Nova Lite.
        timeout: Maximum time (seconds) for LLM calls.

    Example:
        expander = QueryExpander()

        # Full analysis
        analysis = await expander.analyze("Apple's Taiwan suppliers")
        print(analysis.variants)      # Alternative phrasings
        print(analysis.use_2hop)      # True (complex query)

        # Just variants (legacy)
        variants = await expander.expand("NVIDIA revenue")
    """

    def __init__(
        self,
        model_id: str = DEFAULT_MODEL_ID,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        """
        Initialize the query expander.

        Args:
            model_id: Bedrock model ID for query expansion.
                Defaults to amazon.nova-lite-v1:0.
            timeout: Maximum time (seconds) for LLM calls.
                Defaults to 30 seconds.
        """
        self.model_id = model_id
        self.timeout = timeout
        self._client: Any = None
        self._log = logger.bind(component="query_expander", model_id=model_id)

        # Instance-level cache (not shared across instances)
        self._cache: dict[str, QueryAnalysis] = {}
        self._cache_order: list[str] = []

        self._log.info(
            "query_expander_initialized",
            timeout=timeout,
        )

    def _get_client(self) -> Any:
        """
        Get or create the Bedrock runtime client.

        Returns:
            boto3 Bedrock runtime client.

        Raises:
            QueryExpansionError: If client creation fails.
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
                raise QueryExpansionError(
                    f"Failed to create Bedrock client: {e}"
                ) from e
        return self._client

    def _build_prompt(self, query: str, num_variants: int) -> str:
        """
        Build the analysis prompt for Nova Lite.

        Args:
            query: The user's search query.
            num_variants: Number of alternative variants to generate.

        Returns:
            Formatted prompt string.
        """
        return f"""Analyze this search query and respond in JSON format only.

Query: {query}

Generate a JSON response with:
{{
  "variants": ["alt1", "alt2", "alt3"],
  "kg_complexity": "simple" or "complex",
  "complexity_reason": "brief explanation"
}}

Guidelines for variants:
- Generate exactly {num_variants} alternative phrasings with the same intent
- Use different words/synonyms while preserving meaning
- Include relevant financial terms where appropriate

Guidelines for kg_complexity:
- "simple": Direct entity lookup (e.g., "Tell me about NVIDIA", "Apple's 2024 revenue")
- "complex": Needs relationship traversal (e.g., "Apple's Taiwan suppliers", "competitors to NVIDIA", "how X affects Y")

Decision criteria:
- Single entity lookup = simple
- Entity + attribute = simple
- Two+ entities with relationship = complex
- Keywords like "affects", "related", "between", "competitors", "suppliers" = complex
- Comparative queries = complex

Respond ONLY with valid JSON, no markdown or other text."""

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
            QueryExpansionError: If model invocation fails.
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
                    "maxTokens": 500,
                    "temperature": 0.3,  # Low temp for consistent JSON output
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
                self._log.debug(
                    "nova_lite_response",
                    response_length=len(text),
                )
                return text

            raise QueryExpansionError(f"Unexpected response format: {response_body}")

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            self._log.error(
                "nova_lite_invocation_failed",
                error_code=error_code,
                error=str(e),
            )
            raise

    def _parse_response(
        self,
        response: str,
        original_query: str,
        num_variants: int,
    ) -> QueryAnalysis:
        """
        Parse the LLM response into QueryAnalysis.

        Args:
            response: Raw LLM response text.
            original_query: The original user query.
            num_variants: Expected number of variants.

        Returns:
            Parsed QueryAnalysis object.
        """
        try:
            # Try to extract JSON from response (handle markdown code blocks)
            json_str = response.strip()
            if json_str.startswith("```"):
                # Extract JSON from code block
                lines = json_str.split("\n")
                json_lines = [line for line in lines if not line.startswith("```")]
                json_str = "\n".join(json_lines)

            parsed = json.loads(json_str)

            # Extract and deduplicate variants
            raw_variants = parsed.get("variants", [])
            seen = {original_query.lower().strip()}
            unique_variants = [original_query]  # Always include original first

            for variant in raw_variants:
                if isinstance(variant, str):
                    normalized = variant.lower().strip()
                    if normalized and normalized not in seen and len(variant) > 5:
                        seen.add(normalized)
                        unique_variants.append(variant)

            # Limit to requested number + original
            final_variants = tuple(unique_variants[: num_variants + 1])

            # Extract complexity with default fallback
            kg_complexity = parsed.get("kg_complexity", "simple")
            if kg_complexity not in ("simple", "complex"):
                kg_complexity = "simple"

            complexity_reason = parsed.get("complexity_reason", "")

            return QueryAnalysis(
                variants=final_variants,
                kg_complexity=kg_complexity,
                complexity_reason=complexity_reason,
            )

        except json.JSONDecodeError as e:
            self._log.warning(
                "json_parse_failed",
                error=str(e),
                response_preview=response[:100],
            )
            # Fall back to returning just the original query
            return QueryAnalysis(
                variants=(original_query,),
                kg_complexity="simple",
                complexity_reason="JSON parse failed - defaulting to simple",
            )

    async def analyze(
        self,
        query: str,
        num_variants: int = 3,
    ) -> QueryAnalysis:
        """
        Analyze query: generate variants AND determine KG complexity.

        Single LLM call for both tasks (cost-efficient). Results are cached
        for repeated queries.

        Args:
            query: The user's search query.
            num_variants: Number of alternative variants to generate.
                Defaults to 3.

        Returns:
            QueryAnalysis with variants and complexity classification.

        Example:
            analysis = await expander.analyze("Apple's supply chain risks")
            print(analysis.variants)
            # ('Apple's supply chain risks', 'AAPL supplier risks', ...)
            print(analysis.use_2hop)  # True
        """
        # Validate and truncate query
        query = query.strip()
        if not query:
            return QueryAnalysis(
                variants=("",),
                kg_complexity="simple",
                complexity_reason="Empty query",
            )

        if len(query) > MAX_QUERY_LENGTH:
            query = query[:MAX_QUERY_LENGTH]
            self._log.warning("query_truncated", original_length=len(query))

        # Check cache first
        cache_key = f"{query}:{num_variants}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            self._log.debug("cache_hit", query=query[:50])
            return cached

        self._log.debug(
            "analyzing_query",
            query=query[:50],
            num_variants=num_variants,
        )

        try:
            # Build prompt and invoke model with timeout
            prompt = self._build_prompt(query, num_variants)

            response = await asyncio.wait_for(
                self._invoke_nova_lite(prompt),
                timeout=self.timeout,
            )

            # Parse response
            result = self._parse_response(response, query, num_variants)

            # Cache result
            self._set_cached(cache_key, result)

            self._log.info(
                "query_analyzed",
                query=query[:50],
                variant_count=len(result.variants),
                kg_complexity=result.kg_complexity,
            )

            return result

        except asyncio.TimeoutError:
            self._log.warning("analysis_timeout", query=query[:50])
            return QueryAnalysis(
                variants=(query,),
                kg_complexity="simple",
                complexity_reason="Timeout - defaulting to simple",
            )

        except Exception as e:
            self._log.error("analysis_failed", query=query[:50], error=str(e))
            return QueryAnalysis(
                variants=(query,),
                kg_complexity="simple",
                complexity_reason=f"Error - defaulting to simple: {str(e)[:50]}",
            )

    async def expand(
        self,
        query: str,
        num_variants: int = 3,
    ) -> tuple[str, ...]:
        """
        Legacy method - returns only query variants.

        For backwards compatibility. Prefer analyze() for full results.

        Args:
            query: The user's search query.
            num_variants: Number of alternative variants to generate.

        Returns:
            Tuple of query variants (original + alternatives).
        """
        analysis = await self.analyze(query, num_variants)
        return analysis.variants

    # =========================================================================
    # Caching (simple in-memory LRU cache)
    # =========================================================================

    def _get_cached(self, key: str) -> QueryAnalysis | None:
        """Get cached result if available."""
        return self._cache.get(key)

    def _set_cached(self, key: str, value: QueryAnalysis) -> None:
        """Cache result with LRU eviction."""
        if key in self._cache:
            # Move to end (most recently used)
            self._cache_order.remove(key)
            self._cache_order.append(key)
        else:
            # Add new entry
            if len(self._cache) >= CACHE_SIZE:
                # Evict oldest
                oldest = self._cache_order.pop(0)
                del self._cache[oldest]
            self._cache[key] = value
            self._cache_order.append(key)


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    "QueryExpander",
    "QueryAnalysis",
    "QueryExpansionError",
    "QueryAnalysisTimeoutError",
]
