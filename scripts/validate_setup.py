#!/usr/bin/env python3
from __future__ import annotations

"""
Validate local setup for the Enterprise Agentic AI project.

This script checks prerequisites, environment variables, and access to external
services used in Phase 0. It is intended to be run locally before starting
development:

    python scripts/validate_setup.py
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal
import os
import sys

STATUS = Literal["pass", "fail", "warn", "skip"]

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError as exc:  # pragma: no cover - defensive guard
    boto3 = None  # type: ignore
    BotoCoreError = ClientError = Exception  # type: ignore
    _BOTO3_IMPORT_ERROR = exc
else:
    _BOTO3_IMPORT_ERROR = None

try:
    import requests
except ImportError as exc:  # pragma: no cover - defensive guard
    requests = None  # type: ignore
    _REQUESTS_IMPORT_ERROR = exc
else:
    _REQUESTS_IMPORT_ERROR = None

try:
    from dotenv import load_dotenv
except ImportError as exc:  # pragma: no cover - defensive guard
    load_dotenv = None  # type: ignore
    _DOTENV_IMPORT_ERROR = exc
else:
    _DOTENV_IMPORT_ERROR = None

try:
    from pinecone import Pinecone, PineconeApiException
except Exception as exc:  # pragma: no cover - defensive guard
    Pinecone = None  # type: ignore
    PineconeApiException = Exception  # type: ignore
    _PINECONE_IMPORT_ERROR = exc
else:
    _PINECONE_IMPORT_ERROR = None

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"

GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
RESET = "\033[0m"

REQUIRED_ENV_VARS = [
    "ENVIRONMENT",
    "DEBUG",
    "AWS_REGION",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "BEDROCK_MODEL_ID",
    "BEDROCK_FALLBACK_MODEL_ID",
    "BEDROCK_EMBEDDING_MODEL_ID",
    "BEDROCK_VERIFICATION_MODEL_ID",
    "DATABASE_URL",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "VECTOR_STORE_TYPE",
    "CHROMA_URL",
    "BACKEND_HOST",
    "BACKEND_PORT",
    "NEXT_PUBLIC_API_URL",
    "CORS_ORIGINS",
    "RATE_LIMIT_PER_MINUTE",
    "LOG_LEVEL",
    "DEMO_PASSWORD",
    "AUTH_TOKEN_SECRET",
    "AUTH_TOKEN_EXPIRES_MINUTES",
    "AUTH_COOKIE_NAME",
]

PLACEHOLDER_VALUES: dict[str, set[str]] = {
    "AWS_ACCESS_KEY_ID": {"your-access-key-id-here"},
    "AWS_SECRET_ACCESS_KEY": {"your-secret-access-key-here"},
    "PINECONE_API_KEY": {"your-pinecone-api-key-here"},
    "TAVILY_API_KEY": {"tvly-your-api-key-here"},
    "FMP_API_KEY": {"your-fmp-api-key-here"},
    "DEMO_PASSWORD": {"change-this-password"},
    "AUTH_TOKEN_SECRET": {"change-this-secret"},
}


@dataclass
class CheckResult:
    """Represents the outcome of a validation step."""

    name: str
    status: STATUS
    message: str


def color(text: str, color_code: str) -> str:
    """Apply an ANSI color code to text."""

    return f"{color_code}{text}{RESET}"


def format_status(status: STATUS) -> str:
    """Format a status with color for terminal output."""

    if status == "pass":
        return color("PASS", GREEN)
    if status == "fail":
        return color("FAIL", RED)
    if status == "warn":
        return color("WARN", YELLOW)
    return color("SKIP", BLUE)


def print_result(result: CheckResult) -> None:
    """Print a single check result with colored status."""

    print(f"[{format_status(result.status)}] {result.name}: {result.message}")


def check_python_version() -> CheckResult:
    """Verify Python runtime is 3.11 or newer."""

    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"
    if version < (3, 11):
        return CheckResult(
            name="Python version",
            status="fail",
            message=f"Python {version_str} detected. Python 3.11+ is required.",
        )
    return CheckResult(
        name="Python version",
        status="pass",
        message=f"Python {version_str} detected.",
    )


def check_env_file() -> tuple[CheckResult, list[CheckResult]]:
    """
    Load .env and ensure required variables are present and not placeholders.

    Returns a tuple of the main check result plus any warning results.
    """

    warnings: list[CheckResult] = []

    if load_dotenv is None:
        return (
            CheckResult(
                name=".env file",
                status="fail",
                message="python-dotenv is not installed. Install dependencies with "
                "`pip install -r backend/requirements.txt`.",
            ),
            warnings,
        )

    if not ENV_PATH.exists():
        return (
            CheckResult(
                name=".env file",
                status="fail",
                message=f"Missing .env at {ENV_PATH}. Copy .env.example to .env and fill values.",
            ),
            warnings,
        )

    load_dotenv(ENV_PATH, override=False)

    missing = [name for name in REQUIRED_ENV_VARS if not os.getenv(name)]
    placeholder_hits: list[str] = []
    for name, placeholders in PLACEHOLDER_VALUES.items():
        value = os.getenv(name, "")
        if value and value in placeholders and name in REQUIRED_ENV_VARS:
            placeholder_hits.append(name)

    if missing or placeholder_hits:
        details: list[str] = []
        if missing:
            details.append(f"Missing: {', '.join(sorted(missing))}")
        if placeholder_hits:
            details.append(f"Replace placeholders for: {', '.join(sorted(placeholder_hits))}")
        return (
            CheckResult(
                name="Required environment variables",
                status="fail",
                message="; ".join(details),
            ),
            warnings,
        )

    for warning_var in ("DEMO_PASSWORD", "AUTH_TOKEN_SECRET"):
        value = os.getenv(warning_var, "")
        if value and value in PLACEHOLDER_VALUES.get(warning_var, set()):
            warnings.append(
                CheckResult(
                    name=f"Security defaults ({warning_var})",
                    status="warn",
                    message=f"{warning_var} is using a default value. Set a unique value in .env.",
                )
            )

    return (
        CheckResult(
            name="Required environment variables",
            status="pass",
            message=f"Loaded .env from {ENV_PATH}. All required keys are present.",
        ),
        warnings,
    )


def check_aws_credentials(region: str) -> CheckResult:
    """Validate AWS credentials by calling STS GetCallerIdentity."""

    if boto3 is None:
        return CheckResult(
            name="AWS credentials",
            status="fail",
            message=f"boto3 is not installed: {_BOTO3_IMPORT_ERROR}. Install backend dependencies.",
        )

    try:
        session = boto3.Session(region_name=region)
        sts = session.client("sts")
        identity = sts.get_caller_identity()
        account = identity.get("Account", "unknown")
        arn = identity.get("Arn", "unknown")
        return CheckResult(
            name="AWS credentials",
            status="pass",
            message=f"Authenticated with STS (account {account}, ARN {arn}).",
        )
    except (BotoCoreError, ClientError) as exc:
        return CheckResult(
            name="AWS credentials",
            status="fail",
            message=f"STS get-caller-identity failed: {exc}",
        )
    except Exception as exc:  # pragma: no cover - defensive guard
        return CheckResult(
            name="AWS credentials",
            status="fail",
            message=f"Unexpected error calling STS: {exc}",
        )


def check_bedrock_access(region: str) -> CheckResult:
    """Verify Bedrock access by listing foundation models."""

    if boto3 is None:
        return CheckResult(
            name="Bedrock access",
            status="fail",
            message=f"boto3 is not installed: {_BOTO3_IMPORT_ERROR}. Install backend dependencies.",
        )

    try:
        client = boto3.client("bedrock", region_name=region)
        # The API currently only supports filter params; no size limit argument
        response = client.list_foundation_models()
        models = response.get("modelSummaries", [])
        return CheckResult(
            name="Bedrock access",
            status="pass",
            message=f"Bedrock reachable in {region}. Retrieved {len(models)} model summaries.",
        )
    except (BotoCoreError, ClientError) as exc:
        return CheckResult(
            name="Bedrock access",
            status="fail",
            message=f"Failed to list foundation models: {exc}",
        )
    except Exception as exc:  # pragma: no cover - defensive guard
        return CheckResult(
            name="Bedrock access",
            status="fail",
            message=f"Unexpected error calling Bedrock: {exc}",
        )


def check_pinecone_api(api_key: str | None) -> CheckResult:
    """Validate Pinecone API key by listing indexes (if a key is provided)."""

    if not api_key:
        return CheckResult(
            name="Pinecone",
            status="skip",
            message="PINECONE_API_KEY not set. Skipping Pinecone check.",
        )

    if Pinecone is None:
        return CheckResult(
            name="Pinecone",
            status="fail",
            message=f"pinecone-client is not installed: {_PINECONE_IMPORT_ERROR}. Install backend dependencies.",
        )

    try:
        client = Pinecone(api_key=api_key)
        client.list_indexes()
        return CheckResult(
            name="Pinecone",
            status="pass",
            message="Pinecone API key is valid (list_indexes succeeded).",
        )
    except PineconeApiException as exc:
        return CheckResult(
            name="Pinecone",
            status="fail",
            message=f"Pinecone API call failed: {exc}",
        )
    except Exception as exc:  # pragma: no cover - defensive guard
        return CheckResult(
            name="Pinecone",
            status="fail",
            message=f"Unexpected error calling Pinecone: {exc}",
        )


def check_tavily_api(api_key: str | None) -> CheckResult:
    """Validate Tavily API key with a minimal search call (if a key is provided)."""

    if not api_key:
        return CheckResult(
            name="Tavily",
            status="skip",
            message="TAVILY_API_KEY not set. Skipping Tavily check.",
        )

    if requests is None:
        return CheckResult(
            name="Tavily",
            status="fail",
            message=f"requests is not installed: {_REQUESTS_IMPORT_ERROR}. Install backend dependencies.",
        )

    try:
        # Tavily search endpoint (v1 path now returns 404)
        response = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,  # Tavily expects api_key in the payload
                "query": "setup validation ping",
                "max_results": 1,
            },
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        if response.status_code == 200:
            return CheckResult(
                name="Tavily",
                status="pass",
                message="Tavily API key is valid (search request succeeded).",
            )
        return CheckResult(
            name="Tavily",
            status="fail",
            message=f"Tavily responded with {response.status_code}: {response.text[:200]}",
        )
    except requests.RequestException as exc:  # type: ignore[attr-defined]
        return CheckResult(
            name="Tavily",
            status="fail",
            message=f"Tavily request failed: {exc}",
        )
    except Exception as exc:  # pragma: no cover - defensive guard
        return CheckResult(
            name="Tavily",
            status="fail",
            message=f"Unexpected error calling Tavily: {exc}",
        )


def run_checks() -> list[CheckResult]:
    """Run all validation checks and return their results."""

    results: list[CheckResult] = []

    results.append(check_python_version())

    env_result, env_warnings = check_env_file()
    results.append(env_result)
    results.extend(env_warnings)

    if env_result.status != "pass":
        results.append(
            CheckResult(
                name="AWS credentials",
                status="skip",
                message="Skipped AWS checks because environment validation failed.",
            )
        )
        results.append(
            CheckResult(
                name="Bedrock access",
                status="skip",
                message="Skipped Bedrock check because environment validation failed.",
            )
        )
        results.append(
            CheckResult(
                name="Pinecone",
                status="skip",
                message="Skipped Pinecone check because environment validation failed.",
            )
        )
        results.append(
            CheckResult(
                name="Tavily",
                status="skip",
                message="Skipped Tavily check because environment validation failed.",
            )
        )
        return results

    region = os.getenv("AWS_REGION", "us-east-1")
    results.append(check_aws_credentials(region))
    results.append(check_bedrock_access(region))

    pinecone_key = os.getenv("PINECONE_API_KEY")
    results.append(check_pinecone_api(pinecone_key))

    tavily_key = os.getenv("TAVILY_API_KEY")
    results.append(check_tavily_api(tavily_key))

    return results


def summarize(results: Iterable[CheckResult]) -> None:
    """Print a summary of all check outcomes."""

    status_counts: dict[STATUS, int] = {"pass": 0, "fail": 0, "warn": 0, "skip": 0}
    for result in results:
        status_counts[result.status] += 1

    summary = "Summary - "
    summary += ", ".join(
        f"{label}: {count}"
        for label, count in [
            (format_status("pass"), status_counts["pass"]),
            (format_status("warn"), status_counts["warn"]),
            (format_status("skip"), status_counts["skip"]),
            (format_status("fail"), status_counts["fail"]),
        ]
    )
    print(summary)


def main() -> int:
    """Run validation checks and return exit code 0 on success, 1 on failure."""

    results = run_checks()
    for result in results:
        print_result(result)

    summarize(results)

    has_failure = any(result.status == "fail" for result in results)
    return 1 if has_failure else 0


if __name__ == "__main__":
    raise SystemExit(main())
