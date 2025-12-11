from collections.abc import Callable
from unittest.mock import AsyncMock

import httpx
import pytest

import src.agent.tools.market_data as market_data
from src.agent.tools.market_data import (
    MarketDataInput,
    fetch_market_data,
    market_data_tool,
)
from src.config.settings import Settings


class _DummySettings(Settings):
    """Settings subclass for tests to control FMP configuration."""

    def __init__(
        self,
        fmp_api_key: str | None = None,
        fmp_base_url: str = "https://financialmodelingprep.com/api/v3",
    ) -> None:
        super().__init__(
            fmp_api_key=fmp_api_key,
            fmp_base_url=fmp_base_url,
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
        return _DummySettings(fmp_api_key=api_key)

    return _factory


def test_market_data_input_validation() -> None:
    """Pydantic schema cleans tickers and enforces non-empty input."""

    model = MarketDataInput(tickers=[" aapl ", "msft"])

    assert model.tickers == ["AAPL", "MSFT"]

    with pytest.raises(ValueError):
        MarketDataInput(tickers=["   "])


@pytest.mark.asyncio
async def test_market_data_tool_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tool returns deterministic mock data when API key is missing."""

    monkeypatch.setattr(market_data, "Settings", _DummySettings)

    result = await market_data_tool(["aapl", " msft "])

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
        def __init__(self, *args, **kwargs) -> None:  # noqa: ANN001, D401
            pass

        async def __aenter__(self) -> "_DummyAsyncClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001
            return False

        async def get(self, url: str, params: dict | None = None) -> httpx.Response:
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
async def test_tool_error_handling(
    monkeypatch: pytest.MonkeyPatch,
    make_settings: Callable[[str | None], _DummySettings],
) -> None:
    """Gracefully surfaces provider errors as user-friendly messages."""

    test_url = "https://financialmodelingprep.com/api/v3/quote/AAPL"

    class _FailingAsyncClient:
        def __init__(self, *args, **kwargs) -> None:  # noqa: ANN001, D401
            pass

        async def __aenter__(self) -> "_FailingAsyncClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001
            return False

        async def get(self, url: str, params: dict | None = None) -> httpx.Response:
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
    """Returns friendly message for authentication/authorization failures."""

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

    with pytest.raises(ValueError) as exc_info:
        await fetch_market_data(["AAPL"], settings=make_settings("test-key"))

    assert "Invalid or missing market data API key" in str(exc_info.value)


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
