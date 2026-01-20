"""
Retrieval package for hybrid search orchestration.

This package provides the HybridRetriever class that orchestrates the full
hybrid retrieval pipeline combining:
- Dense vector search (Pinecone)
- BM25 sparse search (Pinecone hybrid)
- Knowledge Graph entity lookup with page-level boosting (Neo4j)
- Query expansion with LLM-based complexity analysis
- RRF fusion, reranking, and contextual compression

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
    from src.retrieval import HybridRetriever

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
    - PHASE_2B_HOW_TO_GUIDE.md Section 11
    - backend.mdc for Python patterns
"""

from __future__ import annotations

from src.retrieval.hybrid_retriever import (
    HybridRetriever,
    HybridRetrieverError,
    DenseSearchError,
    RetrievalResult,
    RetrievalResultItem,
    KGEvidence,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    # Main class
    "HybridRetriever",
    # Exceptions
    "HybridRetrieverError",
    "DenseSearchError",
    # Type definitions
    "RetrievalResult",
    "RetrievalResultItem",
    "KGEvidence",
]
