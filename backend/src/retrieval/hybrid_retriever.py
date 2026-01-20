"""
Hybrid retrieval orchestration for RAG pipeline.

This module provides the HybridRetriever class that orchestrates the full
hybrid retrieval pipeline combining:
- Dense vector search (Pinecone)
- BM25 sparse search (Pinecone hybrid)
- Knowledge Graph entity lookup with page-level boosting (Neo4j)
- Query expansion with LLM-based complexity analysis
- RRF fusion, reranking, and contextual compression

Architecture:
    Query → Query Analysis → Parallel Retrieval → RRF Fusion → KG Boost
                 ↓                    ↓               ↓           ↓
           Variants +           Dense + BM25      Merge      Page-level
           KG Complexity        per variant       scores      boost
                                     ↓
                            Parent Deduplication
                                     ↓
                            Reranking (Nova Lite)
                                     ↓
                            Compression (Nova Lite)
                                     ↓
                            Final Results + Citations

8-Step Pipeline:
    1. Query Analysis - Generate variants + determine KG complexity (Nova Lite)
    2. Parallel Retrieval - Dense + BM25 for each variant
    3. Knowledge Graph - Entity extraction + page-level document lookup
    4. RRF Fusion - Merge dense + BM25 results
    5. KG Boost - Apply boost to chunks from KG-matched pages
    6. Parent Deduplication - Keep best child per parent
    7. Reranking - Cross-encoder scoring (Nova Lite)
    8. Compression - Extract relevant sentences (Nova Lite)

Graceful Degradation:
    - Dense search: REQUIRED - raises exception if fails
    - BM25 search: Optional - continues with dense only
    - KG search: Optional - continues without entity boost
    - Query expansion: Optional - uses original query only
    - Reranking: Optional - uses RRF scores directly
    - Compression: Optional - returns full passages

Usage:
    from src.retrieval.hybrid_retriever import HybridRetriever

    retriever = HybridRetriever(
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

    result = await retriever.retrieve(
        query="What are NVIDIA's supply chain risks?",
        top_k=5,
        use_kg=True,
        compress=True,
    )

    for r in result["results"]:
        print(f"{r['id']}: relevance={r['relevance_score']}")
        if r.get("kg_evidence"):
            print(f"  KG: {r['kg_evidence']['matched_entity']}")

Reference:
    - PHASE_2B_HOW_TO_GUIDE.md Section 11.1
    - backend.mdc for Python patterns
    - rrf.py for fusion algorithm
    - reranker.py for cross-encoder reranking
    - compressor.py for contextual compression
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, TypedDict

import structlog

from src.utils.rrf import RRFResult, rrf_fusion

if TYPE_CHECKING:
    from src.ingestion.query_expansion import QueryExpander
    from src.knowledge_graph.extractor import EntityExtractor
    from src.knowledge_graph.queries import GraphQueries
    from src.knowledge_graph.store import Neo4jStore
    from src.utils.bm25_encoder import BM25Encoder
    from src.utils.compressor import ContextualCompressor
    from src.utils.embeddings import BedrockEmbeddings
    from src.utils.pinecone_client import PineconeClient
    from src.utils.reranker import CrossEncoderReranker

# Configure structured logger
logger = structlog.get_logger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Pipeline parameters (from PHASE_2B_HOW_TO_GUIDE.md)
DEFAULT_DENSE_TOP_K = 15  # Per variant
DEFAULT_BM25_TOP_K = 15  # Per variant
DEFAULT_RRF_K = 60  # Standard RRF constant
DEFAULT_RERANK_CANDIDATES = 15  # Top results to rerank
DEFAULT_FINAL_TOP_K = 5  # Final results to return
DEFAULT_KG_BOOST = 0.1  # Additive boost for KG-matched pages

# Rate limiting
MAX_CONCURRENT_SEARCHES = 5  # Max parallel search operations


# =============================================================================
# Type Definitions
# =============================================================================


class KGEvidence(TypedDict, total=False):
    """Knowledge Graph evidence for explainability."""

    matched_entity: str
    entity_type: str
    match_type: str  # "direct_mention" or "related_via"
    pages: list[int]
    related_to: str  # Only for indirect matches
    shared_docs: int  # Only for indirect matches


class RetrievalResultItem(TypedDict, total=False):
    """Single result item from hybrid retrieval."""

    id: str
    parent_id: str
    parent_text: str
    child_text_raw: str
    compressed_text: str
    relevance_score: float
    rrf_score: float
    sources: list[str]
    kg_evidence: KGEvidence
    metadata: dict[str, Any]
    _compression_skipped: bool  # Internal flag for out-of-scope detection


class RetrievalResult(TypedDict):
    """Result from hybrid retrieval pipeline."""

    results: list[RetrievalResultItem]
    retrieval_sources: list[str]
    failed_sources: list[str]


# =============================================================================
# Custom Exceptions
# =============================================================================


class HybridRetrieverError(Exception):
    """Base exception for hybrid retrieval operations."""

    pass


class DenseSearchError(HybridRetrieverError):
    """Error during dense vector search (REQUIRED component)."""

    pass


# =============================================================================
# HybridRetriever Class
# =============================================================================


class HybridRetriever:
    """
    Orchestrates the full hybrid retrieval pipeline.

    Combines dense search, BM25, Knowledge Graph, RRF fusion, reranking,
    and compression with graceful degradation for optional components.

    Attributes:
        pinecone_client: Pinecone client for vector search.
        neo4j_store: Neo4j store for Knowledge Graph.
        entity_extractor: Entity extractor for query analysis.
        graph_queries: Graph query interface for KG lookups.
        embeddings: Bedrock embeddings for query vectorization.
        bm25_encoder: BM25 encoder for sparse vectors.
        query_expander: Query expander for variants and complexity.
        reranker: Cross-encoder reranker for relevance scoring.
        compressor: Contextual compressor for sentence extraction.

    Example:
        retriever = HybridRetriever(
            pinecone_client=pinecone_client,
            neo4j_store=neo4j_store,
            # ... other dependencies
        )

        result = await retriever.retrieve(
            query="What are NVIDIA's supply chain risks?",
            top_k=5,
        )
    """

    def __init__(
        self,
        pinecone_client: "PineconeClient",
        neo4j_store: "Neo4jStore",
        entity_extractor: "EntityExtractor",
        graph_queries: "GraphQueries",
        embeddings: "BedrockEmbeddings",
        bm25_encoder: "BM25Encoder",
        query_expander: "QueryExpander",
        reranker: "CrossEncoderReranker",
        compressor: "ContextualCompressor",
    ) -> None:
        """
        Initialize the HybridRetriever with all dependencies.

        Args:
            pinecone_client: Pinecone client for dense and hybrid queries.
            neo4j_store: Neo4j store for Knowledge Graph access.
            entity_extractor: Entity extractor for query entity extraction.
            graph_queries: Graph queries for KG traversals.
            embeddings: Bedrock embeddings for query vectorization.
            bm25_encoder: BM25 encoder for sparse vector encoding.
            query_expander: Query expander for variants and complexity analysis.
            reranker: Cross-encoder reranker for LLM-based relevance scoring.
            compressor: Contextual compressor for sentence extraction.
        """
        self._pinecone = pinecone_client
        self._neo4j = neo4j_store
        self._extractor = entity_extractor
        self._queries = graph_queries
        self._embeddings = embeddings
        self._bm25 = bm25_encoder
        self._expander = query_expander
        self._reranker = reranker
        self._compressor = compressor

        self._log = logger.bind(component="hybrid_retriever")
        self._log.info("hybrid_retriever_initialized")

    # =========================================================================
    # Main Retrieval Method
    # =========================================================================

    async def retrieve(
        self,
        query: str,
        top_k: int = DEFAULT_FINAL_TOP_K,
        use_kg: bool = True,
        compress: bool = True,
        rerank: bool = True,
        metadata_filter: dict[str, Any] | None = None,
    ) -> RetrievalResult:
        """
        Execute the full hybrid retrieval pipeline.

        8-step pipeline:
        1. Query Analysis - Generate variants + determine KG complexity
        2. Parallel Retrieval - Dense + BM25 for each variant
        3. Knowledge Graph - Entity extraction + page-level document lookup
        4. RRF Fusion - Merge dense + BM25 results
        5. KG Boost - Apply boost to chunks from KG-matched pages
        6. Parent Deduplication - Keep best child per parent
        7. Reranking - Cross-encoder scoring (optional)
        8. Compression - Extract relevant sentences (optional)

        Args:
            query: The user's search query.
            top_k: Number of final results to return. Defaults to 5.
            use_kg: Whether to use Knowledge Graph for boosting. Defaults to True.
            compress: Whether to compress results. Defaults to True.
            rerank: Whether to rerank results. Defaults to True.
            metadata_filter: Optional Pinecone metadata filter.

        Returns:
            RetrievalResult with results, successful sources, and failed sources.

        Raises:
            DenseSearchError: If dense search fails (required component).
            HybridRetrieverError: If critical pipeline error occurs.

        Example:
            result = await retriever.retrieve(
                query="What are NVIDIA's supply chain risks?",
                top_k=5,
                use_kg=True,
                compress=True,
            )
        """
        self._log.info(
            "retrieval_started",
            query=query[:100],
            top_k=top_k,
            use_kg=use_kg,
            compress=compress,
            rerank=rerank,
        )

        retrieval_sources: list[str] = []
        failed_sources: list[str] = []

        # =====================================================================
        # Step 1: Query Analysis (optional - degrades to original query)
        # =====================================================================
        try:
            analysis = await self._expander.analyze(query)
            variants = analysis.variants
            use_2hop = analysis.use_2hop
            self._log.debug(
                "query_analyzed",
                variant_count=len(variants),
                kg_complexity=analysis.kg_complexity,
                use_2hop=use_2hop,
            )
        except Exception as e:
            self._log.warning("query_expansion_failed", error=str(e))
            variants = (query,)
            use_2hop = False
            failed_sources.append("query_expansion")

        # =====================================================================
        # Step 2: Parallel Dense + BM25 Retrieval
        # =====================================================================
        dense_results: list[dict[str, Any]] = []
        bm25_results: list[dict[str, Any]] = []

        # Dense search (REQUIRED)
        try:
            dense_results = await self._parallel_dense_search(
                variants, DEFAULT_DENSE_TOP_K, metadata_filter
            )
            retrieval_sources.append("dense")
            self._log.debug("dense_search_complete", result_count=len(dense_results))
        except Exception as e:
            self._log.error("dense_search_failed", error=str(e))
            raise DenseSearchError(f"Dense search failed: {e}") from e

        # BM25 search (optional)
        try:
            bm25_results = await self._parallel_bm25_search(
                variants, DEFAULT_BM25_TOP_K, metadata_filter
            )
            retrieval_sources.append("bm25")
            self._log.debug("bm25_search_complete", result_count=len(bm25_results))
        except Exception as e:
            self._log.warning("bm25_search_failed", error=str(e))
            failed_sources.append("bm25")

        # =====================================================================
        # Step 3: Knowledge Graph Search (optional)
        # =====================================================================
        kg_results: list[dict[str, Any]] = []
        if use_kg:
            try:
                kg_results = self._kg_search(query, use_2hop=use_2hop)
                if kg_results:
                    retrieval_sources.append("kg")
                self._log.debug("kg_search_complete", result_count=len(kg_results))
            except Exception as e:
                self._log.warning("kg_search_failed", error=str(e))
                failed_sources.append("kg")

        # =====================================================================
        # Step 4: RRF Fusion (dense + BM25)
        # =====================================================================
        result_lists = [dense_results]
        source_labels = ["dense"]

        if bm25_results:
            result_lists.append(bm25_results)
            source_labels.append("bm25")

        fused_results = rrf_fusion(
            result_lists,
            k=DEFAULT_RRF_K,
            source_labels=source_labels,
        )

        self._log.debug(
            "rrf_fusion_complete",
            input_lists=len(result_lists),
            fused_count=len(fused_results),
        )

        # =====================================================================
        # Step 5: KG Boost (page-level precision)
        # =====================================================================
        # Convert RRFResult TypedDict to plain dict for downstream processing
        fused_as_dicts: list[dict[str, Any]] = [dict(r) for r in fused_results]
        if kg_results:
            fused_as_dicts = self._apply_kg_boost(
                fused_as_dicts, kg_results, boost=DEFAULT_KG_BOOST
            )

        # =====================================================================
        # Step 6: Parent Deduplication
        # =====================================================================
        deduplicated = self._deduplicate_by_parent(fused_as_dicts)
        self._log.debug(
            "deduplication_complete",
            before=len(fused_results),
            after=len(deduplicated),
        )

        # =====================================================================
        # Step 7: Reranking (optional)
        # =====================================================================
        candidates = deduplicated[:DEFAULT_RERANK_CANDIDATES]

        if rerank:
            try:
                reranked = await self._reranker.rerank(
                    query=query,
                    results=candidates,
                    top_k=top_k,
                )
                retrieval_sources.append("reranker")
                self._log.debug("reranking_complete", result_count=len(reranked))
            except Exception as e:
                self._log.warning("reranking_failed", error=str(e))
                failed_sources.append("reranker")
                # Fallback: use RRF-sorted results
                reranked = candidates[:top_k]
        else:
            reranked = candidates[:top_k]

        # =====================================================================
        # Step 8: Compression (optional)
        # =====================================================================
        if compress:
            try:
                compressed = await self._compressor.compress_results(
                    query=query,
                    results=reranked,
                )
                retrieval_sources.append("compressor")
                self._log.debug("compression_complete", result_count=len(compressed))
                final_results = compressed
            except Exception as e:
                self._log.warning("compression_failed", error=str(e))
                failed_sources.append("compressor")
                final_results = reranked
        else:
            final_results = reranked

        # =====================================================================
        # Format Output
        # =====================================================================
        formatted_results = self._format_results(final_results)

        self._log.info(
            "retrieval_complete",
            query=query[:50],
            result_count=len(formatted_results),
            sources=retrieval_sources,
            failed=failed_sources,
        )

        return RetrievalResult(
            results=formatted_results,
            retrieval_sources=retrieval_sources,
            failed_sources=failed_sources,
        )

    # =========================================================================
    # Dense Search
    # =========================================================================

    async def _parallel_dense_search(
        self,
        variants: tuple[str, ...],
        top_k: int,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Execute dense search for all query variants in parallel.

        Args:
            variants: Tuple of query variants to search.
            top_k: Number of results per variant.
            metadata_filter: Optional Pinecone metadata filter.

        Returns:
            Combined list of results from all variants.
        """
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_SEARCHES)

        async def search_variant(variant: str) -> list[dict[str, Any]]:
            async with semaphore:
                return await self._dense_search(variant, top_k, metadata_filter)

        # Execute all searches in parallel
        results_per_variant = await asyncio.gather(
            *[search_variant(v) for v in variants],
            return_exceptions=True,
        )

        # Combine results, handling any exceptions
        combined: list[dict[str, Any]] = []
        for i, variant_result in enumerate(results_per_variant):
            if isinstance(variant_result, BaseException):
                self._log.warning(
                    "variant_dense_search_failed",
                    variant_index=i,
                    error=str(variant_result),
                )
                continue
            # variant_result is list[dict[str, Any]] after BaseException check
            combined.extend(variant_result)

        # Deduplicate by ID (same chunk from multiple variants)
        seen_ids: set[str] = set()
        deduplicated: list[dict[str, Any]] = []
        for item in combined:
            result_id = item.get("id")
            if result_id and result_id not in seen_ids:
                seen_ids.add(result_id)
                deduplicated.append(item)

        return deduplicated

    async def _dense_search(
        self,
        query: str,
        top_k: int,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Execute dense vector search for a single query.

        Args:
            query: The search query.
            top_k: Number of results to return.
            metadata_filter: Optional Pinecone metadata filter.

        Returns:
            List of search results with id, score, and metadata.
        """
        # Embed the query
        query_vector = await self._embeddings.embed_text(query)

        # Search Pinecone
        results = self._pinecone.query(
            vector=query_vector,
            top_k=top_k,
            filter=metadata_filter,
            include_metadata=True,
        )

        return results

    # =========================================================================
    # BM25 Search
    # =========================================================================

    async def _parallel_bm25_search(
        self,
        variants: tuple[str, ...],
        top_k: int,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Execute BM25 sparse search for all query variants in parallel.

        Args:
            variants: Tuple of query variants to search.
            top_k: Number of results per variant.
            metadata_filter: Optional Pinecone metadata filter.

        Returns:
            Combined list of results from all variants.
        """
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_SEARCHES)

        async def search_variant(variant: str) -> list[dict[str, Any]]:
            async with semaphore:
                return await self._bm25_search(variant, top_k, metadata_filter)

        # Execute all searches in parallel
        results_per_variant = await asyncio.gather(
            *[search_variant(v) for v in variants],
            return_exceptions=True,
        )

        # Combine results, handling any exceptions
        combined: list[dict[str, Any]] = []
        for i, variant_result in enumerate(results_per_variant):
            if isinstance(variant_result, BaseException):
                self._log.warning(
                    "variant_bm25_search_failed",
                    variant_index=i,
                    error=str(variant_result),
                )
                continue
            # variant_result is list[dict[str, Any]] after BaseException check
            combined.extend(variant_result)

        # Deduplicate by ID
        seen_ids: set[str] = set()
        deduplicated: list[dict[str, Any]] = []
        for item in combined:
            result_id = item.get("id")
            if result_id and result_id not in seen_ids:
                seen_ids.add(result_id)
                deduplicated.append(item)

        return deduplicated

    async def _bm25_search(
        self,
        query: str,
        top_k: int,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Execute BM25 sparse vector search for a single query.

        Args:
            query: The search query.
            top_k: Number of results to return.
            metadata_filter: Optional Pinecone metadata filter.

        Returns:
            List of search results with id, score, and metadata.
        """
        # Embed the query (dense vector still needed for hybrid search)
        query_vector = await self._embeddings.embed_text(query)

        # Encode sparse vector
        sparse_vector = self._bm25.encode(query)

        # Search Pinecone with hybrid (dense + sparse)
        # Cast SparseVector TypedDict to dict for Pinecone API
        sparse_dict: dict[str, list[Any]] = dict(sparse_vector)  # type: ignore[arg-type]
        results = self._pinecone.query(
            vector=query_vector,
            sparse_vector=sparse_dict,
            top_k=top_k,
            filter=metadata_filter,
            include_metadata=True,
        )

        return results

    # =========================================================================
    # Knowledge Graph Search
    # =========================================================================

    def _kg_search(self, query: str, use_2hop: bool = False) -> list[dict[str, Any]]:
        """
        Extract entities from query and find related documents WITH page-level context.

        Returns document IDs plus entity evidence including specific pages for
        precise boosting.

        Note: This method is in HybridRetriever, NOT GraphQueries. It wraps
        GraphQueries.find_document_pages_mentioning() and adds entity evidence.

        Page-Level Boosting:
            Uses find_document_pages_mentioning() to get specific pages where
            entities appear. This enables _apply_kg_boost() to only boost chunks
            from those pages, not the entire document.

        Args:
            query: The user's search query.
            use_2hop: Whether to use 2-hop traversal (from QueryAnalysis.use_2hop).
                True = complex query, use 2-hop for indirect relationships.
                False = simple query, 1-hop only for direct matches.

        Returns:
            list[dict]: Each dict contains:
                - id: Document ID
                - source: "kg"
                - kg_evidence: {
                    matched_entity: str,
                    entity_type: str,
                    match_type: "direct_mention" | "related_via",
                    pages: list[int],
                    related_to: str (if match_type == "related_via"),
                    shared_docs: int (if indirect match)
                  }
        """
        entities = self._extractor.extract_entities(query, "query", 0)

        # Track documents with accumulated pages (merges pages from multiple entities)
        # Structure: {doc_id: {"evidence": {...}, "pages": set(...)}}
        doc_results: dict[str, dict[str, Any]] = {}

        for entity in entities:
            # 1-hop: Direct document mentions with page info (always executed)
            try:
                # Use page-level query for precise boosting
                doc_pages = self._queries.find_document_pages_mentioning(
                    entity.text, fuzzy=True
                )

                for doc_info in doc_pages:
                    doc_id = doc_info["document_id"]
                    pages = doc_info["pages"]

                    if doc_id not in doc_results:
                        # First time seeing this document
                        doc_results[doc_id] = {
                            "evidence": {
                                "matched_entity": entity.text,
                                "entity_type": entity.entity_type.value,
                                "match_type": "direct_mention",
                            },
                            "pages": set(pages),
                        }
                    else:
                        # Document already seen - merge pages from additional entity matches
                        doc_results[doc_id]["pages"].update(pages)
            except Exception as e:
                self._log.warning("kg_1hop_failed", entity=entity.text, error=str(e))
                # Continue with other entities - don't fail entire KG search

            # 2-hop: Related entities (only for complex queries as determined by LLM)
            # Wrapped in separate try/except so 1-hop results are preserved if 2-hop fails
            if use_2hop:
                try:
                    related = self._queries.find_related_entities(
                        entity.text, hops=1, limit=5
                    )
                    for rel in related:
                        # Use page-level query for related entities too
                        rel_doc_pages = self._queries.find_document_pages_mentioning(
                            rel["entity"], fuzzy=True
                        )
                        for doc_info in rel_doc_pages:
                            doc_id = doc_info["document_id"]
                            pages = doc_info["pages"]

                            if doc_id not in doc_results:
                                doc_results[doc_id] = {
                                    "evidence": {
                                        "matched_entity": rel["entity"],
                                        "entity_type": rel["type"],
                                        "match_type": "related_via",
                                        "related_to": entity.text,
                                        "shared_docs": rel["shared_docs"],
                                    },
                                    "pages": set(pages),
                                }
                            else:
                                # Merge pages (keep original evidence - first match wins)
                                doc_results[doc_id]["pages"].update(pages)
                except Exception as e:
                    self._log.warning(
                        "kg_2hop_failed", entity=entity.text, error=str(e)
                    )
                    # 2-hop failure is non-critical - 1-hop results still valid

        # Convert to final results format with pages as list
        kg_result_list: list[dict[str, Any]] = [
            {
                "id": doc_id,
                "source": "kg",
                "kg_evidence": {
                    **info["evidence"],
                    "pages": sorted(info["pages"]),  # Convert set to sorted list
                },
            }
            for doc_id, info in doc_results.items()
        ]

        self._log.debug(
            "kg_search_complete",
            query_entities=len(entities),
            docs_found=len(kg_result_list),
            total_pages=sum(
                len(r["kg_evidence"].get("pages", [])) for r in kg_result_list
            ),
            direct_matches=sum(
                1
                for r in kg_result_list
                if r["kg_evidence"]["match_type"] == "direct_mention"
            ),
            indirect_matches=sum(
                1
                for r in kg_result_list
                if r["kg_evidence"]["match_type"] == "related_via"
            ),
        )

        return kg_result_list

    # =========================================================================
    # KG Boost
    # =========================================================================

    def _apply_kg_boost(
        self,
        chunk_results: list[dict[str, Any]],
        kg_results: list[dict[str, Any]],
        boost: float = DEFAULT_KG_BOOST,
    ) -> list[dict[str, Any]]:
        """
        Apply boost to chunks from KG-matched pages (page-level precision).

        Page-Level Boosting:
            Unlike document-level boosting (which would boost ALL chunks from a
            100-page 10-K), this method only boosts chunks from specific pages
            where entities were mentioned.

        Flow:
            - KG returns document IDs + page numbers where entity appears
            - Dense/BM25 return chunks with start_page/end_page in metadata
            - This method boosts chunks whose start_page is in the KG pages list

        Args:
            chunk_results: Results from RRF fusion (dense + BM25).
            kg_results: Results from _kg_search with kg_evidence containing 'pages'.
            boost: Additive boost to RRF score (default 0.1).
                RRF scores typically range 0.01-0.05, so +0.1 is significant.

        Returns:
            chunk_results with boosted scores and kg_evidence attached
            (only for matching pages).
        """
        # Build lookup of KG evidence by (document_id, page) for page-level matching
        # Structure: {doc_id: {"pages": set(...), "evidence": {...}}}
        kg_pages_by_doc: dict[str, dict[str, Any]] = {}
        for kg_result in kg_results:
            doc_id = kg_result["id"]
            evidence = kg_result.get("kg_evidence", {})
            pages = evidence.get("pages", [])

            if doc_id not in kg_pages_by_doc:
                kg_pages_by_doc[doc_id] = {
                    "pages": set(pages),
                    "evidence": evidence,
                }
            else:
                # Merge pages if multiple entities mention same document
                kg_pages_by_doc[doc_id]["pages"].update(pages)

        boosted_count = 0
        doc_level_fallback_count = 0

        # Apply boost to chunks - page-level when possible, doc-level fallback for news/articles
        for result in chunk_results:
            metadata = result.get("metadata", {})
            doc_id = metadata.get("document_id")
            # Chunks use start_page/end_page (from semantic_chunking.py), not page_number
            start_page = metadata.get("start_page")

            if not doc_id or doc_id not in kg_pages_by_doc:
                continue

            kg_info = kg_pages_by_doc[doc_id]
            kg_pages = kg_info["pages"]
            should_boost = False

            # Strategy: Page-level when available, document-level fallback otherwise
            # This handles both 10-Ks (multi-page PDFs) and news articles (no pages)
            if kg_pages and start_page is not None:
                # Page-level match: both KG and chunk have page info
                # Check if chunk's start_page is in the KG pages set
                if start_page in kg_pages:
                    should_boost = True
            elif not kg_pages or start_page is None:
                # Document-level fallback: either KG or chunk lacks page info
                # This handles news articles, single-page docs, legacy data
                should_boost = True
                doc_level_fallback_count += 1

            if should_boost:
                # Boost the RRF score
                result["rrf_score"] = result.get("rrf_score", 0) + boost
                boosted_count += 1

                # Attach KG evidence for LLM explainability
                result["kg_evidence"] = kg_info["evidence"]

                # Track that KG contributed to this result
                if "sources" in result:
                    if "kg_boost" not in result["sources"]:
                        result["sources"].append("kg_boost")
                else:
                    result["sources"] = ["kg_boost"]

        # Re-sort by boosted score
        boosted_results = sorted(
            chunk_results, key=lambda x: x.get("rrf_score", 0), reverse=True
        )

        self._log.debug(
            "kg_boost_applied",
            total_chunks=len(chunk_results),
            boosted_chunks=boosted_count,
            page_level_boosts=boosted_count - doc_level_fallback_count,
            doc_level_fallbacks=doc_level_fallback_count,
            boost_value=boost,
            matching_docs=len(kg_pages_by_doc),
        )

        return boosted_results

    # =========================================================================
    # Parent Deduplication
    # =========================================================================

    def _deduplicate_by_parent(
        self, results: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Keep only the highest-scoring child per parent.

        This prevents duplicate parent context in final results when multiple
        child chunks from the same parent rank highly after RRF fusion.

        Args:
            results: Results from RRF fusion (potentially with multiple
                children from the same parent).

        Returns:
            Deduplicated list with one result per unique parent, sorted by
            RRF score descending.
        """
        parent_best: dict[str, dict[str, Any]] = {}

        for result in results:
            metadata = result.get("metadata", {})
            parent_id = metadata.get("parent_id", result.get("id", "unknown"))
            score = result.get("rrf_score", 0.0)

            if parent_id not in parent_best or score > parent_best[parent_id].get(
                "rrf_score", 0
            ):
                parent_best[parent_id] = result

        # Sort by RRF score descending
        return sorted(
            parent_best.values(), key=lambda x: x.get("rrf_score", 0), reverse=True
        )

    # =========================================================================
    # Result Formatting
    # =========================================================================

    def _format_results(
        self, results: list[dict[str, Any]]
    ) -> list[RetrievalResultItem]:
        """
        Format results into the standard output format.

        Extracts and normalizes fields from various pipeline stages into the
        RetrievalResultItem format for consistent downstream consumption.

        Args:
            results: Results from the final pipeline stage (reranking or compression).

        Returns:
            List of formatted RetrievalResultItem dicts.
        """
        formatted: list[RetrievalResultItem] = []

        for result in results:
            metadata = result.get("metadata", {})

            item: RetrievalResultItem = {
                "id": result.get("id", ""),
                "parent_id": metadata.get("parent_id", result.get("id", "")),
                "parent_text": (
                    result.get("parent_text")
                    or metadata.get("parent_text")
                    or metadata.get("text")
                    or ""
                ),
                "child_text_raw": (
                    metadata.get("child_text_raw") or metadata.get("child_text") or ""
                ),
                "relevance_score": result.get("relevance_score", 0.0),
                "rrf_score": result.get("rrf_score", 0.0),
                "sources": result.get("sources", []),
                "metadata": metadata,
            }

            # Add compressed_text if available
            if "compressed_text" in result:
                item["compressed_text"] = result["compressed_text"]

            # Add kg_evidence if available
            if "kg_evidence" in result:
                item["kg_evidence"] = result["kg_evidence"]

            # Preserve compression skip flag for out-of-scope detection
            if result.get("_compression_skipped"):
                item["_compression_skipped"] = True

            formatted.append(item)

        return formatted


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    "HybridRetriever",
    "HybridRetrieverError",
    "DenseSearchError",
    "RetrievalResult",
    "RetrievalResultItem",
    "KGEvidence",
]
