"""
Middleware package for request/response processing.

This package contains middleware components for the FastAPI application:
- logging: CloudWatch-compatible structlog configuration
- rate_limit: IP-based rate limiting using slowapi

Usage:
    from src.api.middleware.logging import configure_logging, bind_conversation_context
    from src.api.middleware.rate_limit import get_limiter, rate_limit_exceeded_handler

    # Configure logging at startup
    configure_logging(environment="aws", log_level="INFO")

    # Bind conversation context for request tracing
    bind_conversation_context(conversation_id="abc123")

    # Configure rate limiting
    limiter = get_limiter()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
"""

from src.api.middleware.logging import (
    bind_conversation_context,
    clear_context,
    configure_logging,
    get_logger,
)
from src.api.middleware.rate_limit import (
    DEFAULT_RATE_LIMIT,
    RateLimitExceeded,
    get_limiter,
    get_rate_limit_string,
    limiter,
    rate_limit_exceeded_handler,
)

__all__ = [
    # Logging
    "configure_logging",
    "get_logger",
    "bind_conversation_context",
    "clear_context",
    # Rate limiting
    "DEFAULT_RATE_LIMIT",
    "RateLimitExceeded",
    "get_limiter",
    "get_rate_limit_string",
    "limiter",
    "rate_limit_exceeded_handler",
]
