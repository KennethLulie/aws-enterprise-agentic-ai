"""
FastAPI application factory and configuration.

This module creates and configures the FastAPI application instance for the
backend API. It sets up middleware, error handling, and routes following
best practices for Phase 0 (local development).

The application uses the modern lifespan context manager pattern (recommended
in FastAPI 0.109+) instead of deprecated on_event decorators for startup/shutdown.

Features (Phase 0):
    - CORS middleware for frontend communication (localhost:3000)
    - Basic error handling with user-friendly messages
    - Health check endpoint (/health)
    - Configuration validation on startup
    - Structured for future route additions

Usage:
    # Run directly with uvicorn
    uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

    # Or import and use programmatically
    from src.api.main import app, create_app

    # Create a new app instance (useful for testing)
    test_app = create_app()
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.api import __api_version__, __version__
from src.api.routes import auth_router, health_router
from src.config import Settings, get_settings, validate_config

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

# Configure module logger
logger = logging.getLogger(__name__)


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
    logger.info("Starting application...")

    try:
        # Validate configuration on startup
        validation_result = validate_config()
        settings = get_settings()

        logger.info(
            f"Configuration validated. Environment: {settings.environment}, "
            f"Debug: {settings.debug}"
        )

        # Log any configuration warnings
        for warning in validation_result.get("warnings", []):
            logger.warning(f"Config warning: {warning}")

        logger.info(
            f"Application started successfully. "
            f"Version: {__version__}, API Version: {__api_version__}"
        )

    except ValueError as e:
        logger.error(f"Configuration validation failed: {e}")
        raise

    yield  # Application runs here

    # === Shutdown ===
    logger.info("Shutting down application...")
    # Add cleanup logic here when needed (e.g., close DB connections)
    logger.info("Application shutdown complete.")


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

    Allows the frontend (localhost:3000 in development) to communicate with
    the backend API. In production, the allowed origins will include the
    CloudFront distribution URL.

    Args:
        app: The FastAPI application instance.
        settings: Application settings containing CORS configuration.
    """
    cors_origins = settings.get_cors_origins_list()

    logger.info(f"Configuring CORS for origins: {cors_origins}")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )


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
            f"HTTP exception: {exc.status_code} - {exc.detail}",
            extra={"path": str(request.url.path)},
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
            f"Validation error: {exc}",
            extra={"path": str(request.url.path)},
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
            f"Unhandled exception: {type(exc).__name__}",
            extra={"path": str(request.url.path)},
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
        - Health check router (/health)
        - Root endpoint (/)

    Future additions (Phase 1b+):
        - Chat routes (/api/v1/chat)
        - Additional versioned endpoints

    Args:
        app: The FastAPI application instance.
    """
    # Include routers
    app.include_router(auth_router)
    app.include_router(health_router)

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
