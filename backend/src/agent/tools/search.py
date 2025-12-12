"""
Tavily search tool with real API support and mock fallback.

- Uses real Tavily API when `TAVILY_API_KEY` is configured.
- Falls back to deterministic mock data when no API key is provided (Phase 0 friendly).
- Keeps the same LangChain @tool interface so the agent can call it directly.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

import httpx
import requests
import structlog
from langchain.tools import tool
from langchain_community.tools.tavily_search import TavilySearchResults
from pydantic import BaseModel, Field, field_validator

from src.config.settings import Settings, get_settings

logger = structlog.get_logger(__name__)

# Default configuration tuned for Tavily free tier (1,000 searches/month).
DEFAULT_MAX_RESULTS = 5
MAX_RESULTS_LIMIT = 10  # guardrail to avoid accidental large queries
DEFAULT_SEARCH_DEPTH = "basic"
TAVILY_TIMEOUT_SECONDS = 10.0


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
        """Ensure the query is non-empty once trimmed."""
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
    return {"results": mock_results, "query": query, "source": "mock", "mode": "mock"}


def _format_results(raw_results: Any) -> List[Dict[str, str]]:
    """Normalize Tavily results into the structured format the agent expects."""

    candidates: List[Dict[str, Any]]
    if isinstance(raw_results, dict) and "results" in raw_results:
        candidates = raw_results.get("results", []) or []
    elif isinstance(raw_results, list):
        candidates = raw_results
    else:
        candidates = []

    formatted_results: List[Dict[str, str]] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        formatted_results.append(
            {
                "title": str(item.get("title", "")).strip(),
                "snippet": str(item.get("content", "")).strip(),
                "url": str(item.get("url", "")).strip(),
            }
        )
    return formatted_results


async def _call_tavily_api(
    query: str,
    settings: Settings,
    *,
    max_results: int = DEFAULT_MAX_RESULTS,
    search_depth: str = DEFAULT_SEARCH_DEPTH,
) -> Dict[str, Any]:
    """Call Tavily API for live search results."""

    api_key = (
        settings.tavily_api_key.get_secret_value() if settings.tavily_api_key else None
    )
    if not api_key:
        return _build_mock_results(query)

    safe_max_results = max(1, min(max_results, MAX_RESULTS_LIMIT))
    tool = TavilySearchResults(
        api_key=api_key,
        max_results=safe_max_results,
        search_depth=search_depth,
    )

    try:
        async with asyncio.timeout(TAVILY_TIMEOUT_SECONDS):
            raw_results = await tool.ainvoke({"query": query})
    except TimeoutError:
        logger.error(
            "tavily_search_timeout", query=query, timeout=TAVILY_TIMEOUT_SECONDS
        )
        raise

    formatted_results = _format_results(raw_results)

    return {
        "results": formatted_results,
        "query": query,
        "source": "tavily",
        "mode": "live",
        "max_results": safe_max_results,
        "search_depth": search_depth,
    }


@tool("tavily_search", args_schema=SearchInput)
async def tavily_search(query: str) -> Dict[str, Any]:
    """
    Search the web for current information using Tavily API (with mock fallback).

    Uses real Tavily when `TAVILY_API_KEY` is set; otherwise returns
    deterministic mock data to keep Phase 0 runnable without external calls.
    """

    settings = get_settings()

    try:
        if not settings.tavily_api_key:
            logger.info("tavily_search_mock_mode", query=query)
            return _build_mock_results(query)

        logger.info(
            "tavily_search_live_mode",
            query=query,
            max_results=DEFAULT_MAX_RESULTS,
            search_depth=DEFAULT_SEARCH_DEPTH,
        )
        return await _call_tavily_api(
            query,
            settings,
            max_results=DEFAULT_MAX_RESULTS,
            search_depth=DEFAULT_SEARCH_DEPTH,
        )

    except TimeoutError as exc:
        logger.error(
            "tavily_search_timeout_error",
            query=query,
            timeout=TAVILY_TIMEOUT_SECONDS,
            error=str(exc),
        )
        raise ValueError("Tavily search timed out. Please try again.") from exc

    except requests.HTTPError as exc:
        response = exc.response
        status_code = response.status_code if response is not None else None
        retry_after = (
            response.headers.get("Retry-After", "") if response is not None else ""
        )
        logger.error(
            "tavily_search_http_error_requests",
            query=query,
            status_code=status_code,
            error=str(exc),
        )
        if status_code in (401, 403):
            raise ValueError("Invalid Tavily API key.") from exc
        if status_code == 429:
            message = (
                "Rate limited by Tavily (free tier is ~1,000 searches/month). "
                "Please retry in a moment."
            )
            if retry_after:
                message = f"{message} Retry-After: {retry_after} seconds."
            raise ValueError(message) from exc
        raise ValueError("Tavily search failed. Please try again.") from exc

    except httpx.HTTPStatusError as exc:
        response = exc.response
        status_code = response.status_code if response is not None else None
        logger.error(
            "tavily_search_http_error",
            query=query,
            status_code=status_code,
            error=str(exc),
        )
        if status_code in (401, 403):
            raise ValueError("Invalid Tavily API key.") from exc
        if status_code == 429:
            retry_after = (
                response.headers.get("Retry-After", "") if response is not None else ""
            )
            message = (
                "Rate limited by Tavily (free tier is ~1,000 searches/month). "
                "Please retry in a moment."
            )
            if retry_after:
                message = f"{message} Retry-After: {retry_after} seconds."
            raise ValueError(message) from exc
        raise ValueError("Tavily search failed. Please try again.") from exc

    except httpx.RequestError as exc:
        logger.error("tavily_search_request_error", query=query, error=str(exc))
        raise ValueError("Network error while calling Tavily.") from exc

    except requests.RequestException as exc:
        logger.error(
            "tavily_search_request_error_requests", query=query, error=str(exc)
        )
        raise ValueError("Network error while calling Tavily.") from exc

    except ValueError:
        # Allow already-mapped user-friendly errors to propagate.
        raise

    except Exception as exc:  # pragma: no cover - defensive guard
        logger.error("tavily_search_unknown_error", query=query, error=str(exc))
        raise ValueError("Tavily search is temporarily unavailable.") from exc


def get_search_mode(settings: Optional[Settings] = None) -> str:
    """Return 'live' when Tavily API key is set, else 'mock'."""

    active_settings = settings or Settings()
    return "live" if active_settings.tavily_api_key else "mock"


__all__ = ["tavily_search", "SearchInput", "get_search_mode"]

# Backwards-compatible alias used in early docs/tests.
search_tool = tavily_search
