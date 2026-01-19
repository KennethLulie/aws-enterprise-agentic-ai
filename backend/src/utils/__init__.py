"""
Utility helpers and shared functions for the backend.

This package provides common utilities used across the backend:

- embeddings: Bedrock Titan embeddings for text vectorization in RAG pipelines
- pinecone_client: Pinecone vector store client for RAG operations

Usage:
    from src.utils.embeddings import BedrockEmbeddings
    from src.utils.pinecone_client import PineconeClient

    # Generate embeddings
    embeddings = BedrockEmbeddings()
    vector = await embeddings.embed_text("What is NVIDIA's revenue?")

    # Store/query vectors in Pinecone
    client = PineconeClient()
    results = client.query(vector, top_k=10)
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
]
