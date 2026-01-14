"""
API package for the FastAPI backend application.

This package contains the FastAPI application instance, route definitions,
middleware configurations, and API-related utilities. It follows a modular
structure optimized for maintainability and scalability.

Package Structure:
    - main.py: FastAPI application factory and configuration
    - routes/: API endpoint route definitions
        - health.py: Health check endpoints
        - v1/: Version 1 API endpoints (Phase 1b+)
            - chat.py: Chat/conversation endpoints
    - middleware/: Request/response middleware
        - logging.py: Structured logging middleware (Phase 1b+)
        - rate_limit.py: Rate limiting middleware (Phase 1b+)
        - error_handler.py: Global error handling (Phase 1b+)

Usage:
    from src.api import create_app

    # Create the FastAPI application instance
    app = create_app()

    # Or import the pre-configured app instance
    from src.api.main import app

    # Run with uvicorn
    # uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

Phase 0 Features:
    - Basic FastAPI app with CORS middleware
    - Health check endpoint (/health)
    - Configuration validation on startup
    - Error handling with user-friendly messages

Phase 1b+ Features (planned):
    - API versioning (/api/v1/)
    - Structured logging with structlog
    - Rate limiting with slowapi
    - Enhanced health checks with dependency status

Example:
    # Basic usage in Phase 0
    from src.api.main import app
    from src.api.routes.health import router as health_router

    # Health endpoint is automatically included at /health on the configured host/port
"""

from __future__ import annotations

# Version information for the API
# Increment this when deploying to help verify App Runner has the latest code
__version__ = "1.0.0"  # Phase 1b - PostgresSaver + System Prompt
__api_version__ = "v1"

# Public API exports
# Import app and factory function from main module
from src.api.main import app, create_app

__all__ = [
    "__version__",
    "__api_version__",
    "app",
    "create_app",
]
