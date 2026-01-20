"""
RAG retrieval tool for semantic search over indexed documents.

Phase 2b enhanced:
- Hybrid retrieval: Dense + BM25 + Knowledge Graph integration
- RRF fusion for combining multiple retrieval signals
- Cross-encoder reranking for precision (Nova Lite)
- Contextual compression for focused context (Nova Lite)
- Graceful degradation: Falls back to dense-only if components fail
- KG evidence in citations for explainability

Legacy support (Phase 2a):
- Dense-only retrieval via hybrid=False parameter
- Mock data fallback when Pinecone is not configured

Pipeline (hybrid=True):
    Query → Query Expansion → Parallel Dense+BM25 → RRF Fusion → KG Boost
                                                        ↓
                              Compression ← Reranking ← Parent Dedup

Reference:
    - PHASE_2B_HOW_TO_GUIDE.md Section 11.3
    - backend.mdc for Python patterns
    - agent.mdc for tool patterns
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
    from src.retrieval.hybrid_retriever import HybridRetriever
    from src.utils.embeddings import BedrockEmbeddings
    from src.utils.pinecone_client import PineconeClient

# Import Neo4j exceptions for graceful fallback handling
# These can be raised during HybridRetriever initialization if Neo4j is unavailable
from src.knowledge_graph.store import AuraDBPausedError, Neo4jConnectionError

logger = structlog.get_logger(__name__)

# Configuration
DEFAULT_TOP_K = 5
MAX_TOP_K = 20
QUERY_TIMEOUT_SECONDS = 20.0  # Covers embedding + Pinecone query with margin
HYBRID_TIMEOUT_SECONDS = 45.0  # Hybrid pipeline timeout (expansion + search + rerank)

# Module-level client cache for performance (lazy initialization)
_embeddings_client: "BedrockEmbeddings | None" = None
_pinecone_client: "PineconeClient | None" = None
_hybrid_retriever: "HybridRetriever | None" = None


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
    hybrid: bool = Field(
        default=True,
        description=(
            "Use hybrid retrieval (dense+BM25+KG, reranking). "
            "Set False for simple dense-only search (faster, less accurate)."
        ),
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
    global _embeddings_client, _pinecone_client, _hybrid_retriever
    _embeddings_client = None
    _pinecone_client = None
    _hybrid_retriever = None
    logger.debug("rag_clients_reset")


def _get_hybrid_retriever() -> "HybridRetriever":
    """
    Get or create cached HybridRetriever with all dependencies.

    Lazily initializes all required components:
    - PineconeClient for dense and hybrid search
    - Neo4jStore for Knowledge Graph
    - EntityExtractor for query entity extraction
    - GraphQueries for KG traversals
    - BedrockEmbeddings for query vectorization
    - BM25Encoder for sparse vector encoding
    - QueryExpander for query variants and complexity analysis
    - CrossEncoderReranker for relevance scoring
    - ContextualCompressor for sentence extraction

    Returns:
        HybridRetriever: Configured hybrid retriever instance.

    Raises:
        RuntimeError: If required services are not configured.
    """
    global _hybrid_retriever

    if _hybrid_retriever is not None:
        # Verify Neo4j connection is still healthy (Issue 3: stale connection handling)
        try:
            _hybrid_retriever._neo4j.verify_connectivity()
        except Exception as e:
            logger.warning(
                "hybrid_retriever_connection_stale",
                error=str(e),
                action="resetting_cache",
            )
            _hybrid_retriever = None
        else:
            return _hybrid_retriever

    # Import here to avoid circular imports and heavy runtime loads
    from src.ingestion.query_expansion import QueryExpander
    from src.knowledge_graph import EntityExtractor, GraphQueries, Neo4jStore
    from src.retrieval.hybrid_retriever import HybridRetriever
    from src.utils.bm25_encoder import BM25Encoder
    from src.utils.compressor import ContextualCompressor
    from src.utils.embeddings import BedrockEmbeddings
    from src.utils.pinecone_client import PineconeClient
    from src.utils.reranker import CrossEncoderReranker

    settings = get_settings()

    # Validate required configuration
    if not settings.pinecone_api_key:
        raise RuntimeError(
            "PINECONE_API_KEY is required for hybrid retrieval. "
            "Set hybrid=False to use dense-only search, or configure Pinecone."
        )

    # Initialize all components
    logger.debug("hybrid_retriever_initializing")

    pinecone_client = PineconeClient(
        api_key=settings.pinecone_api_key,
        index_name=settings.pinecone_index_name,
    )

    neo4j_store = Neo4jStore(
        uri=settings.neo4j_uri,
        user=settings.neo4j_user,
        password=settings.neo4j_password.get_secret_value(),
    )

    entity_extractor = EntityExtractor()
    graph_queries = GraphQueries(neo4j_store)
    embeddings = BedrockEmbeddings()
    bm25_encoder = BM25Encoder()
    query_expander = QueryExpander()
    reranker = CrossEncoderReranker()
    compressor = ContextualCompressor()

    _hybrid_retriever = HybridRetriever(
        pinecone_client=pinecone_client,
        neo4j_store=neo4j_store,
        entity_extractor=entity_extractor,
        graph_queries=graph_queries,
        embeddings=embeddings,
        bm25_encoder=bm25_encoder,
        query_expander=query_expander,
        reranker=reranker,
        compressor=compressor,
    )

    logger.info("hybrid_retriever_created", cached=True)
    return _hybrid_retriever


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


def _format_relevance_score(result: dict[str, Any]) -> str:
    """
    Format relevance score from hybrid or dense results.

    For hybrid results: Uses relevance_score (1-10 scale from reranker)
    For dense results: Uses score (0-1 similarity), scaled to 1-10

    Args:
        result: Search result dictionary.

    Returns:
        Formatted relevance string like "9/10" or "0.8542".
    """
    # Hybrid results have relevance_score (1-10 from reranker)
    relevance = result.get("relevance_score")
    if relevance is not None:
        return f"{int(relevance)}/10"

    # Dense-only results have similarity score (0-1)
    score = result.get("score", 0.0)
    if score > 0:
        # Scale to 1-10 for consistency
        scaled = min(10, max(1, int(score * 10)))
        return f"{scaled}/10"

    return "?/10"


def _format_result_with_kg(result: dict[str, Any], index: int) -> str:
    """
    Format a single result with KG evidence for explainability.

    Uses MEDIUM verbosity (entity + type + relationship):
    - Minimal: "KG Match: NVIDIA (Organization)" - too little context
    - Medium: "KG Match: NVIDIA (Organization) - direct mention" ← CHOSEN
    - Verbose: Full path trace with shared_docs - token bloat

    See KNOWLEDGE_GRAPH_UPDATE_PLAN.md Decision 2 for rationale.

    Args:
        result: Single retrieval result (from hybrid or dense search).
        index: 1-based result index for display.

    Returns:
        Formatted result string with citation, KG evidence, and content.
    """
    metadata = result.get("metadata", {})
    kg_evidence = result.get("kg_evidence", {})

    # Base citation
    citation = _format_citation(metadata)
    relevance = _format_relevance_score(result)

    lines = [f"[{index}] Source: {citation} (Relevance: {relevance})"]

    # Add KG evidence if present (explainability) - invisible to users when absent
    if kg_evidence:
        entity = kg_evidence.get("matched_entity", "")
        entity_type = kg_evidence.get("entity_type", "")
        match_type = kg_evidence.get("match_type", "")

        if entity and entity_type:
            if match_type == "direct_mention":
                lines.append(f"    KG Match: {entity} ({entity_type}) - direct mention")
            elif match_type == "related_via":
                related_to = kg_evidence.get("related_to", "")
                if related_to:
                    lines.append(
                        f"    KG Match: {entity} ({entity_type}) - related via {related_to}"
                    )
                else:
                    lines.append(f"    KG Match: {entity} ({entity_type}) - related")
            else:
                # Default case if match_type is unknown
                lines.append(f"    KG Match: {entity} ({entity_type})")

    # Add passage text (prefer compressed_text > parent_text > text)
    # HybridRetriever puts parent_text at top level; also check metadata fallback
    text = (
        result.get("compressed_text")
        or result.get("parent_text")  # Top level from HybridRetriever
        or metadata.get("parent_text")  # Fallback to metadata (dense-only mode)
        or metadata.get("text")
        or "[No content available]"
    )
    lines.append(text)

    # Add matched preview from child_text_raw
    # HybridRetriever puts child_text_raw at top level; also check metadata fallback
    child_raw = (
        result.get("child_text_raw")  # Top level from HybridRetriever
        or metadata.get("child_text_raw")  # Fallback to metadata
        or metadata.get("child_text")
        or ""
    )
    if child_raw:
        preview = child_raw[:100] + "..." if len(child_raw) > 100 else child_raw
        lines.append(f"Matched: {preview}")

    return "\n".join(lines)


def _format_results(
    results: list[dict[str, Any]],
    query: str,
    is_hybrid: bool = False,
    retrieval_sources: list[str] | None = None,
) -> str:
    """
    Format search results into a readable response with citations.

    For hybrid results: Uses _format_result_with_kg() for KG evidence display.
    For dense-only results: Uses simple score format.

    Args:
        results: List of search results after deduplication.
        query: Original search query.
        is_hybrid: Whether results came from hybrid pipeline.
        retrieval_sources: List of successful retrieval sources (hybrid only).

    Returns:
        Formatted string response for the agent.
    """
    if not results:
        return (
            f'No relevant documents found in indexed 10-K filings for: "{query}". '
            f"The document store may not contain information about this topic or company. "
            f"Consider using web search (tavily_search) for current information from the internet."
        )

    # Build header based on retrieval method
    if is_hybrid and retrieval_sources:
        source_str = "+".join(retrieval_sources)
        header = f"Found {len(results)} relevant passage(s) (hybrid: {source_str}, reranked):\n"
    elif is_hybrid:
        header = (
            f"Found {len(results)} relevant passage(s) (hybrid retrieval, reranked):\n"
        )
    else:
        header = f"Found {len(results)} relevant passage(s):\n"

    lines = [header]

    # Track if we've warned about missing parent_text (warn only once per query)
    warned_missing_parent = False

    for i, result in enumerate(results, 1):
        if is_hybrid:
            # Use KG-aware formatting for hybrid results
            lines.append(_format_result_with_kg(result, i))
            lines.append("")  # Blank line between results
        else:
            # Legacy dense-only formatting
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
            match_preview = (
                child_raw[:100] + "..." if len(child_raw) > 100 else child_raw
            )

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

        # Step 5: Format results with citations (dense-only mode)
        return _format_results(final_results, query, is_hybrid=False)

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


async def _retrieve_hybrid(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    filters: dict[str, Any] | None = None,
) -> str:
    """
    Retrieve documents using HybridRetriever with full pipeline.

    8-step hybrid pipeline:
    1. Query Analysis - Generate variants + determine KG complexity
    2. Parallel Retrieval - Dense + BM25 for each variant
    3. Knowledge Graph - Entity extraction + page-level document lookup
    4. RRF Fusion - Merge dense + BM25 results
    5. KG Boost - Apply boost to chunks from KG-matched pages
    6. Parent Deduplication - Keep best child per parent
    7. Reranking - Cross-encoder scoring (Nova Lite)
    8. Compression - Extract relevant sentences (Nova Lite)

    Args:
        query: Search query text.
        top_k: Number of final results to return.
        filters: Optional metadata filters for Pinecone.

    Returns:
        Formatted string of search results with KG evidence.

    Raises:
        ValueError: If hybrid retrieval fails with user-friendly message.
    """
    from src.retrieval.hybrid_retriever import DenseSearchError, HybridRetrieverError

    settings = get_settings()

    # Check if Pinecone is configured (required for hybrid)
    if not settings.pinecone_api_key:
        logger.info("hybrid_retrieval_unavailable", reason="no_pinecone_api_key")
        return _build_mock_results(query)

    try:
        async with asyncio.timeout(HYBRID_TIMEOUT_SECONDS):
            # Get cached HybridRetriever
            retriever = _get_hybrid_retriever()

            logger.debug(
                "hybrid_retrieval_starting",
                query=query[:100],
                top_k=top_k,
                has_filters=bool(filters),
            )

            # Execute hybrid pipeline
            # Request more candidates for parent deduplication (3x)
            # HybridRetriever internally handles deduplication
            result = await retriever.retrieve(
                query=query,
                top_k=top_k * 3,  # Request more for deduplication margin
                use_kg=True,
                compress=True,
                rerank=True,
                metadata_filter=filters,
            )

        # Extract results from TypedDict
        results = result.get("results", [])
        retrieval_sources = result.get("retrieval_sources", [])
        failed_sources = result.get("failed_sources", [])

        if not results:
            logger.info(
                "hybrid_retrieval_no_results", query=query[:100], filters=filters
            )
            return (
                f'No relevant documents found in indexed 10-K filings for: "{query}". '
                f"The document store may not contain information about this topic or company. "
                f"Consider using web search (tavily_search) for current information from the internet."
            )

        # Limit to requested top_k (results already deduplicated and reranked)
        final_results = results[:top_k]

        # Check for "out of scope" queries: low relevance + all compression skipped
        # This detects when the query is about something not in our document store
        top_relevance = final_results[0].get("relevance_score", 0) if final_results else 0
        all_compression_skipped = all(
            r.get("_compression_skipped", False) for r in final_results
        )

        # Threshold: if top score < 3/10 AND compressor found nothing relevant
        MIN_RELEVANCE_THRESHOLD = 3
        if top_relevance < MIN_RELEVANCE_THRESHOLD and all_compression_skipped:
            logger.info(
                "hybrid_retrieval_out_of_scope",
                query=query[:100],
                top_relevance=top_relevance,
                all_compression_skipped=True,
                hint="Query appears to be outside indexed document scope",
            )
            return (
                f'No relevant documents found in indexed 10-K filings for: "{query}". '
                f"The document store contains SEC 10-K filings for tech companies "
                f"(NVIDIA, AMD, Apple, etc.) but may not have information about this topic. "
                f"Consider using web search (tavily_search) for current information from the internet."
            )

        logger.info(
            "hybrid_retrieval_completed",
            query=query[:100],
            total_results=len(results),
            returned=len(final_results),
            sources=retrieval_sources,
            failed=failed_sources,
            top_relevance=top_relevance,
        )

        # Format with KG evidence and sources
        return _format_results(
            final_results,
            query,
            is_hybrid=True,
            retrieval_sources=retrieval_sources,
        )

    except TimeoutError as e:
        logger.error("hybrid_retrieval_timeout", query=query[:100], error=str(e))
        raise ValueError(
            "Document search timed out. Try a simpler query or use hybrid=False."
        ) from e

    except DenseSearchError as e:
        # Dense search is required - surface error clearly
        logger.error("hybrid_dense_search_failed", query=query[:100], error=str(e))
        raise ValueError("Document search failed. Please try again.") from e

    except HybridRetrieverError as e:
        logger.error("hybrid_retriever_error", query=query[:100], error=str(e))
        raise ValueError(
            "Hybrid retrieval failed. Try hybrid=False for basic search."
        ) from e

    except RuntimeError as e:
        # Configuration errors (e.g., missing Pinecone key)
        logger.error("hybrid_config_error", query=query[:100], error=str(e))
        raise ValueError(str(e)) from e

    except Exception as e:
        logger.error("hybrid_retrieval_unknown_error", query=query[:100], error=str(e))
        raise ValueError("Document search failed. Please try again.") from e


@tool("rag_retrieval", args_schema=RAGQueryInput)
async def rag_retrieval(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    hybrid: bool = True,
    ticker: str | None = None,
    document_type: str | None = None,
    section: str | None = None,
) -> str:
    """
    Search 10-K document text for information.

    Use for:
    - Risk factors and challenges
    - Business descriptions and strategy
    - Qualitative questions about company operations
    - Context around numbers from SQL queries
    - Understanding WHY something happened or company reasoning
    - Specific quotes or passages from SEC filings

    DO NOT use this tool for:
    - Simple numeric lookups (revenue, margins, EPS) - use sql_query instead
    - Financial metric comparisons across companies - use sql_query instead
    - Aggregated data or counts - use sql_query instead

    Supports hybrid retrieval (default) combining:
    - Dense vector search for semantic similarity
    - BM25 sparse search for keyword matching
    - Knowledge Graph for entity relationships
    - Cross-encoder reranking for precision

    Set hybrid=False for faster, simpler dense-only search when:
    - Query is simple and specific
    - Speed is more important than precision
    - KG/reranking components are unavailable

    Supports filtering by ticker symbol, document type, and section.
    Returns source citations with relevance scores and KG evidence when available.

    Args:
        query: The search query text describing what information you need.
        top_k: Number of results to return (default 5, max 20).
        hybrid: Use hybrid retrieval (default True). False for dense-only.
        ticker: Optional filter by company ticker (e.g., 'NVDA', 'AAPL').
        document_type: Optional filter by document type ('10k' or 'reference').
        section: Optional filter by section name.

    Returns:
        Formatted string with relevant passages, citations, and KG evidence.
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
        hybrid=hybrid,
        ticker=ticker,
        document_type=document_type,
        section=section,
        has_filters=bool(filters),
    )

    # Check for mock mode (no Pinecone configured)
    if not settings.pinecone_api_key:
        logger.info("rag_retrieval_mock_mode", query=query[:100])
        return _build_mock_results(query)

    # Route to appropriate retrieval method
    if hybrid:
        try:
            return await _retrieve_hybrid(
                query=query,
                top_k=top_k,
                filters=filters,
            )
        except (
            RuntimeError,
            ValueError,
            Neo4jConnectionError,
            AuraDBPausedError,
        ) as e:
            # Fall back to dense-only if hybrid initialization/execution fails
            # Issue 1: Now catches Neo4j connection errors (AuraDB pause, network issues)
            # Issue 5: Log includes fallback reason for debugging visibility
            fallback_reason = type(e).__name__
            logger.warning(
                "hybrid_fallback_to_dense",
                query=query[:100],
                error=str(e),
                fallback_reason=fallback_reason,
            )
            # Get dense-only results and prepend fallback notice
            dense_result = await _retrieve_from_pinecone(
                query=query,
                top_k=top_k,
                filters=filters,
            )
            # Issue 5: Add visibility notice to response when falling back
            fallback_notice = f"[Note: Using dense-only search. Hybrid features unavailable: {fallback_reason}]\n\n"
            return fallback_notice + dense_result
    else:
        # Dense-only mode (Phase 2a behavior)
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
