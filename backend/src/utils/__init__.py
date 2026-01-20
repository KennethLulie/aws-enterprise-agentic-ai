"""
Utility helpers and shared functions for the backend.

This package provides common utilities used across the backend:

- embeddings: Bedrock Titan embeddings for text vectorization in RAG pipelines
- pinecone_client: Pinecone vector store client for RAG operations
- bm25_encoder: BM25 sparse vector encoder for Pinecone hybrid search
- rrf: Reciprocal Rank Fusion for merging dense + BM25 search results
- reranker: Cross-encoder reranking using Nova Lite for relevance scoring
- compressor: Contextual compression using Nova Lite to extract relevant sentences

Usage:
    from src.utils.embeddings import BedrockEmbeddings
    from src.utils.pinecone_client import PineconeClient
    from src.utils.bm25_encoder import BM25Encoder
    from src.utils.rrf import rrf_fusion

    # Generate embeddings
    embeddings = BedrockEmbeddings()
    vector = await embeddings.embed_text("What is NVIDIA's revenue?")

    # Generate sparse vectors for hybrid search
    bm25 = BM25Encoder()
    sparse = bm25.encode("What is NVIDIA's revenue?")

    # Store/query vectors in Pinecone
    client = PineconeClient()
    dense_results = client.query(vector, top_k=15)
    hybrid_results = client.query(vector, sparse_vector=sparse, top_k=15)

    # Fuse results with RRF
    fused = rrf_fusion([dense_results, hybrid_results])
"""

from src.utils.embeddings import (
    BedrockEmbeddings,
    EmbeddingError,
    EmbeddingModelError,
    EmbeddingInputError,
)

from src.utils.pinecone_client import (
    PineconeClient,
    PineconeClientError,
    PineconeConnectionError,
    PineconeValidationError,
    PineconeUpsertError,
    PineconeQueryError,
    PineconeDeleteError,
)

from src.utils.bm25_encoder import (
    BM25Encoder,
    BM25EncoderError,
)

from src.utils.rrf import (
    rrf_fusion,
    RRFResult,
)

from src.utils.reranker import (
    CrossEncoderReranker,
    RerankerError,
    RerankerModelError,
)

from src.utils.compressor import (
    ContextualCompressor,
    CompressorError,
    CompressorModelError,
)

__all__ = [
    # Embeddings
    "BedrockEmbeddings",
    "EmbeddingError",
    "EmbeddingModelError",
    "EmbeddingInputError",
    # Pinecone Client
    "PineconeClient",
    "PineconeClientError",
    "PineconeConnectionError",
    "PineconeValidationError",
    "PineconeUpsertError",
    "PineconeQueryError",
    "PineconeDeleteError",
    # BM25 Encoder
    "BM25Encoder",
    "BM25EncoderError",
    # RRF Fusion
    "rrf_fusion",
    "RRFResult",
    # Reranker
    "CrossEncoderReranker",
    "RerankerError",
    "RerankerModelError",
    # Compressor
    "ContextualCompressor",
    "CompressorError",
    "CompressorModelError",
]
