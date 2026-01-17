"""
SQL Safety module for query validation and sanitization.

This module provides security controls for SQL queries executed by the agent,
preventing SQL injection and ensuring queries only access allowed tables/columns.

Security Features:
    - Table whitelist enforcement
    - Column whitelist enforcement per table
    - Read-only query validation (SELECT only)
    - Dangerous keyword detection
    - Query sanitization (LIMIT enforcement, comment stripping)
    - Query timeout configuration

Usage:
    from src.agent.tools.sql_safety import (
        validate_query,
        sanitize_query,
        ALLOWED_TABLES,
        ALLOWED_COLUMNS,
    )

    is_valid, error = validate_query("SELECT * FROM companies")
    if not is_valid:
        raise ValueError(error)

    safe_query = sanitize_query("SELECT * FROM companies")
"""

from __future__ import annotations

import re

import structlog

logger = structlog.get_logger()


# =============================================================================
# Constants - Table and Column Whitelists
# =============================================================================

ALLOWED_TABLES: set[str] = {
    "companies",
    "financial_metrics",
    "segment_revenue",
    "geographic_revenue",
    "risk_factors",
}

ALLOWED_COLUMNS: dict[str, list[str]] = {
    "companies": [
        "id",
        "ticker",
        "name",
        "sector",
        "fiscal_year_end",
        "filing_date",
        "document_id",
        "created_at",
        "updated_at",
    ],
    "financial_metrics": [
        "id",
        "company_id",
        "fiscal_year",
        "revenue",
        "cost_of_revenue",
        "gross_profit",
        "operating_expenses",
        "operating_income",
        "net_income",
        "total_assets",
        "total_liabilities",
        "total_equity",
        "cash_and_equivalents",
        "long_term_debt",
        "gross_margin",
        "operating_margin",
        "net_margin",
        "earnings_per_share",
        "diluted_eps",
        "currency",
        "created_at",
    ],
    "segment_revenue": [
        "id",
        "company_id",
        "fiscal_year",
        "segment_name",
        "revenue",
        "percentage_of_total",
        "yoy_growth",
        "created_at",
    ],
    "geographic_revenue": [
        "id",
        "company_id",
        "fiscal_year",
        "region",
        "revenue",
        "percentage_of_total",
        "yoy_growth",
        "created_at",
    ],
    "risk_factors": [
        "id",
        "company_id",
        "fiscal_year",
        "category",
        "title",
        "summary",
        "severity",
        "page_number",
        "created_at",
    ],
}

# Dangerous SQL keywords that indicate write operations or DDL
DANGEROUS_KEYWORDS: set[str] = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "TRUNCATE",
    "CREATE",
    "GRANT",
    "REVOKE",
    "EXECUTE",
    "EXEC",
    "CALL",
    "INTO",  # SELECT INTO
}

# Default limits
DEFAULT_ROW_LIMIT = 100
MAX_ROW_LIMIT = 1000
DEFAULT_TIMEOUT_SECONDS = 30


# =============================================================================
# Query Validation Functions
# =============================================================================


def is_read_only(sql: str) -> bool:
    """
    Check if a SQL query is read-only (SELECT only).

    Args:
        sql: The SQL query string to check.

    Returns:
        True if the query is a SELECT statement without dangerous keywords.

    Examples:
        >>> is_read_only("SELECT * FROM companies")
        True
        >>> is_read_only("DELETE FROM companies")
        False
        >>> is_read_only("SELECT * INTO temp FROM companies")
        False
    """
    # Normalize query for checking
    normalized = _normalize_query(sql)

    # Must start with SELECT
    if not normalized.upper().startswith("SELECT"):
        return False

    # Check for dangerous keywords
    words = set(re.findall(r"\b([A-Z]+)\b", normalized.upper()))
    dangerous_found = words & DANGEROUS_KEYWORDS

    if dangerous_found:
        logger.warning(
            "sql_dangerous_keywords_detected",
            keywords=list(dangerous_found),
        )
        return False

    return True


def extract_tables(sql: str) -> set[str]:
    """
    Extract table names referenced in a SQL query.

    Uses regex patterns to find tables after FROM, JOIN, and related clauses.
    This is a lightweight alternative to full SQL parsing.

    Args:
        sql: The SQL query string.

    Returns:
        Set of table names found in the query.

    Examples:
        >>> extract_tables("SELECT * FROM companies")
        {'companies'}
        >>> extract_tables("SELECT * FROM companies c JOIN financial_metrics f ON c.id = f.company_id")
        {'companies', 'financial_metrics'}
    """
    tables: set[str] = set()

    # First normalize and strip comments
    normalized = _normalize_query(sql)

    # Strip string literals to avoid false positives
    # Replace 'string content' and "string content" with empty placeholder
    normalized = _strip_string_literals(normalized)

    # Patterns to match table references
    # FROM table, JOIN table, FROM table alias, etc.
    # Handle optional schema prefix (e.g., public.companies -> companies)
    patterns = [
        r"\bFROM\s+(?:[a-zA-Z_][a-zA-Z0-9_]*\.)?([a-zA-Z_][a-zA-Z0-9_]*)",  # FROM [schema.]table
        r"\bJOIN\s+(?:[a-zA-Z_][a-zA-Z0-9_]*\.)?([a-zA-Z_][a-zA-Z0-9_]*)",  # JOIN [schema.]table
        r"\bINTO\s+(?:[a-zA-Z_][a-zA-Z0-9_]*\.)?([a-zA-Z_][a-zA-Z0-9_]*)",  # INTO [schema.]table
        r"\bUPDATE\s+(?:[a-zA-Z_][a-zA-Z0-9_]*\.)?([a-zA-Z_][a-zA-Z0-9_]*)",  # UPDATE [schema.]table
    ]

    for pattern in patterns:
        matches = re.findall(pattern, normalized, re.IGNORECASE)
        tables.update(match.lower() for match in matches)

    return tables


def validate_tables(tables: set[str]) -> tuple[bool, str | None]:
    """
    Validate that all tables are in the whitelist.

    Args:
        tables: Set of table names to validate.

    Returns:
        Tuple of (is_valid, error_message).
        If valid, returns (True, None).
        If invalid, returns (False, error_message).
    """
    disallowed = tables - ALLOWED_TABLES

    if disallowed:
        error_msg = (
            f"Access denied: tables not allowed: {', '.join(sorted(disallowed))}"
        )
        logger.warning(
            "sql_disallowed_tables",
            disallowed_tables=list(disallowed),
            allowed_tables=list(ALLOWED_TABLES),
        )
        return False, error_msg

    return True, None


def validate_query(sql: str) -> tuple[bool, str | None]:
    """
    Validate a SQL query for safety before execution.

    Performs the following checks:
    1. Query is not empty
    2. Query is read-only (SELECT only)
    3. All referenced tables are in the whitelist

    Args:
        sql: The SQL query string to validate.

    Returns:
        Tuple of (is_valid, error_message).
        If valid, returns (True, None).
        If invalid, returns (False, error_message describing the issue).

    Examples:
        >>> validate_query("SELECT * FROM companies")
        (True, None)
        >>> validate_query("DELETE FROM companies")
        (False, 'Only SELECT queries are allowed')
        >>> validate_query("SELECT * FROM users")
        (False, 'Access denied: tables not allowed: users')
    """
    # Check for empty query
    if not sql or not sql.strip():
        return False, "Query cannot be empty"

    normalized = _normalize_query(sql)

    # Check read-only
    if not is_read_only(normalized):
        return False, "Only SELECT queries are allowed"

    # Extract and validate tables
    tables = extract_tables(normalized)

    if not tables:
        # No tables found - might be a simple SELECT without FROM
        # e.g., SELECT 1, SELECT CURRENT_TIMESTAMP
        # Allow these as they're harmless
        logger.debug("sql_no_tables_found", query=sql[:100])
        return True, None

    is_valid, error = validate_tables(tables)
    if not is_valid:
        return False, error

    logger.debug(
        "sql_query_validated",
        tables=list(tables),
        query_length=len(sql),
    )

    return True, None


# =============================================================================
# Query Sanitization Functions
# =============================================================================


def sanitize_query(sql: str) -> str:
    """
    Sanitize a SQL query for safe execution.

    Performs the following transformations:
    1. Strips SQL comments (-- and /* */)
    2. Normalizes whitespace
    3. Adds LIMIT clause if not present
    4. Ensures query ends properly

    Args:
        sql: The SQL query string to sanitize.

    Returns:
        Sanitized SQL query string.

    Examples:
        >>> sanitize_query("SELECT * FROM companies -- comment")
        'SELECT * FROM companies LIMIT 100'
        >>> sanitize_query("SELECT * FROM companies LIMIT 50")
        'SELECT * FROM companies LIMIT 50'
    """
    # Strip comments
    cleaned = _strip_comments(sql)

    # Normalize whitespace
    cleaned = _normalize_whitespace(cleaned)

    # Add LIMIT if not present
    cleaned = _ensure_limit(cleaned)

    return cleaned


def _normalize_query(sql: str) -> str:
    """
    Normalize a SQL query for analysis.

    Strips comments and normalizes whitespace without modifying
    the query structure.

    Args:
        sql: The SQL query string.

    Returns:
        Normalized SQL string.
    """
    # Strip comments first
    cleaned = _strip_comments(sql)

    # Normalize whitespace
    cleaned = _normalize_whitespace(cleaned)

    return cleaned


def _strip_comments(sql: str) -> str:
    """
    Remove SQL comments from a query.

    Handles:
    - Single-line comments: -- comment
    - Multi-line comments: /* comment */

    Args:
        sql: The SQL query string.

    Returns:
        Query with comments removed.
    """
    # Remove single-line comments
    sql = re.sub(r"--[^\n]*", "", sql)

    # Remove multi-line comments
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)

    return sql


def _strip_string_literals(sql: str) -> str:
    """
    Remove string literals from a query to avoid false positives in table extraction.

    Replaces 'string' and "string" with empty placeholders.
    This prevents table names inside string literals from being detected.

    Args:
        sql: The SQL query string.

    Returns:
        Query with string literals replaced.

    Examples:
        >>> _strip_string_literals("SELECT * FROM t WHERE name = 'FROM users'")
        "SELECT * FROM t WHERE name = ''"
    """
    # Replace single-quoted strings (handles escaped quotes '')
    sql = re.sub(r"'(?:[^']|'')*'", "''", sql)

    # Replace double-quoted strings (handles escaped quotes "")
    sql = re.sub(r'"(?:[^"]|"")*"', '""', sql)

    return sql


def _normalize_whitespace(sql: str) -> str:
    """
    Normalize whitespace in a SQL query.

    Collapses multiple spaces/newlines into single spaces
    and trims leading/trailing whitespace.

    Args:
        sql: The SQL query string.

    Returns:
        Query with normalized whitespace.
    """
    # Replace newlines and tabs with spaces
    sql = re.sub(r"[\n\r\t]+", " ", sql)

    # Collapse multiple spaces
    sql = re.sub(r" +", " ", sql)

    # Trim
    return sql.strip()


def _ensure_limit(sql: str) -> str:
    """
    Ensure a query has a LIMIT clause.

    If the query doesn't have a LIMIT, adds LIMIT 100.
    If it has a LIMIT higher than MAX_ROW_LIMIT, caps it.

    Args:
        sql: The SQL query string.

    Returns:
        Query with appropriate LIMIT clause.
    """
    # Check if LIMIT already exists
    limit_match = re.search(r"\bLIMIT\s+(\d+)", sql, re.IGNORECASE)

    if limit_match:
        # Check if limit is too high
        current_limit = int(limit_match.group(1))
        if current_limit > MAX_ROW_LIMIT:
            # Replace with max limit
            sql = re.sub(
                r"\bLIMIT\s+\d+",
                f"LIMIT {MAX_ROW_LIMIT}",
                sql,
                flags=re.IGNORECASE,
            )
            logger.warning(
                "sql_limit_capped",
                original_limit=current_limit,
                capped_to=MAX_ROW_LIMIT,
            )
        return sql

    # No LIMIT found - add default
    # Remove trailing semicolon if present
    sql = sql.rstrip(";").strip()

    return f"{sql} LIMIT {DEFAULT_ROW_LIMIT}"


# =============================================================================
# Utility Functions
# =============================================================================


def get_table_columns(table_name: str) -> list[str] | None:
    """
    Get the allowed columns for a table.

    Args:
        table_name: Name of the table.

    Returns:
        List of allowed column names, or None if table not allowed.

    Examples:
        >>> get_table_columns("companies")
        ['id', 'ticker', 'name', ...]
        >>> get_table_columns("users")
        None
    """
    return ALLOWED_COLUMNS.get(table_name.lower())


def validate_columns(table_name: str, columns: list[str]) -> tuple[bool, str | None]:
    """
    Validate that columns are allowed for a given table.

    Args:
        table_name: Name of the table.
        columns: List of column names to validate.

    Returns:
        Tuple of (is_valid, error_message).
        If valid, returns (True, None).
        If invalid, returns (False, error_message).

    Examples:
        >>> validate_columns("companies", ["ticker", "name"])
        (True, None)
        >>> validate_columns("companies", ["password"])
        (False, 'Columns not allowed for companies: password')
    """
    allowed = ALLOWED_COLUMNS.get(table_name.lower())

    if allowed is None:
        return False, f"Table not allowed: {table_name}"

    # Normalize column names
    normalized_columns = [c.lower().strip() for c in columns]
    allowed_set = set(c.lower() for c in allowed)

    disallowed = set(normalized_columns) - allowed_set

    if disallowed:
        error_msg = (
            f"Columns not allowed for {table_name}: {', '.join(sorted(disallowed))}"
        )
        logger.warning(
            "sql_disallowed_columns",
            table=table_name,
            disallowed_columns=list(disallowed),
        )
        return False, error_msg

    return True, None


def is_table_allowed(table_name: str) -> bool:
    """
    Check if a table is in the whitelist.

    Args:
        table_name: Name of the table to check.

    Returns:
        True if the table is allowed, False otherwise.
    """
    return table_name.lower() in ALLOWED_TABLES


def get_query_timeout() -> int:
    """
    Get the configured query timeout in seconds.

    Returns:
        Query timeout in seconds.
    """
    return DEFAULT_TIMEOUT_SECONDS


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    # Constants
    "ALLOWED_TABLES",
    "ALLOWED_COLUMNS",
    "DANGEROUS_KEYWORDS",
    "DEFAULT_ROW_LIMIT",
    "MAX_ROW_LIMIT",
    "DEFAULT_TIMEOUT_SECONDS",
    # Validation functions
    "validate_query",
    "is_read_only",
    "extract_tables",
    "validate_tables",
    "validate_columns",
    # Sanitization functions
    "sanitize_query",
    # Utility functions
    "get_table_columns",
    "is_table_allowed",
    "get_query_timeout",
]
