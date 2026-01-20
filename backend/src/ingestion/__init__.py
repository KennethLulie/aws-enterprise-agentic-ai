"""
Data ingestion modules for document processing and extraction.

This package contains modules for ingesting and processing various
document types for the RAG pipeline:

- vlm_extractor: Vision Language Model extraction from PDF documents
  using AWS Bedrock Claude Vision.
- document_processor: High-level document processing with manifest
  tracking, consolidation, and batch processing.
- semantic_chunking: spaCy-based semantic text chunking that respects
  sentence and paragraph boundaries.
- parent_child_chunking: Hierarchical chunking strategy that creates
  large parent chunks (1024 tokens) for context and small child chunks
  (256 tokens) for precise embedding search.
- contextual_chunking: Contextual enrichment for RAG chunks using
  Anthropic's approach - prepends document-level context to improve
  retrieval accuracy.
- query_expansion: Query analysis and expansion using Nova Lite -
  generates query variants and classifies KG complexity.

Usage:
    from src.ingestion import VLMExtractor, DocumentProcessor, SemanticChunker
    from src.ingestion import ParentChildChunker, ContextualEnricher
    from src.ingestion import QueryExpander, QueryAnalysis
    from pathlib import Path

    # Low-level extraction
    extractor = VLMExtractor()
    result = await extractor.extract_document(
        pdf_path=Path("document.pdf"),
        doc_type="10k"
    )

    # High-level processing with manifest tracking
    processor = DocumentProcessor(
        raw_dir=Path("documents/raw"),
        extracted_dir=Path("documents/extracted")
    )
    results = await processor.process_all()

    # Semantic chunking for RAG indexing
    chunker = SemanticChunker(max_tokens=512, overlap_tokens=50)
    chunks = chunker.chunk_document(result["pages"])

    # Parent/child chunking for hierarchical RAG
    pc_chunker = ParentChildChunker(parent_tokens=1024, child_tokens=256)
    parents, children = pc_chunker.chunk_document("DOC_ID", result["pages"])

    # Contextual enrichment for improved retrieval
    enricher = ContextualEnricher()
    metadata = {"document_type": "10k", "company": "Apple Inc.", "ticker": "AAPL"}
    enriched_children = enricher.enrich_children(children, metadata)

    # Query expansion and KG complexity analysis
    expander = QueryExpander()
    analysis = await expander.analyze("Apple's Taiwan suppliers")
    print(analysis.variants)      # Alternative phrasings
    print(analysis.use_2hop)      # True for complex queries
"""

from src.ingestion.vlm_extractor import (
    VLMExtractor,
    VLMExtractionError,
    PDFConversionError,
    BedrockInvocationError,
    JSONParsingError,
)

from src.ingestion.document_processor import (
    DocumentProcessor,
    DocumentProcessingError,
    ManifestError,
)

from src.ingestion.semantic_chunking import (
    SemanticChunker,
    ChunkingError,
    SpaCyLoadError,
)

from src.ingestion.parent_child_chunking import (
    ParentChildChunker,
    ParentChildChunkingError,
)

from src.ingestion.contextual_chunking import (
    ContextualEnricher,
    ContextualEnrichmentError,
)

from src.ingestion.query_expansion import (
    QueryExpander,
    QueryAnalysis,
    QueryExpansionError,
    QueryAnalysisTimeoutError,
)

__all__ = [
    # VLM Extractor
    "VLMExtractor",
    "VLMExtractionError",
    "PDFConversionError",
    "BedrockInvocationError",
    "JSONParsingError",
    # Document Processor
    "DocumentProcessor",
    "DocumentProcessingError",
    "ManifestError",
    # Semantic Chunking
    "SemanticChunker",
    "ChunkingError",
    "SpaCyLoadError",
    # Parent/Child Chunking
    "ParentChildChunker",
    "ParentChildChunkingError",
    # Contextual Enrichment
    "ContextualEnricher",
    "ContextualEnrichmentError",
    # Query Expansion
    "QueryExpander",
    "QueryAnalysis",
    "QueryExpansionError",
    "QueryAnalysisTimeoutError",
]
