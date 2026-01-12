"""
Rate limiting middleware using slowapi.

This module provides IP-based rate limiting for API endpoints to prevent abuse
and ensure fair usage across all clients. It integrates with FastAPI using the
slowapi library and provides user-friendly error responses.

Features:
    - IP-based rate limiting using get_remote_address
    - Configurable rate limit via settings (default: 10 requests/minute)
    - User-friendly error messages (not technical details)
    - Retry-After header for client handling
    - Structured logging of rate limit events

Usage:
    # In main.py
    from src.api.middleware.rate_limit import (
        get_limiter,
        rate_limit_exceeded_handler,
    )
    from slowapi.errors import RateLimitExceeded

    limiter = get_limiter()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    # On route handlers
    @app.post("/api/chat")
    @limiter.limit(DEFAULT_RATE_LIMIT)
    async def chat(request: Request):
        ...

Reference:
    - slowapi documentation: https://slowapi.readthedocs.io/
    - [backend.mdc] for middleware patterns
    - [_security.mdc] for rate limiting requirements
"""

from __future__ import annotations

import structlog
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.requests import Request
from starlette.responses import JSONResponse

# Module logger
logger = structlog.get_logger(__name__)

# =============================================================================
# Rate Limiter Configuration
# =============================================================================

# Default rate limit: 10 requests per minute per IP address
# This can be overridden on specific routes using @limiter.limit("5/minute")
DEFAULT_RATE_LIMIT = "10/minute"

# Create limiter instance with IP-based key function
# Uses X-Forwarded-For header when behind a proxy (App Runner, CloudFront)
_limiter = Limiter(key_func=get_remote_address)


# =============================================================================
# Exception Handler
# =============================================================================


async def rate_limit_exceeded_handler(
    request: Request,
    exc: RateLimitExceeded,
) -> JSONResponse:
    """
    Handle rate limit exceeded exceptions with user-friendly response.

    Returns a 429 Too Many Requests response with:
    - User-friendly error message (no technical details)
    - Retry-After header indicating when the client can retry
    - JSON body with detail and retry_after fields

    Args:
        request: The incoming request that exceeded the rate limit.
        exc: The RateLimitExceeded exception containing limit details.

    Returns:
        JSONResponse with status 429 and retry information.

    Example Response:
        HTTP/1.1 429 Too Many Requests
        Content-Type: application/json
        Retry-After: 60

        {
            "detail": "Rate limit exceeded. Please wait before making more requests.",
            "retry_after": "60 per 1 minute"
        }
    """
    # Extract retry-after value from exception detail
    # slowapi formats this as "X per Y time_unit" (e.g., "10 per 1 minute")
    retry_after_detail = str(exc.detail) if exc.detail else "60"

    # Parse numeric retry value for header (extract first number if present)
    # For "10 per 1 minute", we want to tell client to wait ~60 seconds
    try:
        # Default to 60 seconds if we can't parse
        retry_after_seconds = "60"
        if "minute" in retry_after_detail.lower():
            retry_after_seconds = "60"
        elif "second" in retry_after_detail.lower():
            # Extract the number from formats like "5 per 1 second"
            parts = retry_after_detail.split()
            if parts:
                retry_after_seconds = parts[0]
        elif "hour" in retry_after_detail.lower():
            retry_after_seconds = "3600"
    except (ValueError, IndexError):
        retry_after_seconds = "60"

    # Log rate limit event for monitoring
    # get_remote_address can return None if no client info available
    client_ip = get_remote_address(request) or "unknown"
    logger.warning(
        "rate_limit_exceeded",
        client_ip=client_ip,
        path=str(request.url.path),
        method=request.method,
        limit_detail=retry_after_detail,
    )

    return JSONResponse(
        status_code=429,
        content={
            "detail": "Rate limit exceeded. Please wait before making more requests.",
            "retry_after": retry_after_detail,
            "status_code": 429,
            "error_type": "rate_limit",
        },
        headers={"Retry-After": retry_after_seconds},
    )


# =============================================================================
# Public API
# =============================================================================


def get_limiter() -> Limiter:
    """
    Get the rate limiter instance.

    Returns the configured slowapi Limiter instance. Use this to add
    the limiter to FastAPI app state and to apply rate limits to routes.

    Returns:
        Limiter: The configured slowapi Limiter instance.

    Example:
        limiter = get_limiter()
        app.state.limiter = limiter

        @app.post("/api/chat")
        @limiter.limit("10/minute")
        async def chat(request: Request):
            ...
    """
    return _limiter


def get_rate_limit_string(requests_per_minute: int | None = None) -> str:
    """
    Get a rate limit string for use with @limiter.limit().

    Generates a slowapi-compatible rate limit string in the format "N/minute".
    If no value is provided, uses the DEFAULT_RATE_LIMIT.

    Args:
        requests_per_minute: Number of requests allowed per minute.
            If None, returns DEFAULT_RATE_LIMIT.

    Returns:
        Rate limit string (e.g., "10/minute").

    Example:
        from src.config import get_settings

        settings = get_settings()
        rate_limit = get_rate_limit_string(settings.rate_limit_per_minute)

        @limiter.limit(rate_limit)
        async def my_endpoint(request: Request):
            ...
    """
    if requests_per_minute is None:
        return DEFAULT_RATE_LIMIT
    return f"{requests_per_minute}/minute"


# Re-export commonly used items for convenience
limiter = _limiter


__all__ = [
    "DEFAULT_RATE_LIMIT",
    "get_limiter",
    "get_rate_limit_string",
    "limiter",
    "rate_limit_exceeded_handler",
    "RateLimitExceeded",
]
