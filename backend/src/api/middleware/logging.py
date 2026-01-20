"""
Logging configuration for CloudWatch compatibility.

This module configures structlog for JSON-formatted output that works well
with CloudWatch Logs Insights. It should be initialized once at application
startup via configure_logging().

Features:
    - JSON-formatted output for CloudWatch Logs Insights queries
    - Environment-aware log levels (DEBUG for local, INFO for aws)
    - Automatic context binding (timestamp, log level, logger name)
    - Integration with standard library logging for third-party libraries
    - Sensitive data filtering (API keys, passwords, secrets)

CloudWatch Logs Insights Query Examples:
    # Find errors in the last hour
    fields @timestamp, @message
    | filter level = "error"
    | sort @timestamp desc
    | limit 100

    # Search by conversation_id
    fields @timestamp, @message
    | filter conversation_id = "abc123"
    | sort @timestamp asc

Usage:
    from src.api.middleware.logging import configure_logging

    # In application startup (main.py lifespan)
    configure_logging(environment="aws", log_level="INFO")

    # In modules
    import structlog
    logger = structlog.get_logger(__name__)

    logger.info("tool_executed", tool="search", conversation_id=conv_id, latency_ms=150)
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, Processor, WrappedLogger

# Sensitive field patterns to redact from logs
SENSITIVE_FIELDS = frozenset(
    {
        "password",
        "api_key",
        "apikey",
        "secret",
        "token",
        "authorization",
        "auth_token",
        "access_key",
        "secret_key",
        "private_key",
        "credential",
        "aws_access_key_id",
        "aws_secret_access_key",
    }
)


def _redact_sensitive_data(
    _logger: WrappedLogger,
    _method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """
    Redact sensitive data from log events.

    Scans event dict keys for sensitive field names and replaces their
    values with "[REDACTED]". This prevents accidental logging of secrets.

    Args:
        _logger: The logger instance (unused).
        _method_name: The logging method name (unused).
        event_dict: The event dictionary to process.

    Returns:
        Event dict with sensitive values redacted.
    """
    for key in list(event_dict.keys()):
        key_lower = key.lower()
        if any(sensitive in key_lower for sensitive in SENSITIVE_FIELDS):
            event_dict[key] = "[REDACTED]"
    return event_dict


def configure_logging(
    environment: str = "local",
    log_level: str | None = None,
) -> None:
    """
    Configure logging for the application.

    Sets up structlog with JSON output for CloudWatch compatibility and
    integrates with the standard library logging for third-party libraries.

    Args:
        environment: Runtime environment ('local' or 'aws').
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
            If not provided, defaults to DEBUG for local, INFO for aws.

    Example:
        # In application startup
        configure_logging(environment="aws", log_level="INFO")

        # Then use structlog throughout the app
        import structlog
        logger = structlog.get_logger()
        logger.info("request_started", path="/api/chat")
    """
    # Determine log level based on environment if not explicitly set
    if log_level is None:
        log_level = "DEBUG" if environment == "local" else "INFO"

    # Convert string level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Shared processors for both structlog and stdlib integration
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        _redact_sensitive_data,
    ]

    # Configure structlog
    if environment == "aws":
        # JSON output for CloudWatch
        structlog.configure(
            processors=shared_processors
            + [
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

        # Configure stdlib logging with JSON formatter
        formatter = structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.JSONRenderer(),
            ],
        )
    else:
        # Pretty console output for local development
        structlog.configure(
            processors=shared_processors
            + [
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

        # Configure stdlib logging with colored console output
        formatter = structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.dev.ConsoleRenderer(colors=True),
            ],
        )

    # Apply formatter to root logger
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(numeric_level)

    # Set specific log levels for noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("boto3").setLevel(logging.WARNING)

    # Log confirmation
    logger = structlog.get_logger("logging.config")
    logger.info(
        "logging_configured",
        environment=environment,
        log_level=log_level,
        output_format="json" if environment == "aws" else "console",
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """
    Get a configured structlog logger.

    This is a convenience wrapper around structlog.get_logger() that
    ensures the logging system is properly configured.

    Args:
        name: Logger name (typically __name__).

    Returns:
        Configured structlog BoundLogger instance.
    """
    return structlog.get_logger(name)


# Type alias for log context binding
LogContext = dict[str, Any]


def bind_conversation_context(conversation_id: str) -> None:
    """
    Bind conversation_id to the current context for all subsequent logs.

    Use this at the start of request handling to automatically include
    conversation_id in all logs for that request.

    Args:
        conversation_id: The conversation identifier to bind.

    Example:
        bind_conversation_context(conversation_id)
        logger.info("processing_message")  # conversation_id auto-included
    """
    structlog.contextvars.bind_contextvars(conversation_id=conversation_id)


def clear_context() -> None:
    """
    Clear all bound context variables.

    Call this at the end of request handling to prevent context leakage
    between requests.
    """
    structlog.contextvars.clear_contextvars()


__all__ = [
    "configure_logging",
    "get_logger",
    "bind_conversation_context",
    "clear_context",
    "LogContext",
]
