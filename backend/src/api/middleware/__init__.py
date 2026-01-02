"""
Middleware package for request/response processing.

This package contains middleware components for the FastAPI application:
- logging: CloudWatch-compatible structlog configuration

Usage:
    from src.api.middleware.logging import configure_logging, bind_conversation_context

    # Configure logging at startup
    configure_logging(environment="aws", log_level="INFO")

    # Bind conversation context for request tracing
    bind_conversation_context(conversation_id="abc123")
"""

from src.api.middleware.logging import (
    bind_conversation_context,
    clear_context,
    configure_logging,
    get_logger,
)

__all__ = [
    "configure_logging",
    "get_logger",
    "bind_conversation_context",
    "clear_context",
]
