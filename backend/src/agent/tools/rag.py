"""
Mock RAG retrieval tool for Phase 0/local demos.

- Uses LangChain @tool decorator with a Pydantic input schema.
- Returns deterministic mock documents to avoid external dependencies.
"""

from __future__ import annotations

from typing import Any, Dict, List

from langchain.tools import tool
from pydantic import BaseModel, Field, field_validator


class RAGQueryInput(BaseModel):
    """Input schema for the RAG retrieval tool."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=1024,
        description="User query to retrieve relevant documents for.",
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        """Ensure RAG queries are present after trimming whitespace."""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Query cannot be empty.")
        return cleaned


def _build_mock_results(query: str) -> Dict[str, Any]:
    """Return deterministic mock retrieval results for demo purposes."""
    documents: List[Dict[str, Any]] = [
        {
            "content": "Security architecture overview focusing on network segmentation.",
            "source": "security-architecture.pdf",
            "page": 12,
            "score": 0.95,
        },
        {
            "content": "Cost optimization playbook outlining reserved instances and autoscaling.",
            "source": "cost-optimization-playbook.pdf",
            "page": 4,
            "score": 0.89,
        },
        {
            "content": "Incident response checklist with escalation paths and RTO targets.",
            "source": "incident-response.md",
            "page": 2,
            "score": 0.82,
        },
    ]
    return {
        "query": query,
        "documents": documents,
        "count": len(documents),
        "source": "mock",
    }


@tool("rag_retrieval", args_schema=RAGQueryInput)
async def rag_retrieval(query: str) -> Dict[str, Any]:
    """
    Retrieve relevant documents from vector store using semantic search.

    Phase 0 implementation returns deterministic mock results for offline demos.
    """

    return _build_mock_results(query)


__all__ = ["rag_retrieval", "RAGQueryInput"]
