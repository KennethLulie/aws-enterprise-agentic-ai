"""
Health check endpoint for API monitoring.

This module provides the health check endpoint used by load balancers,
deployment pipelines, and developers to verify the API is running correctly.

Phase 0 (Current):
    - Simple health check returning status and environment
    - No dependency checks (database, external services)
    - No authentication required

Phase 1b+ (Planned):
    - Enhanced health checks with dependency status
    - Database connectivity check
    - External service availability

Usage:
    from src.api.routes.health import router as health_router

    app = FastAPI()
    app.include_router(health_router)

    # Endpoint accessible at: GET /health
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter

from src.api import __api_version__, __version__
from src.config import get_settings

# =============================================================================
# Response Models
# =============================================================================


class HealthResponse(BaseModel):
    """
    Response model for health check endpoint.

    Attributes:
        status: Current health status ("ok" or "degraded")
        environment: Runtime environment ("local" or "aws")
        version: Application version
        api_version: API version
    """

    status: str = Field(
        ...,
        description="Current health status",
        examples=["ok"],
    )
    environment: str = Field(
        ...,
        description="Runtime environment (local or aws)",
        examples=["local"],
    )
    version: str = Field(
        ...,
        description="Application version",
        examples=["0.1.0"],
    )
    api_version: str = Field(
        ...,
        description="API version",
        examples=["v1"],
    )


# =============================================================================
# Router Definition
# =============================================================================

router = APIRouter(
    tags=["Health"],
    responses={
        200: {"description": "API is healthy"},
        503: {"description": "Service unavailable (Phase 1b+)"},
    },
)


# =============================================================================
# Endpoints
# =============================================================================


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Check if the API is running and return environment info.",
)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.

    Returns the current status of the API along with environment information.
    This endpoint is accessible without authentication and is used by:

    - Load balancers for health monitoring
    - Deployment pipelines for smoke tests
    - Developers for quick status checks
    - Container orchestration (Docker, ECS, App Runner)

    Returns:
        HealthResponse: Status information including environment and version.

    Example Response:
        ```json
        {
            "status": "ok",
            "environment": "local",
            "version": "0.1.0",
            "api_version": "v1"
        }
        ```
    """
    settings = get_settings()
    return HealthResponse(
        status="ok",
        environment=settings.environment,
        version=__version__,
        api_version=__api_version__,
    )


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "router",
    "HealthResponse",
]
