#!/usr/bin/env python
"""
Entity indexing script for Knowledge Graph population.

This script processes VLM extraction JSON files from Phase 2a, extracts entities
using spaCy NER, and stores them in Neo4j for graph-based retrieval.

Pipeline per document:
    1. Load JSON extraction from Phase 2a
    2. Create Document node in Neo4j
    3. For each page:
       a. Extract entities using EntityExtractor
       b. Create entity nodes (MERGE deduplicates)
       c. Create MENTIONS relationships (Document→Entity)
    4. Log progress and stats

Usage:
    # Index all documents
    docker-compose exec backend python scripts/index_entities.py

    # Dry run (extract but don't store)
    docker-compose exec backend python scripts/index_entities.py --dry-run

    # Re-index (force update existing)
    docker-compose exec backend python scripts/index_entities.py --force

    # Custom directory
    docker-compose exec backend python scripts/index_entities.py --extracted-dir /path/to/json

Reference:
    - PHASE_2B_HOW_TO_GUIDE.md Section 5.1
    - EntityExtractor from Section 3
    - Neo4jStore from Section 4
    - VLM extraction JSON structure from Phase 2a
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.knowledge_graph.extractor import EntityExtractor
    from src.knowledge_graph.store import Neo4jStore

# Add backend/src to path for imports when running locally or in Docker
PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = PROJECT_ROOT / "backend"

# Check if we're running in Docker (scripts mounted at /app/scripts)
if Path("/app/src").exists():
    # Running in Docker - /app is the backend root
    BACKEND_SRC = Path("/app")
    PROJECT_ROOT = Path("/app")  # Documents are at /app/documents

if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

import structlog

# Use existing structlog configuration from backend
logger = structlog.get_logger(__name__)


# =============================================================================
# Statistics Tracking
# =============================================================================


@dataclass
class IndexingStats:
    """Statistics for entity indexing run."""

    documents_processed: int = 0
    documents_skipped: int = 0
    documents_failed: int = 0
    total_pages: int = 0
    total_entity_mentions: int = 0
    unique_entities: int = 0
    relationships_created: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert stats to dictionary."""
        return {
            "documents_processed": self.documents_processed,
            "documents_skipped": self.documents_skipped,
            "documents_failed": self.documents_failed,
            "total_pages": self.total_pages,
            "total_entity_mentions": self.total_entity_mentions,
            "unique_entities": self.unique_entities,
            "relationships_created": self.relationships_created,
            "error_count": len(self.errors),
        }


# =============================================================================
# Document Processing
# =============================================================================


def extract_metadata_from_document(
    extraction_json: dict[str, Any],
) -> dict[str, Any]:
    """
    Extract metadata for document node from VLM extraction JSON.

    Args:
        extraction_json: The VLM extraction output dictionary.

    Returns:
        Metadata dict with document_type, company, ticker, title.
    """
    document_id = extraction_json.get("document_id", "")
    document_type = extraction_json.get("document_type")
    filename = extraction_json.get("filename", "")

    # Extract ticker from document_id (e.g., "NVDA_10K_2025" → "NVDA")
    ticker = None
    company = None
    if document_id:
        parts = document_id.split("_")
        if len(parts) >= 1:
            # First part is typically the ticker for 10-K files
            potential_ticker = parts[0]
            # Validate it looks like a ticker (2-5 uppercase letters)
            if potential_ticker.isupper() and 2 <= len(potential_ticker) <= 5:
                ticker = potential_ticker

    # Use filename as title (per guide Section 5.1 note)
    title = filename if filename else document_id

    return {
        "document_type": document_type,
        "company": company,
        "ticker": ticker,
        "title": title,
    }


def process_document(
    extraction_path: Path,
    extractor: "EntityExtractor",
    store: "Neo4jStore | None",
    global_unique_entities: set[str],  # Fix 2: Track global unique across documents
    force: bool = False,
    dry_run: bool = False,
) -> tuple[int, int, int, bool, int]:
    """
    Process a single document extraction and index entities.

    Args:
        extraction_path: Path to the VLM extraction JSON file.
        extractor: EntityExtractor instance.
        store: Neo4jStore instance (or None for dry-run).
        global_unique_entities: Set to track unique entities across all documents.
        force: Whether to re-index existing documents.
        dry_run: Whether to skip storing (extract only).

    Returns:
        Tuple of (entity_mentions, unique_in_doc, relationships_created, was_skipped, page_count).

    Raises:
        Exception: If processing fails.
    """
    # Load extraction JSON
    with open(extraction_path, encoding="utf-8") as f:
        extraction_json = json.load(f)

    document_id = extraction_json.get("document_id")
    pages = extraction_json.get("pages", [])
    page_count = len(pages)

    if not document_id:
        raise ValueError(f"No document_id in {extraction_path}")

    print(f"\nProcessing {extraction_path.name}...")

    # Check if document already exists (unless --force or --dry-run)
    if not dry_run and store and not force:
        if store.document_exists(document_id):
            print("  Skipping (already indexed). Use --force to re-index.")
            return 0, 0, 0, True, 0  # was_skipped=True, page_count=0

    # Fix 3: Clear old MENTIONS when re-indexing with --force
    if not dry_run and store and force:
        deleted_count = store.delete_document_entities(document_id)
        if deleted_count > 0:
            print(f"  Cleared {deleted_count} old MENTIONS relationships")

    # Extract metadata
    metadata = extract_metadata_from_document(extraction_json)

    # Create document node (unless dry-run)
    if not dry_run and store:
        store.create_document_node(document_id, metadata)
        print("  Created Document node")

    # Extract entities per page (preserves page info for MENTIONS)
    # Import Entity type inline to avoid circular import issues
    from src.knowledge_graph.extractor import Entity

    all_entities: list[Entity] = []
    unique_entity_texts: set[str] = set()

    # Fix 4: Progress indicator for large documents
    total_pages = len(pages)
    for idx, page_data in enumerate(pages, 1):
        page_number = page_data.get("page_number")
        text = page_data.get("text", "")

        # Show progress every 20 pages for large documents
        if total_pages > 20 and idx % 20 == 0:
            print(f"  Extracting page {idx}/{total_pages}...")

        if not text:
            continue

        # Extract entities for this page
        page_entities = extractor.extract_entities(
            text=text,
            document_id=document_id,
            page=page_number,
        )

        all_entities.extend(page_entities)

        # Track unique entities (by lowercase text for dedup)
        for entity in page_entities:
            entity_key = entity.text.lower()
            unique_entity_texts.add(entity_key)
            # Fix 2: Also add to global set
            global_unique_entities.add(entity_key)

    total_mentions = len(all_entities)
    unique_count = len(unique_entity_texts)

    print(f"  Extracted {total_mentions} entity mentions")
    print(f"  Unique entities in document: {unique_count}")

    relationships_created = 0

    if not dry_run and store and all_entities:
        # Create entity nodes (batch for efficiency)
        # MERGE in Neo4j handles deduplication
        store.batch_create_entities(all_entities)

        # Create MENTIONS relationships (preserves per-page info)
        relationships_created = store.create_mentions_relationships(
            document_id,
            all_entities,
        )

        print(
            f"  Created {unique_count} entity nodes, "
            f"{relationships_created} MENTIONS relationships"
        )
    elif dry_run:
        print("  [DRY RUN] Skipped storing to Neo4j")

    return total_mentions, unique_count, relationships_created, False, page_count


# =============================================================================
# Main Entry Point
# =============================================================================


def find_extraction_files(extracted_dir: Path) -> list[Path]:
    """
    Find all VLM extraction JSON files in a directory.

    Args:
        extracted_dir: Directory containing extraction JSON files.

    Returns:
        List of paths to extraction JSON files.
    """
    files = []

    for path in extracted_dir.iterdir():
        # Skip manifest.json and non-JSON files
        if path.suffix != ".json":
            continue
        if path.name == "manifest.json":
            continue

        files.append(path)

    # Sort for consistent ordering
    files.sort(key=lambda p: p.name)

    return files


def main() -> int:
    """
    Main entry point for entity indexing.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    parser = argparse.ArgumentParser(
        description="Index entities from VLM extraction JSON to Neo4j Knowledge Graph",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Index all documents
  python scripts/index_entities.py

  # Dry run (extract but don't store)
  python scripts/index_entities.py --dry-run

  # Re-index (force update existing)
  python scripts/index_entities.py --force

  # Custom directory
  python scripts/index_entities.py --extracted-dir /path/to/json
        """,
    )

    parser.add_argument(
        "--extracted-dir",
        type=Path,
        default=Path("documents/extracted"),
        help="Directory containing VLM extraction JSON files (default: documents/extracted)",
    )
    parser.add_argument(
        "--neo4j-uri",
        type=str,
        default=None,
        help="Override NEO4J_URI from settings",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-index even if document exists in Neo4j",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Extract entities without storing to Neo4j",
    )

    args = parser.parse_args()

    # Validate extracted directory
    if not args.extracted_dir.exists():
        print(f"Error: Extracted directory not found: {args.extracted_dir}")
        return 1

    # Find extraction files
    extraction_files = find_extraction_files(args.extracted_dir)

    if not extraction_files:
        print(f"No extraction JSON files found in {args.extracted_dir}")
        return 1

    print(f"Found {len(extraction_files)} extraction files")

    # Import knowledge graph modules
    # (Done here to avoid import errors if modules don't exist)
    try:
        from src.knowledge_graph.extractor import EntityExtractor
        from src.knowledge_graph.store import Neo4jStore
    except ImportError as e:
        print(f"Error importing knowledge graph modules: {e}")
        print("Make sure you're running this from the backend container:")
        print("  docker-compose exec backend python scripts/index_entities.py")
        return 1

    # Initialize extractor
    print("\nInitializing EntityExtractor...")
    extractor = EntityExtractor()
    # Trigger lazy loading of spaCy model
    _ = extractor.nlp
    print("EntityExtractor ready")

    # Initialize store (unless dry-run)
    store: Neo4jStore | None = None

    if not args.dry_run:
        print("\nConnecting to Neo4j...")
        try:
            from src.config.settings import get_settings

            settings = get_settings()

            # Use CLI override or settings
            neo4j_uri = args.neo4j_uri or settings.neo4j_uri
            neo4j_user = settings.neo4j_user
            neo4j_password = settings.neo4j_password.get_secret_value()

            store = Neo4jStore(
                uri=neo4j_uri,
                user=neo4j_user,
                password=neo4j_password,
            )

            # Verify connection
            if not store.verify_connection():
                print("Error: Failed to connect to Neo4j")
                return 1

            print(f"Connected to Neo4j at {neo4j_uri}")

        except Exception as e:
            print(f"Error connecting to Neo4j: {e}")
            return 1
    else:
        print("\n[DRY RUN MODE] Skipping Neo4j connection")

    # Process documents
    stats = IndexingStats()
    global_unique_entities: set[str] = set()  # Fix 2: Track global unique

    print("\n" + "=" * 60)
    print("Starting entity indexing...")
    print("=" * 60)

    for extraction_path in extraction_files:
        try:
            mentions, unique, rels, was_skipped, page_count = process_document(
                extraction_path=extraction_path,
                extractor=extractor,
                store=store,
                global_unique_entities=global_unique_entities,  # Fix 2
                force=args.force,
                dry_run=args.dry_run,
            )

            if was_skipped:
                stats.documents_skipped += 1
            else:
                stats.documents_processed += 1
                stats.total_entity_mentions += mentions
                stats.unique_entities += unique  # Per-doc unique (for per-doc stats)
                stats.relationships_created += rels
                stats.total_pages += page_count

        except Exception as e:
            stats.documents_failed += 1
            stats.errors.append(f"{extraction_path.name}: {e}")
            logger.error(
                "document_processing_failed",
                file=extraction_path.name,
                error=str(e),
            )
            print(f"  ERROR: {e}")

    # Get final Neo4j stats
    neo4j_stats = {}
    if store:
        try:
            neo4j_stats = store.get_stats()
        except Exception as e:
            logger.warning("failed_to_get_neo4j_stats", error=str(e))

    # Close store
    if store:
        store.close()

    # Print summary
    print("\n" + "=" * 60)
    print("Summary:")
    print("=" * 60)
    print(f"  Documents processed: {stats.documents_processed}")
    if stats.documents_skipped > 0:
        print(f"  Documents skipped: {stats.documents_skipped}")
    if stats.documents_failed > 0:
        print(f"  Documents failed: {stats.documents_failed}")
    print(f"  Total pages processed: {stats.total_pages:,}")
    print(f"  Total entity mentions: {stats.total_entity_mentions:,}")
    # Fix 2: Show both global unique and per-doc sum for clarity
    print(f"  Global unique entities: {len(global_unique_entities):,}")
    print(f"  Relationships created: {stats.relationships_created:,}")

    if neo4j_stats:
        print(f"\nNeo4j stats:")
        print(f"  Total nodes: {neo4j_stats.get('node_count', 0):,}")
        print(f"  Total relationships: {neo4j_stats.get('relationship_count', 0):,}")
        print(f"  Documents: {neo4j_stats.get('document_count', 0)}")

        type_counts = neo4j_stats.get("entity_type_counts", {})
        if type_counts:
            print("  Entities by type:")
            for entity_type, count in sorted(type_counts.items()):
                print(f"    {entity_type}: {count:,}")

    if stats.errors:
        print(f"\nErrors ({len(stats.errors)}):")
        for error in stats.errors:
            print(f"  - {error}")

    return 0 if stats.documents_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
