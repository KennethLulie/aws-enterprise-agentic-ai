"""
Ontology definitions for the Knowledge Graph.

This module defines the entity types, relationship types, and patterns used
for entity extraction from financial documents. It provides a structured
ontology that maps between spaCy NER labels and our domain-specific types.

Components:
    - EntityType: Enum of all entity categories in the knowledge graph
    - RelationType: Enum of relationship types between entities
    - SPACY_TO_ENTITY_TYPE: Mapping from spaCy NER labels to EntityType
    - FINANCIAL_PATTERNS: spaCy EntityRuler patterns for domain-specific entities

Usage:
    from src.knowledge_graph.ontology import (
        EntityType,
        RelationType,
        SPACY_TO_ENTITY_TYPE,
        FINANCIAL_PATTERNS,
    )

    # Convert spaCy label to our entity type
    entity_type = SPACY_TO_ENTITY_TYPE.get("ORG", EntityType.ORGANIZATION)

    # Check if entity type is valid
    if entity_type == EntityType.ORGANIZATION:
        print("Found an organization")

    # Access EntityRuler patterns for custom NER
    for pattern in FINANCIAL_PATTERNS:
        print(f"Pattern: {pattern['label']} -> {pattern['pattern']}")

Reference:
    - PHASE_2B_HOW_TO_GUIDE.md Section 2.2
    - spaCy EntityRuler: https://spacy.io/usage/rule-based-matching#entityruler
    - backend.mdc for Python patterns
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

# =============================================================================
# Entity Types
# =============================================================================


class EntityType(StrEnum):
    """
    Enumeration of entity types in the knowledge graph.

    These entity types represent the categories of entities that can be
    extracted from financial documents. They include both standard NER
    categories (mapped from spaCy) and financial domain-specific types.

    Attributes:
        DOCUMENT: Source document in the RAG system (e.g., 10-K filing)
        ORGANIZATION: Companies, agencies, institutions (spaCy ORG)
        PERSON: Named individuals like executives, analysts (spaCy PERSON)
        LOCATION: Countries, cities, regions (spaCy GPE - Geopolitical Entity)
        REGULATION: Laws, regulatory bodies (SEC, FINRA, GAAP, IFRS)
        CONCEPT: Financial terms and concepts (EPS, ROE, EBITDA)
        PRODUCT: Financial products and services (credit cards, accounts)
        DATE: Dates and time periods (spaCy DATE)
        MONEY: Monetary values (spaCy MONEY)
        PERCENT: Percentages and rates (spaCy PERCENT)

    Example:
        >>> entity_type = EntityType.ORGANIZATION
        >>> print(entity_type)
        'ORGANIZATION'
        >>> print(entity_type.value)
        'ORGANIZATION'
    """

    DOCUMENT = "DOCUMENT"
    ORGANIZATION = "ORGANIZATION"
    PERSON = "PERSON"
    LOCATION = "LOCATION"
    REGULATION = "REGULATION"
    CONCEPT = "CONCEPT"
    PRODUCT = "PRODUCT"
    DATE = "DATE"
    MONEY = "MONEY"
    PERCENT = "PERCENT"


# =============================================================================
# Relationship Types
# =============================================================================


class RelationType(StrEnum):
    """
    Enumeration of relationship types between entities in the knowledge graph.

    These relationship types define the edges between entity nodes in the
    graph. They capture semantic relationships found in financial documents.

    Attributes:
        MENTIONS: Document mentions an entity (most common relationship)
        DEFINES: Document defines a concept (for glossary/definition extraction)
        GOVERNED_BY: Entity is governed by a regulation (compliance relationship)
        LOCATED_IN: Entity is located in a geography (headquarters, operations)
        RELATED_TO: Generic relationship between entities (fallback)
        WORKS_FOR: Person works for an organization (employment relationship)
        COMPETES_WITH: Organization competes with another organization

    Example:
        >>> rel_type = RelationType.MENTIONS
        >>> print(rel_type)
        'MENTIONS'
    """

    MENTIONS = "MENTIONS"
    DEFINES = "DEFINES"
    GOVERNED_BY = "GOVERNED_BY"
    LOCATED_IN = "LOCATED_IN"
    RELATED_TO = "RELATED_TO"
    WORKS_FOR = "WORKS_FOR"
    COMPETES_WITH = "COMPETES_WITH"


# =============================================================================
# spaCy Label to Entity Type Mapping
# =============================================================================

SPACY_TO_ENTITY_TYPE: dict[str, EntityType] = {
    # Standard spaCy NER labels mapped to our entity types
    "ORG": EntityType.ORGANIZATION,
    "PERSON": EntityType.PERSON,
    "GPE": EntityType.LOCATION,  # Geopolitical Entity (countries, cities)
    "DATE": EntityType.DATE,
    "MONEY": EntityType.MONEY,
    "PERCENT": EntityType.PERCENT,
    "LAW": EntityType.REGULATION,  # Laws, legal documents
    "PRODUCT": EntityType.PRODUCT,
    # Additional spaCy labels that map to our types
    "LOC": EntityType.LOCATION,  # Non-GPE locations (mountains, rivers)
    "NORP": EntityType.ORGANIZATION,  # Nationalities, religious/political groups
    "FAC": EntityType.LOCATION,  # Facilities (buildings, airports)
    "EVENT": EntityType.CONCEPT,  # Named events (conferences, earnings calls)
    "WORK_OF_ART": EntityType.CONCEPT,  # Titles of books, reports
    "CARDINAL": EntityType.CONCEPT,  # Numerals not covered by other types
    "ORDINAL": EntityType.CONCEPT,  # Ordinal numbers (first, second)
    "QUANTITY": EntityType.CONCEPT,  # Measurements (weight, distance)
    "TIME": EntityType.DATE,  # Times (morning, afternoon)
    "LANGUAGE": EntityType.CONCEPT,  # Languages
}
"""
Mapping from spaCy NER labels to our EntityType enum.

This dictionary maps the built-in spaCy NER labels (from the en_core_web_sm
model or any larger variant) to our domain-specific EntityType values. Labels
not in this mapping should be handled with a default type or filtered out.

spaCy Label Reference:
    - ORG: Companies, agencies, institutions
    - PERSON: Named individuals
    - GPE: Geopolitical entities (countries, cities, states)
    - LOC: Non-GPE locations (mountains, rivers, regions)
    - DATE: Dates and periods
    - MONEY: Monetary values with currency
    - PERCENT: Percentage expressions
    - LAW: Named documents made into laws
    - PRODUCT: Objects, vehicles, foods, etc. (not services)
    - NORP: Nationalities or religious/political groups
    - FAC: Facilities (buildings, airports, highways)
    - EVENT: Named hurricanes, battles, wars, sporting events
    - WORK_OF_ART: Titles of books, songs, etc.
    - CARDINAL: Numerals not covered by other types
    - ORDINAL: Ordinal numbers
    - QUANTITY: Measurements
    - TIME: Times smaller than a day
    - LANGUAGE: Named languages

Reference:
    https://spacy.io/models/en#en_core_web_lg-labels
"""


# =============================================================================
# Financial Domain Patterns for EntityRuler
# =============================================================================

FINANCIAL_PATTERNS: list[dict[str, Any]] = [
    # =========================================================================
    # ORGANIZATION Patterns - Major tech companies and their tickers
    # Added to help spaCy recognize company names in short queries
    # =========================================================================
    # NVIDIA and variations
    {"label": "ORG", "pattern": [{"LOWER": "nvidia"}]},
    {"label": "ORG", "pattern": "NVIDIA"},
    {"label": "ORG", "pattern": [{"LOWER": "nvda"}]},
    {"label": "ORG", "pattern": "NVDA"},
    # AMD and variations
    {"label": "ORG", "pattern": [{"LOWER": "amd"}]},
    {"label": "ORG", "pattern": "AMD"},
    {"label": "ORG", "pattern": "Advanced Micro Devices"},
    # Intel
    {"label": "ORG", "pattern": [{"LOWER": "intel"}]},
    {"label": "ORG", "pattern": "Intel"},
    {"label": "ORG", "pattern": [{"LOWER": "intc"}]},
    # Google/Alphabet
    {"label": "ORG", "pattern": [{"LOWER": "google"}]},
    {"label": "ORG", "pattern": "Google"},
    {"label": "ORG", "pattern": [{"LOWER": "alphabet"}]},
    {"label": "ORG", "pattern": "Alphabet"},
    {"label": "ORG", "pattern": [{"LOWER": "goog"}]},
    {"label": "ORG", "pattern": [{"LOWER": "googl"}]},
    # Micron
    {"label": "ORG", "pattern": [{"LOWER": "micron"}]},
    {"label": "ORG", "pattern": "Micron"},
    {"label": "ORG", "pattern": "Micron Technology"},
    {"label": "ORG", "pattern": [{"LOWER": "mu"}]},
    # Apple
    {"label": "ORG", "pattern": [{"LOWER": "apple"}]},
    {"label": "ORG", "pattern": "Apple"},
    {"label": "ORG", "pattern": [{"LOWER": "aapl"}]},
    # Microsoft
    {"label": "ORG", "pattern": [{"LOWER": "microsoft"}]},
    {"label": "ORG", "pattern": "Microsoft"},
    {"label": "ORG", "pattern": [{"LOWER": "msft"}]},
    # Amazon
    {"label": "ORG", "pattern": [{"LOWER": "amazon"}]},
    {"label": "ORG", "pattern": "Amazon"},
    {"label": "ORG", "pattern": [{"LOWER": "amzn"}]},
    # Meta/Facebook
    {"label": "ORG", "pattern": [{"LOWER": "meta"}]},
    {"label": "ORG", "pattern": "Meta"},
    {"label": "ORG", "pattern": [{"LOWER": "facebook"}]},
    {"label": "ORG", "pattern": "Facebook"},
    # Tesla
    {"label": "ORG", "pattern": [{"LOWER": "tesla"}]},
    {"label": "ORG", "pattern": "Tesla"},
    {"label": "ORG", "pattern": [{"LOWER": "tsla"}]},
    # Samsung
    {"label": "ORG", "pattern": [{"LOWER": "samsung"}]},
    {"label": "ORG", "pattern": "Samsung"},
    # TSMC
    {"label": "ORG", "pattern": [{"LOWER": "tsmc"}]},
    {"label": "ORG", "pattern": "TSMC"},
    {"label": "ORG", "pattern": "Taiwan Semiconductor"},
    # SK Hynix
    {"label": "ORG", "pattern": "SK Hynix"},
    {"label": "ORG", "pattern": [{"LOWER": "hynix"}]},
    # Qualcomm
    {"label": "ORG", "pattern": [{"LOWER": "qualcomm"}]},
    {"label": "ORG", "pattern": "Qualcomm"},
    {"label": "ORG", "pattern": [{"LOWER": "qcom"}]},
    # Broadcom
    {"label": "ORG", "pattern": [{"LOWER": "broadcom"}]},
    {"label": "ORG", "pattern": "Broadcom"},
    {"label": "ORG", "pattern": [{"LOWER": "avgo"}]},
    # =========================================================================
    # REGULATION Patterns - Regulatory bodies and frameworks
    # =========================================================================
    # U.S. Financial Regulators (case-insensitive for acronyms)
    {"label": "REGULATION", "pattern": [{"LOWER": "sec"}]},
    {"label": "REGULATION", "pattern": "Securities and Exchange Commission"},
    {"label": "REGULATION", "pattern": [{"LOWER": "finra"}]},
    {"label": "REGULATION", "pattern": "Financial Industry Regulatory Authority"},
    {"label": "REGULATION", "pattern": [{"LOWER": "fdic"}]},
    {"label": "REGULATION", "pattern": "Federal Deposit Insurance Corporation"},
    {"label": "REGULATION", "pattern": [{"LOWER": "occ"}]},
    {"label": "REGULATION", "pattern": "Office of the Comptroller of the Currency"},
    {"label": "REGULATION", "pattern": [{"LOWER": "cfpb"}]},
    {"label": "REGULATION", "pattern": "Consumer Financial Protection Bureau"},
    {"label": "REGULATION", "pattern": "Federal Reserve"},
    {"label": "REGULATION", "pattern": [{"LOWER": "fed"}]},
    {"label": "REGULATION", "pattern": [{"LOWER": "ftc"}]},
    {"label": "REGULATION", "pattern": "Federal Trade Commission"},
    {"label": "REGULATION", "pattern": [{"LOWER": "doj"}]},
    {"label": "REGULATION", "pattern": "Department of Justice"},
    # Accounting Standards (case-insensitive for acronyms)
    {"label": "REGULATION", "pattern": [{"LOWER": "gaap"}]},
    {"label": "REGULATION", "pattern": "Generally Accepted Accounting Principles"},
    {"label": "REGULATION", "pattern": [{"LOWER": "ifrs"}]},
    {"label": "REGULATION", "pattern": "International Financial Reporting Standards"},
    {"label": "REGULATION", "pattern": [{"LOWER": "fasb"}]},
    {"label": "REGULATION", "pattern": "Financial Accounting Standards Board"},
    {"label": "REGULATION", "pattern": [{"LOWER": "pcaob"}]},
    {"label": "REGULATION", "pattern": "Public Company Accounting Oversight Board"},
    # Major Regulations
    {"label": "REGULATION", "pattern": "Sarbanes-Oxley"},
    {"label": "REGULATION", "pattern": [{"LOWER": "sox"}]},
    {"label": "REGULATION", "pattern": "Dodd-Frank"},
    {"label": "REGULATION", "pattern": "Basel III"},
    {"label": "REGULATION", "pattern": "Basel IV"},
    {"label": "REGULATION", "pattern": "MiFID II"},
    {"label": "REGULATION", "pattern": "Regulation NMS"},
    {"label": "REGULATION", "pattern": "Reg NMS"},
    # SEC Filings
    {"label": "REGULATION", "pattern": "Form 10-K"},
    {"label": "REGULATION", "pattern": "Form 10-Q"},
    {"label": "REGULATION", "pattern": "Form 8-K"},
    {"label": "REGULATION", "pattern": "Schedule 13D"},
    {"label": "REGULATION", "pattern": "Schedule 13G"},
    {"label": "REGULATION", "pattern": "Form S-1"},
    {"label": "REGULATION", "pattern": "Form 4"},
    # =========================================================================
    # CONCEPT Patterns - Financial metrics and terms
    # =========================================================================
    # Profitability Metrics (case-insensitive for acronyms)
    {"label": "CONCEPT", "pattern": [{"LOWER": "eps"}]},
    {"label": "CONCEPT", "pattern": "earnings per share"},
    {"label": "CONCEPT", "pattern": [{"LOWER": "p/e"}]},
    {"label": "CONCEPT", "pattern": "P/E ratio"},
    {"label": "CONCEPT", "pattern": "price-to-earnings"},
    {"label": "CONCEPT", "pattern": "price to earnings"},
    {"label": "CONCEPT", "pattern": [{"LOWER": "roe"}]},
    {"label": "CONCEPT", "pattern": "return on equity"},
    {"label": "CONCEPT", "pattern": [{"LOWER": "roa"}]},
    {"label": "CONCEPT", "pattern": "return on assets"},
    {"label": "CONCEPT", "pattern": [{"LOWER": "roic"}]},
    {"label": "CONCEPT", "pattern": "return on invested capital"},
    {"label": "CONCEPT", "pattern": [{"LOWER": "roi"}]},
    {"label": "CONCEPT", "pattern": "return on investment"},
    {"label": "CONCEPT", "pattern": [{"LOWER": "ebitda"}]},
    {"label": "CONCEPT", "pattern": [{"LOWER": "ebit"}]},
    {"label": "CONCEPT", "pattern": "net income"},
    {"label": "CONCEPT", "pattern": "gross profit"},
    {"label": "CONCEPT", "pattern": "operating income"},
    {"label": "CONCEPT", "pattern": "gross margin"},
    {"label": "CONCEPT", "pattern": "operating margin"},
    {"label": "CONCEPT", "pattern": "net margin"},
    {"label": "CONCEPT", "pattern": "profit margin"},
    # Interest Rate Metrics (case-insensitive for acronyms)
    {"label": "CONCEPT", "pattern": [{"LOWER": "apr"}]},
    {"label": "CONCEPT", "pattern": "annual percentage rate"},
    {"label": "CONCEPT", "pattern": [{"LOWER": "apy"}]},
    {"label": "CONCEPT", "pattern": "annual percentage yield"},
    {"label": "CONCEPT", "pattern": "interest rate"},
    {"label": "CONCEPT", "pattern": "prime rate"},
    {"label": "CONCEPT", "pattern": "federal funds rate"},
    {"label": "CONCEPT", "pattern": [{"LOWER": "libor"}]},
    {"label": "CONCEPT", "pattern": [{"LOWER": "sofr"}]},
    # Valuation Metrics (case-insensitive for acronyms)
    # NOTE: "EV" removed - too ambiguous (electric vehicle). Use "enterprise value" or "EV/EBITDA"
    {"label": "CONCEPT", "pattern": "market cap"},
    {"label": "CONCEPT", "pattern": "market capitalization"},
    {"label": "CONCEPT", "pattern": "enterprise value"},
    {"label": "CONCEPT", "pattern": [{"LOWER": "ev/ebitda"}]},
    {"label": "CONCEPT", "pattern": [{"LOWER": "p/b"}]},
    {"label": "CONCEPT", "pattern": "P/B ratio"},
    {"label": "CONCEPT", "pattern": "price-to-book"},
    {"label": "CONCEPT", "pattern": "price to book"},
    {"label": "CONCEPT", "pattern": [{"LOWER": "p/s"}]},
    {"label": "CONCEPT", "pattern": "price-to-sales"},
    {"label": "CONCEPT", "pattern": "price to sales"},
    {"label": "CONCEPT", "pattern": "PEG ratio"},
    {"label": "CONCEPT", "pattern": "book value"},
    {"label": "CONCEPT", "pattern": "intrinsic value"},
    {"label": "CONCEPT", "pattern": "fair value"},
    {"label": "CONCEPT", "pattern": [{"LOWER": "dcf"}]},
    {"label": "CONCEPT", "pattern": "discounted cash flow"},
    # Cash Flow & Liquidity (case-insensitive for acronyms)
    {"label": "CONCEPT", "pattern": "free cash flow"},
    {"label": "CONCEPT", "pattern": [{"LOWER": "fcf"}]},
    {"label": "CONCEPT", "pattern": "operating cash flow"},
    {"label": "CONCEPT", "pattern": "cash flow"},
    {"label": "CONCEPT", "pattern": "working capital"},
    {"label": "CONCEPT", "pattern": "current ratio"},
    {"label": "CONCEPT", "pattern": "quick ratio"},
    {"label": "CONCEPT", "pattern": "liquidity"},
    # Leverage & Debt (case-insensitive for acronyms)
    {"label": "CONCEPT", "pattern": "debt-to-equity"},
    {"label": "CONCEPT", "pattern": [{"LOWER": "d/e"}]},
    {"label": "CONCEPT", "pattern": "D/E ratio"},
    {"label": "CONCEPT", "pattern": "leverage ratio"},
    {"label": "CONCEPT", "pattern": "interest coverage"},
    {"label": "CONCEPT", "pattern": "debt ratio"},
    {"label": "CONCEPT", "pattern": "total debt"},
    {"label": "CONCEPT", "pattern": "long-term debt"},
    {"label": "CONCEPT", "pattern": "short-term debt"},
    # Growth Metrics (case-insensitive for acronyms)
    {"label": "CONCEPT", "pattern": [{"LOWER": "yoy"}]},
    {"label": "CONCEPT", "pattern": "year-over-year"},
    {"label": "CONCEPT", "pattern": "year over year"},
    {"label": "CONCEPT", "pattern": [{"LOWER": "qoq"}]},
    {"label": "CONCEPT", "pattern": "quarter-over-quarter"},
    {"label": "CONCEPT", "pattern": [{"LOWER": "cagr"}]},
    {"label": "CONCEPT", "pattern": "compound annual growth rate"},
    {"label": "CONCEPT", "pattern": "revenue growth"},
    {"label": "CONCEPT", "pattern": "earnings growth"},
    # Dividend Metrics (case-insensitive for acronyms)
    {"label": "CONCEPT", "pattern": "dividend yield"},
    {"label": "CONCEPT", "pattern": "dividend"},
    {"label": "CONCEPT", "pattern": "dividend payout ratio"},
    {"label": "CONCEPT", "pattern": [{"LOWER": "dps"}]},
    {"label": "CONCEPT", "pattern": "dividends per share"},
    # Stock Metrics (case-insensitive for acronyms)
    {"label": "CONCEPT", "pattern": "beta"},
    {"label": "CONCEPT", "pattern": "alpha"},
    {"label": "CONCEPT", "pattern": "volatility"},
    {"label": "CONCEPT", "pattern": "Sharpe ratio"},
    {"label": "CONCEPT", "pattern": "standard deviation"},
    {"label": "CONCEPT", "pattern": "52-week high"},
    {"label": "CONCEPT", "pattern": "52-week low"},
    {"label": "CONCEPT", "pattern": "moving average"},
    {"label": "CONCEPT", "pattern": [{"LOWER": "rsi"}]},
    {"label": "CONCEPT", "pattern": [{"LOWER": "macd"}]},
    # =========================================================================
    # PRODUCT Patterns - Financial products and services
    # =========================================================================
    # Banking Products (case-insensitive for acronyms)
    # NOTE: "CD" removed - too ambiguous (CD-ROM, music CD). Use "certificate of deposit"
    {"label": "PRODUCT", "pattern": "credit card"},
    {"label": "PRODUCT", "pattern": "debit card"},
    {"label": "PRODUCT", "pattern": "checking account"},
    {"label": "PRODUCT", "pattern": "savings account"},
    {"label": "PRODUCT", "pattern": "money market account"},
    {"label": "PRODUCT", "pattern": "certificate of deposit"},
    {"label": "PRODUCT", "pattern": [{"LOWER": "ira"}]},
    {"label": "PRODUCT", "pattern": "401(k)"},
    {"label": "PRODUCT", "pattern": "401k"},
    {"label": "PRODUCT", "pattern": "Roth IRA"},
    {"label": "PRODUCT", "pattern": "traditional IRA"},
    # Loan Products (case-insensitive for acronyms)
    {"label": "PRODUCT", "pattern": "mortgage"},
    {"label": "PRODUCT", "pattern": "home loan"},
    {"label": "PRODUCT", "pattern": "auto loan"},
    {"label": "PRODUCT", "pattern": "car loan"},
    {"label": "PRODUCT", "pattern": "personal loan"},
    {"label": "PRODUCT", "pattern": "student loan"},
    {"label": "PRODUCT", "pattern": [{"LOWER": "heloc"}]},
    {"label": "PRODUCT", "pattern": "home equity line of credit"},
    {"label": "PRODUCT", "pattern": "line of credit"},
    # Investment Products (case-insensitive for acronyms)
    {"label": "PRODUCT", "pattern": "mutual fund"},
    {"label": "PRODUCT", "pattern": [{"LOWER": "etf"}]},
    {"label": "PRODUCT", "pattern": "exchange-traded fund"},
    {"label": "PRODUCT", "pattern": "index fund"},
    {"label": "PRODUCT", "pattern": "hedge fund"},
    {"label": "PRODUCT", "pattern": "bond"},
    {"label": "PRODUCT", "pattern": "treasury bond"},
    {"label": "PRODUCT", "pattern": "corporate bond"},
    {"label": "PRODUCT", "pattern": "municipal bond"},
    {"label": "PRODUCT", "pattern": "stock"},
    {"label": "PRODUCT", "pattern": "common stock"},
    {"label": "PRODUCT", "pattern": "preferred stock"},
    {"label": "PRODUCT", "pattern": "option"},
    {"label": "PRODUCT", "pattern": "futures"},
    {"label": "PRODUCT", "pattern": "derivative"},
    # Insurance Products
    {"label": "PRODUCT", "pattern": "life insurance"},
    {"label": "PRODUCT", "pattern": "term life"},
    {"label": "PRODUCT", "pattern": "whole life"},
    {"label": "PRODUCT", "pattern": "health insurance"},
    {"label": "PRODUCT", "pattern": "auto insurance"},
    {"label": "PRODUCT", "pattern": "homeowners insurance"},
    {"label": "PRODUCT", "pattern": "annuity"},
]
"""
spaCy EntityRuler patterns for financial domain-specific entities.

These patterns supplement spaCy's built-in NER model (en_core_web_sm or larger)
with domain-specific entity recognition for financial documents. The patterns
use the EntityRuler component to add rule-based matching for terms that
the statistical NER model might miss or misclassify.

Pattern Types:
    1. String patterns (case-sensitive): For multi-word phrases and proper names
       {"label": "REGULATION", "pattern": "Securities and Exchange Commission"}

    2. Token patterns (case-insensitive): For acronyms that may appear in any case
       {"label": "CONCEPT", "pattern": [{"LOWER": "ebitda"}]}

Design Decisions:
    - Acronyms use case-insensitive token patterns to catch "EBITDA", "Ebitda", "ebitda"
    - Multi-word phrases use case-sensitive string patterns (natural capitalization)
    - Ambiguous short patterns removed to reduce false positives:
      * "CD" removed - conflicts with CD-ROM, music CDs (use "certificate of deposit")
      * "EV" removed - conflicts with electric vehicles (use "enterprise value")

Usage with spaCy:
    import spacy
    from spacy.pipeline import EntityRuler

    nlp = spacy.load("en_core_web_sm")
    ruler = nlp.add_pipe("entity_ruler", before="ner")
    ruler.add_patterns(FINANCIAL_PATTERNS)

    doc = nlp("The company reported strong EBITDA growth under GAAP standards.")
    for ent in doc.ents:
        print(f"{ent.text}: {ent.label_}")

Reference:
    - https://spacy.io/usage/rule-based-matching#entityruler
    - https://spacy.io/api/entityruler
"""


# =============================================================================
# Pattern Label to EntityType Mapping
# =============================================================================

PATTERN_LABEL_TO_ENTITY_TYPE: dict[str, EntityType] = {
    "REGULATION": EntityType.REGULATION,
    "CONCEPT": EntityType.CONCEPT,
    "PRODUCT": EntityType.PRODUCT,
}
"""
Mapping from custom pattern labels to EntityType enum.

This maps the labels used in FINANCIAL_PATTERNS to our EntityType values.
Used by the entity extractor to convert pattern matches to typed entities.
"""


# =============================================================================
# Helper Functions
# =============================================================================


def get_entity_type(spacy_label: str) -> EntityType | None:
    """
    Convert a spaCy NER label to our EntityType enum.

    This function handles both standard spaCy labels and our custom
    financial domain labels (from EntityRuler patterns).

    Args:
        spacy_label: The entity label from spaCy (e.g., "ORG", "PERSON", "CONCEPT")

    Returns:
        The corresponding EntityType, or None if the label is not recognized.

    Example:
        >>> get_entity_type("ORG")
        <EntityType.ORGANIZATION: 'ORGANIZATION'>
        >>> get_entity_type("CONCEPT")
        <EntityType.CONCEPT: 'CONCEPT'>
        >>> get_entity_type("UNKNOWN")
        None
    """
    # Check custom pattern labels first (from EntityRuler)
    if spacy_label in PATTERN_LABEL_TO_ENTITY_TYPE:
        return PATTERN_LABEL_TO_ENTITY_TYPE[spacy_label]

    # Check standard spaCy labels
    return SPACY_TO_ENTITY_TYPE.get(spacy_label)


def is_valid_entity_type(entity_type: str) -> bool:
    """
    Check if a string is a valid EntityType value.

    Args:
        entity_type: The string to check.

    Returns:
        True if the string is a valid EntityType value, False otherwise.

    Example:
        >>> is_valid_entity_type("ORGANIZATION")
        True
        >>> is_valid_entity_type("INVALID")
        False
    """
    try:
        EntityType(entity_type)
        return True
    except ValueError:
        return False


def is_valid_relation_type(relation_type: str) -> bool:
    """
    Check if a string is a valid RelationType value.

    Args:
        relation_type: The string to check.

    Returns:
        True if the string is a valid RelationType value, False otherwise.

    Example:
        >>> is_valid_relation_type("MENTIONS")
        True
        >>> is_valid_relation_type("INVALID")
        False
    """
    try:
        RelationType(relation_type)
        return True
    except ValueError:
        return False


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    # Enums
    "EntityType",
    "RelationType",
    # Mappings
    "SPACY_TO_ENTITY_TYPE",
    "FINANCIAL_PATTERNS",
    "PATTERN_LABEL_TO_ENTITY_TYPE",
    # Helper functions
    "get_entity_type",
    "is_valid_entity_type",
    "is_valid_relation_type",
]
