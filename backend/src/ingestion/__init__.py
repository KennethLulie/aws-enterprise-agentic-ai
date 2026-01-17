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

Usage:
    from src.ingestion import VLMExtractor, DocumentProcessor, SemanticChunker
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
]
