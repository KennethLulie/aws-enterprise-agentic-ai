from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from src.api import __api_version__, __version__
from src.api.main import create_app
from src.config import settings as settings_module


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    """
    Create a TestClient with stable environment settings.

    We set required auth secrets to non-placeholder values and clear the settings
    cache so configuration validation passes consistently in tests.
    """
    settings_module.get_settings.cache_clear()
    monkeypatch.setenv("DEMO_PASSWORD", "test-demo-password")
    monkeypatch.setenv("AUTH_TOKEN_SECRET", "test-auth-secret")
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.setenv("DEBUG", "true")

    try:
        app = create_app()
        with TestClient(app) as test_client:
            yield test_client
    finally:
        settings_module.get_settings.cache_clear()


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "ok"
    assert data["environment"] == "local"
    assert data["version"] == __version__
    assert data["api_version"] == __api_version__


def test_root_endpoint(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    data = response.json()

    assert data["name"] == "Enterprise Agentic AI API"
    assert data["version"] == __version__
    assert data["api_version"] == __api_version__
    assert data["health"] == "/health"
    assert data["environment"] == "local"


def test_cors_headers(client: TestClient) -> None:
    origin = "http://localhost:3000"

    response = client.get("/health", headers={"Origin": origin})

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin
    assert response.headers.get("access-control-allow-credentials") == "true"
    assert response.headers.get("access-control-expose-headers") == "X-Request-ID"


def test_cors_preflight_options(client: TestClient) -> None:
    origin = "http://localhost:3000"

    response = client.options(
        "/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin
    assert "GET" in response.headers.get("access-control-allow-methods", "")
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_404_response(client: TestClient) -> None:
    response = client.get("/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}
