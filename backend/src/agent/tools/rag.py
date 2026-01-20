"""
RAG retrieval tool for semantic search over indexed documents.

- Uses Pinecone for vector search with BedrockEmbeddings for query embedding.
- Supports metadata filtering by ticker, document_type, section.
- Deduplicates results by parent_id and returns full parent context.
- Falls back to mock data when Pinecone is not configured (Phase 0 friendly).
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import structlog
from langchain.tools import tool
from pydantic import BaseModel, Field, field_validator

from src.config.settings import get_settings

# Type-only imports to avoid circular dependencies and heavy runtime imports
if TYPE_CHECKING:
    from src.utils.embeddings import BedrockEmbeddings
    from src.utils.pinecone_client import PineconeClient

logger = structlog.get_logger(__name__)

# Configuration
DEFAULT_TOP_K = 5
MAX_TOP_K = 20
QUERY_TIMEOUT_SECONDS = 20.0  # Covers embedding + Pinecone query with margin

# Module-level client cache for performance (lazy initialization)
_embeddings_client: "BedrockEmbeddings | None" = None
_pinecone_client: "PineconeClient | None" = None


class RAGQueryInput(BaseModel):
    """Input schema for the RAG retrieval tool."""

    # Allow LLMs to use camelCase parameter names (e.g., topK instead of top_k)
    model_config = {"populate_by_name": True}

    query: str = Field(
        ...,
        min_length=1,
        max_length=1024,
        description="User query to retrieve relevant documents for.",
    )
    top_k: int = Field(
        default=DEFAULT_TOP_K,
        ge=1,
        le=MAX_TOP_K,
        alias="topK",
        description="Number of results to return (default 5, max 20).",
    )
    ticker: str | None = Field(
        default=None,
        description="Filter by company ticker symbol (e.g., 'NVDA', 'AAPL').",
    )
    document_type: str | None = Field(
        default=None,
        alias="documentType",
        description="Filter by document type (e.g., '10k', 'reference').",
    )
    section: str | None = Field(
        default=None,
        description="Filter by section name (e.g., 'Item 1A: Risk Factors').",
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        """Ensure RAG queries are present after trimming whitespace."""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Query cannot be empty.")
        return cleaned


def _get_embeddings_client() -> "BedrockEmbeddings":
    """Get or create cached BedrockEmbeddings client."""
    global _embeddings_client
    if _embeddings_client is None:
        from src.utils.embeddings import BedrockEmbeddings

        _embeddings_client = BedrockEmbeddings()
        logger.debug("embeddings_client_created", cached=True)
    return _embeddings_client


def _get_pinecone_client() -> "PineconeClient":
    """Get or create cached PineconeClient."""
    global _pinecone_client
    if _pinecone_client is None:
        from src.utils.pinecone_client import PineconeClient

        settings = get_settings()
        _pinecone_client = PineconeClient(
            api_key=settings.pinecone_api_key,
            index_name=settings.pinecone_index_name,
        )
        logger.debug("pinecone_client_created", cached=True)
    return _pinecone_client


def _reset_clients() -> None:
    """Reset cached clients (useful for testing or error recovery)."""
    global _embeddings_client, _pinecone_client
    _embeddings_client = None
    _pinecone_client = None
    logger.debug("rag_clients_reset")


def _build_mock_results(query: str) -> str:
    """Return deterministic mock retrieval results for demo purposes."""
    return f"""Found 3 relevant passages for: "{query}"

[1] Source: NVDA 10-K 2025, Item 1A: Risk Factors, Page 15
Our operations depend on complex global supply chains. We rely on third-party manufacturers,
primarily in Asia, for our semiconductor products. Any disruption to these supply chains could
materially affect our ability to meet customer demand and impact our financial results.
Matched: Supply chain risks and manufacturing dependencies...

[2] Source: NVDA 10-K 2025, Item 1: Business, Page 8
NVIDIA designs and manufactures graphics processing units (GPUs) and system-on-chip units.
Our products are used in gaming, professional visualization, data centers, and automotive markets.
We continue to invest in research and development to maintain our competitive position.
Matched: Business overview and product portfolio...

[3] Source: NVDA 10-K 2025, Management Discussion, Page 45
Revenue increased 122% year-over-year driven by strong demand for our data center products.
Gross margin improved to 74.0% from 66.8% in the prior year, reflecting favorable product mix.
Matched: Financial performance highlights...

(Mock results - configure Pinecone for real retrieval)"""


def _build_filters(
    ticker: str | None = None,
    document_type: str | None = None,
    section: str | None = None,
) -> dict[str, Any] | None:
    """Build Pinecone metadata filter from optional parameters."""
    filters: dict[str, Any] = {}

    if ticker:
        filters["ticker"] = ticker.upper()
    if document_type:
        filters["document_type"] = document_type.lower()
    if section:
        # Simple string match for section
        filters["section"] = section

    return filters if filters else None


def _deduplicate_by_parent(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Deduplicate results by parent_id, keeping the highest-scoring match.

    Multiple child chunks may match from the same parent document.
    This returns unique parents, ranked by their best child match score.

    Args:
        results: List of search results with metadata containing parent_id.

    Returns:
        Deduplicated list of results, one per unique parent.
    """
    parent_best: dict[str, dict[str, Any]] = {}

    for result in results:
        metadata = result.get("metadata", {})
        parent_id = metadata.get("parent_id", result.get("id", "unknown"))
        score = result.get("score", 0.0)

        if parent_id not in parent_best or score > parent_best[parent_id]["score"]:
            parent_best[parent_id] = result

    # Sort by best score descending
    unique_parents = sorted(
        parent_best.values(),
        key=lambda x: x.get("score", 0.0),
        reverse=True,
    )

    logger.debug(
        "deduplicated_results",
        original_count=len(results),
        unique_parents=len(unique_parents),
    )

    return unique_parents


def _get_result_text(metadata: dict[str, Any], warn_missing: bool = True) -> str:
    """
    Get text content from result metadata with backwards compatibility.

    Prefers parent_text (new schema), falls back to text or child_text (old schema).

    Args:
        metadata: Result metadata dictionary.
        warn_missing: Whether to log a warning if parent_text is missing.

    Returns:
        Text content for the result.
    """
    content = (
        metadata.get("parent_text")
        or metadata.get("text")
        or metadata.get("child_text")
        or "[No content available]"
    )

    # Only warn if explicitly requested (caller controls to avoid spam)
    if warn_missing and not metadata.get("parent_text"):
        logger.warning(
            "missing_parent_text",
            document_id=metadata.get("document_id"),
            parent_id=metadata.get("parent_id"),
        )

    return content


def _safe_int(value: Any, default: Any = "?") -> int | str:
    """
    Safely convert a value to int with fallback.

    Handles floats (2025.0), strings ("2025"), and malformed values gracefully.

    Args:
        value: Value to convert (could be int, float, str, None, or malformed).
        default: Fallback value if conversion fails.

    Returns:
        Integer value or default.
    """
    if value is None:
        return default
    try:
        # Handle floats like 2025.0 and numeric strings like "2025"
        return int(float(value))
    except (ValueError, TypeError):
        return default


def _format_citation(metadata: dict[str, Any]) -> str:
    """
    Format source citation from result metadata.

    Args:
        metadata: Result metadata dictionary.

    Returns:
        Formatted citation string.
    """
    # Extract citation components
    ticker = metadata.get("ticker", "Unknown")
    doc_type = metadata.get("document_type", "document").upper()
    section = metadata.get("section", "Unknown Section")

    # Format fiscal_year and page safely (handles floats, strings, malformed)
    # Chunks use start_page/end_page from semantic_chunking.py
    fiscal_year = _safe_int(metadata.get("fiscal_year"), default=None)
    start_page = _safe_int(metadata.get("start_page"), default=None)
    end_page = _safe_int(metadata.get("end_page"), default=None)
    
    # Format page reference (show range if chunk spans multiple pages)
    if start_page is not None and end_page is not None and start_page != end_page:
        page = f"{start_page}-{end_page}"
    elif start_page is not None:
        page = str(start_page)
    else:
        page = "?"

    # Build citation based on document type
    if doc_type == "10K":
        if fiscal_year:
            return f"{ticker} 10-K {fiscal_year}, {section}, Page {page}"
        return f"{ticker} 10-K, {section}, Page {page}"
    else:
        # Reference documents
        source_name = metadata.get("source_name", ticker)
        headline = metadata.get("headline", "")
        if headline:
            return f"{source_name}: {headline}, Page {page}"
        return f"{source_name}, {section}, Page {page}"


def _format_results(results: list[dict[str, Any]], query: str) -> str:
    """
    Format search results into a readable response with citations.

    Args:
        results: List of search results after deduplication.
        query: Original search query.

    Returns:
        Formatted string response for the agent.
    """
    if not results:
        return (
            f'No relevant documents found in indexed 10-K filings for: "{query}". '
            f"The document store may not contain information about this topic or company. "
            f"Consider using web search (tavily_search) for current information from the internet."
        )

    lines = [f"Found {len(results)} relevant passage(s):\n"]

    # Track if we've warned about missing parent_text (warn only once per query)
    warned_missing_parent = False

    for i, result in enumerate(results, 1):
        metadata = result.get("metadata", {})
        score = result.get("score", 0.0)

        # Get citation and content (only warn once per query)
        citation = _format_citation(metadata)
        should_warn = not warned_missing_parent and not metadata.get("parent_text")
        content = _get_result_text(metadata, warn_missing=should_warn)
        if should_warn:
            warned_missing_parent = True

        # Get match preview from child_text_raw
        child_raw = metadata.get("child_text_raw", metadata.get("child_text", ""))
        match_preview = child_raw[:100] + "..." if len(child_raw) > 100 else child_raw

        # Format the result
        lines.append(f"[{i}] Source: {citation}")
        lines.append(f"Score: {score:.4f}")
        lines.append(content)
        if match_preview:
            lines.append(f"Matched: {match_preview}")
        lines.append("")  # Blank line between results

    return "\n".join(lines)


async def _retrieve_from_pinecone(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    filters: dict[str, Any] | None = None,
) -> str:
    """
    Retrieve documents from Pinecone using semantic search.

    Args:
        query: Search query text.
        top_k: Number of results to retrieve (before deduplication).
        filters: Optional metadata filters.

    Returns:
        Formatted string of search results.
    """
    # Import here to avoid circular imports and allow graceful fallback
    from src.utils.embeddings import EmbeddingError
    from src.utils.pinecone_client import PineconeClientError

    settings = get_settings()

    # Check if Pinecone is configured
    if not settings.pinecone_api_key:
        logger.info("rag_retrieval_mock_mode", reason="no_pinecone_api_key")
        return _build_mock_results(query)

    try:
        # Timeout covers entire pipeline (embedding + Pinecone query)
        async with asyncio.timeout(QUERY_TIMEOUT_SECONDS):
            # Get cached clients (lazy initialization)
            embeddings_client = _get_embeddings_client()
            pinecone_client = _get_pinecone_client()

            # Step 1: Embed the query
            logger.debug("rag_embedding_query", query=query[:100])
            query_vector = await embeddings_client.embed_text(query)

            # Step 2: Search Pinecone with filters
            # Request more results than top_k to account for deduplication
            search_top_k = min(top_k * 3, MAX_TOP_K * 2)

            logger.debug(
                "rag_searching_pinecone",
                query=query[:100],
                top_k=search_top_k,
                has_filters=bool(filters),
            )

            results = pinecone_client.query(
                vector=query_vector,
                top_k=search_top_k,
                filter=filters,
                include_metadata=True,
            )

        if not results:
            logger.info("rag_no_results", query=query[:100], filters=filters)
            return (
                f'No relevant documents found in indexed 10-K filings for: "{query}". '
                f"The document store may not contain information about this topic or company. "
                f"Consider using web search (tavily_search) for current information from the internet."
            )

        # Step 3: Deduplicate by parent_id
        unique_results = _deduplicate_by_parent(results)

        # Step 4: Limit to requested top_k
        final_results = unique_results[:top_k]

        logger.info(
            "rag_retrieval_completed",
            query=query[:100],
            raw_results=len(results),
            unique_parents=len(unique_results),
            returned=len(final_results),
            top_score=final_results[0].get("score", 0) if final_results else 0,
        )

        # Step 5: Format results with citations
        return _format_results(final_results, query)

    except TimeoutError as e:
        logger.error("rag_retrieval_timeout", query=query[:100], error=str(e))
        raise ValueError("Document search timed out. Please try again.") from e

    except EmbeddingError as e:
        logger.error("rag_embedding_error", query=query[:100], error=str(e))
        raise ValueError("Failed to process query. Please try again.") from e

    except PineconeClientError as e:
        logger.error("rag_pinecone_error", query=query[:100], error=str(e))
        raise ValueError("Document search is temporarily unavailable.") from e

    except Exception as e:
        logger.error("rag_retrieval_unknown_error", query=query[:100], error=str(e))
        raise ValueError("Document search failed. Please try again.") from e


@tool("rag_retrieval", args_schema=RAGQueryInput)
async def rag_retrieval(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    ticker: str | None = None,
    document_type: str | None = None,
    section: str | None = None,
) -> str:
    """
    Search document text for detailed information, context, and explanations.

    Use this tool for questions requiring QUALITATIVE information:
    - Detailed risk factor descriptions and explanations
    - Business strategy and competitive positioning narratives
    - Management discussion and analysis insights
    - Specific quotes or passages from SEC filings
    - Understanding WHY something happened or company reasoning
    - Context and background information

    DO NOT use this tool for:
    - Simple numeric lookups (revenue, margins, EPS)
    - Financial metric comparisons across companies
    - Aggregated data or counts

    Supports filtering by ticker symbol, document type, and section.
    Returns source citations (document, page, section) for each result.

    Args:
        query: The search query text describing what information you need.
        top_k: Number of results to return (default 5, max 20).
        ticker: Optional filter by company ticker (e.g., 'NVDA', 'AAPL').
        document_type: Optional filter by document type ('10k' or 'reference').
        section: Optional filter by section name.

    Returns:
        Formatted string with relevant passages and source citations.
    """
    settings = get_settings()

    # Build filters from optional parameters
    filters = _build_filters(
        ticker=ticker,
        document_type=document_type,
        section=section,
    )

    logger.info(
        "rag_retrieval_started",
        query=query[:100],
        top_k=top_k,
        ticker=ticker,
        document_type=document_type,
        section=section,
        has_filters=bool(filters),
    )

    # Check for mock mode
    if not settings.pinecone_api_key:
        logger.info("rag_retrieval_mock_mode", query=query[:100])
        return _build_mock_results(query)

    # Execute real retrieval
    return await _retrieve_from_pinecone(
        query=query,
        top_k=top_k,
        filters=filters,
    )


def get_rag_mode() -> str:
    """Return 'live' when Pinecone API key is set, else 'mock'."""
    settings = get_settings()
    return "live" if settings.pinecone_api_key else "mock"


__all__ = ["rag_retrieval", "RAGQueryInput", "get_rag_mode", "_reset_clients"]
