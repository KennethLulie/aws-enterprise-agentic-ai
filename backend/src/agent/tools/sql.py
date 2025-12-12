"""
SQL query tool that returns deterministic mock results for Phase 0.

- Uses LangChain @tool decorator with a Pydantic input schema.
- Keeps behavior local-only; no real database calls in Phase 0.
"""

from __future__ import annotations

from typing import Any, Dict, List

from langchain.tools import tool
from pydantic import BaseModel, Field, field_validator


class SQLQueryInput(BaseModel):
    """Input schema for the SQL query tool."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=1024,
        description="Natural language request or SQL to run against PostgreSQL.",
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        """Validate and trim incoming SQL/natural language queries."""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Query cannot be empty.")
        return cleaned


def _build_mock_rows() -> List[Dict[str, Any]]:
    """Return deterministic mock table rows for demo purposes."""

    return [
        {"id": 1, "name": "Alice Johnson", "email": "alice@example.com"},
        {"id": 2, "name": "Bob Smith", "email": "bob@example.com"},
    ]


def _build_mock_result(query: str) -> Dict[str, Any]:
    """Assemble the mock SQL query result payload."""

    rows = _build_mock_rows()
    return {"query": query, "results": rows, "row_count": len(rows), "source": "mock"}


@tool("sql_query", args_schema=SQLQueryInput)
async def sql_query(query: str) -> Dict[str, Any]:
    """
    Query the PostgreSQL database using natural language.

    Returns deterministic mock data in Phase 0 to keep local development simple.
    """

    # TODO: Replace with real SQL execution using parameterized queries (Phase 2).
    # TODO: Add allowlists and SQL injection prevention safeguards (Phase 2).
    return _build_mock_result(query)


__all__ = ["sql_query", "SQLQueryInput"]
