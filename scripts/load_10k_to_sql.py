#!/usr/bin/env python3
"""
SQL data loading script for VLM-extracted 10-K financial data.

This script loads pre-consolidated financial data from VLM extractions into
PostgreSQL tables. It uses the consolidated data structure produced by
DocumentProcessor, NOT raw page parsing.

Usage:
    # Show help
    python scripts/load_10k_to_sql.py --help

    # Validate extractions without loading (dry run)
    python scripts/load_10k_to_sql.py --validate-only

    # Dry run - show what would be loaded
    python scripts/load_10k_to_sql.py --dry-run

    # Load all extracted 10-K documents
    python scripts/load_10k_to_sql.py

    # Load specific ticker only
    python scripts/load_10k_to_sql.py --ticker NVDA

    # Force reload (drop and re-insert data for ticker)
    python scripts/load_10k_to_sql.py --ticker AAPL --force

Reference:
    - PHASE_2A_HOW_TO_GUIDE.md Section 6.3 for requirements
    - backend.mdc for Python patterns
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

# Add backend/src to path for imports when running locally
PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = PROJECT_ROOT / "backend"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

# Load environment variables from .env
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    print("Warning: python-dotenv not installed. Using existing environment variables.")


# =============================================================================
# Terminal Colors
# =============================================================================

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"


# =============================================================================
# DataLoader Class
# =============================================================================


class DataLoader:
    """
    Load VLM-extracted 10-K data into PostgreSQL tables.

    This class handles the transformation and loading of consolidated
    financial data from JSON extractions into the SQL schema created
    by the Alembic migration.

    Attributes:
        database_url: PostgreSQL connection string.
        engine: SQLAlchemy engine instance.
        verbose: Whether to print detailed output.
    """

    def __init__(self, database_url: str, verbose: bool = True) -> None:
        """
        Initialize DataLoader with database connection.

        Args:
            database_url: PostgreSQL connection URL.
            verbose: If True, print progress information.

        Raises:
            ImportError: If SQLAlchemy is not installed.
            ConnectionError: If database connection fails.
        """
        try:
            from sqlalchemy import create_engine, text
            from sqlalchemy.orm import sessionmaker
        except ImportError as e:
            raise ImportError(
                "SQLAlchemy is required. Install with: pip install sqlalchemy"
            ) from e

        # Check for psycopg2 driver
        try:
            import psycopg2  # noqa: F401
        except ImportError as e:
            raise ImportError(
                "psycopg2 is required for PostgreSQL. Install with: "
                "pip install psycopg2-binary"
            ) from e

        self.database_url = database_url
        self.verbose = verbose

        # Create engine and session factory
        self.engine = create_engine(
            database_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
        self.Session = sessionmaker(bind=self.engine)

        # Verify connection
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            if verbose:
                print(f"{GREEN}✓ Database connection successful{RESET}")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to database: {e}") from e

        # Verify required tables exist
        self._verify_tables()

    def _log(self, message: str) -> None:
        """Print message if verbose mode is enabled."""
        if self.verbose:
            print(message)

    def _verify_tables(self) -> None:
        """
        Verify that required database tables exist.

        Raises:
            RuntimeError: If required tables are missing (migration not run).
        """
        from sqlalchemy import text

        required_tables = [
            "companies",
            "financial_metrics",
            "segment_revenue",
            "geographic_revenue",
            "risk_factors",
        ]

        with self.engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                """)
            )
            existing_tables = {row[0] for row in result}

        missing = set(required_tables) - existing_tables
        if missing:
            raise RuntimeError(
                f"Required tables missing: {', '.join(sorted(missing))}\n"
                f"Run the Alembic migration first:\n"
                f"  docker-compose exec backend alembic upgrade head"
            )

    def _safe_decimal(self, value: Any) -> Decimal | None:
        """
        Safely convert a value to Decimal for database storage.

        Args:
            value: Value to convert (int, float, str, or None).

        Returns:
            Decimal value or None if conversion fails.
        """
        if value is None:
            return None

        try:
            # Handle string numbers with commas
            if isinstance(value, str):
                value = value.replace(",", "").replace("$", "").strip()
                if not value or value.lower() in ("null", "none", "n/a", "-"):
                    return None

            return Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return None

    def _safe_int(self, value: Any) -> int | None:
        """Safely convert value to integer."""
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    def _extract_ticker_from_doc_id(self, doc_id: str) -> str | None:
        """
        Extract ticker symbol from document ID.

        Args:
            doc_id: Document ID like "AAPL_10K_2024" or filename.

        Returns:
            Ticker symbol or None if not found.
        """
        # Pattern: TICKER_10K_YEAR or TICKER_10K_YYYY
        match = re.match(r"^([A-Z]{1,5})_10[Kk]_\d{4}", doc_id)
        if match:
            return match.group(1)
        return None

    def _load_company(self, extraction: dict[str, Any]) -> int:
        """
        Load or update company record from extraction metadata.

        Args:
            extraction: Full extraction result dictionary.

        Returns:
            Company ID (existing or newly created).

        Raises:
            ValueError: If ticker cannot be determined.
        """
        from sqlalchemy import text

        metadata = extraction.get("metadata", {})
        doc_id = extraction.get("doc_id", extraction.get("document_id", ""))

        # Get ticker from metadata or doc_id
        ticker = metadata.get("ticker") or self._extract_ticker_from_doc_id(doc_id)
        if not ticker:
            raise ValueError(f"Cannot determine ticker from extraction: {doc_id}")

        # Get company name (fallback to ticker if not found)
        company_name = metadata.get("company") or metadata.get("company_name") or ticker

        # Get fiscal year for filing date
        consolidated = extraction.get("consolidated", {})
        fiscal_years = list(consolidated.get("financial_metrics_by_year", {}).keys())
        fiscal_year = max(fiscal_years) if fiscal_years else None

        with self.Session() as session:
            # Check if company exists
            result = session.execute(
                text("SELECT id FROM companies WHERE ticker = :ticker"),
                {"ticker": ticker}
            )
            existing = result.fetchone()

            if existing:
                company_id = existing[0]
                # Update company record
                session.execute(
                    text("""
                        UPDATE companies
                        SET name = :name,
                            sector = :sector,
                            document_id = :document_id
                        WHERE id = :id
                    """),
                    {
                        "id": company_id,
                        "name": company_name,
                        "sector": metadata.get("sector"),
                        "document_id": doc_id,
                    }
                )
                self._log(f"  Updated company: {ticker} (ID: {company_id})")
            else:
                # Insert new company
                result = session.execute(
                    text("""
                        INSERT INTO companies (ticker, name, sector, document_id)
                        VALUES (:ticker, :name, :sector, :document_id)
                        RETURNING id
                    """),
                    {
                        "ticker": ticker,
                        "name": company_name,
                        "sector": metadata.get("sector"),
                        "document_id": doc_id,
                    }
                )
                company_id = result.fetchone()[0]
                self._log(f"  Created company: {ticker} (ID: {company_id})")

            session.commit()
            return company_id

    def _load_financial_metrics(
        self, consolidated: dict[str, Any], company_id: int
    ) -> int:
        """
        Load financial metrics from consolidated.financial_metrics_by_year.

        Uses upsert (INSERT ... ON CONFLICT UPDATE) to handle re-runs.

        Args:
            consolidated: Consolidated data from extraction.
            company_id: Company ID for foreign key.

        Returns:
            Number of rows inserted/updated.
        """
        from sqlalchemy import text

        metrics_by_year = consolidated.get("financial_metrics_by_year", {})
        rows_affected = 0

        with self.Session() as session:
            for year_str, metrics in metrics_by_year.items():
                fiscal_year = self._safe_int(year_str)
                if not fiscal_year:
                    continue

                # Map consolidated keys to SQL columns
                row = {
                    "company_id": company_id,
                    "fiscal_year": fiscal_year,
                    "revenue": self._safe_decimal(metrics.get("revenue")),
                    "cost_of_revenue": self._safe_decimal(metrics.get("cost_of_revenue")),
                    "gross_profit": self._safe_decimal(metrics.get("gross_profit")),
                    "operating_expenses": self._safe_decimal(metrics.get("operating_expenses")),
                    "operating_income": self._safe_decimal(metrics.get("operating_income")),
                    "net_income": self._safe_decimal(metrics.get("net_income")),
                    "total_assets": self._safe_decimal(metrics.get("total_assets")),
                    "total_liabilities": self._safe_decimal(metrics.get("total_liabilities")),
                    "total_equity": self._safe_decimal(metrics.get("total_equity")),
                    "cash_and_equivalents": self._safe_decimal(metrics.get("cash_and_equivalents")),
                    "long_term_debt": self._safe_decimal(metrics.get("long_term_debt")),
                    "gross_margin": self._safe_decimal(metrics.get("gross_margin")),
                    "operating_margin": self._safe_decimal(metrics.get("operating_margin")),
                    "net_margin": self._safe_decimal(metrics.get("net_margin")),
                    "earnings_per_share": self._safe_decimal(metrics.get("earnings_per_share")),
                    "diluted_eps": self._safe_decimal(metrics.get("diluted_eps")),
                    "currency": metrics.get("currency", "USD"),
                }

                # Upsert: INSERT or UPDATE on conflict
                session.execute(
                    text("""
                        INSERT INTO financial_metrics (
                            company_id, fiscal_year, revenue, cost_of_revenue, gross_profit,
                            operating_expenses, operating_income, net_income,
                            total_assets, total_liabilities, total_equity,
                            cash_and_equivalents, long_term_debt,
                            gross_margin, operating_margin, net_margin,
                            earnings_per_share, diluted_eps, currency
                        ) VALUES (
                            :company_id, :fiscal_year, :revenue, :cost_of_revenue, :gross_profit,
                            :operating_expenses, :operating_income, :net_income,
                            :total_assets, :total_liabilities, :total_equity,
                            :cash_and_equivalents, :long_term_debt,
                            :gross_margin, :operating_margin, :net_margin,
                            :earnings_per_share, :diluted_eps, :currency
                        )
                        ON CONFLICT (company_id, fiscal_year) DO UPDATE SET
                            revenue = EXCLUDED.revenue,
                            cost_of_revenue = EXCLUDED.cost_of_revenue,
                            gross_profit = EXCLUDED.gross_profit,
                            operating_expenses = EXCLUDED.operating_expenses,
                            operating_income = EXCLUDED.operating_income,
                            net_income = EXCLUDED.net_income,
                            total_assets = EXCLUDED.total_assets,
                            total_liabilities = EXCLUDED.total_liabilities,
                            total_equity = EXCLUDED.total_equity,
                            cash_and_equivalents = EXCLUDED.cash_and_equivalents,
                            long_term_debt = EXCLUDED.long_term_debt,
                            gross_margin = EXCLUDED.gross_margin,
                            operating_margin = EXCLUDED.operating_margin,
                            net_margin = EXCLUDED.net_margin,
                            earnings_per_share = EXCLUDED.earnings_per_share,
                            diluted_eps = EXCLUDED.diluted_eps,
                            currency = EXCLUDED.currency
                    """),
                    row
                )
                rows_affected += 1

            session.commit()

        return rows_affected

    def _load_segments(self, consolidated: dict[str, Any], company_id: int) -> int:
        """
        Load segment revenue from consolidated.segment_revenue.

        Args:
            consolidated: Consolidated data from extraction.
            company_id: Company ID for foreign key.

        Returns:
            Number of rows inserted.
        """
        from sqlalchemy import text

        segments = consolidated.get("segment_revenue", [])
        rows_inserted = 0

        with self.Session() as session:
            # First, delete existing segments for this company (avoid duplicates)
            session.execute(
                text("DELETE FROM segment_revenue WHERE company_id = :company_id"),
                {"company_id": company_id}
            )

            for segment in segments:
                if not segment.get("segment_name"):
                    continue

                row = {
                    "company_id": company_id,
                    "fiscal_year": self._safe_int(segment.get("fiscal_year")),
                    "segment_name": segment.get("segment_name"),
                    "revenue": self._safe_decimal(segment.get("revenue")),
                    "percentage_of_total": self._safe_decimal(segment.get("percentage_of_total")),
                    "yoy_growth": self._safe_decimal(segment.get("yoy_growth")),
                }

                # Skip if no fiscal year
                if not row["fiscal_year"]:
                    continue

                session.execute(
                    text("""
                        INSERT INTO segment_revenue (
                            company_id, fiscal_year, segment_name,
                            revenue, percentage_of_total, yoy_growth
                        ) VALUES (
                            :company_id, :fiscal_year, :segment_name,
                            :revenue, :percentage_of_total, :yoy_growth
                        )
                    """),
                    row
                )
                rows_inserted += 1

            session.commit()

        return rows_inserted

    def _load_geographic(self, consolidated: dict[str, Any], company_id: int) -> int:
        """
        Load geographic revenue from consolidated.geographic_revenue.

        Args:
            consolidated: Consolidated data from extraction.
            company_id: Company ID for foreign key.

        Returns:
            Number of rows inserted.
        """
        from sqlalchemy import text

        geographic = consolidated.get("geographic_revenue", [])
        rows_inserted = 0

        with self.Session() as session:
            # First, delete existing geographic data for this company
            session.execute(
                text("DELETE FROM geographic_revenue WHERE company_id = :company_id"),
                {"company_id": company_id}
            )

            for geo in geographic:
                if not geo.get("region"):
                    continue

                row = {
                    "company_id": company_id,
                    "fiscal_year": self._safe_int(geo.get("fiscal_year")),
                    "region": geo.get("region"),
                    "revenue": self._safe_decimal(geo.get("revenue")),
                    "percentage_of_total": self._safe_decimal(geo.get("percentage_of_total")),
                    "yoy_growth": self._safe_decimal(geo.get("yoy_growth")),
                }

                # Skip if no fiscal year
                if not row["fiscal_year"]:
                    continue

                session.execute(
                    text("""
                        INSERT INTO geographic_revenue (
                            company_id, fiscal_year, region,
                            revenue, percentage_of_total, yoy_growth
                        ) VALUES (
                            :company_id, :fiscal_year, :region,
                            :revenue, :percentage_of_total, :yoy_growth
                        )
                    """),
                    row
                )
                rows_inserted += 1

            session.commit()

        return rows_inserted

    def _load_risks(self, consolidated: dict[str, Any], company_id: int) -> int:
        """
        Load risk factors from consolidated.risk_factors.

        Args:
            consolidated: Consolidated data from extraction.
            company_id: Company ID for foreign key.

        Returns:
            Number of rows inserted.
        """
        from sqlalchemy import text

        risks = consolidated.get("risk_factors", [])
        rows_inserted = 0

        # Get fiscal year from financial metrics
        metrics_by_year = consolidated.get("financial_metrics_by_year", {})
        fiscal_years = list(metrics_by_year.keys())
        default_fiscal_year = max(fiscal_years) if fiscal_years else None

        with self.Session() as session:
            # First, delete existing risks for this company
            session.execute(
                text("DELETE FROM risk_factors WHERE company_id = :company_id"),
                {"company_id": company_id}
            )

            for risk in risks:
                if not risk.get("title"):
                    continue

                row = {
                    "company_id": company_id,
                    "fiscal_year": self._safe_int(
                        risk.get("fiscal_year") or default_fiscal_year
                    ),
                    "category": risk.get("category"),
                    "title": risk.get("title"),
                    "summary": risk.get("summary"),
                    "severity": risk.get("severity"),
                    "page_number": self._safe_int(risk.get("page_number")),
                }

                # Validate severity
                if row["severity"] and row["severity"] not in ("high", "medium", "low"):
                    row["severity"] = None

                session.execute(
                    text("""
                        INSERT INTO risk_factors (
                            company_id, fiscal_year, category,
                            title, summary, severity, page_number
                        ) VALUES (
                            :company_id, :fiscal_year, :category,
                            :title, :summary, :severity, :page_number
                        )
                    """),
                    row
                )
                rows_inserted += 1

            session.commit()

        return rows_inserted

    def validate_extraction(self, extraction: dict[str, Any]) -> list[str]:
        """
        Validate extraction has required data for SQL tool.

        Args:
            extraction: Full extraction result dictionary.

        Returns:
            List of warnings (empty = valid).
        """
        warnings: list[str] = []
        consolidated = extraction.get("consolidated", {})
        doc_id = extraction.get("doc_id", extraction.get("document_id", "unknown"))

        # Check if it's a 10-K (reference docs don't have financial metrics)
        # Handle both "doc_type" and "document_type" keys
        doc_type = (
            extraction.get("doc_type")
            or extraction.get("document_type")
            or ""
        ).lower()
        if "10k" not in doc_type:
            warnings.append(f"Not a 10-K document (doc_type={doc_type})")
            return warnings

        # Check consolidated exists
        if not consolidated:
            warnings.append("No consolidated data found - extraction may have failed")
            return warnings

        # Check financial metrics exist
        metrics_by_year = consolidated.get("financial_metrics_by_year", {})
        if not metrics_by_year:
            warnings.append("No financial metrics found - SQL queries will fail")
        else:
            for year, metrics in metrics_by_year.items():
                if not metrics.get("revenue"):
                    warnings.append(f"Missing revenue for year {year}")
                if not metrics.get("net_income"):
                    warnings.append(f"Missing net_income for year {year}")

        # Check segments exist (expected for most 10-Ks)
        segments = consolidated.get("segment_revenue", [])
        if not segments:
            warnings.append("No segment revenue found - segment queries will return empty")

        # Check geographic exists
        geographic = consolidated.get("geographic_revenue", [])
        if not geographic:
            warnings.append("No geographic revenue found - geographic queries will return empty")

        # Check risk factors exist
        risks = consolidated.get("risk_factors", [])
        if not risks:
            warnings.append("No risk factors found - risk queries will return empty")

        return warnings

    def load_document(self, json_path: Path) -> dict[str, Any]:
        """
        Load a single extracted document into SQL.

        Args:
            json_path: Path to the extracted JSON file.

        Returns:
            Statistics dictionary with counts.

        Raises:
            FileNotFoundError: If JSON file doesn't exist.
            ValueError: If extraction is invalid or not a 10-K.
        """
        if not json_path.exists():
            raise FileNotFoundError(f"Extraction file not found: {json_path}")

        with open(json_path, encoding="utf-8") as f:
            extraction = json.load(f)

        # Validate
        warnings = self.validate_extraction(extraction)
        doc_id = extraction.get("doc_id", extraction.get("document_id", json_path.stem))
        doc_type = (
            extraction.get("doc_type")
            or extraction.get("document_type")
            or ""
        ).lower()

        # Skip non-10K documents
        if "10k" not in doc_type:
            return {
                "doc_id": doc_id,
                "status": "skipped",
                "reason": f"Not a 10-K (doc_type={doc_type})",
                "warnings": warnings,
            }

        # Log warnings
        for warning in warnings:
            self._log(f"  {YELLOW}⚠ {warning}{RESET}")

        # Check for critical failures
        consolidated = extraction.get("consolidated", {})
        if not consolidated or not consolidated.get("financial_metrics_by_year"):
            return {
                "doc_id": doc_id,
                "status": "failed",
                "reason": "No financial metrics in consolidated data",
                "warnings": warnings,
            }

        # Load data
        try:
            company_id = self._load_company(extraction)
            metrics_count = self._load_financial_metrics(consolidated, company_id)
            segments_count = self._load_segments(consolidated, company_id)
            geographic_count = self._load_geographic(consolidated, company_id)
            risks_count = self._load_risks(consolidated, company_id)

            return {
                "doc_id": doc_id,
                "status": "success",
                "company_id": company_id,
                "metrics_loaded": metrics_count,
                "segments_loaded": segments_count,
                "geographic_loaded": geographic_count,
                "risks_loaded": risks_count,
                "warnings": warnings,
            }

        except Exception as e:
            return {
                "doc_id": doc_id,
                "status": "error",
                "error": str(e),
                "warnings": warnings,
            }

    def load_all(
        self,
        extracted_dir: Path,
        ticker_filter: str | None = None,
    ) -> dict[str, Any]:
        """
        Load all extracted 10-K documents from directory.

        Args:
            extracted_dir: Path to directory containing extracted JSON files.
            ticker_filter: If provided, only load this ticker.

        Returns:
            Summary statistics dictionary.
        """
        if not extracted_dir.exists():
            raise FileNotFoundError(f"Extracted directory not found: {extracted_dir}")

        # Find all JSON files (excluding manifest)
        json_files = [
            f for f in extracted_dir.glob("*.json")
            if f.name != "manifest.json" and f.is_file()
        ]

        # Filter by ticker if specified
        if ticker_filter:
            json_files = [
                f for f in json_files
                if f.stem.upper().startswith(ticker_filter.upper())
            ]

        if not json_files:
            self._log(f"{YELLOW}No JSON files found in {extracted_dir}{RESET}")
            return {"documents_processed": 0, "documents_loaded": 0}

        self._log(f"\n{BOLD}Loading {len(json_files)} documents...{RESET}\n")

        results = []
        for json_path in sorted(json_files):
            self._log(f"Processing {json_path.name}...")
            result = self.load_document(json_path)
            results.append(result)

            status = result.get("status")
            if status == "success":
                self._log(
                    f"  {GREEN}✓ Loaded: {result.get('metrics_loaded', 0)} metrics, "
                    f"{result.get('segments_loaded', 0)} segments, "
                    f"{result.get('geographic_loaded', 0)} geographic, "
                    f"{result.get('risks_loaded', 0)} risks{RESET}"
                )
            elif status == "skipped":
                self._log(f"  {BLUE}○ Skipped: {result.get('reason')}{RESET}")
            else:
                self._log(f"  {RED}✗ Failed: {result.get('error', result.get('reason'))}{RESET}")

        # Calculate summary
        success_count = sum(1 for r in results if r.get("status") == "success")
        skipped_count = sum(1 for r in results if r.get("status") == "skipped")
        failed_count = sum(1 for r in results if r.get("status") in ("failed", "error"))

        return {
            "documents_processed": len(results),
            "documents_loaded": success_count,
            "documents_skipped": skipped_count,
            "documents_failed": failed_count,
            "results": results,
        }

    def delete_company_data(self, ticker: str) -> bool:
        """
        Delete all data for a company (for --force reload).

        Args:
            ticker: Company ticker symbol.

        Returns:
            True if company was deleted, False if not found.
        """
        from sqlalchemy import text

        with self.Session() as session:
            result = session.execute(
                text("SELECT id FROM companies WHERE ticker = :ticker"),
                {"ticker": ticker.upper()}
            )
            existing = result.fetchone()

            if existing:
                company_id = existing[0]
                # CASCADE delete handles child tables
                session.execute(
                    text("DELETE FROM companies WHERE id = :id"),
                    {"id": company_id}
                )
                session.commit()
                self._log(f"  {YELLOW}Deleted existing data for {ticker}{RESET}")
                return True

        return False


# =============================================================================
# CLI Functions
# =============================================================================


def validate_only(args: argparse.Namespace) -> int:
    """Run validation checks without loading data."""
    extracted_dir = args.extracted_dir

    if not extracted_dir.exists():
        print(f"{RED}Error: Extracted directory not found: {extracted_dir}{RESET}")
        return 1

    json_files = [
        f for f in extracted_dir.glob("*.json")
        if f.name != "manifest.json" and f.is_file()
    ]

    if args.ticker:
        json_files = [
            f for f in json_files
            if f.stem.upper().startswith(args.ticker.upper())
        ]

    if not json_files:
        print(f"{YELLOW}No JSON files found{RESET}")
        return 0

    print(f"\n{BOLD}Validating {len(json_files)} extraction files...{RESET}\n")

    total_warnings = 0
    valid_count = 0

    for json_path in sorted(json_files):
        with open(json_path, encoding="utf-8") as f:
            extraction = json.load(f)

        doc_id = extraction.get("doc_id", extraction.get("document_id", json_path.stem))
        doc_type = (
            extraction.get("doc_type")
            or extraction.get("document_type")
            or "unknown"
        ).lower()
        consolidated = extraction.get("consolidated", {})
        metadata = extraction.get("metadata", {})

        print(f"Processing {json_path.name}...")
        print(f"  Company: {metadata.get('company', 'Unknown')} ({metadata.get('ticker', 'N/A')})")

        # Skip non-10K
        if "10k" not in doc_type.lower():
            print(f"  {BLUE}○ Skipped (not a 10-K){RESET}")
            continue

        # Check financial metrics
        metrics_by_year = consolidated.get("financial_metrics_by_year", {})
        if metrics_by_year:
            years = sorted(metrics_by_year.keys(), reverse=True)
            print(f"  Financial metrics: {len(years)} years ({', '.join(years)})")
            for year in years:
                m = metrics_by_year[year]
                rev = m.get("revenue")
                ni = m.get("net_income")
                if rev and ni:
                    print(f"    {year}: revenue=${rev:,.0f}M, net_income=${ni:,.0f}M {GREEN}✓{RESET}")
                else:
                    print(f"    {year}: {YELLOW}⚠ Missing revenue or net_income{RESET}")
                    total_warnings += 1
        else:
            print(f"  {RED}✗ No financial metrics found{RESET}")
            total_warnings += 1

        # Check segments
        segments = consolidated.get("segment_revenue", [])
        if segments:
            seg_names = [s.get("segment_name", "?") for s in segments[:5]]
            print(f"  Segments: {len(segments)} found ({', '.join(seg_names)}) {GREEN}✓{RESET}")
        else:
            print(f"  {YELLOW}⚠ No segment revenue found{RESET}")
            total_warnings += 1

        # Check geographic
        geographic = consolidated.get("geographic_revenue", [])
        if geographic:
            geo_names = [g.get("region", "?") for g in geographic[:4]]
            print(f"  Geographic regions: {len(geographic)} found ({', '.join(geo_names)}) {GREEN}✓{RESET}")
        else:
            print(f"  {YELLOW}⚠ No geographic revenue found{RESET}")
            total_warnings += 1

        # Check risks
        risks = consolidated.get("risk_factors", [])
        if risks:
            print(f"  Risk factors: {len(risks)} found {GREEN}✓{RESET}")
        else:
            print(f"  {YELLOW}⚠ No risk factors found{RESET}")
            total_warnings += 1

        # Summary for this doc
        doc_warnings = 0
        if not metrics_by_year:
            doc_warnings += 1
        if not segments:
            doc_warnings += 1
        if not geographic:
            doc_warnings += 1
        if not risks:
            doc_warnings += 1

        if doc_warnings == 0:
            print(f"  {GREEN}✓ All validation checks passed{RESET}")
            valid_count += 1
        else:
            print(f"  {YELLOW}⚠ {doc_warnings} warnings (non-blocking){RESET}")
            valid_count += 1  # Still valid, just with warnings

        print()

    # Summary
    print(f"\n{BOLD}Summary:{RESET}")
    print(f"  Documents validated: {len(json_files)}")
    print(f"  Warnings: {total_warnings}")
    print(f"  Ready to load: {GREEN}Yes{RESET}" if valid_count > 0 else f"  Ready to load: {RED}No{RESET}")

    return 0


def dry_run(args: argparse.Namespace, loader: DataLoader) -> int:
    """Show what would be loaded without actually loading."""
    extracted_dir = args.extracted_dir

    json_files = [
        f for f in extracted_dir.glob("*.json")
        if f.name != "manifest.json" and f.is_file()
    ]

    if args.ticker:
        json_files = [
            f for f in json_files
            if f.stem.upper().startswith(args.ticker.upper())
        ]

    print(f"\n{BOLD}Dry run - would load {len(json_files)} documents:{RESET}\n")

    for json_path in sorted(json_files):
        with open(json_path, encoding="utf-8") as f:
            extraction = json.load(f)

        doc_type = (
            extraction.get("doc_type")
            or extraction.get("document_type")
            or "unknown"
        ).lower()
        metadata = extraction.get("metadata", {})
        consolidated = extraction.get("consolidated", {})

        ticker = metadata.get("ticker", "N/A")
        company = metadata.get("company", "Unknown")

        if "10k" not in doc_type.lower():
            print(f"  {BLUE}○ {json_path.name} - Skip (not 10-K){RESET}")
            continue

        metrics_count = len(consolidated.get("financial_metrics_by_year", {}))
        segments_count = len(consolidated.get("segment_revenue", []))
        geo_count = len(consolidated.get("geographic_revenue", []))
        risks_count = len(consolidated.get("risk_factors", []))

        print(f"  {GREEN}✓ {json_path.name}{RESET}")
        print(f"      Company: {company} ({ticker})")
        print(f"      Would load: {metrics_count} years, {segments_count} segments, {geo_count} regions, {risks_count} risks")

    return 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Load VLM-extracted 10-K data into PostgreSQL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate extractions
  python scripts/load_10k_to_sql.py --validate-only

  # Dry run
  python scripts/load_10k_to_sql.py --dry-run

  # Load all 10-K documents
  python scripts/load_10k_to_sql.py

  # Load specific ticker
  python scripts/load_10k_to_sql.py --ticker NVDA

  # Force reload (delete and re-insert)
  python scripts/load_10k_to_sql.py --ticker AAPL --force
        """,
    )

    parser.add_argument(
        "--extracted-dir",
        type=Path,
        default=PROJECT_ROOT / "documents" / "extracted",
        help="Path to extracted JSON files (default: documents/extracted)",
    )
    parser.add_argument(
        "--database-url",
        type=str,
        default=None,
        help="Override DATABASE_URL environment variable",
    )
    parser.add_argument(
        "--ticker",
        type=str,
        help="Load specific ticker only (e.g., AAPL, NVDA)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Drop and reload data for ticker (requires --ticker)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and validate without loading",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Run validation checks without loading",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output",
    )

    args = parser.parse_args()

    # Get database URL
    database_url = args.database_url or os.environ.get("DATABASE_URL")
    if not database_url:
        print(f"{RED}Error: DATABASE_URL not set{RESET}")
        print("Set DATABASE_URL environment variable or use --database-url flag")
        return 1

    # Warn if using Docker default (likely wrong database)
    if "postgres:5432" in database_url or "localhost:5432" in database_url:
        print(f"{YELLOW}⚠ Warning: DATABASE_URL appears to be a local/Docker database{RESET}")
        print(f"  Current: {database_url[:50]}...")
        print(f"  For Neon PostgreSQL, update your .env file with the correct URL")
        print(f"  Get the URL from AWS Secrets Manager: enterprise-ai-demo/dev/neon-database")
        print()

    # Validate --force requires --ticker
    if args.force and not args.ticker:
        print(f"{RED}Error: --force requires --ticker{RESET}")
        return 1

    # Check extracted directory exists
    if not args.extracted_dir.exists():
        print(f"{RED}Error: Extracted directory not found: {args.extracted_dir}{RESET}")
        print(f"\nTo fix this:")
        print(f"  1. Run VLM extraction first: python scripts/extract_and_index.py")
        print(f"  2. Check that JSON files exist in {args.extracted_dir}")
        return 1

    # Validate-only mode (no DB connection needed)
    if args.validate_only:
        return validate_only(args)

    # Create loader
    try:
        loader = DataLoader(database_url, verbose=not args.quiet)
    except Exception as e:
        print(f"{RED}Error connecting to database: {e}{RESET}")
        return 1

    # Dry run mode
    if args.dry_run:
        return dry_run(args, loader)

    # Force mode - delete existing data first
    if args.force and args.ticker:
        loader.delete_company_data(args.ticker)

    # Load data
    try:
        result = loader.load_all(args.extracted_dir, ticker_filter=args.ticker)

        # Print summary
        print(f"\n{BOLD}{'=' * 50}{RESET}")
        print(f"{BOLD}Loading Complete{RESET}")
        print(f"{BOLD}{'=' * 50}{RESET}")
        print(f"  Documents processed: {result.get('documents_processed', 0)}")
        print(f"  Documents loaded: {GREEN}{result.get('documents_loaded', 0)}{RESET}")
        print(f"  Documents skipped: {BLUE}{result.get('documents_skipped', 0)}{RESET}")
        print(f"  Documents failed: {RED}{result.get('documents_failed', 0)}{RESET}")

        return 0 if result.get("documents_failed", 0) == 0 else 1

    except Exception as e:
        print(f"{RED}Error: {e}{RESET}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
