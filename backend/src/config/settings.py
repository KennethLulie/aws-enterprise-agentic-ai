"""
Pydantic settings for backend configuration.

This module centralizes environment-driven configuration for the backend.
It uses Pydantic Settings v2 with SettingsConfigDict to load environment
variables from .env files and environment variables.

The configuration supports two environments:
- local: Development environment using local services (Docker Compose)
- aws: Production environment using AWS services (Secrets Manager, Neon PostgreSQL, etc.)

Auto-detection logic determines the environment based on:
1. Explicit ENVIRONMENT variable (preferred)
2. AWS metadata availability (for EC2/ECS/App Runner)

AWS Secrets Manager Integration (Phase 1a+):
When ENVIRONMENT=aws, secrets are loaded from AWS Secrets Manager:
- enterprise-agentic-ai/demo-password (key: "password")
- enterprise-agentic-ai/auth-token-secret (key: "secret")
- enterprise-agentic-ai/tavily-api-key (key: "api_key")
- enterprise-agentic-ai/fmp-api-key (key: "api_key")

Secrets are cached in memory to avoid repeated API calls.

Usage:
    from src.config.settings import Settings, get_settings, validate_config

    # Get settings singleton (cached)
    settings = get_settings()

    # Validate all configuration on startup
    validate_config()

    # Access settings
    print(settings.aws_region)
    print(settings.bedrock_model_id)
"""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from typing import Any

from pydantic import (
    AnyHttpUrl,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


# =============================================================================
# AWS Secrets Manager Integration
# =============================================================================

# Module-level cache for secrets (loaded once at startup)
_secrets_cache: dict[str, str] = {}
_secrets_loaded: bool = False


def _get_boto3_client() -> Any:
    """
    Get a boto3 Secrets Manager client.

    Returns:
        Any: boto3 SecretsManager client instance. Type is Any to avoid
            requiring boto3 type stubs at import time.

    Raises:
        ImportError: If boto3 is not available.
    """
    import boto3  # type: ignore[import-untyped]

    region = os.environ.get("AWS_REGION", "us-east-1")
    return boto3.client("secretsmanager", region_name=region)


def _load_secret_from_aws(secret_name: str, key: str) -> str | None:
    """
    Load a secret value from AWS Secrets Manager.

    Args:
        secret_name: The full name of the secret in Secrets Manager.
        key: The key within the secret's JSON structure.

    Returns:
        The secret value, or None if not found.
    """
    try:
        client = _get_boto3_client()
        response = client.get_secret_value(SecretId=secret_name)
        secret_data = json.loads(response["SecretString"])
        return secret_data.get(key)
    except Exception as e:
        logger.warning(f"Failed to load secret '{secret_name}': {e}")
        return None


def load_secrets_from_aws() -> dict[str, str]:
    """
    Load all application secrets from AWS Secrets Manager.

    Secrets are cached in the module-level _secrets_cache dict.
    This function should be called once at application startup when
    ENVIRONMENT=aws.

    Returns:
        Dict mapping setting names to their secret values.
    """
    global _secrets_cache, _secrets_loaded

    if _secrets_loaded:
        return _secrets_cache

    # Secret mappings: setting_name -> (secret_name, key)
    secret_mappings = {
        "demo_password": ("enterprise-agentic-ai/demo-password", "password"),
        "auth_token_secret": ("enterprise-agentic-ai/auth-token-secret", "secret"),
        "tavily_api_key": ("enterprise-agentic-ai/tavily-api-key", "api_key"),
        "fmp_api_key": ("enterprise-agentic-ai/fmp-api-key", "api_key"),
    }

    for setting_name, (secret_name, key) in secret_mappings.items():
        try:
            value = _load_secret_from_aws(secret_name, key)
            if value:
                _secrets_cache[setting_name] = value
                logger.debug(f"Loaded secret: {setting_name}")
            else:
                logger.warning(
                    f"Secret '{secret_name}' returned empty value for key '{key}'"
                )
        except Exception as e:
            logger.warning(f"Could not load secret '{secret_name}': {e}")

    _secrets_loaded = True
    logger.info(f"Loaded {len(_secrets_cache)} secrets from AWS Secrets Manager")
    return _secrets_cache


def get_cached_secret(setting_name: str) -> str | None:
    """
    Get a cached secret value by setting name.

    Args:
        setting_name: The setting name (e.g., 'demo_password').

    Returns:
        The cached secret value, or None if not cached.
    """
    return _secrets_cache.get(setting_name)


def clear_secrets_cache() -> None:
    """Clear the secrets cache. Useful for testing."""
    global _secrets_cache, _secrets_loaded
    _secrets_cache = {}
    _secrets_loaded = False


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    All settings have sensible defaults for local development. In production,
    sensitive values should be provided via AWS Secrets Manager or environment
    variables set by the deployment platform.

    Attributes are organized into logical groups:
    - Environment Configuration
    - AWS Configuration
    - AWS Bedrock Configuration
    - Database Configuration
    - Vector Store Configuration
    - External API Configuration
    - Authentication Configuration
    - Application Configuration
    - Rate Limiting Configuration
    - Logging Configuration
    - Cache Configuration
    - Knowledge Graph Configuration (Neo4j only)
    """

    # =========================================================================
    # Environment Configuration
    # =========================================================================
    environment: str = Field(
        default="local",
        description=(
            "Runtime environment identifier. Use 'local' for development, "
            "'aws' for production. This affects secrets loading behavior."
        ),
    )

    debug: bool = Field(
        default=True,
        description="Enable debug mode. Set to False in production.",
    )

    # =========================================================================
    # AWS Configuration
    # =========================================================================
    aws_region: str = Field(
        default="us-east-1",
        description=(
            "AWS region for all services. Always use 'us-east-1' unless "
            "explicitly required otherwise."
        ),
    )

    aws_access_key_id: SecretStr | None = Field(
        default=None,
        description=(
            "AWS access key ID. Required for local development. "
            "In production, use IAM roles instead."
        ),
    )

    aws_secret_access_key: SecretStr | None = Field(
        default=None,
        description=(
            "AWS secret access key. Required for local development. "
            "In production, use IAM roles instead."
        ),
    )

    # =========================================================================
    # AWS Bedrock Configuration
    # =========================================================================
    bedrock_model_id: str = Field(
        default="amazon.nova-pro-v1:0",
        description="Primary Bedrock model ID for chat interactions.",
    )

    bedrock_fallback_model_id: str = Field(
        default="anthropic.claude-3-5-sonnet-20240620-v1:0",
        description=(
            "Fallback Bedrock model ID if primary is unavailable. Must support "
            "on-demand throughput."
        ),
    )

    bedrock_embedding_model_id: str = Field(
        default="amazon.titan-embed-text-v1",
        description="Bedrock model ID for generating text embeddings.",
    )

    bedrock_verification_model_id: str = Field(
        default="amazon.nova-lite-v1:0",
        description=(
            "Bedrock model ID for input/output verification. "
            "Uses a smaller, cheaper model for guards."
        ),
    )

    # =========================================================================
    # Database Configuration
    # =========================================================================
    database_url: str | None = Field(
        default=None,
        description=(
            "PostgreSQL connection string. Uses Docker Compose postgres "
            "service locally. Neon PostgreSQL endpoint in production. "
            "If not provided, a URL is constructed from the postgres_* fields."
        ),
    )

    postgres_db: str = Field(
        default="demo",
        description="PostgreSQL database name.",
    )

    postgres_user: str = Field(
        default="demo",
        description="PostgreSQL username.",
    )

    postgres_password: SecretStr = Field(
        default=SecretStr("demo"),
        description="PostgreSQL password.",
    )

    postgres_host: str = Field(
        default="postgres",
        description="PostgreSQL host name. Defaults to Docker Compose service name.",
    )

    postgres_port: int = Field(
        default=5432,
        description="PostgreSQL port.",
    )

    # =========================================================================
    # Vector Store Configuration
    # =========================================================================
    vector_store_type: str = Field(
        default="chroma",
        description=(
            "Vector store backend type: 'pinecone' for production, "
            "'chroma' for local development."
        ),
    )

    pinecone_api_key: SecretStr | None = Field(
        default=None,
        description="Pinecone API key for vector store operations.",
    )

    pinecone_index_name: str = Field(
        default="demo-index",
        description="Pinecone index name for vector storage.",
    )

    pinecone_environment: str = Field(
        default="us-east-1",
        description="Pinecone environment/region.",
    )

    chroma_url: AnyHttpUrl = Field(
        default="http://chroma:8000",
        description="ChromaDB URL for local development.",
    )

    # =========================================================================
    # External API Configuration
    # =========================================================================
    tavily_api_key: SecretStr | None = Field(
        default=None,
        description=("Tavily Search API key. Free tier provides 1,000 searches/month."),
    )

    fmp_api_key: SecretStr | None = Field(
        default=None,
        description=(
            "Financial Modeling Prep API key. If unset, the market data "
            "tool uses mock data. Free tier: ~250 calls/day."
        ),
    )

    fmp_base_url: AnyHttpUrl = Field(
        default="https://financialmodelingprep.com/stable",
        description="Base URL for Financial Modeling Prep API.",
    )

    fmp_timeout_seconds: float = Field(
        default=10.0,
        ge=1.0,
        le=60.0,
        description="HTTP timeout when calling FMP (seconds).",
    )

    # =========================================================================
    # Authentication Configuration
    # =========================================================================
    demo_password: SecretStr = Field(
        default=SecretStr("change-me"),
        description=(
            "Demo password for the web interface. Override via .env locally or "
            "Secrets Manager in AWS."
        ),
    )
    auth_token_secret: SecretStr = Field(
        default=SecretStr("change-me"),
        description=(
            "Secret used to sign authentication tokens. Override via .env locally "
            "or Secrets Manager in AWS."
        ),
    )
    auth_token_expires_minutes: int = Field(
        default=1440,
        ge=5,
        le=10080,
        description="Session token expiration in minutes (default 24h).",
    )
    auth_cookie_name: str = Field(
        default="session_token",
        description="Cookie name for storing the session token.",
    )

    @model_validator(mode="before")
    @classmethod
    def load_aws_secrets(cls, data: dict[str, Any]) -> dict[str, Any]:
        """
        Load secrets from AWS Secrets Manager when ENVIRONMENT=aws.

        This validator runs before field validation to inject secrets into
        the settings data. It checks for ENVIRONMENT=aws and loads secrets
        from AWS Secrets Manager, then merges them with environment variables.

        Priority (highest to lowest):
        1. Explicit environment variables
        2. AWS Secrets Manager values
        3. Default values

        Args:
            data: The raw settings data from environment variables.

        Returns:
            Updated data dict with secrets injected.
        """
        # Check environment - support both dict and env var
        env_from_data = data.get("environment")
        env_from_os = os.environ.get("ENVIRONMENT", "local")
        environment = str(env_from_data) if env_from_data else env_from_os

        # Set environment-aware log_level default if not explicitly set
        # Default: DEBUG for local, INFO for aws
        if "log_level" not in data and not os.environ.get("LOG_LEVEL"):
            data["log_level"] = "DEBUG" if environment.lower() == "local" else "INFO"

        if environment.lower() == "aws":
            logger.info(
                "AWS environment detected, loading secrets from Secrets Manager..."
            )
            try:
                secrets = load_secrets_from_aws()

                # Inject secrets only if not already set (env vars take precedence)
                for setting_name, secret_value in secrets.items():
                    # Check if setting is already set in data or env
                    env_key = setting_name.upper()
                    if setting_name not in data and not os.environ.get(env_key):
                        data[setting_name] = secret_value
                        logger.debug(f"Injected secret for: {setting_name}")

            except Exception as e:
                logger.error(f"Failed to load secrets from AWS Secrets Manager: {e}")
                # Continue with defaults/env vars - allows graceful degradation
                # The validate_auth_secrets validator will catch missing critical secrets

        return data

    @model_validator(mode="after")
    def populate_database_url(self) -> "Settings":
        """
        Ensure database_url is populated without embedding credentials in code.

        If DATABASE_URL is not provided via environment variables or Secrets
        Manager, construct it from the individual postgres_* fields. This keeps
        defaults in configuration rather than hardcoding credentials in the
        codebase, satisfying secret scanners while preserving local usability.
        """
        if not self.database_url:
            password = self.postgres_password.get_secret_value()
            self.database_url = (
                f"postgresql://{self.postgres_user}:{password}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
            )
        return self

    # =========================================================================
    # Application Configuration
    # =========================================================================
    backend_host: str = Field(
        default="0.0.0.0",  # nosec B104 - Required for containerized deployments (Docker/App Runner)
        description="Host address for the backend server to bind to.",
    )

    backend_port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="Port number for the backend server.",
    )

    cors_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        description="Comma-separated list of allowed CORS origins.",
        validation_alias="ALLOWED_ORIGINS",
    )

    # =========================================================================
    # Rate Limiting Configuration
    # =========================================================================
    rate_limit_per_minute: int = Field(
        default=10,
        ge=1,
        le=1000,
        description="Maximum requests per minute per IP address.",
    )

    # =========================================================================
    # Logging Configuration
    # =========================================================================
    log_level: str = Field(
        default="INFO",
        description=(
            "Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL. "
            "Defaults to DEBUG for local, INFO for aws if not explicitly set."
        ),
    )

    # =========================================================================
    # Cache Configuration (Phase 4+)
    # =========================================================================
    cache_table_name: str = Field(
        default="inference-cache",
        description="DynamoDB table name for inference cache.",
    )

    cache_ttl_seconds: int = Field(
        default=604800,
        ge=0,
        description="Cache TTL in seconds. Default is 7 days (604800 seconds).",
    )

    cache_similarity_threshold: float = Field(
        default=0.95,
        ge=0.0,
        le=1.0,
        description="Similarity threshold for cache hits (0.0-1.0).",
    )

    # =========================================================================
    # Knowledge Graph Configuration (Phase 2+)
    # =========================================================================
    neo4j_uri: str = Field(
        default="bolt://neo4j:7687",
        description=(
            "Neo4j connection URI. Uses Docker Compose neo4j service locally, "
            "Neo4j AuraDB in production."
        ),
    )

    neo4j_user: str = Field(
        default="neo4j",
        description="Neo4j username.",
    )

    neo4j_password: SecretStr = Field(
        default=SecretStr("demo_password"),
        description="Neo4j password.",
    )

    # =========================================================================
    # Pydantic Settings Configuration
    # =========================================================================
    model_config = SettingsConfigDict(
        # Load from .env file
        env_file=".env",
        env_file_encoding="utf-8",
        # Allow extra fields for forward compatibility
        extra="ignore",
        # Case-insensitive environment variable matching
        case_sensitive=False,
        # Validate default values
        validate_default=True,
        # Custom env prefix if needed (empty for no prefix)
        env_prefix="",
        # Enable environment variable nesting with double underscore
        env_nested_delimiter="__",
        # Populate by name for aliases to work properly
        populate_by_name=True,
    )

    # =========================================================================
    # Validators
    # =========================================================================
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is one of the standard Python logging levels."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper_v = v.upper()
        if upper_v not in valid_levels:
            raise ValueError(f"Invalid log level '{v}'. Must be one of: {valid_levels}")
        return upper_v

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment is either 'local' or 'aws'."""
        lower_v = v.lower()
        if lower_v not in {"local", "aws"}:
            raise ValueError(f"Invalid environment '{v}'. Must be 'local' or 'aws'.")
        return lower_v

    @field_validator("vector_store_type")
    @classmethod
    def validate_vector_store_type(cls, v: str) -> str:
        """Validate vector store type is supported."""
        lower_v = v.lower()
        if lower_v not in {"pinecone", "chroma"}:
            raise ValueError(
                f"Invalid vector_store_type '{v}'. Must be 'pinecone' or 'chroma'."
            )
        return lower_v

    @model_validator(mode="after")
    def validate_auth_secrets(self) -> "Settings":
        """
        Ensure authentication secrets are not left at placeholder defaults.

        In AWS, placeholders are rejected. In local development, we emit a warning
        so mock-only Phase 0 flows (e.g., Tavily mock) can run without secrets set.
        """

        placeholders = {"change-me", "change-this-password", "change-this-secret"}

        password_value = self.demo_password.get_secret_value()
        secret_value = self.auth_token_secret.get_secret_value()

        if self.is_aws():
            if password_value in placeholders:
                raise ValueError(
                    "DEMO_PASSWORD must be set in AWS (placeholder detected). "
                    "Store it in Secrets Manager."
                )
            if secret_value in placeholders:
                raise ValueError(
                    "AUTH_TOKEN_SECRET must be set in AWS (placeholder detected). "
                    "Store it in Secrets Manager."
                )
        else:
            if password_value in placeholders:
                logger.warning(
                    "DEMO_PASSWORD is using a placeholder in local dev. "
                    "Set a unique value in .env for closer parity with AWS."
                )
            if secret_value in placeholders:
                logger.warning(
                    "AUTH_TOKEN_SECRET is using a placeholder in local dev. "
                    "Set a unique value in .env for closer parity with AWS."
                )

        return self

    @model_validator(mode="after")
    def validate_aws_credentials(self) -> "Settings":
        """
        Validate AWS credentials are provided for local development.

        In production (environment='aws'), credentials should come from
        IAM roles, so they are not required in environment variables.
        """
        if self.environment == "local":
            # AWS credentials are optional for local dev if using mocks
            # but we log a warning if they're missing
            if not self.aws_access_key_id or not self.aws_secret_access_key:
                logger.warning(
                    "AWS credentials not found in environment. "
                    "Bedrock calls will fail unless using mock mode."
                )
        return self

    # =========================================================================
    # Helper Methods
    # =========================================================================
    def get_cors_origins_list(self) -> list[str]:
        """
        Get CORS origins as a list.

        Parses the comma-separated cors_origins string into a list.
        Also accessible via ALLOWED_ORIGINS environment variable.
        """
        return [
            origin.strip() for origin in self.cors_origins.split(",") if origin.strip()
        ]

    @property
    def allowed_origins(self) -> list[str]:
        """
        Alias for get_cors_origins_list().

        Provides a property-based access pattern for CORS origins.
        """
        return self.get_cors_origins_list()

    def is_local(self) -> bool:
        """Check if running in local development environment."""
        return self.environment == "local"

    def is_aws(self) -> bool:
        """Check if running in AWS production environment."""
        return self.environment == "aws"

    def get_database_url_sync(self) -> str:
        """
        Get synchronous database URL.

        Returns the database URL configured for synchronous operations.
        Use this for SQLAlchemy synchronous operations.
        """
        if not self.database_url:
            raise ValueError(
                "database_url is not configured. Check environment settings."
            )
        return self.database_url

    def get_database_url_async(self) -> str:
        """
        Get asynchronous database URL.

        Converts postgresql:// to postgresql+asyncpg:// for async operations.
        Use this for SQLAlchemy async operations.
        """
        database_url = self.get_database_url_sync()
        if database_url.startswith("postgresql://"):
            return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return database_url


def detect_environment() -> str:
    """
    Auto-detect the runtime environment.

    Detection logic:
    1. Check ENVIRONMENT variable (explicit override)
    2. Check for AWS metadata service availability (EC2/ECS/App Runner)
    3. Default to 'local'

    Returns:
        str: Either 'local' or 'aws'
    """
    # Check explicit environment variable first
    env = os.environ.get("ENVIRONMENT", "").lower()
    if env in {"local", "aws"}:
        return env

    # Check for AWS metadata service (indicates running on AWS)
    # App Runner, ECS, and EC2 all have metadata endpoints
    aws_indicators = [
        "AWS_EXECUTION_ENV",  # Lambda, App Runner
        "ECS_CONTAINER_METADATA_URI",  # ECS
        "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",  # ECS with IAM role
    ]

    for indicator in aws_indicators:
        if os.environ.get(indicator):
            logger.info(f"Detected AWS environment via {indicator}")
            return "aws"

    # Default to local
    return "local"


@lru_cache
def get_settings() -> Settings:
    """
    Get the application settings singleton.

    This function is cached to ensure only one Settings instance is created.
    The instance is created lazily on first access.

    Returns:
        Settings: The application settings instance.

    Example:
        settings = get_settings()
        print(settings.aws_region)
    """
    return Settings()


def validate_config() -> dict[str, Any]:
    """
    Validate all configuration settings on startup.

    This function should be called during application startup to ensure
    all configuration is valid and required settings are present.

    Returns:
        dict: Validation result with status and any warnings.

    Raises:
        ValueError: If critical configuration is missing or invalid.

    Example:
        from src.config.settings import validate_config

        @app.on_event("startup")
        async def startup():
            result = validate_config()
            if result["warnings"]:
                for warning in result["warnings"]:
                    logger.warning(warning)
    """
    warnings: list[str] = []
    errors: list[str] = []

    try:
        settings = get_settings()
    except Exception as e:
        errors.append(f"Failed to load settings: {e}")
        raise ValueError(f"Configuration validation failed: {errors}") from e

    # Placeholder values that indicate unconfigured secrets
    placeholders = {"change-me", "change-this-password", "change-this-secret"}
    demo_password_value = settings.demo_password.get_secret_value()
    auth_secret_value = settings.auth_token_secret.get_secret_value()

    # Check for production-critical settings
    if settings.is_aws():
        # In AWS, placeholder secrets are errors
        if demo_password_value in placeholders:
            errors.append(
                "DEMO_PASSWORD must be changed from default in production. "
                "Store it in AWS Secrets Manager."
            )
        if auth_secret_value in placeholders:
            errors.append(
                "AUTH_TOKEN_SECRET must be set in production. "
                "Store it in AWS Secrets Manager."
            )
        # AWS-specific warnings
        if settings.vector_store_type == "chroma":
            warnings.append(
                "Using ChromaDB in AWS environment. "
                "Consider using Pinecone for production."
            )
        if settings.debug:
            warnings.append(
                "DEBUG mode is enabled in AWS environment. "
                "Consider setting DEBUG=false for production."
            )
    else:
        # In local dev, warn if auth secrets use placeholders
        if auth_secret_value in placeholders:
            warnings.append(
                "AUTH_TOKEN_SECRET is using the default value. "
                "Set a unique secret in local .env to match production behavior."
            )

    # Check API keys for functionality warnings
    if not settings.tavily_api_key:
        warnings.append(
            "TAVILY_API_KEY not set. Web search functionality will be unavailable."
        )

    if not settings.fmp_api_key:
        warnings.append("FMP_API_KEY not set. Market data tool will use mock data.")

    if not settings.pinecone_api_key and settings.vector_store_type == "pinecone":
        errors.append(
            "PINECONE_API_KEY is required when vector_store_type is 'pinecone'."
        )

    # Log validation results
    for warning in warnings:
        logger.warning(f"Configuration warning: {warning}")

    if errors:
        for error in errors:
            logger.error(f"Configuration error: {error}")
        raise ValueError(f"Configuration validation failed: {errors}")

    logger.info(
        f"Configuration validated successfully. Environment: {settings.environment}"
    )

    return {
        "status": "ok",
        "environment": settings.environment,
        "warnings": warnings,
        "settings_summary": {
            "debug": settings.debug,
            "aws_region": settings.aws_region,
            "vector_store_type": settings.vector_store_type,
            "log_level": settings.log_level,
        },
    }


def get_environment() -> str:
    """
    Get the current runtime environment.

    This is a convenience function that returns the environment
    from the settings singleton.

    Returns:
        str: Either 'local' or 'aws'
    """
    return get_settings().environment


# Export public API
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
