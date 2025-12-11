"""
API routes package for endpoint definitions.

This package contains all API route definitions organized by functionality
and API version. Routes are implemented as FastAPI routers that can be
included in the main application.

Package Structure:
    - health.py: Health check endpoints (Phase 0)
    - v1/: Version 1 API endpoints (Phase 1b+)
        - __init__.py: V1 router aggregation
        - chat.py: Chat/conversation endpoints

Route Organization:
    Phase 0 (Current):
        - /health: Basic health check (no auth)
        - Routes defined directly in main.py for simplicity

    Phase 1b+:
        - /health: Enhanced health check with dependency status
        - /api/v1/chat: Chat endpoints with streaming
        - /api/v1/conversations: Conversation management

Usage:
    # Import individual routers
    from src.api.routes.health import router as health_router

    # Include in FastAPI app
    app.include_router(health_router)

    # Or import all routers (Phase 1b+)
    from src.api.routes import health_router, v1_router
    app.include_router(health_router)
    app.include_router(v1_router, prefix="/api/v1")

Example:
    from fastapi import FastAPI
    from src.api.routes.health import router as health_router

    app = FastAPI()
    app.include_router(health_router)

    # Health endpoint accessible at: GET /health
"""

from __future__ import annotations

# Import routers for easy access
from src.api.routes.auth import router as auth_router
from src.api.routes.health import router as health_router

# Phase 1b+: v1_router will be added after v1/ routes are created

__all__ = [
    "health_router",
    "auth_router",
]
