"""
Versioned API routes (v1).

This package contains version 1 API endpoints, providing a stable interface
for production use. The v1 prefix (/api/v1) is applied when including this
router in the main application.

Endpoints:
    - /chat: Chat endpoints with streaming (via chat.router)

Usage:
    # In main.py
    from src.api.routes.v1 import router as v1_router

    app.include_router(v1_router, prefix="/api/v1")

    # Endpoints will be available at:
    # - POST /api/v1/chat
    # - GET /api/v1/chat (SSE streaming)

Note:
    The /api/v1 prefix is NOT included in this router - it is applied
    when including the router in main.py. This allows flexibility in
    mounting the same routes at different prefixes if needed.
"""

from __future__ import annotations

from fastapi import APIRouter

from src.api.routes.v1 import chat

# Create the v1 router
# No prefix here - prefix="/api/v1" is applied in main.py
router = APIRouter(tags=["v1"])

# Include sub-routers
router.include_router(chat.router)

__all__ = ["router"]
