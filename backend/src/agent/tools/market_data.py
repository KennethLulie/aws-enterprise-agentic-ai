"""
Market data tool backed by Financial Modeling Prep (FMP).

- Uses mock data when no FMP API key is provided (Phase 0 friendly).
- Supports batch tickers in a single request.
- Applies basic error handling and structured responses for the agent UI.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx
import structlog
from langchain.tools import tool
from pydantic import BaseModel, Field, field_validator
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config.settings import Settings

logger = structlog.get_logger()

# Simple in-memory circuit breaker to avoid hammering FMP during outages
_CB_STATE: Dict[str, Any] = {"failures": 0, "opened_until": None}
# Lightweight in-memory guardrail to avoid exhausting the free-tier quota
_RATE_LIMIT_STATE: Dict[str, Any] = {"day": None, "count": 0}
_FMP_DAILY_LIMIT = 240  # Free tier is ~250/day; keep a safety buffer


def _is_circuit_open() -> bool:
    """Return True if the circuit is currently open."""
    opened_until = _CB_STATE.get("opened_until")
    return bool(opened_until and datetime.now(timezone.utc) < opened_until)


def _record_success() -> None:
    """Reset circuit breaker after a successful call."""
    _CB_STATE["failures"] = 0
    _CB_STATE["opened_until"] = None


def _record_failure(threshold: int = 3, cooldown_seconds: int = 30) -> None:
    """Increment failures and open circuit when threshold is reached."""
    _CB_STATE["failures"] = _CB_STATE.get("failures", 0) + 1
    if _CB_STATE["failures"] >= threshold:
        _CB_STATE["opened_until"] = datetime.now(timezone.utc) + timedelta(
            seconds=cooldown_seconds
        )


def reset_market_data_circuit() -> None:
    """Reset circuit breaker and local rate-limit state (primarily for testing)."""

    _CB_STATE["failures"] = 0
    _CB_STATE["opened_until"] = None
    _reset_rate_limit_state()


def _reset_rate_limit_state() -> None:
    """Reset rate-limit counters for the current UTC day."""

    _RATE_LIMIT_STATE["day"] = datetime.now(timezone.utc).date()
    _RATE_LIMIT_STATE["count"] = 0


def _consume_rate_limit(limit: int = _FMP_DAILY_LIMIT) -> bool:
    """Consume one request slot; return False if quota exceeded."""

    today = datetime.now(timezone.utc).date()
    if _RATE_LIMIT_STATE.get("day") != today:
        _RATE_LIMIT_STATE["day"] = today
        _RATE_LIMIT_STATE["count"] = 0

    current_count = int(_RATE_LIMIT_STATE.get("count", 0))
    if current_count >= limit:
        return False

    _RATE_LIMIT_STATE["count"] = current_count + 1
    return True


class MarketDataInput(BaseModel):
    """Input schema for requesting market data."""

    tickers: List[str] = Field(
        ...,
        min_length=1,
        description="List of stock/ETF tickers to fetch (e.g., ['AAPL', 'MSFT']).",
    )

    @field_validator("tickers")
    @classmethod
    def validate_tickers(cls, tickers: List[str]) -> List[str]:
        """Normalize tickers and require at least one non-empty symbol."""
        cleaned = [ticker.strip().upper() for ticker in tickers if ticker.strip()]
        if not cleaned:
            raise ValueError("At least one ticker is required.")
        return cleaned


def _build_mock_quotes(tickers: List[str]) -> List[Dict[str, Any]]:
    """Return deterministic mock quotes for Phase 0/local demo."""
    now = datetime.now(timezone.utc).isoformat()
    return [
        {
            "ticker": ticker,
            "price": 123.45,
            "change": 1.23,
            "change_percent": 0.99,
            "volume": 100_000,
            "timestamp": now,
            "source": "mock",
        }
        for ticker in tickers
    ]


def _coerce_timestamp(raw_value: Any) -> Optional[str]:
    """Convert numeric timestamp to ISO 8601 if possible."""
    if raw_value is None:
        return None
    if isinstance(raw_value, (int, float)):
        try:
            return datetime.fromtimestamp(int(raw_value), tz=timezone.utc).isoformat()
        except (OSError, ValueError):
            return None
    if isinstance(raw_value, str):
        return raw_value
    return None


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.RequestError)),
)
async def _call_fmp_api(
    tickers: List[str],
    settings: Settings,
    api_key: str,
) -> List[Dict[str, Any]]:
    """Call FMP quote endpoint for tickers."""
    tickers_param = ",".join(tickers)
    url = f"{str(settings.fmp_base_url).rstrip('/')}/quote"

    async with httpx.AsyncClient(timeout=settings.fmp_timeout_seconds) as client:
        response = await client.get(
            url, params={"symbol": tickers_param, "apikey": api_key}
        )
        response.raise_for_status()
        payload: Any = response.json()

    if not isinstance(payload, list):
        raise ValueError("Unexpected response from FMP.")

    results: List[Dict[str, Any]] = []
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        results.append(
            {
                "ticker": entry.get("symbol") or entry.get("name"),
                "price": entry.get("price"),
                "change": entry.get("change"),
                "change_percent": entry.get("changePercentage"),
                "volume": entry.get("volume"),
                "timestamp": _coerce_timestamp(entry.get("timestamp")),
                "source": "financialmodelingprep",
            }
        )
    return results


async def fetch_market_data(
    tickers: List[str],
    settings: Optional[Settings] = None,
) -> Dict[str, Any]:
    """
    Fetch market data for the given tickers using FMP or mock fallback.

    Args:
        tickers: List of ticker symbols to query.
        settings: Optional Settings injection for testing.

    Returns:
        Dict containing data, mode, and source metadata.
    """
    active_settings = settings or Settings()
    api_key = (
        active_settings.fmp_api_key.get_secret_value()
        if active_settings.fmp_api_key
        else None
    )
    cleaned_tickers = [ticker.strip().upper() for ticker in tickers if ticker.strip()]
    if not cleaned_tickers:
        raise ValueError("At least one ticker is required.")

    if _is_circuit_open():
        logger.warning("market_data_circuit_open", tickers=cleaned_tickers)
        raise ValueError(
            "Market data is temporarily unavailable. Please try again shortly."
        )

    if not api_key:
        logger.info("market_data_mock_mode", tickers=cleaned_tickers)
        return {
            "data": _build_mock_quotes(cleaned_tickers),
            "mode": "mock",
            "source": "financialmodelingprep",
        }

    if not _consume_rate_limit():
        logger.warning(
            "market_data_local_rate_limit_reached",
            tickers=cleaned_tickers,
            limit=_FMP_DAILY_LIMIT,
        )
        return {
            "data": _build_mock_quotes(cleaned_tickers),
            "mode": "mock",
            "mode_reason": "local_rate_limit",
            "source": "financialmodelingprep",
        }

    try:
        logger.info(
            "market_data_live_mode",
            tickers=cleaned_tickers,
            base_url=str(active_settings.fmp_base_url),
        )
        data = await _call_fmp_api(cleaned_tickers, active_settings, api_key)
        _record_success()
        return {"data": data, "mode": "live", "source": "financialmodelingprep"}
    except httpx.HTTPStatusError as exc:
        _record_failure()
        status_code = exc.response.status_code if exc.response else None
        logger.error(
            "market_data_http_error",
            tickers=cleaned_tickers,
            status_code=status_code,
            error=str(exc),
        )
        if status_code in (401, 403):
            logger.warning(
                "market_data_fallback_to_mock",
                tickers=cleaned_tickers,
                reason="invalid_or_legacy_api_key",
            )
            return {
                "data": _build_mock_quotes(cleaned_tickers),
                "mode": "mock",
                "mode_reason": "invalid_api_key",
                "source": "financialmodelingprep",
            }
        if status_code == 402:
            logger.warning(
                "market_data_fallback_to_mock",
                tickers=cleaned_tickers,
                reason="payment_required",
            )
            return {
                "data": _build_mock_quotes(cleaned_tickers),
                "mode": "mock",
                "mode_reason": "payment_required",
                "source": "financialmodelingprep",
            }
        if status_code == 429:
            retry_after = (
                exc.response.headers.get("Retry-After") if exc.response else None
            )
            message = "Rate limited by market data provider. Please retry in a moment."
            if retry_after:
                message = f"{message} Retry-After: {retry_after} seconds."
            raise ValueError(message) from exc
        raise ValueError(
            "Market data provider returned an error. Please try again shortly."
        ) from exc
    except httpx.RequestError as exc:
        _record_failure()
        logger.error(
            "market_data_request_error",
            tickers=cleaned_tickers,
            error=str(exc),
        )
        raise ValueError(
            "Network error while fetching market data. Please try again."
        ) from exc
    except Exception as exc:  # pylint: disable=broad-except
        _record_failure()
        logger.error(
            "market_data_error",
            tickers=cleaned_tickers,
            error=str(exc),
        )
        raise ValueError(
            "Market data is temporarily unavailable. Please try again."
        ) from exc


@tool(
    "market_data",
    args_schema=MarketDataInput,
)
async def market_data_tool(tickers: List[str]) -> Dict[str, Any]:
    """
    Get REAL-TIME stock prices and market data via Financial Modeling Prep.

    USE THIS TOOL FOR:
    - CURRENT stock prices: "What is NVIDIA's stock price?"
    - REAL-TIME market data: price, change, change percent, volume
    - Multiple tickers at once: "Compare prices of NVDA, AMD, MU"
    - Market snapshot for portfolio overview

    DO NOT USE FOR:
    - Historical financial data from 10-K filings (use sql_query)
    - Company fundamentals like revenue or margins (use sql_query)
    - News or analyst opinions (use tavily_search)
    - Qualitative company information (use rag_retrieval)

    AVAILABLE DATA:
    - Any publicly traded US stock ticker
    - Real-time quotes: price, change, change_percent, volume, timestamp
    - Data source: Financial Modeling Prep API

    FALLBACK: Returns mock data ($123.45) if FMP API key is not configured or rate limit exceeded.

    Args:
        tickers: List of stock tickers to fetch (e.g., ['NVDA', 'AMD']).

    Returns:
        Market data with current prices, changes, and trading volume for each ticker.
    """

    return await fetch_market_data(tickers)


def get_market_data_mode(settings: Optional[Settings] = None) -> str:
    """Return 'live' when FMP API key is set, else 'mock'."""

    active_settings = settings or Settings()
    return "live" if active_settings.fmp_api_key else "mock"


__all__ = [
    "market_data_tool",
    "fetch_market_data",
    "get_market_data_mode",
    "MarketDataInput",
    "reset_market_data_circuit",
]
