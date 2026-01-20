# Knowledge Graph Enhancement Plan

> **Status:** Planning Document  
> **Created:** 2026-01-20  
> **Purpose:** Align Knowledge Graph implementation with January 2026 best practices (GraphRAG, KG-RAG, Neurosymbolic RAG)

This document catalogs required enhancements to the Knowledge Graph implementation based on current best practices research, maps impacts across project documentation, and tracks decisions.

---

## Table of Contents

- [Executive Summary](#executive-summary)
- [Architecture Clarification](#architecture-clarification)
- [Enhancement Summary](#enhancement-summary)
- [Enhancement Details](#enhancement-details)
- [kg_evidence Preservation Requirements](#kg_evidence-preservation-requirements)
- [Error Handling & User Experience](#error-handling--user-experience)
- [Documentation Inconsistencies](#documentation-inconsistencies)
- [Decisions Required](#decisions-required)
- [Test Queries for Validation](#test-queries-for-validation)
- [Monitoring & Rollback](#monitoring--rollback)
- [Implementation Order](#implementation-order)
- [Files to Create/Modify](#files-to-createmodify)

---

## Executive Summary

### Current State

Our Knowledge Graph (KG) implementation provides:
- Entity extraction via spaCy + custom financial patterns
- Neo4j AuraDB storage with MENTIONS relationships
- Graph queries (`find_documents_mentioning`, `find_related_entities`, etc.)
- Integration point in `HybridRetriever._kg_search()`

### Gap Analysis (vs January 2026 Best Practices)

| What We Have | What Best Practices Recommend |
|--------------|------------------------------|
| KG returns document IDs only | KG should return entity context (why this doc was matched) |
| KG affects retrieval, not LLM context | KG evidence should appear in LLM prompt for explainability |
| 1-hop queries only in retrieval | 2-hop for complex multi-entity queries |
| Document-level matching | Chunk-level boosting based on KG signals |
| No query complexity detection | Adaptive pipelines based on query complexity |

### Key Research References

- **GraphRAG (Microsoft):** Community detection, entity summarization
- **KG-RAG (2025):** Dual-channel retrieval with entity relationships
- **KG²RAG:** Graph-guided chunk expansion and organization
- **Neurosymbolic RAG:** Modulating embeddings with symbolic features
- **FRAG Framework:** Adaptive pipelines based on query complexity

---

## Architecture Clarification

> **Important:** Understanding the layering between `GraphQueries` and `HybridRetriever` is critical.

### Module Responsibilities

```
┌─────────────────────────────────────────────────────────────────────┐
│                        HybridRetriever                              │
│  (backend/src/retrieval/hybrid_retriever.py)                        │
│                                                                     │
│  • _kg_search() - Wraps GraphQueries, adds entity evidence          │
│  • _apply_kg_boost() - Applies KG boost to chunk results            │
│  • _format_result_with_kg() - Formats results with KG evidence      │
│  • Orchestrates full retrieval pipeline                             │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         GraphQueries                                 │
│  (backend/src/knowledge_graph/queries.py)                           │
│                                                                     │
│  • find_documents_mentioning() → list[str] (doc IDs only)           │
│  • find_related_entities() → list[dict] (entity info)               │
│  • Low-level Neo4j query execution                                  │
│  • NO CHANGES NEEDED to this module                                 │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Points

1. **`GraphQueries` remains unchanged** - It returns raw data (`list[str]` for doc IDs, `list[dict]` for entities)
2. **`HybridRetriever._kg_search()` wraps GraphQueries** - It transforms raw results into entity-evidence-rich dicts
3. **Entity evidence is added at the HybridRetriever level**, not in GraphQueries

### Why This Layering?

- **Separation of concerns:** GraphQueries handles Neo4j; HybridRetriever handles RAG integration
- **Testability:** GraphQueries can be unit tested with mock Neo4j; HybridRetriever tests the integration
- **Reusability:** GraphQueries can be used by other modules without RAG-specific formatting

---

## Enhancement Summary

| ID | Enhancement | Priority | Section 11 Impact | Other Module Impact | Documentation Updates |
|----|-------------|----------|-------------------|---------------------|----------------------|
| A | Enrich KG return values with entity context | High | `_kg_search()` | None | PHASE_2B, RAG_README |
| B | Include KG evidence in LLM prompt | High | `_format_results()` | `rag.py` | PHASE_2B, RAG_README, PROJECT_PLAN |
| C | Multi-hop for complex queries | Medium | `_kg_search()` | None | PHASE_2B |
| D | Chunk-level KG boosting | High | `_apply_kg_boost()` | `rrf.py` | PHASE_2B, RAG_README |
| E | Query complexity detection | Low | New method | None | PHASE_2B (optional) |

---

## Enhancement Details

### Enhancement A: Enrich KG Return Values

**Problem:** Current `_kg_search()` returns only document IDs, losing entity context.

**Current State (Section 11 spec):**
```python
def _kg_search(self, query: str) -> list[dict]:
    # Returns only: [{"id": doc_id}]
    entities = self.extractor.extract_entities(query, "query", 0)
    doc_ids = set()
    for entity in entities:
        docs = self.queries.find_documents_mentioning(entity.text)
        doc_ids.update(docs)
    return [{"id": doc_id} for doc_id in doc_ids]
```

**Required Change:**
```python
def _kg_search(self, query: str) -> list[dict]:
    """
    Extract entities from query and find related documents WITH context.
    Returns document IDs plus entity evidence for explainability.
    
    Note: This method is in HybridRetriever, NOT GraphQueries.
    It wraps GraphQueries.find_documents_mentioning() and adds entity evidence.
    """
    entities = self._extractor.extract_entities(query, "query", 0)
    results: list[dict] = []
    seen_docs: set[str] = set()
    
    for entity in entities:
        # 1-hop: Direct document mentions (always executed)
        try:
            doc_ids = self._queries.find_documents_mentioning(entity.text, fuzzy=True)
            
            for doc_id in doc_ids:
                if doc_id not in seen_docs:
                    seen_docs.add(doc_id)
                    results.append({
                        "id": doc_id,
                        "source": "kg",
                        "kg_evidence": {
                            "matched_entity": entity.text,
                            "entity_type": entity.entity_type.value,
                            "match_type": "direct_mention",
                        }
                    })
        except Exception as e:
            logger.warning("kg_1hop_failed", entity=entity.text, error=str(e))
            # Continue with other entities - don't fail entire KG search
        
        # 2-hop: Related entities (only for complex queries with 2+ entities)
        # Wrapped in separate try/except so 1-hop results are preserved if 2-hop fails
        if len(entities) > 1:
            try:
                related = self._queries.find_related_entities(entity.text, hops=1, limit=5)
                for rel in related:
                    rel_docs = self._queries.find_documents_mentioning(rel["entity"], fuzzy=True)
                    for doc_id in rel_docs:
                        if doc_id not in seen_docs:
                            seen_docs.add(doc_id)
                            results.append({
                                "id": doc_id,
                                "source": "kg",
                                "kg_evidence": {
                                    "matched_entity": rel["entity"],
                                    "entity_type": rel["type"],
                                    "match_type": "related_via",
                                    "related_to": entity.text,
                                    "shared_docs": rel["shared_docs"],
                                }
                            })
            except Exception as e:
                logger.warning("kg_2hop_failed", entity=entity.text, error=str(e))
                # 2-hop failure is non-critical - 1-hop results still valid
    
    logger.debug(
        "kg_search_complete",
        query_entities=len(entities),
        docs_found=len(results),
        direct_matches=sum(1 for r in results if r["kg_evidence"]["match_type"] == "direct_mention"),
        indirect_matches=sum(1 for r in results if r["kg_evidence"]["match_type"] == "related_via"),
    )
    
    return results
```

**Benefits:**
- Explainability: Know WHY each document was matched
- Reranking: Can use entity type for scoring adjustments
- Audit trail: Traceable entity paths for compliance

**Files to Update:**
- `docs/PHASE_2B_HOW_TO_GUIDE.md` - Section 11.1 `_kg_search` specification
- `docs/RAG_README.md` - "Knowledge Graph" section

---

### Enhancement B: Include KG Evidence in LLM Prompt

**Problem:** KG only affects which documents are retrieved; LLM sees no entity evidence.

**Current Response Format:**
```
[1] Source: NVDA_10K_2024, Page 15 (Relevance: 9/10)
{passage text}
```

**Required Response Format:**
```
[1] Source: NVDA_10K_2024, Page 15 (Relevance: 9/10)
    KG Match: NVIDIA (Organization) - direct mention
    Related: supply chain, China (via shared documents)
{passage text}
```

**Implementation:**
```python
def _format_result_with_kg(result: dict, index: int) -> str:
    """Format a single result with KG evidence."""
    metadata = result.get("metadata", {})
    kg_evidence = result.get("kg_evidence", {})
    
    # Base citation
    source = metadata.get("document_id", "Unknown")
    page = metadata.get("page_number", "?")
    section = metadata.get("section", "")
    score = result.get("relevance_score", "?")
    
    lines = [f"[{index}] Source: {source}, Page {page} (Relevance: {score}/10)"]
    
    # Add KG evidence if present
    if kg_evidence:
        entity = kg_evidence.get("matched_entity", "")
        entity_type = kg_evidence.get("entity_type", "")
        match_type = kg_evidence.get("match_type", "")
        
        if match_type == "direct_mention":
            lines.append(f"    KG Match: {entity} ({entity_type}) - direct mention")
        elif match_type == "related_via":
            related_to = kg_evidence.get("related_to", "")
            lines.append(f"    KG Match: {entity} ({entity_type}) - related via {related_to}")
    
    # Add passage text
    text = result.get("compressed_text") or metadata.get("parent_text", metadata.get("text", ""))
    lines.append(text)
    
    return "\n".join(lines)
```

**Benefits:**
- LLM understands WHY these documents were selected
- Reduces hallucination by grounding in entity evidence
- User can see reasoning trail in citations

**Files to Update:**
- `docs/PHASE_2B_HOW_TO_GUIDE.md` - Section 11.3 Response Format
- `docs/RAG_README.md` - Query Pipeline section
- `PROJECT_PLAN.md` - Phase 2c RAG description

---

### Enhancement C: Multi-Hop for Complex Queries

**Problem:** Only 1-hop queries used in retrieval; misses indirect relationships.

**Example:**
```
Query: "How is Apple affected by Taiwan semiconductor issues?"

1-hop only: Find docs mentioning "Apple" - misses TSMC connection
2-hop:      Find Apple → related entities (TSMC) → docs mentioning TSMC
            Captures docs about Taiwan/TSMC without "Apple" mentioned
```

**Implementation:** See Enhancement A code - 2-hop triggered when `len(entities) > 1`.

**Trigger Condition:**
- Simple query (1 entity): Use 1-hop only
- Complex query (2+ entities): Add 2-hop results

**Files to Update:**
- `docs/PHASE_2B_HOW_TO_GUIDE.md` - Section 11.1

---

### Enhancement D: Chunk-Level KG Boosting

**Problem:** KG returns document IDs, but chunks are ranked without KG signal.

**Current Flow:**
```
Dense search → chunks with scores
BM25 search  → chunks with scores
KG search    → document IDs only (not used for chunk scoring)
RRF fusion   → merges dense + BM25, KG docs just filter
```

**Required Flow:**
```
Dense search → chunks with scores
BM25 search  → chunks with scores
KG search    → document IDs with entity evidence
RRF fusion   → merges dense + BM25
KG boost     → chunks from KG docs get +boost to RRF score
```

**Implementation:**
```python
def _apply_kg_boost(
    self, 
    chunk_results: list[dict], 
    kg_results: list[dict],
    boost: float = 0.1
) -> list[dict]:
    """
    Apply boost to chunks from KG-matched documents.
    
    Args:
        chunk_results: Results from RRF fusion (dense + BM25)
        kg_results: Results from _kg_search with kg_evidence
        boost: Additive boost to RRF score (default 0.1)
    
    Returns:
        chunk_results with boosted scores for KG-matched docs
    """
    # Build lookup of KG evidence by document ID
    kg_evidence_by_doc: dict[str, dict] = {}
    for kg_result in kg_results:
        doc_id = kg_result["id"]
        if doc_id not in kg_evidence_by_doc:
            kg_evidence_by_doc[doc_id] = kg_result.get("kg_evidence", {})
    
    # Apply boost to matching chunks
    for result in chunk_results:
        doc_id = result.get("metadata", {}).get("document_id")
        if doc_id in kg_evidence_by_doc:
            result["rrf_score"] = result.get("rrf_score", 0) + boost
            result["kg_evidence"] = kg_evidence_by_doc[doc_id]
            if "sources" in result:
                result["sources"].append("kg_boost")
            else:
                result["sources"] = ["kg_boost"]
    
    # Re-sort by boosted score
    return sorted(chunk_results, key=lambda x: x.get("rrf_score", 0), reverse=True)
```

**Boost Value Rationale:**
- RRF scores typically range 0.01-0.05 for top results
- +0.1 boost is significant but not overwhelming
- KG match becomes a strong signal without dominating

**Files to Update:**
- `docs/PHASE_2B_HOW_TO_GUIDE.md` - Section 9 (RRF) and Section 11.1
- `docs/RAG_README.md` - RRF Fusion section

---

### Enhancement E: Query Complexity Detection (Optional)

**Problem:** Simple queries don't need KG overhead; complex queries benefit from multi-hop.

**Implementation (Deferred to later phase):**
```python
def classify_query_complexity(self, query: str) -> str:
    """
    Classify query complexity for adaptive pipeline selection.
    
    Returns:
        "simple": Skip KG, use dense only
        "medium": Use 1-hop KG
        "complex": Use 2-hop KG with full pipeline
    """
    entities = self.extractor.extract_entities(query, "query", 0)
    
    if len(entities) == 0:
        return "simple"  # "What is a 10-K?" - no entities
    elif len(entities) == 1:
        return "medium"  # "Tell me about NVIDIA" - 1-hop
    else:
        return "complex" # "Compare Apple and NVIDIA China exposure" - 2-hop
```

**Status:** Low priority, deferred to Phase 3+

---

## kg_evidence Preservation Requirements

> **Critical:** The `kg_evidence` dict MUST be preserved through all pipeline steps to reach the final LLM prompt.

### Pipeline Flow

```
_kg_search()
    │
    │ Creates kg_evidence: {matched_entity, entity_type, match_type, ...}
    │
    ▼
_apply_kg_boost()
    │
    │ Attaches kg_evidence to chunks: result["kg_evidence"] = evidence
    │
    ▼
Cross-Encoder Reranking                    ◄── MUST PRESERVE kg_evidence
    │
    │ Reorders chunks by relevance score
    │ ⚠️ Must copy kg_evidence to reranked results
    │
    ▼
Contextual Compression                     ◄── MUST PRESERVE kg_evidence
    │
    │ Extracts relevant sentences from parent_text
    │ ⚠️ Must copy kg_evidence to compressed results
    │
    ▼
_format_result_with_kg()
    │
    │ Reads kg_evidence to format citations
    │
    ▼
Final LLM Prompt
```

### Implementation Requirements

**In CrossEncoderReranker.rerank():**
```python
def rerank(self, query: str, results: list[dict], top_k: int) -> list[dict]:
    # ... scoring logic ...
    
    for result in reranked_results:
        # PRESERVE kg_evidence from original result
        if "kg_evidence" in original_result:
            result["kg_evidence"] = original_result["kg_evidence"]
        if "sources" in original_result:
            result["sources"] = original_result["sources"]
    
    return reranked_results
```

**In ContextualCompressor.compress():**
```python
def compress(self, query: str, results: list[dict]) -> list[dict]:
    # ... compression logic ...
    
    for result in compressed_results:
        # PRESERVE kg_evidence through compression
        if "kg_evidence" in original_result:
            result["kg_evidence"] = original_result["kg_evidence"]
        if "sources" in original_result:
            result["sources"] = original_result["sources"]
    
    return compressed_results
```

### Verification Checklist

- [ ] `_apply_kg_boost()` attaches `kg_evidence` to boosted chunks
- [ ] `CrossEncoderReranker.rerank()` preserves `kg_evidence` on all results
- [ ] `ContextualCompressor.compress()` preserves `kg_evidence` on all results
- [ ] `_format_result_with_kg()` correctly reads `kg_evidence` for formatting
- [ ] Unit tests verify `kg_evidence` survives full pipeline

---

## Error Handling & User Experience

### What Users See When KG Fails

KG failures should be **invisible to users** - the system degrades gracefully to dense+BM25 retrieval.

| Failure Mode | User Impact | What Happens Internally |
|--------------|-------------|-------------------------|
| Neo4j connection fails | None visible | KG search skipped, dense+BM25 only |
| Entity extraction fails | None visible | KG search returns empty, no boost applied |
| 2-hop query times out | None visible | 1-hop results preserved, 2-hop skipped |
| All KG fails | None visible | Results lack `kg_evidence`, no KG Match shown in citations |

### Error Messages (Internal Logging Only)

```python
# Log levels for KG failures
logger.warning("kg_search_skipped", reason="neo4j_connection_failed")
logger.warning("kg_1hop_failed", entity="NVIDIA", error="timeout")
logger.warning("kg_2hop_failed", entity="Apple", error="query_too_complex")
logger.debug("kg_boost_applied", boosted_chunks=5, total_chunks=15)
```

### Citation Display Rules

**With KG Evidence:**
```
[1] Source: NVDA_10K_2025, Page 15 (Relevance: 9/10)
    KG Match: NVIDIA (Organization) - direct mention
The Company's business operations...
```

**Without KG Evidence (graceful degradation):**
```
[1] Source: NVDA_10K_2025, Page 15 (Relevance: 9/10)
The Company's business operations...
```

The user simply doesn't see the "KG Match:" line - no error message, no indication that KG was unavailable.

---

## Documentation Inconsistencies

### PROJECT_PLAN.md Issues

| Line | Issue | Fix |
|------|-------|-----|
| ~709 | "2c. RAG Document Tool... TO BE IMPLEMENTED" | Update to reflect Phase 2a completion status |
| ~746-748 | KG integration description is high-level only | Add reference to KG evidence pattern |
| ~769 | Query pipeline diagram missing chunk-level KG boost | Add KG boost step to diagram |

### DEVELOPMENT_REFERENCE.md Issues

| Line | Issue | Fix |
|------|-------|-----|
| 5 | "Phase 2b active" - accurate | No change needed |
| ~568 | Phase 2 section missing KG integration details | Add KG integration specification |
| Missing | No specification for `_kg_search` return format | Add under Phase 2b specifications |

### RAG_README.md Issues

| Section | Issue | Fix |
|---------|-------|-----|
| Knowledge Graph (~385) | Describes entity relationships but not retrieval integration | Add "KG Integration in Retrieval" subsection |
| Query Pipeline (~458) | Shows parallel retrieval but not KG boost merge | Add chunk-level boosting explanation |
| Component Summary table | Shows KG as "graph traversal" only | Add "entity evidence for LLM" |

### PHASE_2B_HOW_TO_GUIDE.md Issues

| Section | Issue | Fix |
|---------|-------|-----|
| 6.1 (GraphQueries) | Returns document IDs without entity context spec | Update return format |
| 11.1 (HybridRetriever) | `_kg_search` underspecified | Add detailed implementation |
| 11.3 (RAG Tool) | Response format missing KG evidence | Add KG match info |

### REPO_STATE.md Issues

| Issue | Fix |
|-------|-----|
| Missing planned directory | Add `backend/src/retrieval/` directory |
| Missing planned files | Add `backend/src/retrieval/__init__.py` |
| Missing planned files | Add `backend/src/retrieval/hybrid_retriever.py` |

---

## Decisions Required

### Decision 1: KG Boost Weight

**Question:** What boost value should KG-matched documents receive in RRF fusion?

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| 1. Fixed +0.1 | Simple constant boost | Predictable, easy to understand | May need tuning |
| 2. Variable by entity count | More entities = more boost | Nuanced | Complex logic |
| 3. Separate ranking lane | Configurable weight | Most flexible | Harder to tune |

**Recommendation:** Option 1 (fixed +0.1) for Phase 2b, add configurability later.

---

### Decision 2: Entity Evidence Verbosity

**Question:** How much KG evidence should appear in the final prompt to the LLM?

| Option | Example | Pros | Cons |
|--------|---------|------|------|
| 1. Minimal | "KG Match: NVIDIA (Organization)" | Low token cost | Limited context |
| 2. Medium | Entity + type + related entities | Good balance | Moderate tokens |
| 3. Verbose | Full path trace | Maximum context | Token bloat |

**Recommendation:** Option 2 (Medium) - provides explainability without token bloat.

---

### Decision 3: Multi-Hop Threshold

**Question:** When should multi-hop (2-hop) queries be triggered?

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| 1. Always 2-hop | All queries use 2-hop | Comprehensive | Slower, noisier |
| 2. 2+ entities | 2-hop only for complex queries | Balanced | May miss some cases |
| 3. Classifier | ML model decides | Optimal | Requires training |

**Recommendation:** Option 2 (2+ entities) for Phase 2b simplicity.

---

### Decision 4: HybridRetriever File Placement

**Question:** Where should `hybrid_retriever.py` be placed?

| Option | Path | Pros | Cons |
|--------|------|------|------|
| 1. `ingestion/` | `backend/src/ingestion/hybrid_retriever.py` | Matches PHASE_2B guide | `ingestion/` implies write-time, not query-time |
| 2. `retrieval/` | `backend/src/retrieval/hybrid_retriever.py` | Semantically correct (query-time retrieval) | New directory to create |
| 3. `rag/` | `backend/src/rag/hybrid_retriever.py` | Groups RAG components | Another new directory |

**Recommendation:** Option 2 (`backend/src/retrieval/`) - Create a new `retrieval/` directory for query-time components.

**Rationale:**
- `ingestion/` contains document processing: VLM extraction, chunking, embedding
- `HybridRetriever` is query-time retrieval: search, rerank, compress
- Clear separation of write-path (`ingestion/`) vs read-path (`retrieval/`)

**Directory Structure:**
```
backend/src/
├── ingestion/           # Document processing (write-time)
│   ├── vlm_extractor.py
│   ├── semantic_chunking.py
│   └── ...
├── retrieval/           # Query processing (read-time)  ◄── NEW
│   ├── __init__.py
│   └── hybrid_retriever.py
├── knowledge_graph/     # Entity storage and queries
└── utils/               # Shared utilities (BM25, RRF, reranker, compressor)
```

**Files to Update if Option 2 chosen:**
- Create `backend/src/retrieval/__init__.py`
- Create `backend/src/retrieval/hybrid_retriever.py`
- Update PHASE_2B_HOW_TO_GUIDE.md import paths
- Update REPO_STATE.md with new directory

---

## Test Queries for Validation

> These queries should be used to verify KG integration improves retrieval quality.

### 1. Direct Entity Match (1-hop)

**Query:** "What are NVIDIA's risk factors?"

**Expected Behavior:**
- Entity extracted: "NVIDIA" (Organization)
- KG finds: NVDA_10K_2025
- Chunks from NVDA_10K_2025 get +0.1 boost
- Citation shows: `KG Match: NVIDIA (Organization) - direct mention`

**Verification:**
```python
# Check kg_evidence is present
assert results[0].get("kg_evidence", {}).get("matched_entity") == "NVIDIA"
assert results[0].get("kg_evidence", {}).get("match_type") == "direct_mention"
```

### 2. Multi-Entity Query (2-hop)

**Query:** "How does Apple's supply chain depend on Taiwan?"

**Expected Behavior:**
- Entities extracted: "Apple" (Organization), "Taiwan" (Location)
- 1-hop: Docs mentioning Apple, docs mentioning Taiwan
- 2-hop: Apple → related entities (TSMC, Foxconn) → their docs
- Results include docs about TSMC even if "Apple" not mentioned

**Verification:**
```python
# Check 2-hop results are included
related_docs = [r for r in results if r.get("kg_evidence", {}).get("match_type") == "related_via"]
assert len(related_docs) > 0  # Should have indirect matches
```

### 3. No Entity Query (KG Skipped)

**Query:** "What is a 10-K filing?"

**Expected Behavior:**
- No entities extracted (generic question)
- KG search returns empty
- Results rely on dense + BM25 only
- No `kg_evidence` in results

**Verification:**
```python
# Check graceful handling of no entities
assert all("kg_evidence" not in r for r in results)
```

### 4. KG Failure Graceful Degradation

**Query:** "Tell me about Microsoft's cloud business"  
**Condition:** Neo4j is unavailable

**Expected Behavior:**
- KG search fails silently
- Dense + BM25 results returned
- User sees normal results without KG Match info
- No error shown to user

**Verification:**
```python
# With mocked Neo4j failure
with patch.object(queries, 'find_documents_mentioning', side_effect=Exception("Connection failed")):
    results = retriever.retrieve(query)
    assert len(results) > 0  # Still got results
    assert all("kg_evidence" not in r for r in results)  # No KG evidence
```

---

## Monitoring & Rollback

### KG Performance Monitoring

**Metrics to Track:**

| Metric | How to Measure | Target |
|--------|----------------|--------|
| KG hit rate | % of queries where KG found matches | > 60% |
| Boost impact | Avg position change of KG-boosted chunks | +2-3 positions |
| 2-hop usage | % of queries triggering 2-hop | 20-40% |
| KG latency | Time spent in `_kg_search()` | < 200ms |
| Failure rate | % of queries where KG fails | < 5% |

**Logging for Analysis:**
```python
logger.info(
    "kg_retrieval_complete",
    query_id=query_id,
    entities_found=len(entities),
    kg_docs_found=len(kg_results),
    chunks_boosted=boosted_count,
    kg_latency_ms=kg_duration_ms,
    used_2hop=len(entities) > 1,
)
```

### Rollback Plan

**If KG Causes Issues (poor results, latency, errors):**

**Option A: Disable KG Boost (keep KG search for debugging)**
```python
# In HybridRetriever.retrieve()
KG_BOOST_ENABLED = False  # Toggle via environment variable

if KG_BOOST_ENABLED:
    results = self._apply_kg_boost(results, kg_results)
```

**Option B: Disable KG Entirely**
```python
# In HybridRetriever.retrieve()
KG_ENABLED = False  # Toggle via environment variable

if KG_ENABLED:
    try:
        kg_results = self._kg_search(query)
    except Exception:
        kg_results = []
else:
    kg_results = []
```

**Environment Variable Controls:**
```bash
# .env
KG_ENABLED=true           # Master switch for KG search
KG_BOOST_ENABLED=true     # Switch for KG boost (requires KG_ENABLED)
KG_BOOST_VALUE=0.1        # Configurable boost value
KG_2HOP_ENABLED=true      # Switch for 2-hop queries
```

**Rollback Checklist:**
- [ ] Set `KG_ENABLED=false` in environment
- [ ] Restart backend container
- [ ] Verify results no longer have `kg_evidence`
- [ ] Monitor for quality impact (should revert to Phase 2a behavior)

---

## Implementation Order

1. **Create `backend/src/retrieval/` directory** - New directory for query-time components
2. **Update PHASE_2B_HOW_TO_GUIDE.md Section 11.1** - Update path to `retrieval/hybrid_retriever.py`, add detailed `_kg_search` spec with entity evidence and graceful degradation
3. **Update PHASE_2B_HOW_TO_GUIDE.md Section 9** - Add chunk-level KG boosting to RRF
4. **Update PHASE_2B_HOW_TO_GUIDE.md Section 10** - Add kg_evidence preservation requirement to reranker
5. **Update PHASE_2B_HOW_TO_GUIDE.md Section 10b** - Add kg_evidence preservation requirement to compressor
6. **Update PHASE_2B_HOW_TO_GUIDE.md Section 11.3** - Update response format with KG evidence
7. **Update RAG_README.md** - Add KG integration details
8. **Update PROJECT_PLAN.md** - Fix Phase 2c status, add KG evidence description
9. **Update DEVELOPMENT_REFERENCE.md** - Add KG integration specs
10. **Update REPO_STATE.md** - Add planned files including new `retrieval/` directory

---

## Files to Create/Modify

| File | Action | Changes |
|------|--------|---------|
| `docs/KNOWLEDGE_GRAPH_UPDATE_PLAN.md` | Create | This plan document |
| `backend/src/retrieval/__init__.py` | Create | Package init with HybridRetriever export |
| `backend/src/retrieval/hybrid_retriever.py` | Create | Main retrieval orchestration class |
| `docs/PHASE_2B_HOW_TO_GUIDE.md` | Modify | Sections 9, 10, 10b, 11.1, 11.3; update paths to `retrieval/` |
| `docs/RAG_README.md` | Modify | Knowledge Graph section, Query Pipeline, kg_evidence preservation |
| `PROJECT_PLAN.md` | Modify | Phase 2c status, KG integration description |
| `DEVELOPMENT_REFERENCE.md` | Modify | Phase 2 KG integration specs |
| `REPO_STATE.md` | Modify | Add `backend/src/retrieval/` directory and files |

---

## Appendix: Best Practices Research Summary

### GraphRAG (Microsoft, 2024-2025)
- Community detection for document clustering
- Entity summarization at query time
- Hierarchical graph structure

### KG-RAG (Nature, 2025)
- Dual-channel retrieval: dense + graph
- Entity relationships enhance recall
- Structured evidence improves precision

### Neurosymbolic RAG (arXiv, 2025)
- Modulate query embeddings with graph features
- Symbolic reasoning complements neural retrieval
- Path scoring for evidence selection

### FRAG Framework (arXiv, 2025)
- Adaptive pipeline based on query complexity
- Simple queries skip heavy processing
- Complex queries get full graph traversal

---

*Last updated: 2026-01-20*  
*Reviewed: 2026-01-20 - Added architecture clarification, graceful degradation, kg_evidence preservation, error handling, test queries, monitoring/rollback, file placement decision*
