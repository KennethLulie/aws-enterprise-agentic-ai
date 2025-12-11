"""
Configuration package for backend application settings.

This package exposes the Settings class and utility functions for centralized
environment-driven configuration. All application settings should be accessed
through this module.

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
"""

from src.config.settings import (
    Settings,
    detect_environment,
    get_environment,
    get_settings,
    validate_config,
)

__all__ = [
    "Settings",
    "get_settings",
    "validate_config",
    "get_environment",
    "detect_environment",
]
