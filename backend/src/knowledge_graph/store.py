"""
Neo4j graph store for Knowledge Graph entity and relationship storage.

This module provides a Neo4j adapter for storing extracted entities and their
relationships. It supports connection pooling, batch operations, and CRUD
operations for the Knowledge Graph.

Architecture:
    EntityExtractor → Entity objects → Neo4jStore → Neo4j Database
                                           ↓
                                    MERGE (deduplicate)
                                           ↓
                                    Entity nodes + MENTIONS relationships

Features:
    - Connection pooling via Neo4j driver
    - MERGE-based deduplication (same entity text = same node)
    - Batch operations with UNWIND for bulk loading
    - Document→Entity MENTIONS relationships with page tracking
    - Entity importance via mention_count aggregation

Node Labels:
    - Entity nodes use EntityType.name as primary label (Organization, Person, etc.)
    - Secondary label "Entity" enables generic queries across all types
    - Document nodes track source documents

Cost Efficiency:
    - Neo4j AuraDB Free: 200K nodes, 400K relationships ($0/month)
    - Local Docker: neo4j:5-community for development

Usage:
    from src.knowledge_graph.store import Neo4jStore
    from src.knowledge_graph.extractor import EntityExtractor

    # Create store
    store = Neo4jStore(
        uri="bolt://localhost:7687",
        user="neo4j",
        password="your-password"  # pragma: allowlist secret
    )

    # Extract and store entities
    extractor = EntityExtractor()
    entities = extractor.extract_entities(text, document_id="DOC_001", page=1)
    entity_ids = store.batch_create_entities(entities)

    # Create document node and MENTIONS relationships
    store.create_document_node("DOC_001", {"company": "NVIDIA", "type": "10-K"})
    store.create_mentions_relationships("DOC_001", entities)

    # Query
    doc_entities = store.find_entities_by_document("DOC_001")

    # Cleanup
    store.close()

Reference:
    - Neo4j Python driver: https://neo4j.com/docs/python-manual/current/
    - ontology.py for EntityType and RelationType
    - extractor.py for Entity dataclass
    - backend.mdc for Python patterns
    - PHASE_2B_HOW_TO_GUIDE.md Section 4

Local Development:
    Requires Neo4j running via docker-compose:
    - docker-compose up neo4j
    - URI: bolt://neo4j:7687 (from backend container)
    - URI: bolt://localhost:7687 (from host)

AWS Deployment:
    When ENVIRONMENT=aws, credentials loaded from AWS Secrets Manager:
    - Secret: enterprise-agentic-ai/neo4j
    - Keys: uri, user, password
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Generator

import structlog
from neo4j import Driver, GraphDatabase, ManagedTransaction, Result
from neo4j.exceptions import (
    AuthError,
    Neo4jError,
    ServiceUnavailable,
)

from src.knowledge_graph.extractor import Entity
from src.knowledge_graph.ontology import EntityType, RelationType

# Configure structured logger
logger = structlog.get_logger(__name__)


# =============================================================================
# Custom Exceptions
# =============================================================================


class Neo4jStoreError(Exception):
    """Base exception for Neo4j store operations."""

    pass


class Neo4jConnectionError(Neo4jStoreError):
    """Raised when Neo4j connection fails."""

    pass


class QueryError(Neo4jStoreError):
    """Raised when a Cypher query fails."""

    pass


class AuraDBPausedError(Neo4jConnectionError):
    """
    Raised when Neo4j AuraDB instance is paused.

    AuraDB free tier instances auto-pause after ~3 days of inactivity.
    Resume from: https://console.neo4j.io/
    """

    pass


# =============================================================================
# Neo4j Store
# =============================================================================


class Neo4jStore:
    """
    Neo4j graph store adapter for Knowledge Graph operations.

    This class manages Neo4j connections and provides CRUD operations for
    entities and relationships. It uses connection pooling for performance
    and MERGE queries to avoid duplicate entities.

    Attributes:
        uri: Neo4j connection URI (bolt:// or neo4j+s://)
        user: Neo4j username
        _driver: Neo4j driver instance (lazy-loaded)

    Example:
        >>> store = Neo4jStore("bolt://localhost:7687", "neo4j", "password")
        >>> entity_id = store.create_entity(entity)
        >>> store.close()
    """

    def __init__(self, uri: str, user: str, password: str) -> None:
        """
        Initialize the Neo4j store.

        Args:
            uri: Neo4j connection URI (e.g., bolt://localhost:7687)
            user: Neo4j username
            password: Neo4j password

        Raises:
            Neo4jConnectionError: If connection to Neo4j fails.
        """
        self.uri = uri
        self.user = user
        self._password = password
        self._driver: Driver | None = None

        logger.info(
            "neo4j_store_initialized",
            uri=uri,
            user=user,
        )

    @property
    def driver(self) -> Driver:
        """
        Lazy-load and return the Neo4j driver.

        Returns:
            The Neo4j driver instance.

        Raises:
            Neo4jConnectionError: If driver creation fails.
        """
        if self._driver is None:
            self._driver = self._get_driver()
        return self._driver

    def _get_driver(self) -> Driver:
        """
        Create and return a Neo4j driver with connection pooling.

        Returns:
            Configured Neo4j driver.

        Raises:
            ConnectionError: If connection fails.
        """
        try:
            driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self._password),
                max_connection_lifetime=3600,  # 1 hour
                max_connection_pool_size=50,
                connection_acquisition_timeout=60,
            )

            # Verify connectivity
            driver.verify_connectivity()

            logger.info(
                "neo4j_driver_created",
                uri=self.uri,
            )

            return driver

        except AuthError as e:
            logger.error(
                "neo4j_auth_failed",
                uri=self.uri,
                user=self.user,
                error=str(e),
            )
            raise Neo4jConnectionError(
                f"Neo4j authentication failed for user '{self.user}'"
            ) from e

        except ServiceUnavailable as e:
            logger.error(
                "neo4j_unavailable",
                uri=self.uri,
                error=str(e),
            )
            raise Neo4jConnectionError(
                f"Neo4j service unavailable at {self.uri}"
            ) from e

        except Exception as e:
            logger.error(
                "neo4j_connection_failed",
                uri=self.uri,
                error=str(e),
            )
            raise Neo4jConnectionError(f"Failed to connect to Neo4j: {e}") from e

    def close(self) -> None:
        """
        Close the Neo4j driver and release resources.

        Should be called when the store is no longer needed.
        """
        if self._driver is not None:
            self._driver.close()
            self._driver = None
            logger.info("neo4j_driver_closed")

    @contextmanager
    def _session(self) -> Generator[Any, None, None]:
        """
        Context manager for Neo4j sessions.

        Yields:
            A Neo4j session.
        """
        session = self.driver.session()
        try:
            yield session
        finally:
            session.close()

    # =========================================================================
    # Entity CRUD Operations
    # =========================================================================

    def create_entity(self, entity: Entity) -> str:
        """
        Create or merge an entity node in Neo4j.

        Uses MERGE to avoid duplicates - entities with the same text and type
        are considered the same node. Increments mention_count on match.

        Args:
            entity: The Entity object to create.

        Returns:
            The Neo4j element ID of the created/matched node.

        Raises:
            QueryError: If the query fails.
        """

        def _create(tx: ManagedTransaction) -> str:
            # Use entity type as Neo4j label (e.g., Organization, Person)
            label = entity.entity_type.name.title()

            # MERGE on text + type, update mention_count
            query = f"""
            MERGE (e:{label}:Entity {{text: $text}})
            ON CREATE SET
                e.created_at = datetime(),
                e.source_document = $source_document,
                e.mention_count = 1,
                e.confidence = $confidence
            ON MATCH SET
                e.mention_count = coalesce(e.mention_count, 0) + 1
            RETURN elementId(e) as id
            """

            result: Result = tx.run(
                query,
                text=entity.text,
                source_document=entity.source_document_id,
                confidence=entity.confidence,
            )

            record = result.single()
            if record is None:
                raise QueryError(f"Failed to create entity: {entity.text}")

            return str(record["id"])

        try:
            with self._session() as session:
                entity_id = session.execute_write(_create)

            logger.debug(
                "entity_created",
                entity_id=entity_id,
                text=entity.text,
                entity_type=entity.entity_type.name,
            )

            return entity_id

        except Neo4jError as e:
            logger.error(
                "entity_creation_failed",
                text=entity.text,
                error=str(e),
            )
            raise QueryError(f"Failed to create entity: {e}") from e

    def batch_create_entities(
        self,
        entities: list[Entity],
        batch_size: int = 500,
    ) -> list[str]:
        """
        Create multiple entities using UNWIND, chunked for reliability.

        More efficient than creating entities one at a time. Uses MERGE
        to avoid duplicates. Chunks large batches to avoid transaction
        timeouts on Neo4j AuraDB free tier.

        Args:
            entities: List of Entity objects to create.
            batch_size: Maximum entities per transaction (default 500).

        Returns:
            List of Neo4j element IDs for created/matched nodes.

        Raises:
            QueryError: If the batch operation fails.
        """
        if not entities:
            return []

        def _batch_create_chunk(
            tx: ManagedTransaction,
            chunk: list[Entity],
        ) -> list[str]:
            # Group entities by type for efficient MERGE
            # Since we can't parameterize labels, we process each type separately
            entity_ids: list[str] = []

            # Group by entity type
            by_type: dict[EntityType, list[Entity]] = {}
            for entity in chunk:
                if entity.entity_type not in by_type:
                    by_type[entity.entity_type] = []
                by_type[entity.entity_type].append(entity)

            # Process each type
            for entity_type, type_entities in by_type.items():
                label = entity_type.name.title()

                # Prepare batch data
                batch_data = [
                    {
                        "text": e.text,
                        "source_document": e.source_document_id,
                        "confidence": e.confidence,
                    }
                    for e in type_entities
                ]

                query = f"""
                UNWIND $entities as entity
                MERGE (e:{label}:Entity {{text: entity.text}})
                ON CREATE SET
                    e.created_at = datetime(),
                    e.source_document = entity.source_document,
                    e.mention_count = 1,
                    e.confidence = entity.confidence
                ON MATCH SET
                    e.mention_count = coalesce(e.mention_count, 0) + 1
                RETURN elementId(e) as id
                """

                result: Result = tx.run(query, entities=batch_data)

                for record in result:
                    entity_ids.append(str(record["id"]))

            return entity_ids

        try:
            all_ids: list[str] = []

            # Process in chunks to avoid transaction timeouts
            for i in range(0, len(entities), batch_size):
                chunk = entities[i : i + batch_size]

                with self._session() as session:
                    # Use default arg to capture chunk by value (avoid closure bug)
                    chunk_ids = session.execute_write(
                        lambda tx, c=chunk: _batch_create_chunk(tx, c)
                    )
                    all_ids.extend(chunk_ids)

            logger.info(
                "batch_entities_created",
                count=len(all_ids),
                input_count=len(entities),
                chunks=(len(entities) + batch_size - 1) // batch_size,
            )

            return all_ids

        except Neo4jError as e:
            logger.error(
                "batch_entity_creation_failed",
                count=len(entities),
                error=str(e),
            )
            raise QueryError(f"Failed to batch create entities: {e}") from e

    def find_entity_by_text(
        self,
        text: str,
        entity_type: EntityType | None = None,
    ) -> dict[str, Any] | None:
        """
        Find an entity by its text, optionally filtered by type.

        Args:
            text: The entity text to search for.
            entity_type: Optional EntityType to filter by.

        Returns:
            Dictionary with entity properties, or None if not found.
        """

        def _find(tx: ManagedTransaction) -> dict[str, Any] | None:
            if entity_type:
                label = entity_type.name.title()
                query = f"""
                MATCH (e:{label}:Entity {{text: $text}})
                RETURN elementId(e) as id, e.text as text, e.mention_count as mention_count,
                       e.source_document as source_document, e.created_at as created_at
                """
            else:
                query = """
                MATCH (e:Entity {text: $text})
                RETURN elementId(e) as id, e.text as text, e.mention_count as mention_count,
                       e.source_document as source_document, e.created_at as created_at,
                       labels(e) as labels
                """

            result: Result = tx.run(query, text=text)
            record = result.single()

            if record is None:
                return None

            return dict(record)

        with self._session() as session:
            return session.execute_read(_find)

    def find_entities_by_document(self, document_id: str) -> list[dict[str, Any]]:
        """
        Find all entities mentioned in a document.

        Args:
            document_id: The document ID to search for.

        Returns:
            List of entity dictionaries with properties.
        """

        def _find(tx: ManagedTransaction) -> list[dict[str, Any]]:
            query = """
            MATCH (d:Document {document_id: $document_id})-[r:MENTIONS]->(e:Entity)
            RETURN elementId(e) as id, e.text as text, labels(e) as labels,
                   e.mention_count as mention_count, r.page as page
            ORDER BY e.mention_count DESC
            """

            result: Result = tx.run(query, document_id=document_id)
            return [dict(record) for record in result]

        with self._session() as session:
            return session.execute_read(_find)

    def delete_document_entities(self, document_id: str) -> int:
        """
        Delete all MENTIONS relationships for a document.

        Note: This only deletes relationships, not the entity nodes themselves.
        Entity nodes may be referenced by other documents.

        Args:
            document_id: The document ID whose relationships to delete.

        Returns:
            Number of relationships deleted.
        """

        def _delete(tx: ManagedTransaction) -> int:
            query = """
            MATCH (d:Document {document_id: $document_id})-[r:MENTIONS]->()
            DELETE r
            RETURN count(r) as deleted_count
            """

            result: Result = tx.run(query, document_id=document_id)
            record = result.single()

            return int(record["deleted_count"]) if record else 0

        with self._session() as session:
            count = session.execute_write(_delete)

        logger.info(
            "document_relationships_deleted",
            document_id=document_id,
            count=count,
        )

        return count

    # =========================================================================
    # Relationship Operations
    # =========================================================================

    def create_relationship(
        self,
        from_id: str,
        to_id: str,
        rel_type: RelationType,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """
        Create a relationship between two nodes.

        Args:
            from_id: Element ID of the source node.
            to_id: Element ID of the target node.
            rel_type: The RelationType for the relationship.
            properties: Optional properties for the relationship.

        Raises:
            QueryError: If relationship creation fails.
        """

        def _create(tx: ManagedTransaction) -> None:
            rel_name = rel_type.name
            props = properties or {}

            query = f"""
            MATCH (a), (b)
            WHERE elementId(a) = $from_id AND elementId(b) = $to_id
            MERGE (a)-[r:{rel_name}]->(b)
            SET r.created_at = datetime()
            SET r += $props
            """

            tx.run(query, from_id=from_id, to_id=to_id, props=props)

        try:
            with self._session() as session:
                session.execute_write(_create)

            logger.debug(
                "relationship_created",
                from_id=from_id,
                to_id=to_id,
                rel_type=rel_type.name,
            )

        except Neo4jError as e:
            logger.error(
                "relationship_creation_failed",
                from_id=from_id,
                to_id=to_id,
                rel_type=rel_type.name,
                error=str(e),
            )
            raise QueryError(f"Failed to create relationship: {e}") from e

    def batch_create_relationships(
        self,
        relationships: list[tuple[str, str, RelationType, dict[str, Any] | None]],
    ) -> None:
        """
        Create multiple relationships in a single transaction.

        Args:
            relationships: List of (from_id, to_id, rel_type, properties) tuples.

        Raises:
            QueryError: If batch operation fails.
        """
        if not relationships:
            return

        def _batch_create(tx: ManagedTransaction) -> None:
            # Group by relationship type since we can't parameterize rel types
            by_type: dict[RelationType, list[dict[str, Any]]] = {}
            for from_id, to_id, rel_type, props in relationships:
                if rel_type not in by_type:
                    by_type[rel_type] = []
                by_type[rel_type].append(
                    {
                        "from_id": from_id,
                        "to_id": to_id,
                        "props": props or {},
                    }
                )

            for rel_type, rels in by_type.items():
                rel_name = rel_type.name

                query = f"""
                UNWIND $rels as rel
                MATCH (a), (b)
                WHERE elementId(a) = rel.from_id AND elementId(b) = rel.to_id
                MERGE (a)-[r:{rel_name}]->(b)
                SET r.created_at = datetime()
                SET r += rel.props
                """

                tx.run(query, rels=rels)

        try:
            with self._session() as session:
                session.execute_write(_batch_create)

            logger.info(
                "batch_relationships_created",
                count=len(relationships),
            )

        except Neo4jError as e:
            logger.error(
                "batch_relationship_creation_failed",
                count=len(relationships),
                error=str(e),
            )
            raise QueryError(f"Failed to batch create relationships: {e}") from e

    def create_mentions_relationship(
        self,
        document_id: str,
        entity_text: str,
        page: int | None = None,
    ) -> None:
        """
        Create a MENTIONS relationship from a document to an entity.

        Creates a unique relationship for each (document, entity, page) tuple.
        If the same entity appears on multiple pages, multiple relationships
        are created to preserve citation information.

        Args:
            document_id: The document ID.
            entity_text: The entity text to link to.
            page: Optional page number where the entity was found.
        """

        def _create(tx: ManagedTransaction) -> None:
            # Include page in MERGE pattern to create separate relationships per page
            # This preserves citation info when same entity appears on multiple pages
            query = """
            MATCH (d:Document {document_id: $document_id})
            MATCH (e:Entity {text: $entity_text})
            MERGE (d)-[r:MENTIONS {page: $page}]->(e)
            ON CREATE SET r.created_at = datetime()
            """

            tx.run(query, document_id=document_id, entity_text=entity_text, page=page)

        with self._session() as session:
            session.execute_write(_create)

        logger.debug(
            "mentions_relationship_created",
            document_id=document_id,
            entity_text=entity_text,
            page=page,
        )

    def create_mentions_relationships(
        self,
        document_id: str,
        entities: list[Entity],
        batch_size: int = 500,
    ) -> int:
        """
        Create MENTIONS relationships from a document to multiple entities.

        Creates unique relationships for each (document, entity, page) tuple.
        If the same entity appears on multiple pages in the entities list,
        multiple relationships are created to preserve citation information.
        Chunks large batches to avoid transaction timeouts.

        Args:
            document_id: The document ID.
            entities: List of Entity objects to link (uses text and source_page).
            batch_size: Maximum entities per transaction (default 500).

        Returns:
            Number of relationships created.
        """
        if not entities:
            return 0

        def _batch_create_chunk(
            tx: ManagedTransaction,
            chunk: list[Entity],
        ) -> int:
            # Prepare batch data
            batch_data = [
                {
                    "entity_text": e.text,
                    "page": e.source_page,
                }
                for e in chunk
            ]

            # Include page in MERGE pattern to create separate relationships per page
            # This preserves citation info when same entity appears on multiple pages
            query = """
            UNWIND $entities as entity
            MATCH (d:Document {document_id: $document_id})
            MATCH (e:Entity {text: entity.entity_text})
            MERGE (d)-[r:MENTIONS {page: entity.page}]->(e)
            ON CREATE SET r.created_at = datetime()
            RETURN count(r) as count
            """

            result: Result = tx.run(query, document_id=document_id, entities=batch_data)
            record = result.single()

            return int(record["count"]) if record else 0

        total_count = 0

        # Process in chunks to avoid transaction timeouts
        for i in range(0, len(entities), batch_size):
            chunk = entities[i : i + batch_size]

            with self._session() as session:
                # Use default arg to capture chunk by value (avoid closure bug)
                chunk_count = session.execute_write(
                    lambda tx, c=chunk: _batch_create_chunk(tx, c)
                )
                total_count += chunk_count

        logger.info(
            "mentions_relationships_created",
            document_id=document_id,
            count=total_count,
            chunks=(len(entities) + batch_size - 1) // batch_size,
        )

        return total_count

    # =========================================================================
    # Document Operations
    # =========================================================================

    def create_document_node(
        self,
        document_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Create or merge a Document node.

        Uses MERGE to create the node if it doesn't exist, or update metadata
        if it does (for re-indexing with --force). Sets created_at on create
        and updated_at on match.

        Args:
            document_id: Unique document identifier.
            metadata: Optional metadata dict with keys:
                - document_type: Type of document (e.g., "10k", "reference")
                - company: Company name
                - ticker: Stock ticker symbol
                - title: Document title (use filename from VLM extraction)

        Returns:
            The Neo4j element ID of the document node.
        """
        metadata = metadata or {}

        def _create(tx: ManagedTransaction) -> str:
            # ON CREATE: Set created_at and all metadata
            # ON MATCH: Update metadata (for --force re-indexing) and set updated_at
            query = """
            MERGE (d:Document {document_id: $document_id})
            ON CREATE SET
                d.created_at = datetime(),
                d.document_type = $document_type,
                d.company = $company,
                d.ticker = $ticker,
                d.title = $title
            ON MATCH SET
                d.updated_at = datetime(),
                d.document_type = $document_type,
                d.company = $company,
                d.ticker = $ticker,
                d.title = $title
            RETURN elementId(d) as id
            """

            result: Result = tx.run(
                query,
                document_id=document_id,
                document_type=metadata.get("document_type"),
                company=metadata.get("company"),
                ticker=metadata.get("ticker"),
                title=metadata.get("title"),
            )

            record = result.single()
            if record is None:
                raise QueryError(f"Failed to create document node: {document_id}")

            return str(record["id"])

        with self._session() as session:
            doc_id = session.execute_write(_create)

        logger.info(
            "document_node_created",
            document_id=document_id,
            neo4j_id=doc_id,
        )

        return doc_id

    def document_exists(self, document_id: str) -> bool:
        """
        Check if a document node exists in Neo4j.

        Args:
            document_id: The document ID to check.

        Returns:
            True if document exists, False otherwise.
        """

        def _check(tx: ManagedTransaction) -> bool:
            query = """
            MATCH (d:Document {document_id: $document_id})
            RETURN count(d) > 0 as exists
            """

            result: Result = tx.run(query, document_id=document_id)
            record = result.single()

            return bool(record["exists"]) if record else False

        with self._session() as session:
            return session.execute_read(_check)

    # =========================================================================
    # Statistics and Utilities
    # =========================================================================

    def get_stats(self) -> dict[str, Any]:
        """
        Get statistics about the Knowledge Graph.

        Returns:
            Dictionary with node_count, relationship_count, and entity_type_counts.
        """

        def _get_stats(tx: ManagedTransaction) -> dict[str, Any]:
            # Get total counts
            count_query = """
            MATCH (n)
            WITH count(n) as node_count
            MATCH ()-[r]->()
            RETURN node_count, count(r) as relationship_count
            """

            result: Result = tx.run(count_query)
            record = result.single()

            stats: dict[str, Any] = {
                "node_count": record["node_count"] if record else 0,
                "relationship_count": record["relationship_count"] if record else 0,
            }

            # Get counts by entity type
            type_query = """
            MATCH (e:Entity)
            RETURN labels(e) as labels, count(e) as count
            """

            result = tx.run(type_query)
            type_counts: dict[str, int] = {}
            for record in result:
                labels = record["labels"]
                # Find the entity type label (not "Entity")
                for label in labels:
                    if label != "Entity":
                        type_counts[label] = type_counts.get(label, 0) + int(
                            record["count"]
                        )

            stats["entity_type_counts"] = type_counts

            # Get document count
            doc_query = "MATCH (d:Document) RETURN count(d) as count"
            result = tx.run(doc_query)
            record = result.single()
            stats["document_count"] = record["count"] if record else 0

            return stats

        with self._session() as session:
            return session.execute_read(_get_stats)

    def verify_connection(self) -> bool:
        """
        Verify that the Neo4j connection is working.

        Returns:
            True if connection is successful.

        Raises:
            AuraDBPausedError: If AuraDB instance is paused (with actionable message).
            Neo4jConnectionError: For other connection failures.
        """
        try:
            self.driver.verify_connectivity()
            return True
        except ServiceUnavailable as e:
            error_str = str(e).lower()
            # AuraDB pause detection - common patterns in error messages
            if any(
                pattern in error_str
                for pattern in [
                    "unable to retrieve routing",
                    "connection refused",
                    "timed out",
                ]
            ):
                logger.error(
                    "auradb_possibly_paused",
                    error=str(e),
                    hint="AuraDB free tier auto-pauses after ~3 days. Resume at https://console.neo4j.io/",
                )
                raise AuraDBPausedError(
                    "Neo4j AuraDB instance appears to be paused. "
                    "Resume at https://console.neo4j.io/ and wait ~60 seconds."
                ) from e
            logger.error("neo4j_service_unavailable", error=str(e))
            raise Neo4jConnectionError(f"Neo4j service unavailable: {e}") from e
        except Exception as e:
            logger.error("neo4j_connection_verification_failed", error=str(e))
            raise Neo4jConnectionError(f"Neo4j connection failed: {e}") from e


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    "Neo4jStore",
    "Neo4jStoreError",
    "Neo4jConnectionError",
    "AuraDBPausedError",
    "QueryError",
]
