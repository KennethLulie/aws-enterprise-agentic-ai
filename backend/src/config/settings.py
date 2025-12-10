"""
Pydantic settings for backend configuration.

This module centralizes environment-driven configuration for the backend and
provides a single Settings class that tools can depend on. The configuration
is intentionally small for Phase 0 and can be extended as features are added.
"""

from typing import Optional

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    environment: str = Field(
        default="local",
        alias="ENVIRONMENT",
        description="Runtime environment identifier (local or aws).",
    )
    aws_region: str = Field(
        default="us-east-1",
        alias="AWS_REGION",
        description="AWS region for all services.",
    )

    fmp_api_key: Optional[str] = Field(
        default=None,
        alias="FMP_API_KEY",
        description="Financial Modeling Prep API key. If unset, the market data tool uses mock data.",
    )
    fmp_base_url: AnyHttpUrl = Field(
        default="https://financialmodelingprep.com/api/v3",
        alias="FMP_BASE_URL",
        description="Base URL for Financial Modeling Prep API.",
    )
    fmp_timeout_seconds: float = Field(
        default=10.0,
        alias="FMP_TIMEOUT_SECONDS",
        description="HTTP timeout when calling FMP (seconds).",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",
    )


__all__ = ["Settings"]

