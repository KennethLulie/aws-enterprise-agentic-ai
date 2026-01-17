"""Create 10-K financial data schema.

This migration creates the database tables for storing structured financial
data extracted from SEC 10-K filings using VLM extraction.

Tables:
- companies: Company metadata (ticker, name, sector)
- financial_metrics: Annual financial metrics (revenue, income, margins)
- segment_revenue: Business segment breakdowns
- geographic_revenue: Geographic revenue distribution
- risk_factors: Identified risk factors from Item 1A

Revision ID: 001_10k_financial_schema
Revises: None (first migration)
Create Date: 2026-01-17

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "001_10k_financial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create 10-K financial data tables and indexes."""
    # ==========================================================================
    # Create trigger function for auto-updating updated_at column
    # This is required because SQLAlchemy's onupdate doesn't work at DB level
    # ==========================================================================
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)

    # ==========================================================================
    # companies table - Core company information
    # ==========================================================================
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ticker", sa.String(10), unique=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("sector", sa.String(100), nullable=True),
        sa.Column("fiscal_year_end", sa.Date(), nullable=True),
        sa.Column("filing_date", sa.Date(), nullable=True),
        sa.Column(
            "document_id",
            sa.String(100),
            nullable=True,
            comment="Links to Pinecone document for RAG queries",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )

    # Create index on ticker for fast lookups (unique constraint also creates one)
    op.create_index("idx_companies_ticker", "companies", ["ticker"])

    # Create trigger to auto-update updated_at on companies table
    op.execute("""
        CREATE TRIGGER update_companies_updated_at
        BEFORE UPDATE ON companies
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)

    # ==========================================================================
    # financial_metrics table - Annual financial data
    # ==========================================================================
    op.create_table(
        "financial_metrics",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        # Income Statement
        sa.Column(
            "revenue",
            sa.Numeric(15, 2),
            nullable=True,
            comment="Total revenue in millions USD",
        ),
        sa.Column(
            "cost_of_revenue",
            sa.Numeric(15, 2),
            nullable=True,
            comment="Cost of goods sold in millions USD",
        ),
        sa.Column(
            "gross_profit",
            sa.Numeric(15, 2),
            nullable=True,
            comment="Gross profit in millions USD",
        ),
        sa.Column(
            "operating_expenses",
            sa.Numeric(15, 2),
            nullable=True,
            comment="Operating expenses in millions USD",
        ),
        sa.Column(
            "operating_income",
            sa.Numeric(15, 2),
            nullable=True,
            comment="Operating income in millions USD",
        ),
        sa.Column(
            "net_income",
            sa.Numeric(15, 2),
            nullable=True,
            comment="Net income in millions USD",
        ),
        # Balance Sheet
        sa.Column(
            "total_assets",
            sa.Numeric(15, 2),
            nullable=True,
            comment="Total assets in millions USD",
        ),
        sa.Column(
            "total_liabilities",
            sa.Numeric(15, 2),
            nullable=True,
            comment="Total liabilities in millions USD",
        ),
        sa.Column(
            "total_equity",
            sa.Numeric(15, 2),
            nullable=True,
            comment="Total stockholders equity in millions USD",
        ),
        sa.Column(
            "cash_and_equivalents",
            sa.Numeric(15, 2),
            nullable=True,
            comment="Cash and cash equivalents in millions USD",
        ),
        sa.Column(
            "long_term_debt",
            sa.Numeric(15, 2),
            nullable=True,
            comment="Long-term debt in millions USD",
        ),
        # Margins (stored as percentages, e.g., 45.5 for 45.5%)
        sa.Column(
            "gross_margin",
            sa.Numeric(5, 2),
            nullable=True,
            comment="Gross margin percentage",
        ),
        sa.Column(
            "operating_margin",
            sa.Numeric(5, 2),
            nullable=True,
            comment="Operating margin percentage",
        ),
        sa.Column(
            "net_margin",
            sa.Numeric(5, 2),
            nullable=True,
            comment="Net profit margin percentage",
        ),
        # Per Share Data
        sa.Column(
            "earnings_per_share",
            sa.Numeric(10, 4),
            nullable=True,
            comment="Basic EPS",
        ),
        sa.Column(
            "diluted_eps",
            sa.Numeric(10, 4),
            nullable=True,
            comment="Diluted EPS",
        ),
        # Metadata
        sa.Column(
            "currency",
            sa.String(3),
            server_default="USD",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        # Unique constraint: one record per company per fiscal year
        sa.UniqueConstraint("company_id", "fiscal_year", name="uq_financial_metrics_company_year"),
    )

    # Indexes for common query patterns
    op.create_index(
        "idx_financial_metrics_company",
        "financial_metrics",
        ["company_id"],
    )
    op.create_index(
        "idx_financial_metrics_year",
        "financial_metrics",
        ["fiscal_year"],
    )

    # ==========================================================================
    # segment_revenue table - Business segment breakdown
    # ==========================================================================
    op.create_table(
        "segment_revenue",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column(
            "segment_name",
            sa.String(100),
            nullable=False,
            comment="Business segment name (e.g., Data Center, Gaming)",
        ),
        sa.Column(
            "revenue",
            sa.Numeric(15, 2),
            nullable=True,
            comment="Segment revenue in millions USD",
        ),
        sa.Column(
            "percentage_of_total",
            sa.Numeric(5, 2),
            nullable=True,
            comment="Percentage of total revenue",
        ),
        sa.Column(
            "yoy_growth",
            sa.Numeric(5, 2),
            nullable=True,
            comment="Year-over-year growth percentage",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )

    op.create_index(
        "idx_segment_revenue_company",
        "segment_revenue",
        ["company_id"],
    )
    op.create_index(
        "idx_segment_revenue_year",
        "segment_revenue",
        ["fiscal_year"],
    )

    # ==========================================================================
    # geographic_revenue table - Geographic distribution
    # ==========================================================================
    op.create_table(
        "geographic_revenue",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column(
            "region",
            sa.String(100),
            nullable=False,
            comment="Geographic region (e.g., Americas, EMEA, Asia Pacific)",
        ),
        sa.Column(
            "revenue",
            sa.Numeric(15, 2),
            nullable=True,
            comment="Regional revenue in millions USD",
        ),
        sa.Column(
            "percentage_of_total",
            sa.Numeric(5, 2),
            nullable=True,
            comment="Percentage of total revenue",
        ),
        sa.Column(
            "yoy_growth",
            sa.Numeric(5, 2),
            nullable=True,
            comment="Year-over-year growth percentage",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )

    op.create_index(
        "idx_geographic_revenue_company",
        "geographic_revenue",
        ["company_id"],
    )
    op.create_index(
        "idx_geographic_revenue_year",
        "geographic_revenue",
        ["fiscal_year"],
    )

    # ==========================================================================
    # risk_factors table - Risk factors from Item 1A
    # ==========================================================================
    op.create_table(
        "risk_factors",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column(
            "category",
            sa.String(100),
            nullable=True,
            comment="Risk category (Supply Chain, Regulatory, Competition, etc.)",
        ),
        sa.Column(
            "title",
            sa.String(500),
            nullable=True,
            comment="Risk factor title/heading",
        ),
        sa.Column(
            "summary",
            sa.Text(),
            nullable=True,
            comment="Brief summary of the risk factor",
        ),
        sa.Column(
            "severity",
            sa.String(20),
            sa.CheckConstraint("severity IN ('high', 'medium', 'low')", name="ck_risk_factors_severity"),
            nullable=True,
            comment="Risk severity level",
        ),
        sa.Column(
            "page_number",
            sa.Integer(),
            nullable=True,
            comment="Source page number in the 10-K filing",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )

    op.create_index(
        "idx_risk_factors_company",
        "risk_factors",
        ["company_id"],
    )
    op.create_index(
        "idx_risk_factors_category",
        "risk_factors",
        ["category"],
    )
    op.create_index(
        "idx_risk_factors_year",
        "risk_factors",
        ["fiscal_year"],
    )


def downgrade() -> None:
    """Drop all 10-K financial data tables in reverse order."""
    # Drop tables in reverse order of creation (respecting foreign key dependencies)
    op.drop_table("risk_factors")
    op.drop_table("geographic_revenue")
    op.drop_table("segment_revenue")
    op.drop_table("financial_metrics")

    # Drop trigger before dropping companies table
    op.execute("DROP TRIGGER IF EXISTS update_companies_updated_at ON companies;")
    op.drop_table("companies")

    # Drop the trigger function
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column();")
