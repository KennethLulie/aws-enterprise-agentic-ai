# RAG Improvements Delta Document

> **Purpose:** This document captures all changes needed to implement advanced chunking strategies for the news impact analysis use case. It serves as a comprehensive delta against the existing Phase 2A and 2B how-to guides.
>
> **Status:** Planning document - changes not yet implemented
>
> **Created:** 2026-01-17

---

## Table of Contents

- [Executive Summary](#executive-summary)
- [Current State Assessment](#current-state-assessment)
- [Document Metadata Flow](#document-metadata-flow)
- [Priority 1: Parent/Child Chunking](#priority-1-parentchild-chunking)
- [Priority 2: Section-Aware Boundaries](#priority-2-section-aware-boundaries)
- [Priority 3: Enhanced Contextual Prefix](#priority-3-enhanced-contextual-prefix)
- [Priority 4: Smaller Child Chunks (256 tokens)](#priority-4-smaller-child-chunks-256-tokens)
- [Edge Cases and Error Handling](#edge-cases-and-error-handling)
- [Implementation Order](#implementation-order)
- [Pinecone Schema Changes](#pinecone-schema-changes)
- [Testing Strategy](#testing-strategy)
- [Rollback Strategy](#rollback-strategy)

---

## Executive Summary

### Goal

Enable sophisticated news impact analysis by improving RAG retrieval quality through:
1. **Parent/child chunking** - Retrieve small chunks, return large context
2. **Section-aware boundaries** - Never split across 10-K sections
3. **Enhanced contextual prefix** - Richer metadata in embedded text
4. **Smaller retrieval chunks** - 256 tokens for precision matching

### Why These Changes Matter for News Impact Analysis

| Challenge | Current Limitation | Solution |
|-----------|-------------------|----------|
| News mentions specific risk | 512-token chunks may include unrelated content | 256-token children for precise matching |
| Need full context for analysis | Retrieved chunk lacks surrounding context | Parent chunks (1024 tokens) returned |
| Cross-section retrieval noise | Chunks span Item 1 → Item 1A boundaries | Section-aware splitting |
| Disambiguation in search | Generic chunks lack document context | Enhanced contextual prefix |

### Complexity and Cost Assessment

| Priority | Complexity | Cost Impact | Implementation Time |
|----------|------------|-------------|---------------------|
| 1. Parent/Child | Medium | +~20% storage (parent text in metadata) | 2-3 hours |
| 2. Section-Aware | Low | $0 | 1 hour |
| 3. Enhanced Prefix | Low | $0 | 30 minutes |
| 4. Smaller Chunks | Low | +~50% more vectors | 30 minutes |

**Total estimated additional Pinecone storage:** ~2x current (more chunks + parent text in metadata)

---

## Current State Assessment

### Implemented Components

| Component | File | Status | Notes |
|-----------|------|--------|-------|
| Semantic Chunking | `backend/src/ingestion/semantic_chunking.py` | ✅ Complete | 512 tokens, 50 overlap |
| VLM Extraction | `backend/src/ingestion/vlm_extractor.py` | ✅ Complete | Extracts `section` per page |
| Embeddings | `backend/src/utils/embeddings.py` | ✅ Complete | Titan 1536 dimensions |
| Document Processor | `backend/src/ingestion/document_processor.py` | ✅ Complete | Orchestrates extraction |

### Planned but NOT Implemented

| Component | Planned Location | Phase 2A Section | Status |
|-----------|------------------|------------------|--------|
| Contextual Enrichment | `backend/src/ingestion/contextual_chunking.py` | Section 8.3 | ❌ Not created |
| Pinecone Client | `backend/src/utils/pinecone_client.py` | Section 9.1 | ❌ Not created |
| Indexing Pipeline | `scripts/extract_and_index.py` (update) | Section 9.3 | ❌ Missing indexing step |
| Real RAG Tool | `backend/src/agent/tools/rag.py` (update) | Section 10.1 | ❌ Still stub |

### NOT in Any Guide (New Additions)

| Component | Proposed Location | Notes |
|-----------|-------------------|-------|
| Parent/Child Chunking | `backend/src/ingestion/parent_child_chunking.py` | **NEW FILE** |
| Section boundary detection | Modify `semantic_chunking.py` | **MODIFY EXISTING** |

---

## Document Metadata Flow

### Where Metadata Comes From

Understanding the metadata flow is critical for implementing these changes. The pipeline already extracts and stores document metadata.

```
┌─────────────────────────────────────────────────────────────────┐
│                    PDF Document                                  │
│                 AAPL_10K_2024.pdf                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              VLM Extraction (vlm_extractor.py)                   │
│  Extracts per-page:                                             │
│  - section: "Item 1A: Risk Factors"                             │
│  - text: page content                                           │
│  - financial_metrics: { fiscal_year: 2024 }                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│           Document Processor (document_processor.py)             │
│  Consolidates and adds:                                         │
│  - document_id: "AAPL_10K_2024" (from filename)                 │
│  - ticker: "AAPL" (regex from filename)                         │
│  - company: "Apple Inc." (from page content)                    │
│  - fiscal_year: 2024 (from financial_metrics)                   │
│  - total_pages: 127                                             │
│  - document_type: "10k" | "reference"                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│               Extracted JSON File                                │
│          documents/extracted/AAPL_10K_2024.json                 │
│                                                                  │
│  {                                                               │
│    "document_id": "AAPL_10K_2024",                              │
│    "document_type": "10k",                                       │
│    "total_pages": 127,                                           │
│    "metadata": {                                                 │
│      "ticker": "AAPL",                                          │
│      "company": "Apple Inc.",                                    │
│      "fiscal_year": 2024                                        │
│    },                                                            │
│    "pages": [ ... ]                                             │
│  }                                                               │
└─────────────────────────────────────────────────────────────────┘
```

### Metadata Available for Chunking

| Field | Source | Available In |
|-------|--------|--------------|
| `document_id` | Filename parsing | `result["document_id"]` |
| `document_type` | Filename pattern | `result["document_type"]` |
| `ticker` | Filename regex `^([A-Z]{1,5})_` | `result["metadata"]["ticker"]` |
| `company` | Page content extraction | `result["metadata"]["company"]` |
| `fiscal_year` | Financial metrics | `result["metadata"]["fiscal_year"]` |
| `total_pages` | VLM extraction | `result["total_pages"]` |
| `section` | Per-page VLM extraction | `page["section"]` |
| `page_number` | VLM extraction | `page["page_number"]` |

### Reference Document Metadata

| Field | Source | Available In |
|-------|--------|--------------|
| `headline` | First page content | `result["metadata"]["headline"]` |
| `publication_date` | First page content | `result["metadata"]["publication_date"]` |
| `source_type` | Filename pattern | Derived from filename |
| `source_name` | Filename or content | Derived from filename |

### Key Implication for Implementation

The indexing pipeline (`extract_and_index.py`) must:
1. Load the extracted JSON file
2. Pass `result["metadata"]` to the chunking/enrichment modules
3. Use `result["document_id"]` for generating parent/child IDs

---

## Priority 1: Parent/Child Chunking

### What It Is

Parent/child chunking stores documents at two granularities:
- **Child chunks (256 tokens):** Small, precise chunks used for embedding and retrieval
- **Parent chunks (1024 tokens):** Larger context chunks returned in search results

The child chunk is what gets embedded and matched; the parent chunk is what the LLM receives for context.

### Why It Matters for News Impact Analysis

When a news article mentions "supply chain risks in China," the RAG system needs to:
1. **Find the exact mention** (precise 256-token child matches "supply chain" + "China")
2. **Return full context** (1024-token parent includes surrounding risk factors)

Without parent/child:
- 512-token chunks are too large for precise matching
- 512-token chunks are too small for full context
- No way to get both precision AND context

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Original Document                            │
│  [Item 1A: Risk Factors - Pages 15-25]                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Parent Chunks (1024 tokens)                   │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐            │
│  │  Parent P1   │ │  Parent P2   │ │  Parent P3   │  ...       │
│  │ (pages 15-16)│ │ (pages 16-17)│ │ (pages 17-18)│            │
│  │  1024 tokens │ │  1024 tokens │ │  1024 tokens │            │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘            │
│         │                │                │                     │
└─────────┼────────────────┼────────────────┼─────────────────────┘
          │                │                │
          ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Child Chunks (256 tokens)                     │
│  ┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐  │
│  │Child C1││Child C2││Child C3││Child C4││Child C5││Child C6│  │
│  │parent: ││parent: ││parent: ││parent: ││parent: ││parent: │  │
│  │  P1    ││  P1    ││  P1    ││  P2    ││  P2    ││  P2    │  │
│  └────────┘└────────┘└────────┘└────────┘└────────┘└────────┘  │
│      │         │         │         │         │         │        │
│      ▼         ▼         ▼         ▼         ▼         ▼        │
│  [Embed]   [Embed]   [Embed]   [Embed]   [Embed]   [Embed]     │
│      │         │         │         │         │         │        │
│      ▼         ▼         ▼         ▼         ▼         ▼        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Pinecone Index                        │   │
│  │  - Child vectors (1536 dims)                            │   │
│  │  - parent_id in metadata                                │   │
│  │  - parent_text in metadata (for retrieval)              │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### File Changes

#### NEW FILE: `backend/src/ingestion/parent_child_chunking.py`

**Location in Guide:** This is a NEW addition - not currently in Phase 2A or 2B.

**Insert after:** Phase 2A Section 8.2 (Semantic Chunking)

**Upstream Dependencies:**
- Requires `semantic_chunking.py` for sentence boundary detection
- Requires section information from VLM extraction

**Downstream Dependencies:**
- `extract_and_index.py` must call this instead of raw semantic chunking
- `pinecone_client.py` must store parent_text in metadata
- `rag.py` must return parent_text instead of child text

**Requirements:**

```
Create `backend/src/ingestion/parent_child_chunking.py`

Requirements:
1. Module docstring explaining parent/child chunking strategy
2. Custom exceptions: ParentChildChunkingError
3. Constants section with defaults

4. ParentChildChunker class with:
   - __init__(self, parent_tokens: int = 1024, child_tokens: int = 256, overlap_tokens: int = 50)
   - chunk_document(self, document_id: str, pages: list[dict]) -> tuple[list[dict], list[dict]]
   - _create_parent_chunks(self, document_id: str, pages: list[dict]) -> list[dict]
   - _create_children_from_parent(self, parent: dict) -> list[dict]
   - _count_tokens(self, text: str) -> int  # Use same formula as semantic_chunking: words * 1.3

5. Parent chunk format:
   {
     "parent_id": "AAPL_10K_2024_parent_0",
     "document_id": "AAPL_10K_2024",
     "text": "The full 1024-token parent text...",
     "token_count": 1024,
     "start_page": 15,
     "end_page": 16,
     "section": "Item 1A: Risk Factors",
     "parent_index": 0
   }

6. Child chunk format:
   {
     "child_id": "AAPL_10K_2024_parent_0_child_0",
     "parent_id": "AAPL_10K_2024_parent_0",
     "document_id": "AAPL_10K_2024",
     "text": "The 256-token child text...",
     "token_count": 256,
     "start_page": 15,
     "end_page": 15,
     "section": "Item 1A: Risk Factors",
     "child_index": 0,
     "child_index_in_document": 5  # Global index across all children
   }

7. Use SemanticChunker internally for sentence boundary detection
8. Never split parent chunks across section boundaries (delegate to semantic_chunking.py)
9. Children inherit section from parent
10. Children do NOT have overlap across parent boundaries (only within same parent)

Key Features:
- Synchronous methods (no I/O, pure computation)
- Parents are non-overlapping (no redundant storage)
- Children have 50-token overlap WITHIN same parent only
- Parent text stored for retrieval (not re-embedded)
- Section-aware parent boundaries (see Priority 2)
- Use structlog for logging
- Include __all__ exports: ["ParentChildChunker", "ParentChildChunkingError"]

Token Counting (IMPORTANT - must match semantic_chunking.py):
```python
def _count_tokens(self, text: str) -> int:
    """Use same formula as SemanticChunker: words * 1.3"""
    if not text:
        return 0
    words = len(text.split())
    return max(1, int(words * 1.3))
```

Reference:
- [backend.mdc] for Python patterns
- semantic_chunking.py for sentence boundary logic and token counting
- LangChain ParentDocumentRetriever concept

Verify: docker-compose exec backend python -c "from src.ingestion.parent_child_chunking import ParentChildChunker; print('OK')"
```

#### MODIFY: `backend/src/utils/pinecone_client.py`

**Location in Guide:** Phase 2A Section 9.1 (not yet implemented)

**Change Type:** Add parent storage support to planned implementation

**Additional Requirements to Add:**

```
Additional requirements for pinecone_client.py (Priority 1):

1. Store parent_text in child vector metadata:
   {
     "id": "AAPL_10K_2024_parent_0_child_0",
     "values": [0.1, 0.2, ...],  # Child embedding
     "metadata": {
       "document_id": "AAPL_10K_2024",
       "parent_id": "AAPL_10K_2024_parent_0",
       "parent_text": "The full 1024-token parent text...",  # NEW
       "child_text": "The 256-token child text...",
       "document_type": "10k",
       "section": "Item 1A: Risk Factors",
       "page_number": 15,
       ...
     }
   }

2. Query returns parent_text, not child_text:
   def query(...) -> list[dict]:
       # Returns parent_text for LLM context
       # Returns child_text for debugging/citation

3. Metadata size consideration:
   - Pinecone metadata limit: 40KB per vector
   - 1024 tokens ≈ 4KB text (well under limit)
   - Include both parent_text and child_text
```

#### MODIFY: `backend/src/agent/tools/rag.py`

**Location in Guide:** Phase 2A Section 10.1 (currently stub)

**Change Type:** Update planned implementation to use parent retrieval

**Additional Requirements to Add:**

```
Additional requirements for rag.py (Priority 1):

1. Response format uses parent_text:
   "Found {n} relevant passages:

   [1] Source: Apple 10-K 2024, Item 1A: Risk Factors, Page 15
   {parent_text - the full 1024-token context}

   [2] Source: ..."

2. Deduplicate by parent_id (ALGORITHM):
   ```python
   def deduplicate_by_parent(results: list[dict]) -> list[dict]:
       """
       Multiple children may match from same parent.
       Return unique parents, ranked by best child match score.
       """
       parent_best: dict[str, dict] = {}
       
       for result in results:
           parent_id = result["metadata"]["parent_id"]
           score = result["score"]
           
           if parent_id not in parent_best or score > parent_best[parent_id]["score"]:
               parent_best[parent_id] = result
       
       # Sort by best score descending
       unique_parents = sorted(
           parent_best.values(),
           key=lambda x: x["score"],
           reverse=True
       )
       return unique_parents
   ```

3. Citation includes child match location:
   - Show which part of parent matched (for transparency)
   - Include child_text_raw in citation (not the enriched version)
   - Format: "Matched: {first 100 chars of child_text_raw}..."

4. Handle case where parent_text is missing (backwards compatibility):
   - If no parent_text in metadata, fall back to child_text
   - Log warning for debugging
```

---

## Priority 2: Section-Aware Boundaries

### What It Is

Modify the chunking algorithm to detect 10-K section boundaries and never create chunks that span multiple sections.

### Why It Matters for News Impact Analysis

10-K sections have distinct purposes:
- **Item 1:** Business description
- **Item 1A:** Risk factors (most relevant for news analysis)
- **Item 7:** MD&A (management discussion)
- **Item 8:** Financial statements

A chunk spanning Item 1 → Item 1A mixes business description with risk factors, reducing retrieval precision.

### File Changes

#### MODIFY: `backend/src/ingestion/semantic_chunking.py`

**Location in Guide:** Phase 2A Section 8.2 (already implemented)

**Change Type:** UPDATE existing implementation

**Upstream Dependencies:**
- VLM extraction already provides `section` per page
- No new dependencies needed

**Downstream Dependencies:**
- `parent_child_chunking.py` uses this for parent boundary detection
- No changes needed to downstream consumers

**Specific Changes:**

```
Update `backend/src/ingestion/semantic_chunking.py`

Changes:
1. Add section boundary detection in chunk_document():
   - Track current_section from page metadata
   - When section changes, force new chunk (even if under max_tokens)
   - Log section transitions for debugging

2. Add method: _is_section_boundary(prev_section: str, curr_section: str) -> bool
   - Returns True if sections differ
   - Handle None sections gracefully

3. Update _build_chunk_dict() to always include section in output

Code location to modify:
- chunk_document() method, around line 514-543
- Add section boundary check before adding sentence to chunk

Example logic:
```python
def _is_section_boundary(self, prev_section: str | None, curr_section: str | None) -> bool:
    """
    Detect section boundary, handling None gracefully.
    See Edge Cases section for full logic.
    """
    if prev_section is None and curr_section is None:
        return False
    if prev_section is None or curr_section is None:
        return True
    return prev_section != curr_section

# In chunk_document() loop:
for sentence_data in all_sentences:
    sent_text, page_num, section = sentence_data
    
    # NEW: Check for section boundary BEFORE adding sentence
    if current_chunk_sentences:
        prev_section = current_chunk_sentences[-1][2]
        if self._is_section_boundary(prev_section, section):
            # Force finalize current chunk WITHOUT overlap
            # (overlap would pollute the new section with old section content)
            chunk_dict = self._build_chunk_dict(current_chunk_sentences, chunk_index)
            all_chunks.append(chunk_dict)
            chunk_index += 1
            
            # Start fresh - NO overlap across section boundaries
            current_chunk_sentences = []
            current_tokens = 0
            
            self._log.debug(
                "section_boundary_detected",
                from_section=prev_section,
                to_section=section,
                chunk_index=chunk_index
            )
    
    # Check if adding this sentence exceeds max_tokens
    # (existing logic continues...)
```

Verify: Test that chunks from Item 1A don't include Item 1 content
```

### 10-K Section Patterns to Detect

> **IMPORTANT:** The VLM extraction already produces normalized section names like `"Item 1: Business"` and `"Item 1A: Risk Factors"` in the `page["section"]` field. The section boundary detection compares these **string values directly** - no regex pattern matching is needed at chunking time.
>
> The `_is_section_boundary()` function simply checks `prev_section != curr_section`.

**Reference: Section values in extracted data (from NVDA_10K_2025.json):**

| Section Field Value | Description |
|---------------------|-------------|
| `"Cover Page"` | SEC cover page |
| `"Table of Contents"` | TOC page |
| `"Item 1: Business"` | Business description |
| `"Item 1A: Risk Factors"` | Risk factors section |
| `"Item 1B: Unresolved Staff Comments"` | Staff comments |
| `"Item 1C: Cybersecurity"` | Cybersecurity (newer filings) |
| `"Item 2: Properties"` | Properties |
| `"Item 3: Legal Proceedings"` | Legal proceedings |
| `"Item 7: Management's Discussion..."` | MD&A |
| `"Item 7A: Quantitative..."` | Market risk disclosures |
| `"Item 8: Financial Statements..."` | Financial statements |

**Key Point:** Section boundary detection is a simple string comparison, not pattern matching. The VLM has already normalized the section names.

---

## Priority 3: Enhanced Contextual Prefix

### What It Is

Improve the contextual prefix prepended to chunks before embedding to include richer metadata for better retrieval disambiguation.

### Current Plan (Phase 2A Section 8.3)

```
[Document: Apple 10-K 2024] [Section: Item 1A: Risk Factors] [Page: 15]

The Company's business, reputation, results of operations...
```

### Enhanced Format

```
[10-K Filing] [Apple Inc. (AAPL)] [FY2024] [Item 1A: Risk Factors] [Page 15 of 127]

The Company's business, reputation, results of operations...
```

### Why This Matters for News Impact Analysis

| Field | Why It Helps |
|-------|--------------|
| Document type | Distinguishes 10-K from news articles |
| Company + Ticker | Enables "AAPL risks" queries to match |
| Fiscal year | Temporal disambiguation (FY2024 vs FY2023) |
| Section name | Disambiguates risk factors from business description |
| Page X of Y | Indicates document position (early = overview, late = details) |

### File Changes

#### CREATE: `backend/src/ingestion/contextual_chunking.py`

**Location in Guide:** Phase 2A Section 8.3 (planned but not implemented)

**Change Type:** CREATE with enhanced format

**Upstream Dependencies:**
- Requires document metadata from VLM extraction
- Requires chunk data from parent_child_chunking.py

**Downstream Dependencies:**
- Called by extract_and_index.py before embedding
- Child chunks get enriched; parent chunks stored as-is

**Updated Requirements:**

```
Create `backend/src/ingestion/contextual_chunking.py`

Requirements:
1. Module docstring explaining contextual retrieval approach
2. Custom exceptions: ContextualEnrichmentError
3. Constants section with prefix templates

4. ContextualEnricher class with:
   - __init__(self)
   - enrich_chunk(self, chunk: dict, document_metadata: dict) -> dict
   - enrich_children(self, children: list[dict], document_metadata: dict) -> list[dict]
   - _get_prefix_10k(self, chunk: dict, metadata: dict) -> str
   - _get_prefix_reference(self, chunk: dict, metadata: dict) -> str
   - _count_tokens(self, text: str) -> int  # Same formula as semantic_chunking

5. Enhanced prefix format for 10-K documents:
   "[10-K Filing] [{company_name} ({ticker})] [FY{fiscal_year}] [{section}] [Page {page} of {total_pages}]

   {chunk_text}"

6. Enhanced prefix format for news/reference documents:
   "[{source_type}] [{source_name}] [{publication_date}] [{headline}]

   {chunk_text}"

7. Document metadata fields required (with fallbacks for missing):
   - document_type: "10k" | "reference" (REQUIRED)
   - company: "Apple Inc." (10-K only, fallback: "Unknown Company")
   - ticker: "AAPL" (10-K only, fallback: "N/A")
   - fiscal_year: 2024 (10-K only, fallback: "N/A")
   - total_pages: 127 (fallback: "?")
   - source_type: "news" | "research" | "policy" (reference only)
   - source_name: "Reuters" (reference only, fallback: "Unknown Source")
   - publication_date: "2025-01-10" (reference only)
   - headline: "Apple reports..." (reference only)

8. Apply enrichment to CHILD chunks only (parents stored as-is)

9. Update token_count after enrichment (prefix adds ~20-30 tokens)

10. Return enriched chunk with both:
    - "text": enriched text with prefix (for embedding)
    - "text_raw": original text without prefix (for citation display)

Key Features:
- Synchronous methods (no I/O)
- Type-specific prefix formats
- Graceful fallbacks for missing metadata (log warning, don't fail)
- Include ticker for query matching
- Include fiscal year for temporal queries
- Prefix tokens counted in chunk budget
- Use structlog for logging
- Include __all__ exports: ["ContextualEnricher", "ContextualEnrichmentError"]

Reference:
- Anthropic Contextual Retrieval: https://www.anthropic.com/news/contextual-retrieval
- [backend.mdc] for Python patterns
- See Edge Cases section for missing metadata handling

Verify: docker-compose exec backend python -c "from src.ingestion.contextual_chunking import ContextualEnricher; print('OK')"
```

---

## Priority 4: Smaller Child Chunks (256 tokens)

### What It Is

Reduce child chunk size from the current 512 tokens to 256 tokens for more precise retrieval matching.

### Why It Matters for News Impact Analysis

| Chunk Size | Precision | Recall | Use Case |
|------------|-----------|--------|----------|
| 512 tokens | Medium | High | General Q&A |
| 256 tokens | High | Medium | Precise matching (news analysis) |
| 128 tokens | Very High | Low | Fact extraction |

For news impact analysis, precision matters more than recall because:
1. News mentions specific topics (e.g., "China tariffs")
2. We need to find the exact risk factor that matches
3. Parent chunks provide recall (1024 tokens of context)

### File Changes

#### MODIFY: `backend/src/ingestion/parent_child_chunking.py`

**Location in Guide:** New file from Priority 1

**Change Type:** Configure with 256-token children

**Configuration:**

```
Default configuration for ParentChildChunker:

parent_tokens = 1024  # Large context for response
child_tokens = 256    # Small chunks for precise retrieval (changed from 512)
overlap_tokens = 50   # Continuity between children

Rationale:
- 256 tokens ≈ 3-4 sentences
- Precise enough to match specific risk mentions
- Parent provides full context (4x child size)
- 50-token overlap maintains continuity
```

#### MODIFY: `backend/src/ingestion/semantic_chunking.py`

**Location in Guide:** Phase 2A Section 8.2

**Change Type:** UPDATE defaults

**Changes:**

```
Update `backend/src/ingestion/semantic_chunking.py`

Changes:
1. Update DEFAULT_MAX_TOKENS constant:
   - Old: DEFAULT_MAX_TOKENS = 512
   - New: DEFAULT_MAX_TOKENS = 256

2. Keep DEFAULT_OVERLAP_TOKENS = 50 (unchanged)

3. Add docstring note explaining the change:
   "256 tokens provides higher precision for news impact analysis.
    Parent/child chunking provides larger context via parent_text."

Note: This only affects new indexing runs. Re-indexing required for existing documents.
```

---

## Edge Cases and Error Handling

### Edge Case 0: Reference Documents Have No Section Field

**Scenario:** Reference documents (news articles, research reports) do NOT have `section` metadata - only 10-K documents do.

**Evidence from extracted data:**
- 10-K: `page["section"] = "Item 1A: Risk Factors"`
- Reference: `page["section"]` does not exist (or is `None`)

**Handling:**
- Section boundary detection only applies to 10-K documents
- For reference documents, chunks flow normally without section breaks
- The `_is_section_boundary()` function handles `None` gracefully (see Edge Case 1)

**This is intentional:** Reference documents (news, research) don't have formal sections like SEC filings, so we chunk them continuously without forced section breaks.

---

### Edge Case 1: Section is None

**Scenario:** Some pages may not have section metadata (e.g., cover page, table of contents, or ALL pages in reference documents).

**Handling:**
```python
def _is_section_boundary(self, prev_section: str | None, curr_section: str | None) -> bool:
    """
    Detect section boundary, handling None gracefully.
    
    Rules:
    - None -> None: Not a boundary (both unknown)
    - None -> "Item 1A": IS a boundary (entering known section)
    - "Item 1A" -> None: IS a boundary (leaving known section)
    - "Item 1A" -> "Item 1A": Not a boundary (same section)
    - "Item 1A" -> "Item 7": IS a boundary (different sections)
    """
    if prev_section is None and curr_section is None:
        return False
    if prev_section is None or curr_section is None:
        return True  # Transitioning to/from known section
    return prev_section != curr_section
```

### Edge Case 2: Parent Smaller Than Child Tokens

**Scenario:** A section has very little text (e.g., "Item 6. [Reserved]" is often empty or one sentence).

**Handling:**
```python
# In _create_children_from_parent()
if parent["token_count"] <= self.child_tokens:
    # Parent is smaller than child size - create single child with parent's full text
    return [{
        "child_id": f"{parent['parent_id']}_child_0",
        "parent_id": parent["parent_id"],
        "document_id": parent["document_id"],
        "text": parent["text"],
        "token_count": parent["token_count"],
        "start_page": parent["start_page"],
        "end_page": parent["end_page"],
        "section": parent["section"],
        "child_index": 0,
    }]
```

### Edge Case 3: Overlap at Section Boundaries

**Scenario:** When a section boundary forces a new chunk, should overlap be included?

**Decision:** NO overlap across section boundaries.

**Rationale:**
- Overlap from Item 1 would pollute Item 1A chunks
- Section boundaries are semantic boundaries - overlap would reduce precision
- Parent chunks already provide context, so overlap is less critical

**Implementation:**
```python
# In semantic_chunking.py chunk_document()
if self._is_section_boundary(prev_section, section):
    # Force finalize WITHOUT overlap
    chunk_dict = self._build_chunk_dict(current_chunk_sentences, chunk_index)
    all_chunks.append(chunk_dict)
    chunk_index += 1
    current_chunk_sentences = []  # NO overlap - start fresh
    current_tokens = 0
```

### Edge Case 4: Very Short Documents

**Scenario:** A reference document has only 1-2 pages with minimal text.

**Handling:**
- If total document < parent_tokens: Create single parent with entire document
- If total document < child_tokens: Create single child (which equals the parent)
- Log warning for unusually small documents

### Edge Case 5: Missing Metadata Fields

**Scenario:** Extracted JSON is missing required metadata (e.g., no ticker found).

**Handling:**
```python
# In contextual_chunking.py
def _get_prefix_10k(self, metadata: dict) -> str:
    """Build prefix with graceful fallbacks for missing fields."""
    company = metadata.get("company", "Unknown Company")
    ticker = metadata.get("ticker", "N/A")
    fiscal_year = metadata.get("fiscal_year", "N/A")
    
    # Log if critical fields missing
    if ticker == "N/A":
        self._log.warning("missing_ticker", document_id=metadata.get("document_id"))
    
    return f"[10-K Filing] [{company} ({ticker})] [FY{fiscal_year}]"
```

### Error Handling Patterns

All new modules should follow existing project patterns:

1. **Custom Exceptions:**
   ```python
   class ParentChildChunkingError(Exception):
       """Base exception for parent/child chunking operations."""
       pass
   ```

2. **Structured Logging:**
   ```python
   import structlog
   logger = structlog.get_logger(__name__)
   
   self._log = logger.bind(
       parent_tokens=parent_tokens,
       child_tokens=child_tokens,
   )
   ```

3. **Input Validation:**
   ```python
   if not pages:
       self._log.warning("empty_pages_input")
       return [], []
   
   if self.child_tokens >= self.parent_tokens:
       raise ValueError(
           f"child_tokens ({self.child_tokens}) must be less than "
           f"parent_tokens ({self.parent_tokens})"
       )
   ```

---

## Implementation Order

### Recommended Sequence

```
┌─────────────────────────────────────────────────────────────────┐
│  Step 1: Update semantic_chunking.py                            │
│  - Add section boundary detection (Priority 2)                  │
│  - Update default chunk size to 256 (Priority 4)                │
│  - No new dependencies                                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 2: Create parent_child_chunking.py (Priority 1)           │
│  - Uses updated semantic_chunking.py                            │
│  - Creates parent/child structure                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 3: Create contextual_chunking.py (Priority 3)             │
│  - Enhanced prefix format                                       │
│  - Applied to child chunks from Step 2                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 4: Create/Update pinecone_client.py                       │
│  - Add parent_text storage in metadata                          │
│  - Follows Phase 2A Section 9.1 with additions                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 5: Update extract_and_index.py                            │
│  - Add indexing pipeline                                        │
│  - Use new chunking modules                                     │
│  - Follows Phase 2A Section 9.3 with additions                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 6: Update rag.py                                          │
│  - Replace stub with real implementation                        │
│  - Return parent_text in results                                │
│  - Follows Phase 2A Section 10.1 with additions                 │
└─────────────────────────────────────────────────────────────────┘
```

### Dependencies Graph

```
semantic_chunking.py (P2, P4)
         │
         ▼
parent_child_chunking.py (P1)
         │
         ├──────────────────┐
         ▼                  ▼
contextual_chunking.py   pinecone_client.py
         │                  │
         └────────┬─────────┘
                  ▼
      extract_and_index.py
                  │
                  ▼
              rag.py
```

---

## Pinecone Schema Changes

### Current Schema (Phase 2A Section 9.1)

```json
{
  "id": "AAPL_10K_2024_chunk_42",
  "values": [0.1, 0.2, ...],
  "metadata": {
    "document_id": "AAPL_10K_2024",
    "document_type": "10k",
    "company": "Apple Inc.",
    "ticker": "AAPL",
    "fiscal_year": 2024,
    "section": "Item 1A: Risk Factors",
    "page_number": 15,
    "chunk_index": 42,
    "text": "The chunk text..."
  }
}
```

### Updated Schema (With Parent/Child)

```json
{
  "id": "AAPL_10K_2024_parent_5_child_2",
  "values": [0.1, 0.2, ...],
  "metadata": {
    "document_id": "AAPL_10K_2024",
    "document_type": "10k",
    "source_type": "official",
    "company": "Apple Inc.",
    "ticker": "AAPL",
    "fiscal_year": 2024,
    "section": "Item 1A: Risk Factors",
    "page_number": 15,
    "total_pages": 127,
    "parent_id": "AAPL_10K_2024_parent_5",
    "parent_index": 5,
    "child_index": 2,
    "parent_text": "The full 1024-token parent text for LLM context...",
    "child_text": "The 256-token enriched child text that was embedded...",
    "child_text_raw": "The 256-token child text without contextual prefix..."
  }
}
```

### Schema Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `parent_id` | string | Unique ID linking child to parent |
| `parent_index` | int | Index of parent within document |
| `child_index` | int | Index of child within parent |
| `parent_text` | string | Full 1024-token parent text (returned to LLM) |
| `child_text` | string | Enriched 256-token child (what was embedded) |
| `child_text_raw` | string | Child text without prefix (for citation) |
| `total_pages` | int | Total document pages (for prefix) |

### Storage Impact

**Calculation Basis:**
- Average 10-K: ~100 pages of text content (excluding graphics)
- ~500 words per page = 50,000 words total
- ~65,000 tokens total (words × 1.3)

**Parent Chunks:**
- 1024 tokens per parent
- ~65 parents per 10-K (65,000 / 1024)

**Child Chunks:**
- 256 tokens per child (with 50 token overlap)
- ~4 children per parent (1024 / 256)
- ~260 children per 10-K (65 parents × 4)

| Metric | Before (512 chunks) | After (Parent/Child) | Change |
|--------|---------------------|---------------------|--------|
| Vectors per 10-K | ~127 | ~260 | +2x |
| Metadata per vector | ~2KB | ~6KB | +3x (parent_text) |
| Total storage per 10-K | ~250KB | ~1.5MB | ~6x |
| 7 companies | ~1.75MB | ~10.5MB | Still well under free tier |

**Pinecone Free Tier:** 100,000 vectors, plenty of headroom (~1,820 children for 7 companies).

---

## Testing Strategy

### Unit Tests

| Test | File | Validates |
|------|------|-----------|
| Section boundary detection | `test_semantic_chunking.py` | Chunks don't span sections |
| Section boundary with None | `test_semantic_chunking.py` | None → Section and Section → None handled |
| No overlap at section boundary | `test_semantic_chunking.py` | Overlap not included when section changes |
| Parent/child creation | `test_parent_child_chunking.py` | Correct relationships |
| Parent smaller than child | `test_parent_child_chunking.py` | Single child created |
| Child overlap within parent | `test_parent_child_chunking.py` | Overlap only within same parent |
| Token counting consistency | `test_parent_child_chunking.py` | Same result as semantic_chunking |
| Contextual enrichment | `test_contextual_chunking.py` | Prefix format |
| Missing metadata fallback | `test_contextual_chunking.py` | Graceful handling of missing fields |

### Integration Tests

| Test | Description |
|------|-------------|
| End-to-end indexing | Process sample 10-K, verify Pinecone vectors |
| RAG query | Query returns parent_text with correct citation |
| Section filtering | Query for "risk factors" returns only Item 1A |
| Parent deduplication | Multiple child matches return unique parents |
| Backwards compatibility | Old schema vectors still work |

### Manual Verification Commands

```bash
# 1. Test section boundary detection
docker-compose exec backend python -c "
from src.ingestion.semantic_chunking import SemanticChunker

# Create test pages with section transitions
pages = [
    {'page_number': 1, 'text': 'Business description content here.', 'section': 'Item 1: Business'},
    {'page_number': 2, 'text': 'Risk factors content here.', 'section': 'Item 1A: Risk Factors'},
]

chunker = SemanticChunker(max_tokens=256)
chunks = chunker.chunk_document(pages)

print(f'Created {len(chunks)} chunks')
for i, chunk in enumerate(chunks):
    print(f'Chunk {i}: section={chunk.get(\"section\")}, tokens={chunk[\"token_count\"]}')
    print(f'  Text preview: {chunk[\"text\"][:50]}...')

# VERIFY: Each chunk should have only ONE section
"

# 2. Test parent/child relationships
docker-compose exec backend python -c "
from src.ingestion.parent_child_chunking import ParentChildChunker

# Create test pages
pages = [
    {'page_number': 1, 'text': 'A ' * 400, 'section': 'Item 1A'},  # ~520 tokens
    {'page_number': 2, 'text': 'B ' * 400, 'section': 'Item 1A'},  # ~520 tokens
]

chunker = ParentChildChunker(parent_tokens=1024, child_tokens=256)
parents, children = chunker.chunk_document('TEST_DOC', pages)

print(f'Parents: {len(parents)}')
print(f'Children: {len(children)}')

# Verify relationships
for child in children:
    parent_id = child['parent_id']
    matching_parent = next((p for p in parents if p['parent_id'] == parent_id), None)
    assert matching_parent, f'Child {child[\"child_id\"]} has no matching parent!'
    print(f'Child {child[\"child_index\"]} -> Parent {parent_id} ✓')

print('All parent/child relationships valid!')
"

# 3. Test contextual prefix format
docker-compose exec backend python -c "
from src.ingestion.contextual_chunking import ContextualEnricher

enricher = ContextualEnricher()

# Test 10-K format
chunk_10k = {'text': 'Risk factor content...', 'start_page': 15, 'section': 'Item 1A'}
metadata_10k = {
    'document_type': '10k',
    'company': 'Apple Inc.',
    'ticker': 'AAPL',
    'fiscal_year': 2024,
    'total_pages': 127
}

enriched = enricher.enrich_chunk(chunk_10k, metadata_10k)
print('10-K Format:')
print(enriched['text'][:200])
print()

# Test reference document format
chunk_ref = {'text': 'News content...', 'start_page': 1}
metadata_ref = {
    'document_type': 'reference',
    'source_type': 'news',
    'source_name': 'Reuters',
    'publication_date': '2025-01-10',
    'headline': 'Apple reports record revenue',
    'total_pages': 2
}

enriched_ref = enricher.enrich_chunk(chunk_ref, metadata_ref)
print('Reference Format:')
print(enriched_ref['text'][:200])
"

# 4. Test Pinecone parent storage and retrieval
docker-compose exec backend python -c "
from src.utils.pinecone_client import PineconeClient
from src.utils.embeddings import BedrockEmbeddings
from src.config.settings import get_settings

settings = get_settings()
client = PineconeClient(
    api_key=settings.pinecone_api_key,
    index_name=settings.pinecone_index_name
)

# Verify vectors have parent_text
stats = client.get_stats()
print(f'Total vectors: {stats.get(\"total_vector_count\", 0)}')

# Query and check metadata
embeddings = BedrockEmbeddings()
query_vector = embeddings.embed_text('supply chain risks')
results = client.query(query_vector, top_k=1)

if results:
    metadata = results[0].get('metadata', {})
    has_parent = 'parent_text' in metadata
    has_child = 'child_text' in metadata
    print(f'Has parent_text: {has_parent}')
    print(f'Has child_text: {has_child}')
    if has_parent:
        print(f'Parent text preview: {metadata[\"parent_text\"][:100]}...')
else:
    print('No results - index may be empty')
"
```

### Verification Queries for News Impact Analysis

After full implementation, verify the use case works:

```bash
# Test query that should use parent context
docker-compose exec backend python -c "
from src.agent.tools.rag import retrieve_documents

# This query should:
# 1. Match child chunks mentioning China/supply chain
# 2. Return parent context with full risk description
# 3. Deduplicate if multiple children from same parent match

result = retrieve_documents('What are Apple supply chain risks related to China?')
print(result)

# VERIFY:
# - Results include full paragraphs (parent_text), not fragments
# - Citations show specific page/section
# - No duplicate results from same parent
"
```

---

## Phase 2A Guide Updates Summary

### Sections to Update

| Section | Update Type | Changes |
|---------|-------------|---------|
| 8.2 Semantic Chunking | MODIFY | Add section boundary detection, change default to 256 |
| 8.3 Contextual Enrichment | MODIFY | Enhanced prefix format |
| NEW 8.4 | ADD | Parent/Child Chunking section |
| 9.1 Pinecone Client | MODIFY | Add parent_text storage |
| 9.3 Indexing Pipeline | MODIFY | Use parent/child chunking |
| 10.1 RAG Tool | MODIFY | Return parent_text |

### New Files to Add to REPO_STATE.md

| File | Purpose |
|------|---------|
| `backend/src/ingestion/parent_child_chunking.py` | Parent/child chunk creation |
| `backend/src/ingestion/contextual_chunking.py` | Contextual prefix enrichment |
| `backend/src/utils/pinecone_client.py` | Pinecone operations |

---

## Summary

This delta document specifies changes to implement:

1. **Priority 1 (Parent/Child):** New `parent_child_chunking.py` file, schema changes
2. **Priority 2 (Section-Aware):** Modify `semantic_chunking.py` chunk boundaries
3. **Priority 3 (Enhanced Prefix):** Create `contextual_chunking.py` with rich format
4. **Priority 4 (256 tokens):** Update default chunk size configuration

**Implementation order:** P2 + P4 → P1 → P3 → Pinecone → Indexing → RAG

**Total estimated time:** 4-6 hours

**Risk:** Re-indexing required for all documents after implementation

---

## Rollback Strategy

### If Implementation Fails Mid-Way

**Scenario:** Something breaks during implementation and you need to restore working state.

**Step 1: Code Rollback**
```bash
# If changes are uncommitted
git checkout -- backend/src/ingestion/semantic_chunking.py

# If changes are committed but need to revert
git revert HEAD  # or specific commit
```

**Step 2: Pinecone Data Rollback**

If vectors were indexed with the new schema and need rollback:

```python
# Delete all vectors and re-index with old code
from pinecone import Pinecone

pc = Pinecone(api_key=settings.pinecone_api_key)
index = pc.Index(settings.pinecone_index_name)

# Option A: Delete by document (if tracking document_id)
for doc_id in document_ids:
    index.delete(filter={"document_id": doc_id})

# Option B: Delete entire namespace (nuclear option)
index.delete(delete_all=True, namespace="")
```

### Staged Rollout Recommendation

To minimize risk, implement in stages:

**Stage 1: Code Changes (No Re-indexing)**
- Implement all code changes
- Test with unit tests
- Verify imports work
- **Do NOT re-index Pinecone yet**

**Stage 2: Test with Single Document**
```bash
# Index just one document with new code
python scripts/extract_and_index.py --index-doc AAPL_10K_2024 --reindex
```

**Stage 3: Verify Retrieval Works**
```bash
# Test RAG query returns parent_text
docker-compose exec backend python -c "
from src.agent.tools.rag import retrieve_documents
result = retrieve_documents('What are Apple supply chain risks?')
print(result)
# Verify: result includes parent_text, not just child_text
"
```

**Stage 4: Full Re-index**
```bash
# Only after Stage 3 passes
python scripts/extract_and_index.py --reindex
```

### Backwards Compatibility

The RAG tool should handle both old and new schema gracefully:

```python
# In rag.py query handling
def format_result(result: dict) -> str:
    metadata = result.get("metadata", {})
    
    # Prefer parent_text, fall back to text (old schema) or child_text
    content = (
        metadata.get("parent_text") or 
        metadata.get("text") or 
        metadata.get("child_text") or 
        "[No content available]"
    )
    
    return content
```

### Manifest Tracking

The manifest (`documents/extracted/manifest.json`) should track indexing schema version:

```json
{
  "documents": {
    "AAPL_10K_2024": {
      "indexed_to_pinecone": true,
      "indexed_at": "2026-01-17T10:00:00Z",
      "index_schema_version": "v2_parent_child",
      "chunk_count": 260,
      "parent_count": 65
    }
  }
}
```

**Implementation Code for `document_processor._update_manifest()`:**

Add these fields when updating the manifest after indexing:

```python
# In extract_and_index.py or a new indexing module:
CURRENT_INDEX_SCHEMA_VERSION = "v2_parent_child"

def update_manifest_after_indexing(
    manifest: dict,
    doc_id: str,
    parent_count: int,
    child_count: int,
) -> None:
    """Update manifest with indexing results."""
    from datetime import datetime, timezone
    
    if doc_id not in manifest["documents"]:
        raise ValueError(f"Document {doc_id} not in manifest")
    
    manifest["documents"][doc_id].update({
        "indexed_to_pinecone": True,
        "indexed_at": datetime.now(timezone.utc).isoformat(),
        "index_schema_version": CURRENT_INDEX_SCHEMA_VERSION,
        "chunk_count": child_count,  # Number of child chunks (vectors)
        "parent_count": parent_count,  # Number of parent chunks
    })
    
    # Update totals
    manifest["totals"]["documents_indexed"] = sum(
        1 for doc in manifest["documents"].values()
        if doc.get("indexed_to_pinecone")
    )

def needs_reindexing(manifest: dict, doc_id: str) -> bool:
    """Check if document needs re-indexing due to schema change."""
    if doc_id not in manifest["documents"]:
        return True
    
    doc = manifest["documents"][doc_id]
    if not doc.get("indexed_to_pinecone"):
        return True
    
    # Re-index if schema version changed
    if doc.get("index_schema_version") != CURRENT_INDEX_SCHEMA_VERSION:
        return True
    
    return False
```

This allows detecting which documents need re-indexing after schema changes.

---

---

## Critical Friction Points and Risks

### Risk Assessment Summary

| Risk | Severity | Status | Mitigation |
|------|----------|--------|------------|
| 1. Missing `company` metadata | HIGH | ✅ RESOLVED | Company extraction added to document_processor.py |
| 2. `__init__.py` export conflicts | MEDIUM | ✅ NOT APPLICABLE | Guide uses direct imports |
| 3. Phase 2A guide out of sync | MEDIUM | ✅ RESOLVED | Used "Delta Addition" naming pattern |
| 4. Pinecone schema migration | HIGH | DOCUMENTED | Delete-before-upsert pattern (future implementation) |
| 5. extract_and_index.py integration | MEDIUM | DOCUMENTED | Major refactor needed (future implementation) |

---

### Risk 1: Missing `company` Metadata Field (CRITICAL)

**Status:** ✅ RESOLVED - Company extraction code added to `document_processor.py`, existing JSONs updated

**Evidence:** Looking at `NVDA_10K_2025.json`:
```json
"metadata": {
  "ticker": "NVDA",
  "fiscal_year": 2025,
  "document_type": "SEC 10-K Filing"
  // MISSING: "company": "NVIDIA Corporation"
}
```

**Impact:**
- Contextual prefix will use fallback "Unknown Company" for ALL existing documents
- Queries like "NVIDIA risk factors" may not match as well
- Degraded search quality

**Root Cause:** 
The VLM extraction DOES output company info, but `document_processor._extract_metadata()` only captures it if `page.get("company")` exists. The VLM doesn't extract to that field - it's in the text, not a structured field.

**Solution Options:**

1. **Option A: Re-run VLM extraction** (NOT recommended)
   - Cost: ~$5+ already spent
   - Time: 30-60 minutes
   - Not needed - data is there

2. **Option B: Update document_processor.py metadata extraction** (RECOMMENDED)
   - Parse company name from first page text
   - Add regex or simple extraction from "NVIDIA CORPORATION" in cover page text
   - Re-run `process_document()` with `--force` to update metadata only

3. **Option C: Extract company from filename pattern**
   - `NVDA` → "NVIDIA Corporation" (lookup table)
   - Quick but brittle

**Implementation Code for Option B:**

Add to `document_processor._extract_metadata()` around line 672-684:

```python
# In _extract_metadata() for 10k documents:
if doc_type == "10k":
    # Try to extract company name from first page text
    if not metadata.get("company") and pages:
        first_page_text = pages[0].get("text", "")
        # Pattern: Look for "COMPANY NAME" in all caps near start of cover page
        # Common patterns: "NVIDIA CORPORATION", "APPLE INC.", "MICROSOFT CORPORATION"
        import re
        company_match = re.search(
            r'\n([A-Z][A-Z\s&,\.]+(?:CORPORATION|CORP|INC|LLC|LTD|COMPANY|CO)\.?)\s*\n',
            first_page_text[:2000],  # Only search first 2000 chars
            re.IGNORECASE
        )
        if company_match:
            # Clean up: Title case, remove extra spaces
            company_name = company_match.group(1).strip()
            # Convert "NVIDIA CORPORATION" to "NVIDIA Corporation"
            metadata["company"] = company_name.title().replace("Llc", "LLC").replace("Inc.", "Inc.").replace("Corp.", "Corp.")
            logger.debug("company_extracted_from_text", company=metadata["company"])
        else:
            logger.warning("company_not_found_in_text", document_id=pdf_path.stem)
```

**Do we need to re-run VLM?** NO - the text data is already extracted. We just need better metadata extraction from the existing JSON.

**To apply to existing documents:** Run `python scripts/extract_and_index.py --force` after updating the code. This will re-process the JSONs with the new metadata extraction (no VLM calls needed since JSONs exist).

---

### Risk 2: `__init__.py` Export Updates Required

**Status:** ✅ NOT APPLICABLE

The Phase 2A guide uses **direct imports** throughout, which do not require `__init__.py` updates:

```python
# Guide uses direct imports like these (no __init__.py update needed):
from src.utils.pinecone_client import PineconeClient
from src.utils.embeddings import BedrockEmbeddings
from src.ingestion.semantic_chunking import SemanticChunker
from src.ingestion.parent_child_chunking import ParentChildChunker
from src.ingestion.contextual_chunking import ContextualEnricher
```

Package-level imports (`from src.utils import PineconeClient`) would require `__init__.py` updates, but the guide does not use this pattern for new modules.

**Optional Enhancement:** If you prefer cleaner package-level imports for consistency with VLMExtractor/DocumentProcessor, you can update `__init__.py` files manually. This is not required for the guide to work.

---

### Risk 3: Phase 2A Guide Section Numbers Out of Sync

**Status:** ✅ RESOLVED - Used "8.2 Delta Addition" naming pattern to avoid renumbering existing sections

**Current Phase 2A Structure:**
- Section 8.2: Semantic Chunking (implemented)
- Section 8.3: Contextual Enrichment (NOT implemented)
- Section 8.4: Test Chunking Pipeline
- Section 9.1: Pinecone Client

**Delta Document References:**
- "Insert after Phase 2A Section 8.2"
- "Phase 2A Section 8.3 (planned but not implemented)"
- "Phase 2A Section 9.1"

**Friction Points:**
1. If we insert "8.4 Parent/Child Chunking", existing 8.4 becomes 8.5
2. Checklist items reference section numbers
3. Cross-references in guide break

**Solution:**
- Either renumber all sections (risky, breaks references)
- OR add as subsections (8.2a, 8.2b) - less clean but safer
- OR add new sections at end and update TOC

**Action Item:** Decide on section numbering strategy before implementation.

---

### Risk 4: Pinecone Schema Migration

**Status:** Existing vectors (if any) won't have new fields

**New Fields Required:**
```json
{
  "parent_id": "NVDA_10K_2025_parent_0",
  "parent_text": "...",
  "child_text": "...",
  "child_text_raw": "...",
  "parent_index": 0,
  "child_index": 0,
  "total_pages": 119
}
```

**Friction Points:**

1. **No Pinecone schema migrations** - Pinecone is schemaless
   - Old vectors won't have `parent_text`
   - New code must handle missing fields gracefully

2. **Delete-before-upsert required**
   - Can't update existing vectors in place
   - Must delete all vectors for a document, then re-insert

3. **Mixed schema during transition**
   - If indexing fails mid-way, some docs have old schema, some new
   - RAG tool must handle both

**Current State:** Manifest shows `"indexed_to_pinecone": false` for all documents, so this is lower risk - no existing vectors to migrate.

**Solution:** The backwards compatibility code in delta document handles this:
```python
content = (
    metadata.get("parent_text") or 
    metadata.get("text") or 
    metadata.get("child_text") or 
    "[No content available]"
)
```

---

### Risk 5: extract_and_index.py Major Refactor Needed

**Status:** Current script only does extraction, needs indexing pipeline

**Current Flow:**
```
PDF → VLM Extraction → JSON file → Done
```

**Required Flow:**
```
PDF → VLM Extraction → JSON file → Parent/Child Chunking → 
Contextual Enrichment → Embeddings → Pinecone Upsert → Update Manifest
```

**Friction Points:**

1. **New dependencies needed:**
   ```python
   from src.ingestion.parent_child_chunking import ParentChildChunker
   from src.ingestion.contextual_chunking import ContextualEnricher
   from src.utils.pinecone_client import PineconeClient  # Doesn't exist yet
   from src.utils.embeddings import BedrockEmbeddings
   ```

2. **Async vs Sync mismatch:**
   - `BedrockEmbeddings.embed_batch()` is async
   - Chunking modules are sync
   - Script needs `async def index_document()`

3. **New CLI flags needed:**
   - `--index-only` (skip extraction)
   - `--reindex` (delete and re-index)
   - `--index-doc DOC_ID` (single document)

4. **Manifest schema changes:**
   - Add `index_schema_version`
   - Add `parent_count`
   - Update `chunk_count` to be children count

5. **Error handling complexity:**
   - What if embedding fails mid-batch?
   - What if Pinecone upsert fails?
   - Need transaction-like behavior (or at least good recovery)

**Impact:** This is the most complex change - essentially adding a second pipeline to the script.

---

### Summary: Do We Need to Re-run VLM?

**NO** - VLM extraction does NOT need to be re-run because:

1. ✅ Page text is already extracted (`page["text"]`)
2. ✅ Section info is already extracted (`page["section"]`)  
3. ✅ Page numbers are already tracked (`page["page_number"]`)
4. ✅ Document structure is preserved

**What needs updating:**
- `document_processor._extract_metadata()` - better company name extraction
- Could re-run `process_document()` on existing JSONs to update metadata only

---

### Inputs/Outputs Change Summary

| Module | Current Input | Current Output | New Input | New Output |
|--------|---------------|----------------|-----------|------------|
| `semantic_chunking.py` | pages[] | chunks[] | pages[] (unchanged) | chunks[] (with section boundary logic) |
| `contextual_chunking.py` | N/A | N/A | children[], metadata | enriched_children[] |
| `parent_child_chunking.py` | N/A | N/A | document_id, pages[] | parents[], children[] |
| `pinecone_client.py` | N/A | N/A | vectors[] | upsert result |
| `rag.py` | query | mock results | query | real results with parent_text |
| `extract_and_index.py` | PDFs | JSONs | PDFs or JSONs | JSONs + Pinecone vectors |

---

## Pre-Implementation Checklist

Before starting implementation, verify:

- [ ] Phase 2A Section 8.2 (semantic_chunking.py) is complete and working
- [ ] VLM extraction has been run and JSON files exist in `documents/extracted/`
- [ ] Pinecone index exists and is accessible
- [ ] Local development environment is set up (docker-compose up)
- [ ] No uncommitted changes in repository

## Post-Implementation Checklist

After implementation, verify:

- [ ] All new files have docstrings and `__all__` exports
- [ ] All new files are added to REPO_STATE.md
- [ ] Unit tests pass for all new modules
- [ ] Integration test: index one document, query returns parent_text
- [ ] Full re-index completes without errors
- [ ] RAG tool returns correct results with proper citations
- [ ] Manifest shows `index_schema_version: "v2_parent_child"`
