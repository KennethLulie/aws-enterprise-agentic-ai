"""API surface and CORS behavior smoke tests."""

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
    """Health endpoint returns status payload with versions and environment."""
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()

    # Accept "ok" or "degraded" - both indicate service is functional
    # "degraded" occurs when external deps (database, bedrock) are unavailable
    assert data["status"] in ("ok", "degraded")
    assert data["environment"] == "local"
    assert data["version"] == __version__
    assert data["api_version"] == __api_version__


def test_root_endpoint(client: TestClient) -> None:
    """Root endpoint returns service metadata."""
    response = client.get("/")

    assert response.status_code == 200
    data = response.json()

    assert data["name"] == "Enterprise Agentic AI API"
    assert data["version"] == __version__
    assert data["api_version"] == __api_version__
    assert data["health"] == "/health"
    assert data["environment"] == "local"


def test_chat_post_returns_conversation_id(client: TestClient) -> None:
    """POST /api/chat returns a conversation id for streaming."""

    login = client.post("/api/login", json={"password": "test-demo-password"})
    assert login.status_code == 200

    response = client.post("/api/chat", json={"message": "hello world"})

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["conversationId"], str)
    assert data["conversationId"]


def test_cors_headers(client: TestClient) -> None:
    """CORS headers allow browser access from configured origin."""
    origin = "http://localhost:3000"

    response = client.get("/health", headers={"Origin": origin})

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin
    assert response.headers.get("access-control-allow-credentials") == "true"
    assert response.headers.get("access-control-expose-headers") == "Content-Type"


def test_cors_preflight_options(client: TestClient) -> None:
    """CORS preflight responds with allowed methods, headers, and credentials."""
    origin = "http://localhost:3000"

    response = client.options(
        "/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin
    assert response.headers.get("access-control-allow-credentials") == "true"

    # Verify allowed methods (GET, POST, OPTIONS for Phase 1a)
    allowed_methods = response.headers.get("access-control-allow-methods", "")
    assert "GET" in allowed_methods
    assert "POST" in allowed_methods

    # Verify allowed headers (Content-Type, Authorization, Cookie for auth)
    allowed_headers = response.headers.get("access-control-allow-headers", "")
    assert "content-type" in allowed_headers.lower()


def test_404_response(client: TestClient) -> None:
    """Unknown routes return FastAPI default 404 JSON shape."""
    response = client.get("/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}
