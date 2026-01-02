"""
Configuration package for backend application settings.

This package exposes the Settings class and utility functions for centralized
environment-driven configuration. All application settings should be accessed
through this module.

AWS Secrets Manager Integration (Phase 1a+):
When ENVIRONMENT=aws, secrets are automatically loaded from AWS Secrets Manager
and cached in memory. The following secrets are loaded:
- enterprise-agentic-ai/demo-password (key: "password")
- enterprise-agentic-ai/auth-token-secret (key: "secret")
- enterprise-agentic-ai/tavily-api-key (key: "api_key")
- enterprise-agentic-ai/fmp-api-key (key: "api_key")

Usage:
    from src.config import Settings, get_settings, validate_config

    # Get settings singleton (cached, preferred method)
    settings = get_settings()
    print(settings.aws_region)

    # Create new instance (useful for testing)
    settings = Settings()
    print(settings.environment)

    # Validate configuration on startup
    result = validate_config()
    if result["warnings"]:
        for warning in result["warnings"]:
            print(f"Warning: {warning}")

    # Get environment directly
    from src.config import get_environment
    env = get_environment()  # 'local' or 'aws'

    # Access CORS origins (also settable via ALLOWED_ORIGINS env var)
    origins = settings.allowed_origins  # Returns list
    origins_str = settings.cors_origins  # Returns comma-separated string
"""

from src.config.settings import (
    Settings,
    clear_secrets_cache,
    detect_environment,
    get_cached_secret,
    get_environment,
    get_settings,
    load_secrets_from_aws,
    validate_config,
)

__all__ = [
    "Settings",
    "get_settings",
    "validate_config",
    "get_environment",
    "detect_environment",
    "load_secrets_from_aws",
    "get_cached_secret",
    "clear_secrets_cache",
]
