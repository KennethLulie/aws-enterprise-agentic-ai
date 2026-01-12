"""
FastAPI application factory and configuration.

This module creates and configures the FastAPI application instance for the
backend API. It sets up middleware, error handling, and routes following
best practices for Phase 1b (production hardening).

The application uses the modern lifespan context manager pattern (recommended
in FastAPI 0.109+) instead of deprecated on_event decorators for startup/shutdown.

Features:
    - CORS middleware with configurable origins (ALLOWED_ORIGINS env var)
    - Rate limiting middleware (10 requests/minute per IP via slowapi)
    - Cookie-based authentication with credentials support
    - User-friendly error handling with consistent response format
    - Health check endpoint (/health)
    - Versioned API routes (/api/v1/chat) with backward compatibility (/api/chat)
    - Configuration validation on startup (including AWS Secrets Manager)
    - Structured for future route additions

CORS Configuration:
    Origins are configured via ALLOWED_ORIGINS environment variable:
    - Local: http://localhost:3000 (default)
    - Production: https://xxxxx.cloudfront.net (set via App Runner env)

Rate Limiting:
    IP-based rate limiting is configured via slowapi:
    - Default: 10 requests per minute per IP address
    - Configurable per-route using @limiter.limit() decorator
    - User-friendly error messages (not technical details)
    - Retry-After header included in 429 responses

Usage:
    # Run directly with uvicorn
    uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

    # Or import and use programmatically
    from src.api.main import app, create_app

    # Create a new app instance (useful for testing)
    test_app = create_app()
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

import structlog
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from slowapi.errors import RateLimitExceeded

from src.api import __api_version__, __version__
from src.api.middleware.logging import configure_logging
from src.api.middleware.rate_limit import limiter, rate_limit_exceeded_handler
from src.api.routes import auth_router, chat_router, health_router
from src.api.routes.v1 import router as v1_router
from src.config import Settings, get_settings, validate_config

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

# Module logger - configured after configure_logging() is called
logger = structlog.get_logger(__name__)


# =============================================================================
# Response Models
# =============================================================================


class ErrorResponse(BaseModel):
    """Response model for error responses."""

    detail: str
    status_code: int
    error_type: str


# =============================================================================
# Lifespan Context Manager
# =============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Manage application lifespan events.

    This context manager handles startup and shutdown events for the FastAPI
    application. It replaces the deprecated @app.on_event decorators.

    Startup:
        - Validates configuration settings
        - Logs startup information
        - Initializes any required resources

    Shutdown:
        - Cleans up resources
        - Logs shutdown information

    Args:
        app: The FastAPI application instance.

    Yields:
        None: Control is yielded to the application after startup.

    Raises:
        ValueError: If configuration validation fails.
    """
    # === Startup ===
    # Configure logging FIRST before any log statements
    settings = get_settings()
    configure_logging(
        environment=settings.environment,
        log_level=settings.log_level,
    )

    logger.info("application_starting")

    try:
        # Validate configuration on startup
        validation_result = validate_config()

        logger.info(
            "configuration_validated",
            environment=settings.environment,
            debug=settings.debug,
        )

        # Log any configuration warnings
        for warning in validation_result.get("warnings", []):
            logger.warning("config_warning", message=warning)

        logger.info(
            "application_started",
            version=__version__,
            api_version=__api_version__,
        )

    except ValueError as e:
        logger.error("configuration_validation_failed", error=str(e))
        raise

    yield  # Application runs here

    # === Shutdown ===
    logger.info("application_shutting_down")
    # Add cleanup logic here when needed (e.g., close DB connections)
    logger.info("application_shutdown_complete")


# =============================================================================
# Application Factory
# =============================================================================


def create_app(settings: Settings | None = None) -> FastAPI:
    """
    Create and configure a FastAPI application instance.

    This factory function creates a new FastAPI application with all middleware,
    error handlers, and routes configured. It can be used to create the main
    application or test instances with custom settings.

    Args:
        settings: Optional Settings instance. If not provided, settings are
            loaded from environment variables.

    Returns:
        FastAPI: Configured FastAPI application instance.

    Example:
        # Create app with default settings
        app = create_app()

        # Create app with custom settings (useful for testing)
        test_settings = Settings(environment="local", debug=True)
        test_app = create_app(settings=test_settings)
    """
    if settings is None:
        settings = get_settings()

    # Create FastAPI application
    application = FastAPI(
        title="Enterprise Agentic AI API",
        description=(
            "Enterprise-grade agentic AI backend powered by LangGraph and AWS Bedrock. "
            "Provides chat interactions with multi-tool orchestration, RAG retrieval, "
            "and real-time streaming responses."
        ),
        version=__version__,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None,
        lifespan=lifespan,
    )

    # Configure middleware
    _configure_cors(application, settings)
    _configure_rate_limiting(application)

    # Register error handlers
    _register_error_handlers(application)

    # Register routes
    _register_routes(application)

    return application


# =============================================================================
# Middleware Configuration
# =============================================================================


def _configure_cors(app: FastAPI, settings: Settings) -> None:
    """
    Configure CORS middleware for cross-origin requests.

    Allows the frontend to communicate with the backend API:
    - Local development: http://localhost:3000, http://127.0.0.1:3000
    - Production: CloudFront distribution URL (https://xxxxx.cloudfront.net)

    Origins are configured via ALLOWED_ORIGINS environment variable (comma-separated)
    or the cors_origins setting. Defaults support local development out of the box.

    Args:
        app: The FastAPI application instance.
        settings: Application settings containing CORS configuration.

    Note:
        allow_credentials=True is required for cookie-based authentication.
        This means allow_origins cannot be ["*"] - specific origins must be listed.
    """
    cors_origins = settings.get_cors_origins_list()

    logger.info("cors_configured", origins=cors_origins)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "Cookie"],
        expose_headers=["Content-Type"],
    )


def _configure_rate_limiting(app: FastAPI) -> None:
    """
    Configure rate limiting middleware using slowapi.

    Sets up IP-based rate limiting to prevent abuse and ensure fair usage.
    The limiter is added to app.state so it can be accessed by route decorators.

    Rate limits are applied per-route using the @limiter.limit() decorator.
    The default rate limit is 10 requests per minute per IP address.

    Args:
        app: The FastAPI application instance.

    Note:
        We use our custom rate_limit_exceeded_handler (from rate_limit.py) for
        user-friendly error messages, NOT slowapi's default handler.
    """
    # Add limiter to app state so it can be accessed by route decorators
    app.state.limiter = limiter

    # Register our custom exception handler for rate limit errors
    # This provides user-friendly messages instead of technical details
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    logger.info("rate_limiting_configured", default_limit="10/minute")


# =============================================================================
# Error Handlers
# =============================================================================


def _register_error_handlers(app: FastAPI) -> None:
    """
    Register global error handlers for the application.

    Provides user-friendly error responses for various exception types.
    In production, internal error details are hidden from users.

    Args:
        app: The FastAPI application instance.
    """

    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request, exc: HTTPException
    ) -> JSONResponse:
        """Handle HTTP exceptions with consistent response format."""
        logger.warning(
            "http_exception",
            status_code=exc.status_code,
            detail=exc.detail,
            path=str(request.url.path),
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.detail,
                "status_code": exc.status_code,
                "error_type": "http_error",
            },
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        """Handle validation errors with user-friendly messages."""
        logger.warning(
            "validation_error",
            error=str(exc),
            path=str(request.url.path),
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": str(exc),
                "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY,
                "error_type": "validation_error",
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """
        Handle unexpected exceptions.

        In production, hides internal error details from users while logging
        the full exception for debugging.
        """
        settings = get_settings()

        # Log full exception details
        logger.exception(
            "unhandled_exception",
            exception_type=type(exc).__name__,
            path=str(request.url.path),
        )

        # Return user-friendly message (hide details in production)
        detail = str(exc) if settings.debug else "An unexpected error occurred."

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": detail,
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "error_type": "internal_error",
            },
        )


# =============================================================================
# Route Registration
# =============================================================================


def _register_routes(app: FastAPI) -> None:
    """
    Register API routes with the application.

    Currently registers:
        - Auth routes (/api/login, /api/logout, /api/me)
        - Chat routes (/api/chat) - legacy, kept for backward compatibility
        - V1 API routes (/api/v1/chat) - versioned endpoints
        - Health check router (/health)
        - Root endpoint (/)

    Args:
        app: The FastAPI application instance.
    """
    # Include routers
    app.include_router(auth_router)
    app.include_router(chat_router)  # Legacy /api/chat (backward compatibility)
    app.include_router(health_router)

    # V1 API routes - versioned endpoints
    # CRITICAL: prefix="/api/v1" ensures routes are mounted at /api/v1/chat
    app.include_router(v1_router, prefix="/api/v1")

    # Root endpoint for basic connectivity check
    @app.get(
        "/",
        tags=["Root"],
        summary="API Root",
        description="Root endpoint returning basic API information.",
    )
    async def root() -> dict[str, Any]:
        """
        Root endpoint.

        Returns basic API information and links to documentation.

        Returns:
            dict: API name, version, and documentation links.
        """
        settings = get_settings()
        return {
            "name": "Enterprise Agentic AI API",
            "version": __version__,
            "api_version": __api_version__,
            "environment": settings.environment,
            "docs": "/docs" if settings.debug else None,
            "health": "/health",
        }


# =============================================================================
# Application Instance
# =============================================================================

# Create the default application instance
# This is what uvicorn uses when running: uvicorn src.api.main:app
app = create_app()


# =============================================================================
# Development Server
# =============================================================================

if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "src.api.main:app",
        host=settings.backend_host,
        port=settings.backend_port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
