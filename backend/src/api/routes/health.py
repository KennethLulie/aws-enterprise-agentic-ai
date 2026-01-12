"""
Health check endpoint for API monitoring with dependency checks.

This module provides the health check endpoint used by load balancers,
deployment pipelines, and developers to verify the API is running correctly.

Features:
    - Basic health status (ok, degraded, error)
    - Environment and version information
    - Dependency checks with graceful degradation:
        - Database connectivity with latency tracking
        - Bedrock availability check
    - Non-blocking checks with configurable timeouts
    - No authentication required

Status Logic:
    - "ok": All checks pass
    - "degraded": Some non-critical checks fail but service can function
    - "error": Critical checks fail (not used currently - all checks optional)

Usage:
    from src.api.routes.health import router as health_router

    app = FastAPI()
    app.include_router(health_router)

    # Endpoint accessible at: GET /health

Example Response:
    {
        "status": "ok",
        "environment": "local",
        "version": "0.1.0",
        "api_version": "v1",
        "checks": {
            "database": {"status": "ok", "latency_ms": 50},
            "bedrock": {"status": "ok"}
        }
    }
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import structlog
from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import text

from src.api import __api_version__, __version__
from src.config import get_settings
from src.db import get_engine

# Module logger
logger = structlog.get_logger(__name__)

# Timeout for dependency checks (seconds)
CHECK_TIMEOUT_SECONDS = 5.0


# =============================================================================
# Response Models
# =============================================================================


class DependencyCheckResult(BaseModel):
    """Result of a single dependency check."""

    status: str = Field(
        ...,
        description="Check status: ok, error, or skipped",
        examples=["ok"],
    )
    latency_ms: int | None = Field(
        default=None,
        description="Latency in milliseconds (for database checks)",
        examples=[50],
    )
    error: str | None = Field(
        default=None,
        description="Error message if check failed",
        examples=[None],
    )


class DependencyChecks(BaseModel):
    """Container for all dependency check results."""

    database: DependencyCheckResult = Field(
        ...,
        description="Database connectivity check result",
    )
    bedrock: DependencyCheckResult = Field(
        ...,
        description="AWS Bedrock availability check result",
    )


class HealthResponse(BaseModel):
    """
    Response model for health check endpoint.

    Attributes:
        status: Overall health status (ok, degraded, or error)
        environment: Runtime environment (local or aws)
        version: Application version
        api_version: API version
        checks: Results of individual dependency checks
    """

    status: str = Field(
        ...,
        description="Overall health status: ok, degraded, or error",
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
    checks: DependencyChecks = Field(
        ...,
        description="Results of dependency checks",
    )


# =============================================================================
# Dependency Check Functions
# =============================================================================


async def check_database() -> DependencyCheckResult:
    """
    Check database connectivity with latency measurement.

    Attempts to execute a simple SELECT 1 query to verify the database
    connection is working. Measures latency for monitoring.

    Returns:
        DependencyCheckResult with status and latency_ms if successful,
        or status="error" with error message if failed,
        or status="skipped" if database is not configured.

    Note:
        This is a non-blocking check that runs in a thread pool to avoid
        blocking the event loop.
    """
    try:
        engine = get_engine()

        if engine is None:
            # Database not configured (local dev without DATABASE_URL)
            return DependencyCheckResult(
                status="skipped",
                error="Database not configured",
            )

        # Run the blocking database operation in a thread pool
        def _execute_check() -> tuple[bool, int]:
            start_time = time.perf_counter()
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            return True, elapsed_ms

        # Execute with timeout
        loop = asyncio.get_event_loop()
        success, latency_ms = await asyncio.wait_for(
            loop.run_in_executor(None, _execute_check),
            timeout=CHECK_TIMEOUT_SECONDS,
        )

        return DependencyCheckResult(
            status="ok",
            latency_ms=latency_ms,
        )

    except asyncio.TimeoutError:
        logger.warning("database_check_timeout", timeout_seconds=CHECK_TIMEOUT_SECONDS)
        return DependencyCheckResult(
            status="error",
            error=f"Database check timed out after {CHECK_TIMEOUT_SECONDS}s",
        )

    except Exception as exc:
        logger.warning(
            "database_check_failed",
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return DependencyCheckResult(
            status="error",
            error=str(exc),
        )


async def check_bedrock() -> DependencyCheckResult:
    """
    Check AWS Bedrock availability.

    Attempts to verify Bedrock is accessible by listing foundation models
    or checking credentials. This is a lightweight check that doesn't
    invoke a model.

    Returns:
        DependencyCheckResult with status="ok" if Bedrock is accessible,
        status="error" with error message if failed,
        or status="skipped" if not in AWS environment.

    Note:
        In local development without AWS credentials, this check returns
        "skipped" rather than failing, allowing graceful degradation.
    """
    try:
        settings = get_settings()

        # Check if we have AWS credentials configured
        # In AWS environment, IAM role provides credentials
        # In local, we need explicit credentials
        if not settings.is_aws() and not (
            settings.aws_access_key_id and settings.aws_secret_access_key
        ):
            return DependencyCheckResult(
                status="skipped",
                error="AWS credentials not configured",
            )

        # Import boto3 here to avoid import errors if not installed
        import boto3  # type: ignore[import-untyped]

        def _check_bedrock() -> bool:
            """Verify Bedrock access by listing models."""
            # Create Bedrock client
            client_kwargs: dict[str, Any] = {
                "service_name": "bedrock",
                "region_name": settings.aws_region,
            }

            # Add explicit credentials for local development
            if not settings.is_aws():
                if settings.aws_access_key_id:
                    client_kwargs["aws_access_key_id"] = settings.aws_access_key_id
                if settings.aws_secret_access_key:
                    client_kwargs["aws_secret_access_key"] = (
                        settings.aws_secret_access_key.get_secret_value()
                    )

            client = boto3.client(**client_kwargs)

            # List foundation models (lightweight operation)
            # Just check if we can make the API call, limit to 1 result
            client.list_foundation_models(maxResults=1)
            return True

        # Execute with timeout
        loop = asyncio.get_event_loop()
        await asyncio.wait_for(
            loop.run_in_executor(None, _check_bedrock),
            timeout=CHECK_TIMEOUT_SECONDS,
        )

        return DependencyCheckResult(status="ok")

    except asyncio.TimeoutError:
        logger.warning("bedrock_check_timeout", timeout_seconds=CHECK_TIMEOUT_SECONDS)
        return DependencyCheckResult(
            status="error",
            error=f"Bedrock check timed out after {CHECK_TIMEOUT_SECONDS}s",
        )

    except ImportError:
        return DependencyCheckResult(
            status="skipped",
            error="boto3 not available",
        )

    except Exception as exc:
        logger.warning(
            "bedrock_check_failed",
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return DependencyCheckResult(
            status="error",
            error=str(exc),
        )


def determine_overall_status(checks: DependencyChecks) -> str:
    """
    Determine overall health status based on dependency check results.

    Status Logic:
        - "ok": All checks pass (status="ok" or "skipped")
        - "degraded": Some checks fail but service can still function
        - "error": Critical failures (not currently used - all checks optional)

    Args:
        checks: Results of all dependency checks.

    Returns:
        Overall status string: "ok", "degraded", or "error".
    """
    all_checks = [checks.database, checks.bedrock]
    error_checks = [c for c in all_checks if c.status == "error"]

    if not error_checks:
        return "ok"

    # Currently all checks are optional, so errors result in "degraded"
    # If we add critical checks in the future, check them here for "error" status
    return "degraded"


# =============================================================================
# Router Definition
# =============================================================================

router = APIRouter(
    tags=["Health"],
    responses={
        200: {"description": "API is healthy or degraded"},
        503: {"description": "Service unavailable"},
    },
)


# =============================================================================
# Endpoints
# =============================================================================


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Check API status and dependency health.",
)
async def health_check() -> HealthResponse:
    """
    Health check endpoint with dependency status.

    Returns the current status of the API along with environment information
    and results of dependency checks (database, Bedrock).

    This endpoint is accessible without authentication and is used by:
    - Load balancers for health monitoring
    - Deployment pipelines for smoke tests
    - Developers for quick status checks
    - Container orchestration (Docker, ECS, App Runner)

    Dependency checks are non-blocking with 5-second timeouts and fail
    gracefully. A failed dependency check results in "degraded" status
    rather than complete failure.

    Returns:
        HealthResponse: Status information including environment, version,
            and dependency check results.

    Example Response:
        ```json
        {
            "status": "ok",
            "environment": "local",
            "version": "0.1.0",
            "api_version": "v1",
            "checks": {
                "database": {"status": "ok", "latency_ms": 50},
                "bedrock": {"status": "ok"}
            }
        }
        ```
    """
    settings = get_settings()

    # Run dependency checks concurrently
    db_result, bedrock_result = await asyncio.gather(
        check_database(),
        check_bedrock(),
    )

    checks = DependencyChecks(
        database=db_result,
        bedrock=bedrock_result,
    )

    overall_status = determine_overall_status(checks)

    # Log health check result for monitoring
    logger.debug(
        "health_check_completed",
        status=overall_status,
        database_status=db_result.status,
        bedrock_status=bedrock_result.status,
    )

    return HealthResponse(
        status=overall_status,
        environment=settings.environment,
        version=__version__,
        api_version=__api_version__,
        checks=checks,
    )


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "router",
    "HealthResponse",
    "DependencyChecks",
    "DependencyCheckResult",
    "check_database",
    "check_bedrock",
]
