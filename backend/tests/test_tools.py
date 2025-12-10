import httpx
import pytest

from src.agent.tools.market_data import fetch_market_data
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


@pytest.mark.asyncio
async def test_fetch_market_data_mock_mode() -> None:
    settings = _DummySettings(fmp_api_key=None)

    result = await fetch_market_data(["AAPL", "MSFT"], settings=settings)

    assert result["mode"] == "mock"
    assert len(result["data"]) == 2
    assert result["data"][0]["ticker"] == "AAPL"


@pytest.mark.asyncio
async def test_fetch_market_data_live_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _DummySettings(fmp_api_key="test-key")
    test_url = "https://financialmodelingprep.com/api/v3/quote/AAPL"

    class _DummyAsyncClient:
        def __init__(self, *args, **kwargs) -> None:  # noqa: ANN001, D401
            pass

        async def __aenter__(self) -> "_DummyAsyncClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001
            return False

        async def get(self, url: str, params: dict | None = None) -> httpx.Response:
            response = httpx.Response(
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
            return response

    monkeypatch.setattr("src.agent.tools.market_data.httpx.AsyncClient", _DummyAsyncClient)

    result = await fetch_market_data(["AAPL"], settings=settings)

    assert result["mode"] == "live"
    assert result["data"][0]["price"] == 200.0
    assert result["data"][0]["ticker"] == "AAPL"


@pytest.mark.asyncio
async def test_fetch_market_data_handles_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _DummySettings(fmp_api_key="test-key")
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
                json={"error": "rate limit"},
                request=httpx.Request("GET", test_url),
            )

    monkeypatch.setattr("src.agent.tools.market_data.httpx.AsyncClient", _FailingAsyncClient)

    with pytest.raises(ValueError):
        await fetch_market_data(["AAPL"], settings=settings)

