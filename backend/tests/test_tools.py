"""Tool-level unit tests for market data utilities and behaviors."""

from collections.abc import Callable
from datetime import datetime, timezone
from types import TracebackType
from typing import cast
from unittest.mock import AsyncMock

import httpx
import pytest
import requests
from pydantic import AnyHttpUrl, SecretStr

import src.agent.tools.market_data as market_data
import src.agent.tools.search as search
from src.agent.tools.market_data import (
    MarketDataInput,
    fetch_market_data,
    market_data_tool,
)
from src.agent.tools.search import get_search_mode, tavily_search
from src.config.settings import Settings


class _DummySettings(Settings):
    """Settings subclass for tests to control FMP configuration."""

    def __init__(
        self,
        fmp_api_key: str | None = None,
        fmp_base_url: str = "https://financialmodelingprep.com/api/v3",
    ) -> None:
        """Initialize test settings with optional API key overrides."""
        super().__init__(
            fmp_api_key=SecretStr(fmp_api_key) if fmp_api_key else None,
            fmp_base_url=cast(AnyHttpUrl, fmp_base_url),
            fmp_timeout_seconds=5.0,
        )


@pytest.fixture(autouse=True)
def reset_circuit_breaker() -> None:
    """Reset circuit breaker state between tests."""

    market_data.reset_market_data_circuit()


@pytest.fixture
def make_settings() -> Callable[[str | None], _DummySettings]:
    """Factory fixture to create settings with configurable API keys."""

    def _factory(api_key: str | None) -> _DummySettings:
        """Return test settings configured with the provided API key."""
        return _DummySettings(fmp_api_key=api_key)

    return _factory


def test_market_data_input_validation() -> None:
    """Pydantic schema cleans tickers and enforces non-empty input."""

    model = MarketDataInput(tickers=[" aapl ", "msft"])

    assert model.tickers == ["AAPL", "MSFT"]

    with pytest.raises(ValueError):
        MarketDataInput(tickers=["   "])


@pytest.mark.asyncio
async def test_tavily_search_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tavily search returns mock payload when API key is absent."""

    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    result = await tavily_search.ainvoke({"query": "latest AI news"})

    assert result["mode"] == "mock"
    assert result["source"] == "mock"
    assert result["results"]
    assert get_search_mode() == "mock"


class _TavilySettings(Settings):
    """Settings subclass for Tavily tests to inject API key."""

    def __init__(self, tavily_api_key: str | None = "test-key") -> None:
        """Initialize with optional Tavily API key override."""
        super().__init__(
            tavily_api_key=SecretStr(tavily_api_key) if tavily_api_key else None
        )


@pytest.mark.asyncio
async def test_tavily_search_live_formats_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Formats live Tavily results into structured shape."""

    class _StubTavilyTool:
        """Stub Tavily tool that returns a fixed successful response."""

        def __init__(self, *args: object, **kwargs: object) -> None:
            """Initialize stub (ignores all arguments)."""
            return None

        async def ainvoke(self, _: dict[str, str]) -> list[dict[str, str]]:
            """Return a fixed search result for testing."""
            return [
                {
                    "title": "Result One",
                    "content": "Body text",
                    "url": "https://example.com/one",
                }
            ]

    monkeypatch.setattr(search, "get_settings", lambda: _TavilySettings())
    monkeypatch.setattr(search, "TavilySearchResults", _StubTavilyTool)

    result = await tavily_search.ainvoke({"query": "latest AI news"})

    assert result["mode"] == "live"
    assert result["source"] == "tavily"
    assert result["results"][0]["title"] == "Result One"
    assert result["results"][0]["snippet"] == "Body text"
    assert result["results"][0]["url"] == "https://example.com/one"


@pytest.mark.asyncio
async def test_tavily_search_live_handles_rate_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Returns friendly message when Tavily responds with 429."""

    response = requests.Response()
    response.status_code = 429
    response.headers["Retry-After"] = "5"
    error = requests.HTTPError("rate limited", response=response)

    class _FailingTavilyTool:
        """Stub Tavily tool that raises a rate limit error."""

        def __init__(self, *args: object, **kwargs: object) -> None:
            """Initialize stub (ignores all arguments)."""
            return None

        async def ainvoke(self, _: dict[str, str]) -> list[dict[str, str]]:
            """Raise a rate limit error to test error handling."""
            raise error

    monkeypatch.setattr(search, "get_settings", lambda: _TavilySettings())
    monkeypatch.setattr(search, "TavilySearchResults", _FailingTavilyTool)

    with pytest.raises(ValueError) as exc_info:
        await tavily_search.ainvoke({"query": "latest AI news"})

    assert "Rate limited by Tavily" in str(exc_info.value)


@pytest.mark.asyncio
async def test_market_data_tool_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tool returns deterministic mock data when API key is missing."""

    monkeypatch.setattr(market_data, "Settings", _DummySettings)

    result = await market_data_tool.ainvoke({"tickers": ["aapl", " msft "]})

    assert result["mode"] == "mock"
    assert {quote["ticker"] for quote in result["data"]} == {"AAPL", "MSFT"}
    assert result["source"] == "financialmodelingprep"


@pytest.mark.asyncio
async def test_fetch_market_data_live_success(
    monkeypatch: pytest.MonkeyPatch,
    make_settings: Callable[[str | None], _DummySettings],
) -> None:
    """Live path returns parsed data when FMP responds successfully."""

    test_url = "https://financialmodelingprep.com/api/v3/quote/AAPL"

    class _DummyAsyncClient:
        """Async client stub that returns a fixed successful response."""

        def __init__(self, *args: object, **kwargs: object) -> None:
            """Ignore initialization arguments for test stub."""
            return None

        async def __aenter__(self) -> "_DummyAsyncClient":
            """Support async context manager entry."""
            return self

        async def __aexit__(
            self,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            tb: TracebackType | None,
        ) -> bool:
            """Support async context manager exit without suppressing errors."""
            return False

        async def get(
            self, url: str, params: dict[str, str] | None = None
        ) -> httpx.Response:
            """Return a deterministic success response payload."""
            return httpx.Response(
                status_code=200,
                json=[
                    {
                        "symbol": "AAPL",
                        "price": 200.0,
                        "change": 1.0,
                        "changesPercentage": 0.5,
                        "open": 199.0,
                        "previousClose": 198.0,
                        "dayHigh": 201.0,
                        "dayLow": 197.0,
                        "volume": 10_000,
                        "currency": "USD",
                        "exchange": "NASDAQ",
                        "timestamp": 1_700_000_000,
                    }
                ],
                request=httpx.Request("GET", test_url),
            )

    monkeypatch.setattr(
        "src.agent.tools.market_data.httpx.AsyncClient", _DummyAsyncClient
    )

    result = await fetch_market_data(["AAPL"], settings=make_settings("test-key"))

    assert result["mode"] == "live"
    assert result["data"][0]["ticker"] == "AAPL"
    assert result["data"][0]["price"] == 200.0


@pytest.mark.asyncio
async def test_fetch_market_data_local_rate_limit_guard(
    monkeypatch: pytest.MonkeyPatch,
    make_settings: Callable[[str | None], _DummySettings],
) -> None:
    """Falls back to mock data when local daily guard is hit."""

    monkeypatch.setattr(market_data, "Settings", _DummySettings)
    monkeypatch.setattr(
        market_data,
        "_call_fmp_api",
        AsyncMock(side_effect=RuntimeError("should not call live API")),
    )

    today = datetime.now(timezone.utc).date()
    market_data._RATE_LIMIT_STATE["day"] = today  # noqa: SLF001
    market_data._RATE_LIMIT_STATE["count"] = (
        market_data._FMP_DAILY_LIMIT
    )  # noqa: SLF001

    result = await fetch_market_data(["AAPL"], settings=make_settings("test-key"))

    assert result["mode"] == "mock"
    assert result.get("mode_reason") == "local_rate_limit"


@pytest.mark.asyncio
async def test_tool_error_handling(
    monkeypatch: pytest.MonkeyPatch,
    make_settings: Callable[[str | None], _DummySettings],
) -> None:
    """Gracefully surfaces provider errors as user-friendly messages."""

    test_url = "https://financialmodelingprep.com/api/v3/quote/AAPL"

    class _FailingAsyncClient:
        """Async client stub that simulates provider errors."""

        def __init__(self, *args: object, **kwargs: object) -> None:
            """Ignore initialization arguments for failing stub."""
            return None

        async def __aenter__(self) -> "_FailingAsyncClient":
            """Support async context manager entry."""
            return self

        async def __aexit__(
            self,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            tb: TracebackType | None,
        ) -> bool:
            """Support async context manager exit without suppressing errors."""
            return False

        async def get(
            self, url: str, params: dict[str, str] | None = None
        ) -> httpx.Response:
            """Return a throttling-style response to trigger retry logic."""
            return httpx.Response(
                status_code=429,
                headers={"Retry-After": "5"},
                json={"error": "rate limit"},
                request=httpx.Request("GET", test_url),
            )

    monkeypatch.setattr(
        "src.agent.tools.market_data.httpx.AsyncClient", _FailingAsyncClient
    )

    with pytest.raises(ValueError) as exc_info:
        await fetch_market_data(["AAPL"], settings=make_settings("test-key"))

    assert "Rate limited by market data provider" in str(exc_info.value)
    assert market_data._CB_STATE["failures"] == 1  # noqa: SLF001


@pytest.mark.asyncio
async def test_circuit_opens_after_consecutive_failures(
    monkeypatch: pytest.MonkeyPatch,
    make_settings: Callable[[str | None], _DummySettings],
) -> None:
    """Opens circuit after repeated provider failures and blocks subsequent calls."""

    error = httpx.RequestError(
        "network down", request=httpx.Request("GET", "http://test")
    )
    monkeypatch.setattr(
        market_data,
        "_call_fmp_api",
        AsyncMock(side_effect=error),
    )

    settings = make_settings("test-key")
    for _ in range(3):
        with pytest.raises(ValueError):
            await fetch_market_data(["AAPL"], settings=settings)

    # Circuit should have counted failures up to threshold
    assert market_data._CB_STATE["failures"] == 3  # noqa: SLF001

    with pytest.raises(ValueError) as exc_info:
        await fetch_market_data(["AAPL"], settings=settings)

    assert "temporarily unavailable" in str(exc_info.value)
    assert market_data._CB_STATE["opened_until"] is not None  # noqa: SLF001


@pytest.mark.asyncio
async def test_handles_auth_error(
    monkeypatch: pytest.MonkeyPatch,
    make_settings: Callable[[str | None], _DummySettings],
) -> None:
    """Gracefully falls back to mock data for authentication/authorization failures."""

    response = httpx.Response(
        status_code=401,
        request=httpx.Request("GET", "http://test"),
    )
    error = httpx.HTTPStatusError(
        "unauthorized", request=response.request, response=response
    )
    monkeypatch.setattr(
        market_data,
        "_call_fmp_api",
        AsyncMock(side_effect=error),
    )

    # Should not raise an exception - gracefully falls back to mock data
    result = await fetch_market_data(["AAPL"], settings=make_settings("test-key"))

    # Verify it returned mock data
    assert result["mode"] == "mock"
    assert result["mode_reason"] == "invalid_api_key"
    assert "data" in result
    assert len(result["data"]) == 1  # One ticker requested
    assert result["data"][0]["ticker"] == "AAPL"


@pytest.mark.asyncio
async def test_handles_generic_exception(
    monkeypatch: pytest.MonkeyPatch,
    make_settings: Callable[[str | None], _DummySettings],
) -> None:
    """Returns generic message for unexpected errors."""

    monkeypatch.setattr(
        market_data,
        "_call_fmp_api",
        AsyncMock(side_effect=RuntimeError("unexpected boom")),
    )

    with pytest.raises(ValueError) as exc_info:
        await fetch_market_data(["AAPL"], settings=make_settings("test-key"))

    assert "temporarily unavailable" in str(exc_info.value)
