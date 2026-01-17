"""
Utility helpers and shared functions for the backend.

This package provides common utilities used across the backend:

- embeddings: Bedrock Titan embeddings for text vectorization in RAG pipelines

Usage:
    from src.utils.embeddings import BedrockEmbeddings

    embeddings = BedrockEmbeddings()
    vector = await embeddings.embed_text("What is NVIDIA's revenue?")
"""

from src.utils.embeddings import (
    BedrockEmbeddings,
    EmbeddingError,
    EmbeddingModelError,
    EmbeddingInputError,
)

__all__ = [
    "BedrockEmbeddings",
    "EmbeddingError",
    "EmbeddingModelError",
    "EmbeddingInputError",
]
