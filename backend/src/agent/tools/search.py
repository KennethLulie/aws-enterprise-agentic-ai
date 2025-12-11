"""
Tavily-style search tool that returns deterministic mock data for Phase 0.

- Uses LangChain @tool decorator with a Pydantic input schema.
- Keeps behavior local-only; no external network calls in Phase 0.
"""

from __future__ import annotations

from typing import Any, Dict, List

from langchain.tools import tool
from pydantic import BaseModel, Field, field_validator


class SearchInput(BaseModel):
    """Input schema for the Tavily search tool."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description="Search query to look up.",
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Query cannot be empty.")
        return cleaned


def _build_mock_results(query: str) -> Dict[str, Any]:
    """Return deterministic mock search results for demo purposes."""
    mock_results: List[Dict[str, str]] = [
        {
            "title": "Example result one",
            "snippet": "A concise summary of the first mock search finding.",
            "url": "https://example.com/result-1",
        },
        {
            "title": "Example result two",
            "snippet": "Follow-up insight related to the search topic.",
            "url": "https://example.com/result-2",
        },
        {
            "title": "Example result three",
            "snippet": "Additional context for the query, sourced from mock data.",
            "url": "https://example.com/result-3",
        },
    ]
    return {"results": mock_results, "query": query, "source": "mock"}


@tool("tavily_search", args_schema=SearchInput)
async def tavily_search(query: str) -> Dict[str, Any]:
    """
    Search the web for current information using Tavily API (mocked in Phase 0).

    Returns deterministic mock results to keep local development self-contained.
    """

    return _build_mock_results(query)


__all__ = ["tavily_search", "SearchInput"]
