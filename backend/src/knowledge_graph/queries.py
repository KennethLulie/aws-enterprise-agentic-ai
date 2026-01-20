"""
Graph traversal queries for Knowledge Graph entity and document lookups.

This module provides query functions for traversing the Knowledge Graph,
enabling entity-based retrieval to enhance RAG results. It supports 1-hop
and 2-hop traversals, fuzzy entity search, and co-occurrence analysis.

Architecture:
    RAG Query → GraphQueries → Neo4jStore → Neo4j Database
                     ↓
              Document IDs → RAG Retrieval → Enhanced Context

Features:
    - 1-hop queries: Find documents mentioning an entity
    - 2-hop queries: Find related entities through shared documents
    - Co-occurrence analysis: Entities frequently appearing together
    - Fuzzy entity search: Case-insensitive partial matching
    - Path finding: Discover connections between entities

Integration with RAG:
    Document queries return list[str] of document_ids, which can be used
    to filter or boost Pinecone vector search results, providing
    graph-enhanced retrieval.

Output Format:
    Entity queries return dicts with a "type" field in UPPERCASE format
    (e.g., "ORGANIZATION", "PERSON") to match EntityType.value from ontology.py.
    This ensures consistency with EntityExtractor output in HybridRetriever._kg_search().

Usage:
    from src.knowledge_graph.queries import GraphQueries
    from src.knowledge_graph.store import Neo4jStore

    store = Neo4jStore(uri, user, password)
    queries = GraphQueries(store)

    # Find documents mentioning NVIDIA
    doc_ids = queries.find_documents_mentioning("NVIDIA")

    # Find entities related to NVIDIA through shared documents
    related = queries.find_related_entities("NVIDIA", hops=1)

    # Fuzzy search for entities
    matches = queries.entity_search("nvid")  # Finds "NVIDIA", "NVDA", etc.

Reference:
    - PHASE_2B_HOW_TO_GUIDE.md Section 6.1
    - Neo4j Cypher documentation
    - store.py for Neo4jStore
    - backend.mdc for Python patterns
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from src.knowledge_graph.ontology import EntityType

if TYPE_CHECKING:
    from src.knowledge_graph.store import Neo4jStore

# Configure structured logger
logger = structlog.get_logger(__name__)


# =============================================================================
# Custom Exceptions
# =============================================================================


class GraphQueryError(Exception):
    """Raised when a graph query fails."""

    pass


# =============================================================================
# Graph Queries
# =============================================================================


class GraphQueries:
    """
    Query interface for Knowledge Graph traversals.

    Provides methods for entity-based document retrieval, related entity
    discovery, and fuzzy entity search. All document queries return
    document_id strings suitable for RAG integration.

    Attributes:
        store: Neo4jStore instance for database access.

    Example:
        >>> store = Neo4jStore(uri, user, password)
        >>> queries = GraphQueries(store)
        >>> doc_ids = queries.find_documents_mentioning("Apple")
        >>> print(doc_ids)
        ['AAPL_10K_2024', 'AAPL_10K_2023']
    """

    def __init__(self, store: "Neo4jStore") -> None:
        """
        Initialize GraphQueries with a Neo4jStore.

        Args:
            store: Neo4jStore instance for database access.
        """
        self._store = store

        logger.debug("graph_queries_initialized")

    # =========================================================================
    # Document Queries (return document_id list for RAG)
    # =========================================================================

    def find_documents_mentioning(
        self,
        entity_text: str,
        entity_type: EntityType | None = None,
        fuzzy: bool = False,
        limit: int = 100,
    ) -> list[str]:
        """
        Find all documents that mention a specific entity (1-hop).

        This is the primary query for graph-enhanced RAG: given an entity
        name from a user query, find relevant documents in the corpus.

        Args:
            entity_text: The entity text to search for (case-insensitive).
            entity_type: Optional filter by entity type.
            fuzzy: If True, use CONTAINS for partial matching (catches variants
                   like "NVIDIA" matching "NVIDIA Corporation"). Default False.
            limit: Maximum number of document IDs to return.

        Returns:
            List of document_id strings for RAG filtering/boosting.

        Example:
            >>> doc_ids = queries.find_documents_mentioning("NVIDIA")
            >>> doc_ids = queries.find_documents_mentioning("NVIDIA", fuzzy=True)
            >>> doc_ids = queries.find_documents_mentioning("Tim Cook", EntityType.PERSON)
        """
        # Ensure driver is initialized
        self._store.verify_connection()

        # Choose match operator based on fuzzy flag
        match_operator = "CONTAINS" if fuzzy else "="

        # Build query based on whether entity_type filter is provided
        if entity_type:
            label = entity_type.name.title()
            query = f"""
            MATCH (d:Document)-[:MENTIONS]->(e:{label})
            WHERE toLower(e.text) {match_operator} toLower($entity_text)
            RETURN DISTINCT d.document_id as document_id
            LIMIT $limit
            """
        else:
            query = f"""
            MATCH (d:Document)-[:MENTIONS]->(e:Entity)
            WHERE toLower(e.text) {match_operator} toLower($entity_text)
            RETURN DISTINCT d.document_id as document_id
            LIMIT $limit
            """

        try:
            with self._store.driver.session() as session:
                result = session.run(
                    query,
                    entity_text=entity_text,
                    limit=limit,
                )
                doc_ids = [record["document_id"] for record in result]

            logger.debug(
                "find_documents_mentioning",
                entity_text=entity_text,
                entity_type=entity_type.value if entity_type else None,
                fuzzy=fuzzy,
                result_count=len(doc_ids),
            )

            return doc_ids

        except Exception as e:
            logger.error(
                "find_documents_mentioning_failed",
                entity_text=entity_text,
                error=str(e),
            )
            raise GraphQueryError(f"Failed to find documents: {e}") from e

    # =========================================================================
    # Entity Queries (return entity info dicts)
    # =========================================================================

    def find_related_entities(
        self,
        entity_text: str,
        hops: int = 1,
        limit: int = 50,
    ) -> list[dict]:
        """
        Find entities related to the given entity through shared documents.

        For hops=1: Entities that appear in the same documents
        For hops=2: Entities connected through intermediate entities

        Args:
            entity_text: The source entity text.
            hops: Number of relationship hops (1 or 2).
            limit: Maximum results to return.

        Returns:
            List of dicts with entity info:
            - entity: Entity text
            - type: Entity type (UPPERCASE, e.g., "ORGANIZATION")
            - shared_docs: Number of shared documents (relevance score)

        Example:
            >>> related = queries.find_related_entities("NVIDIA", hops=1)
            >>> for r in related[:5]:
            ...     print(f"{r['entity']} ({r['type']}): {r['shared_docs']} shared docs")
            AMD (ORGANIZATION): 45 shared docs
        """
        self._store.verify_connection()

        if hops == 1:
            # 2-hop in graph terms: entity <- doc -> entity
            query = """
            MATCH (e1:Entity)<-[:MENTIONS]-(d:Document)-[:MENTIONS]->(e2:Entity)
            WHERE toLower(e1.text) = toLower($entity_text) AND e1 <> e2
            RETURN e2.text as entity,
                   [l IN labels(e2) WHERE l <> 'Entity'][0] as type,
                   count(DISTINCT d) as shared_docs
            ORDER BY shared_docs DESC
            LIMIT $limit
            """
        else:
            # 4-hop: entity <- doc -> entity <- doc -> entity
            query = """
            MATCH (e1:Entity)<-[:MENTIONS]-(d1:Document)-[:MENTIONS]->(e_mid:Entity)
                  <-[:MENTIONS]-(d2:Document)-[:MENTIONS]->(e2:Entity)
            WHERE toLower(e1.text) = toLower($entity_text)
              AND e1 <> e_mid AND e_mid <> e2 AND e1 <> e2
            RETURN e2.text as entity,
                   [l IN labels(e2) WHERE l <> 'Entity'][0] as type,
                   count(DISTINCT d2) as shared_docs
            ORDER BY shared_docs DESC
            LIMIT $limit
            """

        try:
            with self._store.driver.session() as session:
                result = session.run(
                    query,
                    entity_text=entity_text,
                    limit=limit,
                )
                entities = [
                    {
                        "entity": record["entity"],
                        # Normalize to uppercase to match EntityType.value format
                        "type": record["type"].upper() if record["type"] else None,
                        "shared_docs": record["shared_docs"],
                    }
                    for record in result
                ]

            logger.debug(
                "find_related_entities",
                entity_text=entity_text,
                hops=hops,
                result_count=len(entities),
            )

            return entities

        except Exception as e:
            logger.error(
                "find_related_entities_failed",
                entity_text=entity_text,
                hops=hops,
                error=str(e),
            )
            raise GraphQueryError(f"Failed to find related entities: {e}") from e

    def find_entities_in_document(
        self,
        document_id: str,
        entity_type: EntityType | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """
        Find all entities mentioned in a specific document.

        Useful for understanding document content and for display in UI.

        Args:
            document_id: The document identifier.
            entity_type: Optional filter by entity type.
            limit: Maximum results to return.

        Returns:
            List of dicts with entity info:
            - entity: Entity text
            - type: Entity type (UPPERCASE, e.g., "ORGANIZATION")
            - mentions: Number of times mentioned in the document

        Example:
            >>> entities = queries.find_entities_in_document("NVDA_10K_2025")
            >>> for e in entities[:10]:
            ...     print(f"{e['entity']} ({e['type']}): {e['mentions']} mentions")
            NVIDIA (ORGANIZATION): 156 mentions
        """
        self._store.verify_connection()

        if entity_type:
            label = entity_type.name.title()
            query = f"""
            MATCH (d:Document {{document_id: $document_id}})-[r:MENTIONS]->(e:{label})
            RETURN e.text as entity,
                   [l IN labels(e) WHERE l <> 'Entity'][0] as type,
                   count(r) as mentions
            ORDER BY mentions DESC
            LIMIT $limit
            """
        else:
            query = """
            MATCH (d:Document {document_id: $document_id})-[r:MENTIONS]->(e:Entity)
            RETURN e.text as entity,
                   [l IN labels(e) WHERE l <> 'Entity'][0] as type,
                   count(r) as mentions
            ORDER BY mentions DESC
            LIMIT $limit
            """

        try:
            with self._store.driver.session() as session:
                result = session.run(
                    query,
                    document_id=document_id,
                    limit=limit,
                )
                entities = [
                    {
                        "entity": record["entity"],
                        # Normalize to uppercase to match EntityType.value format
                        "type": record["type"].upper() if record["type"] else None,
                        "mentions": record["mentions"],
                    }
                    for record in result
                ]

            logger.debug(
                "find_entities_in_document",
                document_id=document_id,
                entity_type=entity_type.value if entity_type else None,
                result_count=len(entities),
            )

            return entities

        except Exception as e:
            logger.error(
                "find_entities_in_document_failed",
                document_id=document_id,
                error=str(e),
            )
            raise GraphQueryError(f"Failed to find entities in document: {e}") from e

    def find_co_occurring_entities(
        self,
        entity_text: str,
        min_co_occurrences: int = 2,
        limit: int = 50,
    ) -> list[dict]:
        """
        Find entities that frequently appear together with the given entity.

        Identifies entities that are contextually related based on their
        co-occurrence in the same documents.

        Args:
            entity_text: The source entity text.
            min_co_occurrences: Minimum shared document count (default 2).
            limit: Maximum results to return.

        Returns:
            List of dicts with entity info:
            - entity: Entity text
            - type: Entity type (UPPERCASE, e.g., "LOCATION")
            - co_occurrences: Number of shared documents

        Example:
            >>> co_entities = queries.find_co_occurring_entities("China")
            >>> # Finds entities like "Taiwan" (LOCATION), "Asia" (LOCATION)
        """
        self._store.verify_connection()

        query = """
        MATCH (e1:Entity)<-[:MENTIONS]-(d:Document)-[:MENTIONS]->(e2:Entity)
        WHERE toLower(e1.text) = toLower($entity_text) AND e1 <> e2
        WITH e2, count(DISTINCT d) as co_occurrences
        WHERE co_occurrences >= $min_co_occurrences
        RETURN e2.text as entity,
               [l IN labels(e2) WHERE l <> 'Entity'][0] as type,
               co_occurrences
        ORDER BY co_occurrences DESC
        LIMIT $limit
        """

        try:
            with self._store.driver.session() as session:
                result = session.run(
                    query,
                    entity_text=entity_text,
                    min_co_occurrences=min_co_occurrences,
                    limit=limit,
                )
                entities = [
                    {
                        "entity": record["entity"],
                        # Normalize to uppercase to match EntityType.value format
                        "type": record["type"].upper() if record["type"] else None,
                        "co_occurrences": record["co_occurrences"],
                    }
                    for record in result
                ]

            logger.debug(
                "find_co_occurring_entities",
                entity_text=entity_text,
                min_co_occurrences=min_co_occurrences,
                result_count=len(entities),
            )

            return entities

        except Exception as e:
            logger.error(
                "find_co_occurring_entities_failed",
                entity_text=entity_text,
                error=str(e),
            )
            raise GraphQueryError(f"Failed to find co-occurring entities: {e}") from e

    def find_path_between_entities(
        self,
        entity1: str,
        entity2: str,
        max_hops: int = 3,
    ) -> list[dict]:
        """
        Find shortest path between two entities through the document graph.

        Useful for understanding how two entities are connected in the corpus.

        Args:
            entity1: First entity text.
            entity2: Second entity text.
            max_hops: Maximum path length (default 3, max 5 for performance).

        Returns:
            List of path steps, each a dict with:
            - node: Entity or document name
            - type: Node type (UPPERCASE, e.g., "ORGANIZATION", "DOCUMENT")

        Example:
            >>> path = queries.find_path_between_entities("NVIDIA", "AMD")
            >>> # Returns path like: [{"node": "NVIDIA", "type": "ORGANIZATION"},
            >>> #                     {"node": "NVDA_10K_2025", "type": "DOCUMENT"},
            >>> #                     {"node": "AMD", "type": "ORGANIZATION"}]
        """
        self._store.verify_connection()

        # Cap max_hops for performance
        max_hops = min(max_hops, 5)

        query = """
        MATCH (e1:Entity), (e2:Entity)
        WHERE toLower(e1.text) = toLower($entity1)
          AND toLower(e2.text) = toLower($entity2)
        MATCH path = shortestPath((e1)-[*..%d]-(e2))
        RETURN [n in nodes(path) |
            CASE
                WHEN 'Document' IN labels(n) THEN {node: n.document_id, type: 'DOCUMENT'}
                ELSE {node: n.text, type: toUpper([l IN labels(n) WHERE l <> 'Entity'][0])}
            END
        ] as path_nodes
        LIMIT 1
        """ % (
            max_hops * 2
        )  # Each hop is entity-doc-entity, so double

        try:
            with self._store.driver.session() as session:
                result = session.run(
                    query,
                    entity1=entity1,
                    entity2=entity2,
                )
                record = result.single()

                if record and record["path_nodes"]:
                    path = record["path_nodes"]
                else:
                    path = []

            logger.debug(
                "find_path_between_entities",
                entity1=entity1,
                entity2=entity2,
                path_length=len(path),
            )

            return path

        except Exception as e:
            logger.error(
                "find_path_between_entities_failed",
                entity1=entity1,
                entity2=entity2,
                error=str(e),
            )
            raise GraphQueryError(f"Failed to find path between entities: {e}") from e

    # =========================================================================
    # Entity Search (fuzzy matching)
    # =========================================================================

    def entity_search(
        self,
        search_query: str,
        entity_type: EntityType | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """
        Fuzzy search for entities matching a query string.

        Case-insensitive partial matching for entity discovery.
        Useful for autocomplete and entity disambiguation.

        Args:
            search_query: Search string (partial match, case-insensitive).
            entity_type: Optional filter by entity type.
            limit: Maximum results to return.

        Returns:
            List of dicts with entity info:
            - entity: Entity text
            - type: Entity type (UPPERCASE, e.g., "ORGANIZATION")
            - mention_count: Total mentions across all documents

        Example:
            >>> matches = queries.entity_search("nvid")
            >>> # Returns: [{"entity": "NVIDIA", "type": "ORGANIZATION", ...}]
        """
        self._store.verify_connection()

        if entity_type:
            label = entity_type.name.title()
            cypher_query = f"""
            MATCH (e:{label})
            WHERE toLower(e.text) CONTAINS toLower($search_text)
            RETURN e.text as entity,
                   [l IN labels(e) WHERE l <> 'Entity'][0] as type,
                   coalesce(e.mention_count, 1) as mention_count
            ORDER BY mention_count DESC
            LIMIT $limit
            """
        else:
            cypher_query = """
            MATCH (e:Entity)
            WHERE toLower(e.text) CONTAINS toLower($search_text)
            RETURN e.text as entity,
                   [l IN labels(e) WHERE l <> 'Entity'][0] as type,
                   coalesce(e.mention_count, 1) as mention_count
            ORDER BY mention_count DESC
            LIMIT $limit
            """

        try:
            with self._store.driver.session() as session:
                result = session.run(
                    cypher_query,
                    search_text=search_query,
                    limit=limit,
                )
                entities = [
                    {
                        "entity": record["entity"],
                        # Normalize to uppercase to match EntityType.value format
                        "type": record["type"].upper() if record["type"] else None,
                        "mention_count": record["mention_count"],
                    }
                    for record in result
                ]

            logger.debug(
                "entity_search",
                search_query=search_query,
                entity_type=entity_type.value if entity_type else None,
                result_count=len(entities),
            )

            return entities

        except Exception as e:
            logger.error(
                "entity_search_failed",
                search_query=search_query,
                error=str(e),
            )
            raise GraphQueryError(f"Failed to search entities: {e}") from e

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def get_entity_types_summary(self) -> dict[str, int]:
        """
        Get count of entities by type in the graph.

        Returns:
            Dict mapping entity type names (UPPERCASE) to counts.

        Example:
            >>> summary = queries.get_entity_types_summary()
            >>> print(summary)
            {'ORGANIZATION': 744, 'DATE': 492, 'CONCEPT': 357, ...}
        """
        self._store.verify_connection()

        query = """
        MATCH (e:Entity)
        RETURN [l IN labels(e) WHERE l <> 'Entity'][0] as type, count(e) as count
        ORDER BY count DESC
        """

        try:
            with self._store.driver.session() as session:
                result = session.run(query)
                # Normalize type keys to uppercase to match EntityType.value format
                summary = {
                    record["type"].upper() if record["type"] else "UNKNOWN": record["count"]
                    for record in result
                }

            logger.debug("get_entity_types_summary", types=len(summary))

            return summary

        except Exception as e:
            logger.error("get_entity_types_summary_failed", error=str(e))
            raise GraphQueryError(f"Failed to get entity summary: {e}") from e
