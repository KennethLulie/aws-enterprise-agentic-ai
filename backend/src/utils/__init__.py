"""
Utility helpers and shared functions for the backend.

This package provides common utilities used across the backend:

- embeddings: Bedrock Titan embeddings for text vectorization in RAG pipelines
- pinecone_client: Pinecone vector store client for RAG operations
- bm25_encoder: BM25 sparse vector encoder for Pinecone hybrid search

Usage:
    from src.utils.embeddings import BedrockEmbeddings
    from src.utils.pinecone_client import PineconeClient
    from src.utils.bm25_encoder import BM25Encoder

    # Generate embeddings
    embeddings = BedrockEmbeddings()
    vector = await embeddings.embed_text("What is NVIDIA's revenue?")

    # Generate sparse vectors for hybrid search
    bm25 = BM25Encoder()
    sparse = bm25.encode("What is NVIDIA's revenue?")

    # Store/query vectors in Pinecone
    client = PineconeClient()
    results = client.query(vector, sparse_vector=sparse, top_k=10)
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
]
