"""
Entity extraction module for Knowledge Graph population.

This module provides entity extraction from financial documents using spaCy NER
combined with custom financial domain patterns. Extracted entities are used to
populate the Knowledge Graph (Neo4j) for entity-based retrieval in hybrid search.

Components:
    - Entity: Dataclass representing an extracted entity with metadata
    - EntityExtractor: Main extraction class with spaCy pipeline

Architecture:
    Text → spaCy Pipeline → Entity Objects → Neo4j (via store.py)
              ↓
         EntityRuler (FINANCIAL_PATTERNS)
              ↓
         NER (en_core_web_sm)
              ↓
         Label Filtering (SPACY_TO_ENTITY_TYPE)
              ↓
         Deduplication & Normalization

Cost Efficiency:
    spaCy NER is ~95% cheaper than LLM-based extraction:
    - spaCy: ~$0.001/document (local CPU)
    - LLM: ~$0.02-0.05/document (API calls)

Usage:
    from src.knowledge_graph.extractor import EntityExtractor, Entity

    extractor = EntityExtractor()

    # Extract from text
    entities = extractor.extract_entities(
        text="NVIDIA Corporation reported $60B revenue under GAAP.",
        document_id="NVDA_10K_2024",
        page=5
    )

    # Extract from VLM extraction JSON
    entities = extractor.extract_from_document(extraction_json)

    for entity in entities:
        print(f"{entity.entity_type}: {entity.text}")

Reference:
    - ontology.py for EntityType and FINANCIAL_PATTERNS
    - spaCy docs: https://spacy.io/usage/linguistic-features#named-entities
    - backend.mdc for Python patterns
    - PHASE_2B_HOW_TO_GUIDE.md Section 3
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import spacy
import structlog
from spacy.language import Language

from src.knowledge_graph.ontology import (
    FINANCIAL_PATTERNS,
    EntityType,
    get_entity_type,
)

# Configure structured logger
logger = structlog.get_logger(__name__)

# =============================================================================
# Constants
# =============================================================================

# Default spaCy model (small English model for speed/cost)
DEFAULT_MODEL_NAME = "en_core_web_sm"

# Minimum entity text length (filter out single characters)
MIN_ENTITY_LENGTH = 2

# Maximum entity text length (filter out excessively long entities)
MAX_ENTITY_LENGTH = 100


# =============================================================================
# Custom Exceptions
# =============================================================================


class EntityExtractionError(Exception):
    """Base exception for entity extraction operations."""

    pass


class ModelLoadError(EntityExtractionError):
    """Raised when spaCy model fails to load."""

    pass


# =============================================================================
# Entity Dataclass
# =============================================================================


@dataclass
class Entity:
    """
    Represents an extracted entity from document text.

    This dataclass stores all metadata about an extracted entity including
    its text, type, position in the source text, and provenance information.

    Attributes:
        text: The extracted entity text (normalized)
        entity_type: The EntityType enum value
        start_char: Starting character position in source text
        end_char: Ending character position in source text
        confidence: Extraction confidence score (0.0-1.0, from spaCy if available)
        source_document_id: ID of the source document (for graph relationships)
        source_page: Page number where entity was found (for citations)
        mention_count: Number of times this entity appears (for deduplication)
        raw_text: Original text before normalization (for debugging)

    Example:
        >>> entity = Entity(
        ...     text="NVIDIA Corporation",
        ...     entity_type=EntityType.ORGANIZATION,
        ...     start_char=0,
        ...     end_char=18,
        ...     confidence=0.95,
        ...     source_document_id="NVDA_10K_2024",
        ...     source_page=5
        ... )
    """

    text: str
    entity_type: EntityType
    start_char: int
    end_char: int
    confidence: float = 1.0
    source_document_id: str | None = None
    source_page: int | None = None
    mention_count: int = 1
    raw_text: str = field(default="", repr=False)

    def __post_init__(self) -> None:
        """Store raw text if not provided."""
        if not self.raw_text:
            self.raw_text = self.text


# =============================================================================
# Entity Extractor
# =============================================================================


class EntityExtractor:
    """
    Extracts entities from text using spaCy NER with financial domain patterns.

    This class loads a spaCy model, adds custom EntityRuler patterns for
    financial domain entities, and provides methods to extract entities from
    text or full document extractions.

    The extraction pipeline:
    1. Load spaCy model (en_core_web_sm by default)
    2. Add EntityRuler with FINANCIAL_PATTERNS before NER
    3. Process text through pipeline
    4. Filter entities by SPACY_TO_ENTITY_TYPE
    5. Normalize and deduplicate entities
    6. Return list of Entity objects

    Attributes:
        model_name: Name of the spaCy model to use
        _nlp: Loaded spaCy Language pipeline (lazy-loaded)

    Example:
        >>> extractor = EntityExtractor()
        >>> entities = extractor.extract_entities(
        ...     "Apple Inc. reported $394 billion revenue.",
        ...     document_id="AAPL_10K_2024"
        ... )
        >>> for e in entities:
        ...     print(f"{e.entity_type}: {e.text}")
        ORGANIZATION: Apple Inc.
        MONEY: $394 billion
    """

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME) -> None:
        """
        Initialize the entity extractor.

        Args:
            model_name: Name of the spaCy model to load.
                       Default is "en_core_web_sm" for speed/cost.
        """
        self.model_name = model_name
        self._nlp: Language | None = None

    @property
    def nlp(self) -> Language:
        """
        Lazy-load and return the spaCy pipeline.

        The model is loaded once on first access and reused for all
        subsequent extractions.

        Returns:
            The configured spaCy Language pipeline.

        Raises:
            ModelLoadError: If the spaCy model fails to load.
        """
        if self._nlp is None:
            self._nlp = self._load_model()
        return self._nlp

    def _load_model(self) -> Language:
        """
        Load the spaCy model and configure the pipeline.

        This method:
        1. Loads the spaCy model
        2. Adds EntityRuler with FINANCIAL_PATTERNS before NER
        3. Disables unused pipeline components for speed

        Returns:
            Configured spaCy Language pipeline.

        Raises:
            ModelLoadError: If the model cannot be loaded.
        """
        try:
            logger.info(
                "loading_spacy_model",
                model_name=self.model_name,
            )

            # Load the model
            nlp = spacy.load(self.model_name)

            # Add financial patterns via EntityRuler (before NER for priority)
            self._add_financial_patterns(nlp)

            # Disable components we don't need for speed
            # Keep: tok2vec, ner, entity_ruler
            # Disable: tagger, parser, lemmatizer, attribute_ruler
            disabled = []
            for pipe_name in ["tagger", "parser", "lemmatizer", "attribute_ruler"]:
                if pipe_name in nlp.pipe_names:
                    nlp.disable_pipe(pipe_name)
                    disabled.append(pipe_name)

            logger.info(
                "spacy_model_loaded",
                model_name=self.model_name,
                pipeline=nlp.pipe_names,
                disabled=disabled,
                pattern_count=len(FINANCIAL_PATTERNS),
            )

            return nlp

        except OSError as e:
            logger.error(
                "spacy_model_load_failed",
                model_name=self.model_name,
                error=str(e),
            )
            raise ModelLoadError(
                f"Failed to load spaCy model '{self.model_name}'. "
                f"Run: python -m spacy download {self.model_name}"
            ) from e

    def _add_financial_patterns(self, nlp: Language) -> None:
        """
        Add financial domain patterns to the spaCy pipeline.

        Adds an EntityRuler component with FINANCIAL_PATTERNS from ontology.py.
        The ruler is placed BEFORE the NER component so custom patterns take
        priority over statistical NER predictions.

        Args:
            nlp: The spaCy Language pipeline to modify.
        """
        # Add EntityRuler before NER for pattern priority
        # Type ignore needed because add_pipe returns generic Callable, not EntityRuler
        ruler = nlp.add_pipe("entity_ruler", before="ner")
        ruler.add_patterns(FINANCIAL_PATTERNS)  # type: ignore[attr-defined]

        logger.debug(
            "financial_patterns_added",
            pattern_count=len(FINANCIAL_PATTERNS),
        )

    def extract_entities(
        self,
        text: str,
        document_id: str | None = None,
        page: int | None = None,
    ) -> list[Entity]:
        """
        Extract entities from text.

        This is the main extraction method. It processes text through the
        spaCy pipeline, filters by known entity types, normalizes text,
        and deduplicates entities.

        Args:
            text: The text to extract entities from.
            document_id: Optional document ID for provenance tracking.
            page: Optional page number for provenance tracking.

        Returns:
            List of Entity objects, deduplicated and normalized.

        Example:
            >>> extractor = EntityExtractor()
            >>> entities = extractor.extract_entities(
            ...     "The SEC requires GAAP compliance.",
            ...     document_id="DOC_001",
            ...     page=1
            ... )
        """
        if not text or not text.strip():
            return []

        # Process text through spaCy pipeline
        doc = self.nlp(text)

        # Extract entities with type filtering
        raw_entities: list[Entity] = []

        for ent in doc.ents:
            # Get our entity type for this spaCy label
            entity_type = get_entity_type(ent.label_)

            if entity_type is None:
                # Skip entities with unmapped labels
                continue

            # Filter by length
            entity_text = ent.text.strip()
            if len(entity_text) < MIN_ENTITY_LENGTH:
                continue
            if len(entity_text) > MAX_ENTITY_LENGTH:
                continue

            # Create Entity object
            entity = Entity(
                text=self._normalize_text(entity_text, entity_type),
                entity_type=entity_type,
                start_char=ent.start_char,
                end_char=ent.end_char,
                confidence=1.0,  # spaCy doesn't provide confidence for NER
                source_document_id=document_id,
                source_page=page,
                raw_text=entity_text,
            )

            raw_entities.append(entity)

        # Deduplicate entities
        deduplicated = self._deduplicate_entities(raw_entities)

        logger.debug(
            "entities_extracted",
            document_id=document_id,
            page=page,
            raw_count=len(raw_entities),
            deduplicated_count=len(deduplicated),
        )

        return deduplicated

    def extract_from_document(
        self,
        extraction_json: dict[str, Any],
    ) -> list[Entity]:
        """
        Extract entities from a VLM extraction JSON (for aggregate statistics).

        This method processes the output of the VLM document extraction
        pipeline (from Phase 2a). It extracts entities from each page's
        text and aggregates them with deduplication across all pages.

        ⚠️ Important: This method deduplicates across ALL pages, keeping only
        the FIRST occurrence's source_page. Use this for:
        - Getting aggregate entity statistics for a document
        - Counting unique entities across a document
        - Quick document-level entity overview

        For Neo4j indexing with per-page MENTIONS relationships, use
        `extract_entities()` per page instead to preserve page information:

            for page in extraction_json["pages"]:
                entities = extractor.extract_entities(
                    text=page["text"],
                    document_id=extraction_json["document_id"],
                    page=page["page_number"]
                )
                # Store entities with correct page info

        Args:
            extraction_json: The VLM extraction output dictionary with structure:
                {
                    "document_id": "NVDA_10K_2024",
                    "pages": [
                        {"page_number": 1, "text": "..."},
                        {"page_number": 2, "text": "..."},
                        ...
                    ]
                }

        Returns:
            List of Entity objects from all pages, deduplicated by text.
            Each entity's source_page reflects FIRST occurrence only.
            Use mention_count to see total occurrences across pages.

        Example:
            >>> with open("documents/extracted/NVDA_10K_2024.json") as f:
            ...     extraction = json.load(f)
            >>> entities = extractor.extract_from_document(extraction)
            >>> print(f"Document has {len(entities)} unique entities")
        """
        document_id = extraction_json.get("document_id")
        pages = extraction_json.get("pages", [])

        if not pages:
            logger.warning(
                "no_pages_in_extraction",
                document_id=document_id,
            )
            return []

        all_entities: list[Entity] = []

        for page_data in pages:
            page_number = page_data.get("page_number")
            text = page_data.get("text", "")

            if not text:
                continue

            page_entities = self.extract_entities(
                text=text,
                document_id=document_id,
                page=page_number,
            )

            all_entities.extend(page_entities)

        # Deduplicate across all pages
        deduplicated = self._deduplicate_entities(all_entities)

        logger.info(
            "document_entities_extracted",
            document_id=document_id,
            page_count=len(pages),
            raw_count=len(all_entities),
            deduplicated_count=len(deduplicated),
        )

        return deduplicated

    def _normalize_text(self, text: str, entity_type: EntityType) -> str:
        """
        Normalize entity text for consistent storage.

        Normalization rules:
        - Strip leading/trailing whitespace
        - For acronyms (all caps, 2-5 chars): keep uppercase
        - For names (PERSON, ORGANIZATION): title case
        - For everything else: preserve original

        Args:
            text: The raw entity text.
            entity_type: The entity type (affects normalization).

        Returns:
            Normalized entity text.
        """
        text = text.strip()

        # Collapse internal whitespace
        text = re.sub(r"\s+", " ", text)

        # Detect acronyms: all uppercase, 2-5 characters, letters only
        if re.match(r"^[A-Z]{2,5}$", text):
            return text.upper()

        # Detect acronyms with special characters (P/E, D/E, EV/EBITDA)
        if re.match(r"^[A-Z/]{2,10}$", text):
            return text.upper()

        # Names get title case (but preserve acronyms in names)
        if entity_type in (EntityType.PERSON, EntityType.ORGANIZATION):
            # Don't title-case if it contains common acronyms
            if any(
                acr in text.upper()
                for acr in ["LLC", "INC", "CORP", "LTD", "PLC", "CEO", "CFO", "CTO"]
            ):
                return text  # Preserve original casing
            # Check if already properly cased
            if text[0].isupper():
                return text
            return text.title()

        # Everything else: preserve original
        return text

    def _deduplicate_entities(self, entities: list[Entity]) -> list[Entity]:
        """
        Deduplicate entities by normalized text.

        Deduplication strategy:
        - Group entities by lowercase normalized text
        - Keep the entity with highest confidence
        - Aggregate mention count
        - Keep first occurrence's position

        Args:
            entities: List of entities to deduplicate.

        Returns:
            Deduplicated list of entities.
        """
        if not entities:
            return []

        # Group by normalized text (case-insensitive)
        seen: dict[str, Entity] = {}

        for entity in entities:
            key = entity.text.lower()

            if key not in seen:
                seen[key] = entity
            else:
                # Update mention count
                existing = seen[key]
                existing.mention_count += 1

                # Keep higher confidence
                if entity.confidence > existing.confidence:
                    # Preserve mention count from existing
                    entity.mention_count = existing.mention_count
                    seen[key] = entity

        return list(seen.values())


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    "Entity",
    "EntityExtractor",
    "EntityExtractionError",
    "ModelLoadError",
]
