"""
Knowledge Graph package for entity extraction and graph queries.

This package provides entity extraction and knowledge graph functionality
for the Enterprise Agentic AI project. It enables structured extraction
of entities from financial documents and relationship queries via Neo4j.

Components:
- Entity extraction using spaCy NER with financial domain patterns
- Neo4j graph store for entity and relationship storage
- Graph query functions for 1-hop and 2-hop traversals
- Financial domain ontology (EntityType, RelationType)

Architecture:
    Document → Entity Extraction → Neo4j Storage → Graph Queries
                    ↓                    ↓              ↓
               spaCy NER           Cypher         Relationship
            + Custom Rules         Insert           Traversal

Entity Types (from ontology.py):
    - DOCUMENT: Source document in RAG system
    - ORGANIZATION: Companies, agencies, institutions (spaCy ORG)
    - PERSON: Named individuals, executives, analysts (spaCy PERSON)
    - LOCATION: Countries, cities, regions (spaCy GPE)
    - REGULATION: Laws, regulatory bodies (SEC, FINRA, GAAP)
    - CONCEPT: Financial terms and concepts (EPS, ROE, EBITDA)
    - PRODUCT: Financial products and services
    - DATE: Dates and time periods (spaCy DATE)
    - MONEY: Monetary values (spaCy MONEY)
    - PERCENT: Percentages (spaCy PERCENT)

Relationship Types (from ontology.py):
    - MENTIONS: Document mentions an entity
    - DEFINES: Document defines a concept
    - GOVERNED_BY: Entity governed by regulation
    - LOCATED_IN: Entity located in geography
    - RELATED_TO: Generic relationship between entities
    - WORKS_FOR: Person works for organization
    - COMPETES_WITH: Organization competes with organization

Usage:
    # Entity extraction (Phase 2b Section 3)
    from src.knowledge_graph import EntityExtractor

    extractor = EntityExtractor()
    entities = extractor.extract_entities(
        text="NVIDIA Corporation reported $60B revenue...",
        document_id="NVDA_10K_2024",
        page=1
    )

    # Graph storage (Phase 2b Section 4)
    from src.knowledge_graph import Neo4jStore

    store = Neo4jStore(uri, user, password)
    entity_ids = store.batch_create_entities(entities)

    # Graph queries (Phase 2b Section 6)
    from src.knowledge_graph import GraphQueries

    queries = GraphQueries(store)

    # Find documents mentioning an entity (for RAG integration)
    doc_ids = queries.find_documents_mentioning("NVIDIA")

    # Find related entities through shared documents (2-hop)
    related = queries.find_related_entities("NVIDIA", hops=2)

Local Development:
    Requires Neo4j running locally or Neo4j AuraDB (free tier):
    - docker-compose up neo4j  # Local Neo4j container
    - Set NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD in .env

AWS Deployment:
    When ENVIRONMENT=aws, Neo4j credentials are loaded from
    AWS Secrets Manager (enterprise-agentic-ai/neo4j).

See Also:
    - backend.mdc for Python development patterns
    - PHASE_2B_HOW_TO_GUIDE.md for implementation steps
    - spaCy docs: https://spacy.io/usage/linguistic-features#named-entities
    - Neo4j Python driver: https://neo4j.com/docs/python-manual/current/
"""

from __future__ import annotations

# =============================================================================
# Module Imports (to be added as submodules are created)
# =============================================================================

# Phase 2b Section 2.3: Ontology definitions
from src.knowledge_graph.ontology import (
    EntityType,
    RelationType,
    SPACY_TO_ENTITY_TYPE,
    FINANCIAL_PATTERNS,
    PATTERN_LABEL_TO_ENTITY_TYPE,
    get_entity_type,
    is_valid_entity_type,
    is_valid_relation_type,
)

# Phase 2b Section 3.3: Entity extraction
from src.knowledge_graph.extractor import (
    Entity,
    EntityExtractor,
    EntityExtractionError,
    ModelLoadError,
)

# Phase 2b Section 4.4: Neo4j graph store
from src.knowledge_graph.store import (
    Neo4jStore,
    Neo4jStoreError,
    Neo4jConnectionError,
    AuraDBPausedError,
    QueryError,
)

# Phase 2b Section 6.3: Graph queries
from src.knowledge_graph.queries import GraphQueries, GraphQueryError

# =============================================================================
# Package Version
# =============================================================================

__version__ = "0.1.0"

# =============================================================================
# Public API (will be populated as modules are added)
# =============================================================================

__all__: list[str] = [
    "__version__",
    # Ontology (Phase 2b Section 2.3)
    "EntityType",
    "RelationType",
    "SPACY_TO_ENTITY_TYPE",
    "FINANCIAL_PATTERNS",
    "PATTERN_LABEL_TO_ENTITY_TYPE",
    "get_entity_type",
    "is_valid_entity_type",
    "is_valid_relation_type",
    # Entity Extraction (Phase 2b Section 3.3)
    "Entity",
    "EntityExtractor",
    "EntityExtractionError",
    "ModelLoadError",
    # Graph Store (Phase 2b Section 4.4)
    "Neo4jStore",
    "Neo4jStoreError",
    "Neo4jConnectionError",
    "AuraDBPausedError",
    "QueryError",
    # Graph Queries (Phase 2b Section 6.3)
    "GraphQueries",
    "GraphQueryError",
]
