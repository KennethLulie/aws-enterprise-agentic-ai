"""
SQL query tool for querying 10-K financial data from PostgreSQL.

This tool converts natural language questions to SQL queries, executes them
against the Neon PostgreSQL database, and returns formatted results.

Features:
    - Natural language to SQL conversion using Bedrock LLM
    - SQL injection prevention via sql_safety module
    - Query timeout and result limits
    - Transparent query display for user verification

Usage:
    The agent calls this tool when users ask questions about financial data:
    - "What was NVIDIA's revenue in 2024?"
    - "Which company has the highest net margin?"
    - "Compare segment revenue across tech companies"

Reference:
    - PHASE_2A_HOW_TO_GUIDE.md Section 7.2
    - sql_safety.py for query validation
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog
from langchain.tools import tool
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, ProgrammingError

from src.agent.tools.sql_safety import (
    DEFAULT_TIMEOUT_SECONDS,
    sanitize_query,
    validate_query,
)
from src.config.settings import get_settings

logger = structlog.get_logger(__name__)

# Module-level engine cache (lazy initialization)
_engine_cache: dict[str, Any] = {}

# =============================================================================
# Constants
# =============================================================================

# NL-to-SQL system prompt with schema context
NL_TO_SQL_PROMPT = """You are a SQL query generator for a 10-K financial database.

Available tables and columns:
- companies (id, ticker, name, sector, fiscal_year_end, filing_date, document_id)
- financial_metrics (id, company_id, fiscal_year, revenue, cost_of_revenue, gross_profit,
  operating_expenses, operating_income, net_income, total_assets, total_liabilities,
  total_equity, cash_and_equivalents, long_term_debt, gross_margin, operating_margin,
  net_margin, earnings_per_share, diluted_eps, currency)
- segment_revenue (id, company_id, fiscal_year, segment_name, revenue, percentage_of_total, yoy_growth)
- geographic_revenue (id, company_id, fiscal_year, region, revenue, percentage_of_total, yoy_growth)
- risk_factors (id, company_id, fiscal_year, category, title, summary, severity, page_number)

Key relationships:
- financial_metrics.company_id → companies.id
- segment_revenue.company_id → companies.id
- geographic_revenue.company_id → companies.id
- risk_factors.company_id → companies.id

Rules:
1. ONLY use SELECT statements - no INSERT, UPDATE, DELETE, DROP, etc.
2. ALWAYS JOIN companies table when user wants ticker or company name
3. Use fiscal_year for time-based filtering
4. Include LIMIT clause (max 100 rows)
5. Use column aliases for clarity (e.g., fm.revenue AS revenue)
6. For "highest" or "top" questions, use ORDER BY DESC LIMIT
7. For comparisons, consider using appropriate aggregations
8. Revenue and financial values are in millions USD

Example queries:
- "What was NVIDIA's revenue?" →
  SELECT c.ticker, c.name, fm.fiscal_year, fm.revenue
  FROM companies c JOIN financial_metrics fm ON c.id = fm.company_id
  WHERE c.ticker = 'NVDA' ORDER BY fm.fiscal_year DESC LIMIT 5

- "Which company has highest margin?" →
  SELECT c.ticker, c.name, fm.fiscal_year, fm.net_margin
  FROM companies c JOIN financial_metrics fm ON c.id = fm.company_id
  ORDER BY fm.net_margin DESC LIMIT 10

User question: {query}

Generate ONLY the SQL query, no explanations. The query must be safe and follow all rules above."""


# =============================================================================
# Input Schema
# =============================================================================


class SQLQueryInput(BaseModel):
    """Input schema for the SQL query tool."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=1024,
        description="Natural language question about financial data.",
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        """Validate and trim incoming queries."""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Query cannot be empty.")
        return cleaned


# =============================================================================
# Helper Functions
# =============================================================================


def _get_database_engine() -> Any:
    """
    Get SQLAlchemy engine for database connection.

    Uses a module-level cache to avoid recreating the engine on every query.
    The engine manages its own connection pool.

    Returns:
        SQLAlchemy engine instance.

    Raises:
        ValueError: If DATABASE_URL is not configured.
    """
    global _engine_cache

    settings = get_settings()
    database_url = settings.get_database_url_sync()

    # Check cache
    if "engine" not in _engine_cache or _engine_cache.get("url") != database_url:
        _engine_cache["engine"] = create_engine(
            database_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
        )
        _engine_cache["url"] = database_url
        logger.debug("sql_engine_created", url=database_url[:30] + "...")

    return _engine_cache["engine"]


async def _convert_nl_to_sql(natural_language_query: str) -> str:
    """
    Convert natural language question to SQL using Bedrock LLM.

    Uses Claude Sonnet 4.5 as primary, with fallback to Claude 3.5 Sonnet.

    Args:
        natural_language_query: User's question in natural language.

    Returns:
        Generated SQL query string.

    Raises:
        ValueError: If SQL generation fails with both models.
    """
    import boto3
    from botocore.exceptions import ClientError

    settings = get_settings()

    # Use Bedrock for NL-to-SQL conversion
    client = boto3.client("bedrock-runtime", region_name=settings.aws_region)

    prompt = NL_TO_SQL_PROMPT.format(query=natural_language_query)

    # Models to try in order (primary and fallback)
    models = [
        "us.anthropic.claude-sonnet-4-5-20250929-v1:0",  # Primary
        "anthropic.claude-3-5-sonnet-20241022-v2:0",  # Fallback
    ]

    last_error: Exception | None = None

    for model_id in models:
        try:
            response = await asyncio.to_thread(
                client.converse,
                modelId=model_id,
                messages=[
                    {
                        "role": "user",
                        "content": [{"text": prompt}],
                    }
                ],
                inferenceConfig={
                    "maxTokens": 500,
                    "temperature": 0.0,  # Deterministic for SQL
                },
            )

            # Extract SQL from response
            output = response.get("output", {})
            message = output.get("message", {})
            content = message.get("content", [])

            if content and len(content) > 0:
                sql = content[0].get("text", "").strip()
                # Clean up markdown code blocks if present
                if sql.startswith("```sql"):
                    sql = sql[6:]
                if sql.startswith("```"):
                    sql = sql[3:]
                if sql.endswith("```"):
                    sql = sql[:-3]

                logger.debug(
                    "nl_to_sql_success",
                    model=model_id,
                    sql_length=len(sql),
                )
                return sql.strip()

            raise ValueError("No SQL generated from LLM response")

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            logger.warning(
                "nl_to_sql_model_failed",
                model=model_id,
                error_code=error_code,
                error=str(e),
            )
            last_error = e
            # Try next model
            continue

        except Exception as e:
            logger.warning(
                "nl_to_sql_model_error",
                model=model_id,
                error=str(e),
            )
            last_error = e
            # Try next model
            continue

    # All models failed
    logger.error(
        "nl_to_sql_all_models_failed",
        query=natural_language_query,
        error=str(last_error),
    )
    raise ValueError(
        "Unable to generate SQL query. Please try rephrasing your question."
    ) from last_error


def _execute_query(
    sql: str, timeout: int = DEFAULT_TIMEOUT_SECONDS
) -> list[dict[str, Any]]:
    """
    Execute SQL query with timeout.

    Args:
        sql: SQL query to execute.
        timeout: Query timeout in seconds.

    Returns:
        List of result rows as dictionaries.

    Raises:
        ValueError: If query execution fails.
    """
    engine = _get_database_engine()

    try:
        with engine.connect() as conn:
            # Set statement timeout (PostgreSQL uses milliseconds)
            timeout_ms = timeout * 1000
            conn.execute(text(f"SET statement_timeout = {timeout_ms}"))

            # Execute query
            result = conn.execute(text(sql))

            # Convert to list of dicts
            columns = result.keys()
            rows = [dict(zip(columns, row)) for row in result.fetchall()]

            logger.info(
                "sql_query_executed",
                sql=sql[:200],
                row_count=len(rows),
            )

            return rows

    except OperationalError as e:
        error_str = str(e).lower()
        if "timeout" in error_str or "cancel" in error_str:
            logger.warning("sql_query_timeout", sql=sql[:100])
            raise ValueError(
                "Query took too long to execute. Please try a simpler query."
            ) from e
        logger.error("sql_query_operational_error", sql=sql[:100], error=str(e))
        raise ValueError("Database connection error. Please try again.") from e

    except ProgrammingError as e:
        logger.error("sql_query_programming_error", sql=sql[:100], error=str(e))
        raise ValueError("Invalid query syntax. Please rephrase your question.") from e

    except Exception as e:
        logger.error("sql_query_unknown_error", sql=sql[:100], error=str(e))
        raise ValueError("Query execution failed. Please try again.") from e


def _format_results(
    rows: list[dict[str, Any]],
    sql: str,
    original_query: str,
) -> str:
    """
    Format query results into a readable response.

    Args:
        rows: Query result rows.
        sql: The executed SQL query.
        original_query: The original natural language query.

    Returns:
        Formatted response string.
    """
    if not rows:
        return f"No data found matching your query.\n\n" f"Query used: `{sql}`"

    # Build response
    response_parts = []

    # Summary based on number of results
    if len(rows) == 1:
        response_parts.append("Based on the financial data:\n")
    else:
        response_parts.append(f"Based on the financial data ({len(rows)} results):\n")

    # Financial columns that should be formatted as millions USD
    financial_columns = {
        "revenue",
        "net_income",
        "gross_profit",
        "operating_income",
        "total_assets",
        "total_liabilities",
        "total_equity",
        "cost_of_revenue",
        "operating_expenses",
        "cash_and_equivalents",
        "long_term_debt",
    }
    # Percentage columns
    percentage_columns = {
        "gross_margin",
        "operating_margin",
        "net_margin",
        "percentage_of_total",
        "yoy_growth",
    }
    # EPS columns
    eps_columns = {"earnings_per_share", "diluted_eps"}

    # Format results as a table or list
    if len(rows) <= 10:
        # Detailed list format for small result sets
        for i, row in enumerate(rows, 1):
            row_parts = []
            for key, value in row.items():
                if value is not None:
                    # Convert Decimal to float for formatting
                    try:
                        numeric_value = float(value)
                        is_numeric = True
                    except (ValueError, TypeError):
                        is_numeric = False

                    if is_numeric:
                        if key in financial_columns:
                            # Financial values in millions
                            row_parts.append(f"{key}: ${numeric_value:,.0f}M")
                        elif key in percentage_columns:
                            # Percentages
                            row_parts.append(f"{key}: {numeric_value:.1f}%")
                        elif key in eps_columns:
                            row_parts.append(f"{key}: ${numeric_value:.2f}")
                        elif key == "fiscal_year":
                            row_parts.append(f"{key}: {int(numeric_value)}")
                        else:
                            row_parts.append(f"{key}: {value}")
                    else:
                        row_parts.append(f"{key}: {value}")

            if len(rows) > 1:
                response_parts.append(f"\n{i}. " + ", ".join(row_parts))
            else:
                response_parts.append("\n" + "\n".join(f"  • {p}" for p in row_parts))
    else:
        # Summary for large result sets
        response_parts.append(f"\nShowing first 10 of {len(rows)} results:\n")
        for i, row in enumerate(rows[:10], 1):
            # Show key columns only - prioritize segment/region names
            key_values = []
            display_keys = [
                "ticker",
                "segment_name",
                "region",
                "category",
                "fiscal_year",
                "revenue",
                "net_income",
                "percentage_of_total",
            ]
            for key in display_keys:
                if key in row and row[key] is not None:
                    value = row[key]
                    try:
                        numeric_value = float(value)
                        if key in financial_columns:
                            key_values.append(f"${numeric_value:,.0f}M")
                        elif key in percentage_columns:
                            key_values.append(f"{numeric_value:.1f}%")
                        elif key == "fiscal_year":
                            key_values.append(str(int(numeric_value)))
                        else:
                            key_values.append(str(value))
                    except (ValueError, TypeError):
                        key_values.append(str(value))
            response_parts.append(f"\n  {i}. " + " | ".join(key_values))

    # Add query for transparency
    response_parts.append(f"\n\nQuery used: `{sql}`")

    return "".join(response_parts)


def _build_mock_result(query: str) -> str:
    """
    Return mock results when database is not available.

    Args:
        query: The natural language query.

    Returns:
        Mock response string.
    """
    return (
        "Based on the financial data:\n\n"
        "  • ticker: NVDA\n"
        "  • name: NVIDIA Corporation\n"
        "  • fiscal_year: 2025\n"
        "  • revenue: $130,497M\n"
        "  • net_income: $72,880M\n\n"
        "Note: This is mock data. Configure DATABASE_URL for real queries.\n\n"
        f"Query: {query}"
    )


# =============================================================================
# Main Tool Function
# =============================================================================


@tool("sql_query", args_schema=SQLQueryInput)
async def sql_query(query: str) -> str:
    """
    Query the 10-K financial database using natural language.

    This tool converts your question to SQL, validates it for safety,
    executes it against the PostgreSQL database, and returns formatted results.

    Examples:
        - "What was NVIDIA's revenue in 2024?"
        - "Which company has the highest net margin?"
        - "Show segment revenue breakdown for tech companies"
        - "List all risk factors related to supply chain"

    Args:
        query: Natural language question about financial data.

    Returns:
        Formatted response with data and the SQL query used.
    """
    settings = get_settings()

    # Check if database is configured
    if not settings.database_url:
        logger.info("sql_query_mock_mode", query=query)
        return _build_mock_result(query)

    try:
        # Step 1: Convert natural language to SQL
        logger.info("sql_query_converting", query=query)
        sql = await _convert_nl_to_sql(query)

        logger.debug("sql_query_generated", sql=sql)

        # Step 2: Validate the generated SQL
        is_valid, error_message = validate_query(sql)
        if not is_valid:
            logger.warning(
                "sql_query_validation_failed",
                query=query,
                sql=sql,
                error=error_message,
            )
            return (
                f"I couldn't execute that query safely: {error_message}\n\n"
                f"Please try rephrasing your question. I can answer questions about "
                f"company financials, revenue segments, geographic breakdown, and risk factors."
            )

        # Step 3: Sanitize the query (add LIMIT if needed)
        safe_sql = sanitize_query(sql)

        # Step 4: Execute with timeout
        rows = _execute_query(safe_sql, timeout=DEFAULT_TIMEOUT_SECONDS)

        # Step 5: Format and return results
        return _format_results(rows, safe_sql, query)

    except ValueError as e:
        # User-friendly errors from our code
        return str(e)

    except Exception as e:
        logger.error(
            "sql_query_unexpected_error",
            query=query,
            error=str(e),
        )
        return (
            "I encountered an error processing your query. "
            "Please try rephrasing your question or ask about a different topic."
        )


# =============================================================================
# Module Exports
# =============================================================================

__all__ = ["sql_query", "SQLQueryInput"]
