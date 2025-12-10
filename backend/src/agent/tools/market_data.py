"""
Market data tool backed by Financial Modeling Prep (FMP).

- Uses mock data when no FMP API key is provided (Phase 0 friendly).
- Supports batch tickers in a single request.
- Applies basic error handling and structured responses for the agent UI.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
import structlog
from langchain.tools import tool
from pydantic import BaseModel, Field, field_validator

from src.config.settings import Settings

logger = structlog.get_logger()


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
            "open": 122.0,
            "previous_close": 122.22,
            "day_high": 125.0,
            "day_low": 121.5,
            "volume": 100_000,
            "currency": "USD",
            "exchange": "NYSE",
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


async def _call_fmp_api(
    tickers: List[str],
    settings: Settings,
) -> List[Dict[str, Any]]:
    """Call FMP quote endpoint for tickers."""
    tickers_param = ",".join(tickers)
    url = f"{str(settings.fmp_base_url).rstrip('/')}/quote/{tickers_param}"

    async with httpx.AsyncClient(timeout=settings.fmp_timeout_seconds) as client:
        response = await client.get(url, params={"apikey": settings.fmp_api_key})
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
                "change_percent": entry.get("changesPercentage"),
                "open": entry.get("open"),
                "previous_close": entry.get("previousClose"),
                "day_high": entry.get("dayHigh"),
                "day_low": entry.get("dayLow"),
                "volume": entry.get("volume"),
                "currency": entry.get("currency"),
                "exchange": entry.get("exchange"),
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
    cleaned_tickers = [ticker.strip().upper() for ticker in tickers if ticker.strip()]
    if not cleaned_tickers:
        raise ValueError("At least one ticker is required.")

    if not active_settings.fmp_api_key:
        logger.info("market_data_mock_mode", tickers=cleaned_tickers)
        return {
            "data": _build_mock_quotes(cleaned_tickers),
            "mode": "mock",
            "source": "financialmodelingprep",
        }

    try:
        data = await _call_fmp_api(cleaned_tickers, active_settings)
        return {"data": data, "mode": "live", "source": "financialmodelingprep"}
    except Exception as exc:  # pylint: disable=broad-except
        logger.error(
            "market_data_error",
            tickers=cleaned_tickers,
            error=str(exc),
        )
        raise ValueError(
            "Market data is temporarily unavailable. Please try again."
        ) from exc


@tool("market_data", args_schema=MarketDataInput)
async def market_data_tool(tickers: List[str]) -> Dict[str, Any]:
    """
    Retrieve market data for one or more tickers via Financial Modeling Prep.

    Uses mock data if `FMP_API_KEY` is not configured to keep Phase 0 runnable.
    """

    return await fetch_market_data(tickers)


__all__ = ["market_data_tool", "fetch_market_data", "MarketDataInput"]

