# RAG System Architecture

> A modern Retrieval-Augmented Generation system for financial document analysis, optimized for 10-K filings and enterprise knowledge retrieval.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Document Ingestion](#document-ingestion)
- [Retrieval Strategy](#retrieval-strategy)
- [Knowledge Graph](#knowledge-graph)
- [Query Pipeline](#query-pipeline)
- [Storage Systems](#storage-systems)
- [Use Case: News vs 10-K Analysis](#use-case-news-vs-10-k-analysis)
- [Alternatives for Different Use Cases](#alternatives-for-different-use-cases)
- [Enterprise Features (Not Implemented)](#enterprise-features-not-implemented)

---

## Overview

### What This System Does

This RAG system enables natural language querying over complex financial documents (SEC 10-K filings). Users can ask questions like:

- "What are Apple's main risk factors related to China?"
- "How did Microsoft's cloud revenue change year over year?"
- "Compare the gross margins of tech companies in my database"
- "Does this news article align with what the company disclosed in their 10-K?"

### Why Financial Documents Are Hard

10-K filings present unique challenges that standard RAG approaches fail to handle:

| Challenge | Why It's Hard | Our Solution |
|-----------|---------------|--------------|
| Complex tables | Financial statements are 80% tables with precise alignment | Vision-based extraction |
| Multi-column layouts | Year-over-year comparisons in parallel columns | Layout-aware processing |
| Cross-references | "See Note 12" requires linking | Knowledge graph relationships |
| Domain terminology | "GAAP reconciliation", "diluted EPS" | Financial entity extraction |
| Numerical precision | $394.254B vs $394.3B matters | Structured data preservation |

### Design Principles

1. **Quality over cost** - For a demo with ~30-40 documents, we optimize for accuracy and simplicity
2. **VLM for all documents** - Single extraction pipeline using Claude Sonnet 4.5 Vision for consistency
3. **Hybrid retrieval** - Combine semantic understanding with keyword matching and graph traversal
4. **Structured + unstructured** - Preserve table structure while enabling natural language queries
5. **Traceable answers** - Every response cites specific pages and sections
6. **Batch processing** - Local scripts instead of Lambda for simplicity and no timeout limits

---

## Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER QUERY                                      │
│                "What are Apple's supply chain risks?"                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           QUERY PROCESSING                                   │
│                                                                              │
│   1. Query Analysis - Generate variants + determine KG complexity           │
│   2. Entity Extraction - Identify "Apple", "supply chain", "risks"          │
│   3. Parallel Search - Hit all three systems (KG uses complexity signal)    │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                 ┌───────────────────┼───────────────────┐
                 ▼                   ▼                   ▼
┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐
│  SEMANTIC SEARCH   │  │   KEYWORD SEARCH   │  │  KNOWLEDGE GRAPH   │
│                    │  │                    │  │                    │
│  "What does this   │  │  "Find documents   │  │  "What entities    │
│   MEAN?"           │  │   with these       │  │   are connected    │
│                    │  │   exact words"     │  │   to Apple?"       │
│  Pinecone          │  │  Pinecone BM25     │  │  Neo4j             │
│  Dense Vectors     │  │  Sparse Vectors    │  │  Graph Traversal   │
└─────────┬──────────┘  └─────────┬──────────┘  └─────────┬──────────┘
          │                       │                       │
          └───────────────────────┼───────────────────────┘
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          RESULT FUSION                                       │
│                                                                              │
│   1. RRF (Reciprocal Rank Fusion) - Merge results from all sources          │
│   2. Cross-Encoder Reranking - LLM scores relevance of top results          │
│   3. Contextual Compression - Extract only the relevant portions            │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FINAL RESPONSE                                     │
│                                                                              │
│   "Based on Apple's 2024 10-K (Item 1A, pages 15-18):                       │
│                                                                              │
│    Apple identifies several supply chain risks:                              │
│    1. Manufacturing concentration in Asia...                                 │
│    2. Single-source components...                                            │
│                                                                              │
│    Sources: AAPL-10K-2024, Page 15, Item 1A: Risk Factors"                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Component Summary

| Component | Technology | Purpose |
|-----------|------------|---------|
| Document Extraction | Claude Sonnet 4.5 Vision (VLM) via Bedrock | Convert ALL PDF pages to structured text |
| Entity Extraction | spaCy NER | Extract entities for Knowledge Graph (cost-efficient) |
| Embeddings | AWS Bedrock Titan v2 | Convert text to 1024-dim semantic vectors |
| Vector Store | Pinecone Serverless | Semantic (dense) and keyword (BM25) search |
| Knowledge Graph | Neo4j AuraDB Free | Entity relationships, graph traversal, page-level chunk boosting + LLM evidence |
| SQL Database | Neon PostgreSQL | Structured 10-K financial metrics |
| Orchestration | LangGraph | Coordinate retrieval and synthesis |
| LLM | AWS Bedrock Nova Pro | Query expansion, reranking, synthesis |

---

## Document Ingestion

> **Key Decision:** We use Claude Sonnet 4.5 Vision (VLM) for ALL documents - both complex 10-Ks and simple reference documents. This gives us one code path, consistent output, and the highest quality extraction. The cost difference is negligible for our document volume (~$40-60 total). Note: Claude 3.5 Sonnet V2 was deprecated in Oct 2025 and will shut down Feb 2026; Claude Sonnet 4.5 is the current recommended model.

### The Challenge of 10-K Documents

A typical 10-K filing is 80-150 pages containing:

- **Narrative sections** - Business description, risk factors, MD&A
- **Financial statements** - Balance sheet, income statement, cash flows
- **Footnotes** - Critical details in small print with cross-references
- **Exhibits** - Legal documents, certifications

Traditional PDF extraction (like pdfplumber or PyPDF2) produces unusable output for tables:

```
# What basic extraction gives you:
"Revenue 394,254 383,285 394,328 Cost of sales 228,184 226,253..."

# What you actually need:
Revenue (2024): $394,254M
Revenue (2023): $383,285M
```

### Our Approach: Vision Language Model Extraction

We use Claude Sonnet 4.5 Vision to "see" each page as a human would, understanding:

- Which numbers belong to which columns
- Table headers and row hierarchies
- Section boundaries and cross-references
- The difference between data and footnotes

**Process (via batch script):**

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    python scripts/extract_and_index.py                        │
└──────────────────────────────────────────────────────────────────────────────┘
                                      │
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   PDF File   │────▶│  Page Images │────▶│ Claude Sonnet│
│ (any type)   │     │  (150 DPI)   │     │  4.5 Vision  │
│              │     │              │     │  (Bedrock)   │
└──────────────┘     └──────────────┘     └──────┬───────┘
                                                 │
                                                 ▼
                     ┌───────────────────────────────────────┐
                     │         Structured JSON Output         │
                     │                                        │
                     │  • Tables with preserved structure     │
                     │  • Clean narrative text                │
                     │  • Section identification              │
                     │  • Page-level metadata                 │
                     └───────────────────────────┬───────────┘
                                                 │
         ┌───────────────────────────────────────┼───────────────────────────┐
         │                                       │                           │
         ▼                                       ▼                           ▼
┌─────────────────┐               ┌──────────────────┐           ┌──────────────────┐
│ Semantic Chunk  │               │    spaCy NER     │           │  Parse Tables    │
│ + Titan Embed   │               │ Entity Extraction │           │ (10-Ks only)     │
│                 │               │                  │           │                  │
│ → Pinecone      │               │ → Neo4j          │           │ → PostgreSQL     │
│   (vectors)     │               │   (entities)     │           │   (SQL metrics)  │
└─────────────────┘               └──────────────────┘           └──────────────────┘
```

**Why VLM for ALL documents (including simple ones):**

- ~30-40 documents total = ~$40-60 one-time extraction cost
- **One code path** - No need for separate pdfplumber pipeline
- **Consistent output** - Same JSON format for all documents
- Highest accuracy on complex tables AND simple text
- Simplest implementation (no document type detection, no fallback logic)
- Batch script processing (no Lambda timeouts)

> **Decision:** We use VLM even for "simple" documents (news articles, policies) because the cost difference is negligible (~$0.10 per article) and maintaining two extraction pipelines adds complexity without meaningful benefit for a demo. See `docs/PHASE_2_REQUIREMENTS.md` "Why Batch Script" section for full rationale.

### Alternative: HTML + Markdown for SEC Filings

For production systems processing thousands of SEC filings, an alternative approach offers significant cost savings:

| Approach | Cost per 10-K | Best For |
|----------|---------------|----------|
| **PDF + Vision** (current) | ~$4.00 | Any document type, complex layouts, charts, scanned docs |
| **HTML + Text API** | ~$0.30 | SEC filings only, high-volume processing |

**How it works:** SEC EDGAR provides 10-K filings as structured HTML. Download HTML → convert to Markdown → send text to LLM (no vision needed) → 90% cost reduction.

**Why we chose PDF + Vision:**
- Works with ANY document (not just SEC filings)
- Handles charts, graphs, and images
- Works with scanned documents and non-standard PDFs
- More robust to formatting variations
- Simpler implementation (one pipeline for all document types)
- Cost difference minimal for demo scale (~$40 vs ~$3 total)

**When to consider HTML approach:**
- Processing 1000s of SEC filings regularly
- Cost optimization is critical
- Chart/graph extraction not needed
- Want to chunk by SEC section (Item 1, 7, 8)

> **Note:** The HTML approach would require ~2-3 days of additional development to implement SEC EDGAR API integration, HTML parsing, and a parallel text-based extraction pipeline.

### Semantic Chunking

After extraction, we split text into chunks that preserve meaning:

**Bad (fixed-size chunking):**
```
Chunk 1: "...the Company faces significant risk. The"
Chunk 2: "primary manufacturing facilities are located in..."
```

**Good (semantic chunking):**
```
Chunk 1: "The Company faces significant risk related to manufacturing 
          concentration. The primary manufacturing facilities are 
          located in Asia, particularly China and Taiwan."
```

Key principles:
- Split at sentence boundaries
- Keep paragraphs together when possible
- Preserve context with overlap between chunks
- Maximum ~256 tokens per child chunk (optimized for precision matching)
- Parent/child chunking provides larger context (1024 tokens) via parent_text
- Section-aware boundaries for 10-K documents (never split across Item sections)

### Contextual Enrichment

Before creating embeddings, we prepend context to each chunk:

```
[Document: Apple Inc. 10-K FY2024]
[Section: Item 1A: Risk Factors]
[Page: 15]

The Company's business could be adversely affected by political events, 
trade disputes, or other circumstances beyond its control...
```

This technique (from Anthropic's "Contextual Retrieval" research) improves retrieval precision by 15-20% because:
- Chunks "know" where they came from
- Similar content from different sections stays distinguishable
- The embedding captures both content and context

---

## Retrieval Strategy

### Why Hybrid Search?

No single retrieval method handles all query types well:

| Query Type | Best Method | Why |
|------------|-------------|-----|
| "What are the risks?" | Semantic | Finds conceptually related content |
| "GAAP reconciliation" | Keyword (BM25) | Exact terminology matters |
| "What did Tim Cook say?" | Knowledge Graph | Entity-specific lookup |
| "Compare revenue growth" | Structured SQL | Numerical precision needed |

Our system combines all four approaches.

### Semantic Search (Dense Vectors)

**How it works:**

Text is converted to a 1024-dimensional vector (Titan v2) that captures meaning. Similar meanings produce similar vectors, even with different words.

```
"supply chain disruption"  →  [0.023, -0.145, 0.089, ...]
"manufacturing delays"     →  [0.021, -0.142, 0.091, ...]  (similar!)
"revenue growth"           →  [0.412, 0.033, -0.201, ...]  (different)
```

**Strengths:**
- Understands synonyms and paraphrases
- Handles natural language queries
- Finds conceptually related content

**Weaknesses:**
- May miss exact terminology
- Can't do numerical comparisons
- Struggles with rare domain terms

### Keyword Search (BM25 Sparse Vectors)

**How it works:**

BM25 scores documents based on term frequency and rarity. Documents with query terms get higher scores, especially for rare terms.

```
Query: "GAAP reconciliation"

Document A: Contains "GAAP" 5 times, "reconciliation" 3 times → High score
Document B: Contains "accounting standards" → Low score (no exact match)
```

**Strengths:**
- Precise terminology matching
- Handles acronyms and technical terms
- Fast and well-understood

**Weaknesses:**
- No semantic understanding
- Misses synonyms completely
- Sensitive to word choice

### Knowledge Graph (Entity Relationships)

**How it works:**

Entities (companies, people, concepts) and their relationships are stored in a graph. Queries can traverse connections.

```
Query: "What risks are related to China?"

Graph traversal:
  China (GPE) ──[MENTIONED_IN]──▶ Risk Factors Section
                                         │
  China (GPE) ──[RELATED_TO]──▶ Supply Chain (CONCEPT)
                                         │
                               ──[MENTIONED_IN]──▶ More documents
```

**Strengths:**
- Finds indirect relationships
- Enables "show me everything about X"
- Connects information across documents

**Weaknesses:**
- Requires entity extraction upfront
- Graph quality depends on extraction quality
- More complex to query

### Reciprocal Rank Fusion (RRF)

Dense and BM25 results (both chunk-level) are merged using RRF:

```
Score = Σ (1 / (k + rank))

Where:
- k = 60 (standard constant)
- rank = position in each result list
```

A chunk ranked #1 in semantic and #3 in BM25:
```
Score = 1/(60+1) + 1/(60+3) = 0.0164 + 0.0159 = 0.0323
```

**Note:** Knowledge Graph results are NOT included in RRF directly because KG queries return document-level information while dense/BM25 return chunks. Instead, KG results are applied as a **page-level boost** after RRF.

RRF naturally balances semantic and keyword sources without manual weighting.

### KG Boost (After RRF) - Page-Level Precision

After RRF fusion, chunks from KG-matched **pages** receive a score boost. This is page-level boosting,
not document-level - only chunks from pages where the entity was mentioned get boosted.

```
Flow:
Dense (chunks) + BM25 (chunks) → RRF Fusion → KG Boost → Reranking
                                                 ↑
                        KG search → doc IDs + pages + entity evidence
```

**Boost mechanism:**
- KG returns document IDs AND specific page numbers where entities appear
- Only chunks whose `start_page` is in KG results get +0.1 to RRF score
- KG entity evidence is attached to these chunks for LLM explainability
- Results are re-sorted after boosting

**Why Page-Level (with Document-Level Fallback)?**

| Document Type | Boost Strategy | Behavior |
|--------------|----------------|----------|
| 10-K PDFs | Page-level | Only relevant pages boosted |
| News articles | Document-level fallback | All chunks boosted (articles are typically small) |

| Query | Old Approach | New Page-Level Approach |
|-------|--------------|------------------------|
| "NVIDIA risks" on 10-K | Boosts ALL 500 chunks | Boosts only pages 15-25 (Risk Factors) |
| "NVIDIA news" on article | Boosts all chunks | Same - falls back to doc-level |

**Example:**
```
Before KG boost:
  NVDA_chunk_42 (page 67): rrf_score=0.032
  AAPL_chunk_15 (page 22): rrf_score=0.031

KG found: AAPL_10K_2024, pages [15, 22, 45] (matched entity: "Apple")

After KG boost:
  AAPL_chunk_15 (page 22): rrf_score=0.131, kg_evidence={entity: "Apple", pages: [15,22,45]}
  NVDA_chunk_42 (page 67): rrf_score=0.032  (NOT boosted - page not in KG results)
```

This provides precise page-level KG intelligence for chunk-level ranking.

---

## Knowledge Graph

### Purpose

The knowledge graph captures **what entities exist** and **how they relate**. This enables queries that vector search alone cannot handle:

- "Find all documents mentioning Tim Cook"
- "What topics are discussed alongside supply chain?"
- "Which regulations apply to Apple's services business?"

### Ontology (Entity and Relationship Types)

**Entity Types (10 types - see `ontology.py`):**

| Type | Description | Example |
|------|-------------|---------|
| Document | Source 10-K filing | AAPL-10K-2024 |
| Organization | Companies, agencies | Apple Inc., SEC |
| Person | Named individuals | Tim Cook, Luca Maestri |
| Location | Geographic entities (spaCy GPE) | China, California |
| Regulation | Laws and standards | SOX, GAAP, GDPR |
| Concept | Business/financial terms | Supply chain, EBITDA |
| Product | Products and services | iPhone, App Store |
| Date | Dates and time periods (spaCy DATE) | FY 2024, Q3 2024 |
| Money | Monetary values (spaCy MONEY) | $394 billion |
| Percent | Percentages and rates (spaCy PERCENT) | 23.5%, 15% growth |

**Relationship Types (7 defined, 1 currently implemented):**

| Relationship | Status | Meaning | Example |
|--------------|--------|---------|---------|
| MENTIONS | ✅ Active | Document mentions entity | (10-K)─[MENTIONS {page: 5}]→(Tim Cook) |
| DEFINES | Defined | Document defines concept | Future: glossary extraction |
| GOVERNED_BY | Defined | Subject to regulation | Future: compliance mapping |
| LOCATED_IN | Defined | Entity located in geography | Future: geographic analysis |
| RELATED_TO | Defined | Generic entity relationship | Future: custom relationships |
| WORKS_FOR | Defined | Person works for org | Future: org chart extraction |
| COMPETES_WITH | Defined | Orgs compete | Future: competitive analysis |

**Note:** Currently only MENTIONS relationships are created during entity indexing. Other relationship types are defined in `ontology.py` for future expansion.

### Entity Extraction

Entities are extracted from VLM output using spaCy NLP (not LLM) for cost efficiency:

```
PDF → Claude Sonnet 4.5 VLM → Clean Text → spaCy NER → Entities → Neo4j
```

- **Standard NER:** People, organizations, locations, dates, money
- **Custom patterns:** Financial regulations (SEC, GAAP), metrics (revenue, EPS)
- **Relationship inference:** Entities in the same sentence/paragraph are related

**Why spaCy instead of LLM for entity extraction:**

| Method | Cost per Document | For 22 Documents |
|--------|-------------------|------------------|
| LLM extraction | ~$0.02-0.05 | ~$20-50 |
| spaCy extraction | ~$0.001 | ~$0.02 |
| **Savings** | **20-50x cheaper** | **~$20-50 saved** |

The VLM already produces clean text - spaCy can reliably extract entities from that clean text without needing another LLM call.

### Graph Queries

**1-hop query:** Direct connections
```
"Find documents mentioning Apple"
→ All documents with (Document)─[MENTIONS]→(Apple)
```

**2-hop query:** Indirect connections
```
"What risks are related to China?"
→ Find (China)─[RELATED_TO]→(X)─[MENTIONED_IN]→(Document)
→ Returns documents about supply chain, manufacturing, trade policy
```

### KG Integration in Retrieval

The Knowledge Graph integrates with the retrieval pipeline in three ways:

**1. Entity Evidence for Explainability (with Page Numbers)**

KG queries return document IDs, page numbers, and entity evidence explaining WHY each document matched:

```python
# Instead of just returning document IDs:
[{"id": "AAPL_10K_2024"}, {"id": "NVDA_10K_2024"}]

# Return entity evidence with pages (from HybridRetriever._kg_search):
[
  {
    "id": "AAPL_10K_2024",
    "source": "kg",
    "kg_evidence": {
      "matched_entity": "Apple",
      "entity_type": "Organization",
      "match_type": "direct_mention",
      "pages": [15, 22, 45]  # Specific pages for page-level boosting
    }
  },
  {
    "id": "NVDA_10K_2024",
    "source": "kg",
    "kg_evidence": {
      "matched_entity": "supply chain",
      "entity_type": "Concept",
      "match_type": "related_via",
      "pages": [12, 18, 67],  # Pages where related entity appears
      "related_to": "Apple",
      "shared_docs": 3
    }
  }
]
```

**2. Page-Level Boosting**

KG provides page-level precision for chunk-level ranking:

```
KG: "AAPL_10K_2024 mentions Apple on pages [15, 22, 45]"
    ↓
Boost only chunks from pages 15, 22, 45 by +0.1
    ↓
Attach kg_evidence (including pages) to those chunks for LLM context
```

This is more precise than document-level boosting - only relevant pages are boosted.

**3. Multi-Hop for Complex Queries**

Simple queries (1 entity) use 1-hop; complex queries (2+ entities) add 2-hop:

| Query | Entities | Strategy |
|-------|----------|----------|
| "Tell me about NVIDIA" | 1 | 1-hop only |
| "Apple's China supply chain risks" | 3 | 1-hop + 2-hop |

**LLM Response Format with KG Evidence:**

```
[1] Source: Apple 10-K 2024, Item 1A, Page 15 (Relevance: 9/10)
    KG Match: Apple (Organization) - direct mention
The Company's operations in Greater China...

[2] Source: NVIDIA 10-K 2024, Item 1A, Page 22 (Relevance: 8/10)
    KG Match: supply chain (Concept) - related via Apple
Our supply chain and manufacturing operations...
```

This provides transparency: users and downstream LLMs see WHY each document was retrieved.

---

## Query Pipeline

### Complete Flow

When a user asks a question, the system executes this pipeline:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 1: QUERY ANALYSIS & EXPANSION                                           │
│                                                                              │
│ Original: "What are Apple's supply chain risks?"                            │
│                                                                              │
│ Output (single Nova Lite call):                                              │
│   • Variants: ["Apple supply chain risk factors", ...]                       │
│   • KG Complexity: "complex"                                                 │
│   • Reason: "Relationship between Apple and supply chain entities"          │
│                                                                              │
│ Purpose:                                                                     │
│   • Cast a wider net, improve recall by 20-30%                              │
│   • Determine KG traversal depth (1-hop vs 2-hop)                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 2: PARALLEL RETRIEVAL                                                   │
│                                                                              │
│ All expanded queries searched simultaneously across:                         │
│   • Pinecone dense index (semantic similarity)                              │
│   • Pinecone sparse index (BM25 keyword matching)                           │
│   • Neo4j graph (entity lookup and traversal)                               │
│                                                                              │
│ Each returns top 15 candidates                                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 3: RRF FUSION                                                           │
│                                                                              │
│ Merge dense + BM25 results into unified ranking                              │
│ Duplicates consolidated, scores combined                                     │
│ Output: Top 15 candidates with combined scores                               │
│ Note: KG results NOT included (document-level vs chunk-level)               │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 3b: KG BOOST (Page-Level)                                               │
│                                                                              │
│ Apply +0.1 boost to chunks from KG-matched PAGES (not entire documents)     │
│ KG returns doc_id + pages where entity appears → boost only those pages     │
│ Attach kg_evidence (incl. pages) to boosted chunks for LLM explainability   │
│ Re-sort by boosted RRF score                                                 │
│ See "KG Boost (After RRF)" section for details                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 4: CROSS-ENCODER RERANKING                                              │
│                                                                              │
│ LLM evaluates each candidate against original query:                         │
│   "On a scale of 1-10, how relevant is this passage to the question?"       │
│                                                                              │
│ Reorders based on true relevance, not just vector similarity                │
│ Impact: +20-25% precision improvement                                        │
│                                                                              │
│ Output: Top 5 most relevant passages                                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 5: CONTEXTUAL COMPRESSION                                               │
│                                                                              │
│ Extract only sentences relevant to the query from each passage               │
│ Removes tangential information                                               │
│ Reduces context length for final synthesis                                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 6: ANSWER SYNTHESIS                                                     │
│                                                                              │
│ LLM generates final answer with:                                             │
│   • Direct answer to the question                                            │
│   • Supporting evidence from retrieved passages                              │
│   • Source citations (document, page, section)                               │
│   • KG evidence in citations (entity, type, match reason)                    │
│   • Confidence indication if information is incomplete                       │
│                                                                              │
│ Citation format with KG evidence:                                            │
│   [1] Source: AAPL_10K_2024, Item 1A, Page 15 (Relevance: 9/10)             │
│       KG Match: Apple (Organization) - direct mention                        │
│   {passage text}                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Latency Budget

| Step | Target Latency | Notes |
|------|----------------|-------|
| Query analysis | ~200ms | Single LLM call (variants + KG complexity) |
| Parallel retrieval | ~150ms | All searches concurrent (dense + BM25 + KG) |
| RRF fusion | ~10ms | In-memory computation |
| KG boost | ~5ms | In-memory lookup and score adjustment |
| Cross-encoder rerank | ~400ms | 15 LLM scoring calls (batched) |
| Compression | ~200ms | Single LLM call |
| Synthesis | ~500ms | Final LLM call |
| **Total** | **~1.5 seconds** | Acceptable for interactive use |

---

## Storage Systems

### Pinecone (Vector Store)

**What's stored:**
- Dense vectors (1024 dimensions, Titan v2) for semantic search
- Sparse vectors (BM25) for keyword search
- Metadata for filtering and retrieval

**Metadata Fields:**

| Field | 10-K Documents | Reference Documents | Purpose |
|-------|----------------|---------------------|---------|
| `document_id` | ✓ | ✓ | Unique identifier (e.g., "AAPL_10K_2024") |
| `document_type` | "10k" | "reference" | Primary type filter |
| `source_type` | "official" | "news"/"research"/"policy" | Authority level for verification |
| `ticker` | ✓ | if applicable | Company filter (e.g., "AAPL") |
| `company` | ✓ | if applicable | Company name |
| `fiscal_year` | ✓ | - | Year for temporal filtering |
| `publication_date` | - | ✓ | Document date (YYYY-MM-DD) |
| `source` | - | ✓ | Publication name (Reuters, FT) |
| `section` | ✓ | - | 10-K section (Item 1A, etc.) |
| `start_page` | ✓ | ✓ | First page of chunk |
| `end_page` | ✓ | ✓ | Last page of chunk |
| `chunk_index` | ✓ | ✓ | Position in document |
| `text` | ✓ | ✓ | Chunk content for retrieval |

**Index configuration:**
- Name: `enterprise-agentic-ai`
- Metric: Dotproduct (optimal for hybrid search)
- Dimensions: 1024 (Titan v2)
- Cloud: AWS us-east-1
- Tier: Free (100K vectors)

**Estimated usage:**
- ~7 10-Ks × 100 pages × 5 chunks/page = 3,500 vectors
- ~15 reference docs × 10 pages × 5 chunks/page = 750 vectors
- **Total: ~4,250 vectors** - Well within free tier limits (100K)

### Neo4j AuraDB (Knowledge Graph)

**What's stored:**
- Entity nodes with properties (name, type, document source)
- Relationship edges (type, context, strength)
- Document nodes linking to contained entities

**Instance configuration:**
- Tier: Free (200K nodes, 400K relationships)
- Region: Closest to us-east-1

**Estimated usage:**
- ~22 documents × 150 entities = 3,300 nodes
- ~22 documents × 400 relationships = 8,800 edges
- **Total: ~3,300 nodes, ~8,800 edges** - Well within free tier limits (200K nodes)

### S3 (Document Storage) - Optional

**What's stored:**
- Original PDF files (optional - can be local)
- Extracted structured JSON
- Processing metadata and logs

**Demo configuration:**
- Local file storage for simplicity
- Documents processed via batch script
- S3 optional for backup/sharing

> **Note:** Lambda auto-ingestion is an enterprise pattern documented but not implemented for this demo. See "Enterprise Scaling" section in `docs/completed-phases/PHASE_2_REQUIREMENTS.md`.

---

## Use Case: News vs 10-K Analysis

### The Scenario

A user reads a news headline:
> "Apple reports record services revenue amid concerns about iPhone sales in China"

They want to know:
1. Is the "record services revenue" claim accurate?
2. What does Apple's 10-K actually say about China risks?
3. Does the news align with or contradict official disclosures?

### How The System Handles This

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ INPUT: News article text                                                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ CLAIM EXTRACTION                                                             │
│                                                                              │
│ Identified claims:                                                           │
│   1. "Record services revenue" (METRIC claim)                               │
│   2. "Concerns about iPhone sales" (TREND claim)                            │
│   3. "in China" (GEOGRAPHY context)                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
         ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
         │ VERIFY METRICS   │ │ FIND CONTEXT     │ │ CHECK RISKS      │
         │                  │ │                  │ │                  │
         │ Query financial  │ │ Search for       │ │ Search Item 1A   │
         │ tables for       │ │ iPhone/China     │ │ for China-related│
         │ services revenue │ │ discussion in    │ │ risk factors     │
         │ by year          │ │ MD&A section     │ │                  │
         └────────┬─────────┘ └────────┬─────────┘ └────────┬─────────┘
                  │                    │                    │
                  ▼                    ▼                    ▼
         ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
         │ FINDING:         │ │ FINDING:         │ │ FINDING:         │
         │                  │ │                  │ │                  │
         │ 2024: $96.2B     │ │ "Greater China   │ │ "The Company's   │
         │ 2023: $85.2B     │ │ revenue declined │ │ business could   │
         │ Growth: +12.9%   │ │ 8% year over     │ │ be impacted by   │
         │                  │ │ year..."         │ │ geopolitical     │
         │ ✓ CONFIRMED      │ │                  │ │ tensions..."     │
         │   Record high    │ │ ✓ ALIGNED        │ │                  │
         └──────────────────┘ └──────────────────┘ └──────────────────┘
                  │                    │                    │
                  └────────────────────┼────────────────────┘
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ SYNTHESIZED ANALYSIS                                                         │
│                                                                              │
│ The news article's claims are MOSTLY ACCURATE:                              │
│                                                                              │
│ ✓ "Record services revenue" - CONFIRMED                                     │
│   Services revenue reached $96.2B in FY2024, up 12.9% from $85.2B in FY2023│
│   Source: AAPL-10K-2024, Consolidated Statements of Operations, Page 45     │
│                                                                              │
│ ⚠ "Concerns about iPhone sales in China" - PARTIALLY SUPPORTED              │
│   Greater China revenue declined 8% YoY to $66.7B                           │
│   However, total Products revenue was flat globally ($298B both years)      │
│   The decline is China-specific, not global iPhone weakness                 │
│   Source: AAPL-10K-2024, Item 7: MD&A, Page 32                              │
│                                                                              │
│ ADDITIONAL CONTEXT from 10-K:                                                │
│   Apple explicitly lists China-related risks in Item 1A including:          │
│   - Trade tensions and tariffs                                               │
│   - Regulatory requirements for data localization                           │
│   - Competition from domestic manufacturers                                  │
│   Source: AAPL-10K-2024, Item 1A: Risk Factors, Pages 15-18                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Cross-Document Verification Workflow

The system supports three key analysis patterns for comparing sources:

1. **Claim Verification (News → 10-K):** Verify numerical claims from news against SQL data and official disclosures
2. **Risk Context (News → 10-K Risks):** Find 10-K risk disclosures relevant to current news events
3. **Competitive Analysis:** Compare strategy and positioning across multiple companies' 10-Ks with current news

Each query can state whether claims are **CONFIRMED**, **CONTRADICTED**, or **PARTIALLY_SUPPORTED** based on official disclosures.

See `docs/PHASE_2B_HOW_TO_GUIDE.md` Section 12b for implementation details.

---

## Alternatives for Different Use Cases

While we use the VLM (Vision Language Model) approach for this demo due to its simplicity and high accuracy with a small document set, different scenarios call for different architectures.

### When to Use Each Approach

| Scenario | Recommended Approach | Why |
|----------|---------------------|-----|
| **< 100 documents, quality critical** | VLM (our approach) | Highest accuracy, simplest code, ~$50-100 one-time |
| **100-500 documents, budget conscious** | AWS Textract + VLM fallback | Good balance of cost and quality |
| **500+ documents, high volume** | LayoutLM + Textract hybrid | Scale with acceptable quality |
| **Scanned/poor quality PDFs** | VLM or specialized OCR | Handles degraded images |
| **Real-time auto-ingestion** | Lambda + tiered extraction | Enterprise pattern (not implemented in demo) |
| **Multilingual documents** | VLM with language hints | Best cross-lingual understanding |

---

### Alternative 1: AWS Textract (Cost-Optimized)

**Best for:** 50-500 documents where budget matters

**Architecture change:**
- Replace Claude Vision with AWS Textract for table extraction
- Add confidence-based fallback to VLM for complex tables
- Keep rest of pipeline identical

**Trade-offs:**

| Aspect | VLM (Current) | Textract |
|--------|---------------|----------|
| Cost per page | ~$0.003-0.005 | ~$0.015 (tables) |
| Cost for 100 docs | ~$30-50 | ~$150 |
| Accuracy on tables | 95%+ | 75-85% |
| Complex nested tables | Excellent | May fail |
| Setup complexity | API key only | AWS service setup |
| Code complexity | ~100 lines | ~300 lines (with fallback) |

**When to switch:** If scaling beyond 50 documents and tables are relatively simple (clear borders, no complex nesting).

---

### Alternative 2: Open Source Stack (Self-Hosted)

**Best for:** Privacy requirements, no cloud dependency, high volume

**Architecture change:**
- Replace Claude Vision with LayoutLMv3 or DocTR (self-hosted)
- Replace Pinecone with Qdrant or Weaviate (self-hosted)
- Replace Neo4j AuraDB with self-hosted Neo4j
- Replace Bedrock with local LLM (Llama, Mistral)

**Trade-offs:**

| Aspect | Cloud (Current) | Self-Hosted |
|--------|-----------------|-------------|
| Infrastructure | Managed services | Your servers/GPU |
| Cost model | Per-request | Fixed infrastructure |
| Setup time | Hours | Days to weeks |
| Maintenance | Zero | Ongoing |
| Privacy | Data leaves your network | Full control |
| Quality | State-of-the-art | Depends on model choice |
| Scaling | Automatic | Manual capacity planning |

**When to switch:** Regulatory requirements prohibit cloud processing, or volume is so high that per-request pricing becomes expensive.

---

### Alternative 3: Simplified (No Knowledge Graph)

**Best for:** Faster implementation, simpler maintenance

**Architecture change:**
- Remove Neo4j entirely
- Remove entity extraction pipeline
- Keep only Pinecone (dense + sparse)

**Trade-offs:**

| Aspect | Full (Current) | No KG |
|--------|----------------|-------|
| Setup complexity | 3 systems | 1 system |
| Entity queries | Supported | Not supported |
| "Find related" queries | Graph traversal | Vector similarity only |
| Maintenance | More moving parts | Simpler |
| Quality on entity queries | High | Lower |

**When to switch:** If queries are primarily content-based ("What does X say about Y?") rather than entity-based ("Find everything about person X").

---

### Alternative 4: SQL-Heavy (Structured Queries)

**Best for:** Heavy numerical analysis, precise financial comparisons

**Architecture change:**
- Add PostgreSQL for structured financial data
- Extract key metrics into relational tables
- Enable SQL queries for numerical operations

**Example queries enabled:**
```sql
-- Which company had highest revenue growth?
SELECT company, 
       (revenue_2024 - revenue_2023) / revenue_2023 * 100 as growth_pct
FROM financial_metrics
ORDER BY growth_pct DESC;

-- Compare gross margins across tech companies
SELECT company, gross_margin_2024
FROM financial_metrics  
WHERE sector = 'Technology'
ORDER BY gross_margin_2024 DESC;
```

**Trade-offs:**

| Aspect | RAG-Only (Current) | RAG + SQL |
|--------|-------------------|-----------|
| Setup complexity | Medium | Higher |
| Numerical precision | Approximate | Exact |
| Comparative queries | LLM-dependent | SQL-precise |
| Natural language queries | Supported | Supported |
| Data extraction effort | Lower | Higher (structured extraction) |

**When to switch:** If primary use case involves numerical comparisons, trend analysis, or financial modeling.

---

### Alternative 5: Real-Time News Integration

**Best for:** Continuous monitoring, breaking news analysis

**Architecture change:**
- Add news ingestion pipeline (RSS, news APIs)
- Implement streaming processing
- Add alerting for significant discrepancies

**Additional components:**
- News API integration (NewsAPI, Benzinga, etc.)
- Apache Kafka or AWS Kinesis for streaming
- Scheduled comparison jobs
- Alert notification system

**Trade-offs:**

| Aspect | Batch (Current) | Real-Time |
|--------|-----------------|-----------|
| Freshness | Query-time | Continuous |
| Infrastructure | Simpler | More complex |
| Cost | Lower | Higher (always-on) |
| Use case | Ad-hoc analysis | Monitoring/alerting |

**When to switch:** If the goal is proactive monitoring rather than reactive analysis.

---

## Enterprise Features (Not Implemented)

The following features are critical for production enterprise RAG systems but are **not implemented in this demo**. We document them here to demonstrate awareness of real-world requirements.

---

### 1. Document-Level Access Control

**The Problem:**

In enterprise environments, not all users should see all documents. A financial analyst might access public filings, but only executives see M&A due diligence documents. HR documents should be restricted to HR staff.

Without access control, RAG systems can inadvertently leak sensitive information through:
- Direct retrieval of restricted documents
- Cross-document inference ("Based on the merger documents and public filings...")
- Metadata exposure in citations

**How It's Solved:**

Access Control Lists (ACLs) are attached to documents and enforced at query time.

```
Query Flow with ACL:
                                          
User Query ──▶ Get User Permissions ──▶ Filter Vector Search ──▶ Results
                     │                         │
                     ▼                         ▼
              user.groups = [              WHERE doc.acl IN 
                "analysts",                  ["public", "analysts"]
                "us-employees"             
              ]
```

**Implementation Options:**

| Approach | How It Works | Pros | Cons |
|----------|--------------|------|------|
| **Metadata filtering** | Store ACL in vector metadata, filter at query time | Simple, works with any vector DB | Performance degrades with complex ACLs |
| **Namespace separation** | Separate index per access level | Fast queries, strong isolation | Index proliferation, no cross-level search |
| **Pre-query authorization** | Check permissions before search, modify query | Flexible, supports complex rules | Added latency, complex logic |
| **Post-retrieval filtering** | Retrieve broadly, filter results | Simple implementation | Wastes resources, may return fewer results |

**Enterprise considerations:**
- Integration with identity providers (Okta, Azure AD, AWS IAM)
- Group-based vs. user-based permissions
- Attribute-based access control (ABAC) for dynamic rules
- Permission inheritance (folder → document → chunk)

---

### 2. Multi-Tenancy

**The Problem:**

SaaS RAG applications serve multiple customers (tenants). Each tenant's data must be completely isolated—Company A must never see Company B's documents, even accidentally through similarity search.

Risks without proper multi-tenancy:
- Data leakage between tenants
- Cross-tenant inference attacks
- Compliance violations (GDPR, SOC2)
- Noisy neighbor performance issues

**How It's Solved:**

Data isolation at storage and query layers ensures tenant boundaries are never crossed.

**Implementation Options:**

| Approach | How It Works | Pros | Cons |
|----------|--------------|------|------|
| **Database per tenant** | Separate vector DB instance per customer | Strongest isolation, easy compliance | Expensive, operational overhead |
| **Namespace per tenant** | Single DB, separate namespace/collection | Good isolation, efficient | Some DBs have namespace limits |
| **Metadata filtering** | Single namespace, tenant_id in metadata | Simplest, cheapest | Weakest isolation, filter bugs = leaks |
| **Row-level security** | Database enforces tenant boundaries | Strong guarantees | Requires DB support, complex setup |

**Enterprise considerations:**
- Tenant provisioning and deprovisioning workflows
- Cross-tenant analytics (aggregated, anonymized)
- Tenant-specific model fine-tuning
- Data residency requirements (EU tenant data stays in EU)

---

### 3. Audit Logging & Compliance

**The Problem:**

Regulated industries (finance, healthcare, government) require detailed records of:
- Who accessed what information
- What queries were run
- What answers were provided
- What sources were cited

This supports compliance (SOX, HIPAA, GDPR), forensic investigation, and user accountability.

**How It's Solved:**

Comprehensive logging captures every interaction with immutable, tamper-evident storage.

**What to Log:**

| Event | Data Captured |
|-------|---------------|
| Query submitted | User ID, timestamp, query text, session ID |
| Documents retrieved | Document IDs, relevance scores, ACL check results |
| Answer generated | Full response, sources cited, model used, tokens consumed |
| Feedback received | User rating, corrections, flagged issues |
| Document accessed | User ID, document ID, access type (view/download) |

**Implementation Options:**

| Approach | How It Works | Pros | Cons |
|----------|--------------|------|------|
| **Application logging** | Log to files/CloudWatch, archive to S3 | Simple, cheap | Not tamper-evident, query performance |
| **Dedicated audit DB** | Append-only database (e.g., Amazon QLDB) | Tamper-evident, queryable | Additional cost, complexity |
| **Event streaming** | Kafka/Kinesis to data lake | Real-time, scalable | Infrastructure overhead |
| **Third-party SIEM** | Send to Splunk, Datadog, etc. | Rich analysis, alerting | Cost at scale, vendor lock-in |

**Enterprise considerations:**
- Retention policies (7 years for financial, varies by regulation)
- PII in logs (may need redaction)
- Chain of custody for legal holds
- Real-time alerting on suspicious patterns

---

### 4. PII Detection & Handling

**The Problem:**

Documents may contain personally identifiable information (PII):
- Social Security numbers, credit card numbers
- Names, addresses, phone numbers
- Health information (PHI under HIPAA)
- Financial account details

RAG systems must either:
- Prevent PII from being indexed
- Redact PII before returning to users
- Restrict access to PII-containing documents

**How It's Solved:**

PII detection runs during ingestion and/or retrieval to identify and handle sensitive data.

**Implementation Options:**

| Approach | How It Works | Pros | Cons |
|----------|--------------|------|------|
| **Ingestion-time redaction** | Detect and remove PII before indexing | PII never stored, simplest compliance | Information loss, can't undo |
| **Query-time redaction** | Detect and mask PII in responses | Preserves data, flexible | Latency, detection must be perfect |
| **Tokenization** | Replace PII with tokens, store mapping separately | Reversible for authorized users | Complexity, token store security |
| **Encryption** | Encrypt PII fields, decrypt for authorized users | Strong protection | Key management, search limitations |

**Detection Methods:**

| Method | Examples | Accuracy | Speed |
|--------|----------|----------|-------|
| Regex patterns | SSN, credit cards, phone numbers | High for structured | Fast |
| NER models | Names, organizations, locations | Medium-high | Medium |
| AWS Comprehend | Built-in PII detection | High | API latency |
| LLM-based | Context-aware detection | Highest | Slow, expensive |

**Enterprise considerations:**
- False positive handling (don't redact "John Smith Avenue")
- Audit trail for PII access
- Data subject access requests (GDPR right to know)
- Cross-border PII transfer rules

---

### 5. Document Versioning

**The Problem:**

Documents change over time:
- Annual 10-K filings supersede previous years
- Policies get updated quarterly
- Contracts have amendments

Users may need to:
- Query the latest version only
- Compare across versions
- Access historical versions for audit

**How It's Solved:**

Version metadata enables filtering and comparison across document states.

**Implementation Options:**

| Approach | How It Works | Pros | Cons |
|----------|--------------|------|------|
| **Version in metadata** | Store version/date, filter at query time | Simple, flexible queries | All versions in same index |
| **Separate indices** | Index per time period (2023, 2024) | Clean separation | Cross-version queries harder |
| **Soft delete + replace** | Mark old chunks deleted, add new | Current-only queries fast | Historical queries need undelete |
| **Temporal database** | Built-in versioning (e.g., Datomic) | Native time-travel queries | Specialized infrastructure |

**Version Query Patterns:**

| Query Type | Example | Implementation |
|------------|---------|----------------|
| Latest only | "What are current risks?" | Filter: `version = latest` |
| Point in time | "What did 2022 10-K say?" | Filter: `year = 2022` |
| Comparison | "How did risks change?" | Retrieve both, compare |
| Historical | "When was this first mentioned?" | Search all versions, sort by date |

**Enterprise considerations:**
- Retention policies (how long to keep old versions)
- Default behavior (latest vs. all versions)
- Version-aware citations
- Storage cost of keeping all versions

---

### 6. Hallucination Detection & Grounding

**The Problem:**

LLMs can generate confident-sounding answers that aren't supported by the retrieved documents:
- Inventing statistics that sound plausible
- Mixing information from different contexts
- Extrapolating beyond what sources say

In enterprise contexts, hallucinated financial figures or legal statements can have serious consequences.

**Note**

This project actually does have arize phoenix/ragas with deep eval set up for later phases.
This allows for LLM log tracing, and RAGAS evaluates the performance against a 'golden dataset' to detect answer faithfullness (hallucinations)

**How It's Solved:**

Verification layers check that generated answers are grounded in retrieved sources.

**Implementation Options:**

| Approach | How It Works | Pros | Cons |
|----------|--------------|------|------|
| **Citation verification** | Require inline citations, verify each | High precision | Adds latency, complex prompting |
| **Entailment checking** | NLI model checks if sources support claims | Automated, scalable | Model accuracy limitations |
| **Confidence scoring** | LLM self-reports confidence per claim | Simple to implement | LLMs often overconfident |
| **Dual-model verification** | Second LLM checks first LLM's answer | Catches many errors | Doubles LLM cost |
| **Human-in-the-loop** | Flag low-confidence for review | Highest accuracy | Doesn't scale |

**Grounding Techniques:**

| Technique | Description |
|-----------|-------------|
| Constrained decoding | Force LLM to only use words from sources |
| Quote extraction | Answer must include direct quotes |
| Confidence thresholds | Refuse to answer if retrieval confidence low |
| Source highlighting | Show users exactly which text supports each claim |

**Enterprise considerations:**
- Acceptable hallucination rate (0.1%? 1%?)
- User trust indicators (confidence badges)
- Escalation paths for uncertain answers
- Training data for verification models

---

### 7. Feedback & Continuous Learning

**The Problem:**

RAG systems degrade over time if they can't learn from:
- User corrections ("That's not what the document says")
- Query patterns (what users actually ask)
- Retrieval failures (relevant docs not found)

Without feedback loops, the same errors repeat indefinitely.

**How It's Solved:**

Feedback collection and analysis pipelines identify improvement opportunities.

**Feedback Types:**

| Type | Signal | Use |
|------|--------|-----|
| Explicit thumbs up/down | User satisfaction | Quality monitoring |
| Corrections | "The answer should be..." | Fine-tuning, prompt improvement |
| Re-queries | Same topic, different phrasing | Query expansion training |
| Citation clicks | Which sources users verify | Relevance signal |
| Dwell time | How long users read answers | Engagement signal |

**Implementation Options:**

| Approach | How It Works | Pros | Cons |
|----------|--------------|------|------|
| **Feedback logging** | Store feedback, manual analysis | Simple, low risk | Doesn't auto-improve |
| **Active learning** | Prioritize uncertain cases for labeling | Efficient improvement | Requires labeling infrastructure |
| **RLHF** | Fine-tune on preferences | Learns user preferences | Expensive, complex |
| **Prompt optimization** | Analyze failures, improve prompts | Quick wins | Limited ceiling |
| **Retrieval tuning** | Adjust weights based on feedback | Improves recall | Needs significant data |

**Enterprise considerations:**
- Privacy (is feedback PII?)
- Feedback quality (malicious/gaming)
- A/B testing infrastructure
- Model retraining frequency

---

### 8. Query Guardrails & Safety
**Note**

We also actually do have input/output verification in a later phase.

**The Problem:**

Users may intentionally or accidentally submit problematic queries:
- Prompt injection attempts ("Ignore previous instructions...")
- Requests for harmful content
- Queries outside system scope
- Attempts to extract training data

**How It's Solved:**

Input and output guardrails filter problematic content before and after LLM processing.

**Implementation Options:**

| Approach | How It Works | Pros | Cons |
|----------|--------------|------|------|
| **Keyword blocklists** | Reject queries with blocked terms | Fast, simple | Easy to bypass |
| **Classification models** | ML model detects malicious intent | More robust | Requires training data |
| **LLM-based checking** | Ask LLM if query is appropriate | Context-aware | Adds latency, cost |
| **Scope verification** | Check if query matches allowed topics | Prevents off-topic | May frustrate users |

**Guardrail Layers:**

```
User Query
    │
    ▼
┌──────────────────┐
│ INPUT GUARDRAILS │ ─── Block: injection, harmful, off-topic
└────────┬─────────┘
         │
         ▼
   [RAG Pipeline]
         │
         ▼
┌───────────────────┐
│ OUTPUT GUARDRAILS │ ─── Block: PII, harmful, ungrounded
└────────┬──────────┘
         │
         ▼
    User Response
```

**Enterprise considerations:**
- False positive rate (don't block legitimate queries)
- User experience for blocked queries
- Logging blocked attempts for security review
- Regular guardrail updates for new attack patterns

---

### Summary: Enterprise Feature Priorities

When productionizing a RAG system, prioritize features based on your context:

| If You Have... | Prioritize |
|----------------|------------|
| Multiple customers | Multi-tenancy, access control |
| Regulated industry | Audit logging, PII handling |
| Sensitive documents | Access control, PII detection |
| High-stakes decisions | Hallucination detection, citations |
| Evolving document base | Versioning, feedback loops |
| External users | Guardrails, rate limiting |

This demo intentionally omits these features to focus on core RAG capabilities. Production deployment would require addressing the relevant subset based on use case requirements.

---

## Summary

This RAG system combines three retrieval methods (semantic, keyword, graph) with modern document understanding (VLM extraction) to enable natural language queries over complex financial documents.

**Key design decisions for this project:**

1. **VLM extraction for ALL documents** - Single code path using Claude Sonnet 4.5 Vision for both 10-Ks and reference documents (~$40-60 one-time cost for ~30-40 documents)
2. **Batch script processing** - Local scripts instead of Lambda for simplicity and no timeout limits
3. **Hybrid retrieval** - Combine semantic (Titan embeddings), keyword (BM25), and graph (Neo4j) for robust query handling
4. **spaCy for entity extraction** - Cost-efficient NER for Knowledge Graph (20-50x cheaper than LLM)
5. **Structured SQL output** - 10-K financial metrics stored in PostgreSQL for precise numerical queries

**Data flow:**
```
PDF → Claude Sonnet 4.5 VLM → Clean Text → ┬→ Titan Embeddings → Pinecone (semantic + BM25)
                                ├→ spaCy NER → Neo4j (knowledge graph)
                                └→ Parse Tables → PostgreSQL (SQL queries, 10-Ks only)
```

The architecture can be adapted for different scales and requirements using the alternatives described above. See `docs/PHASE_2_REQUIREMENTS.md` for enterprise scaling patterns (Lambda auto-ingestion, tiered extraction).

---

## References

- [Anthropic: Contextual Retrieval](https://www.anthropic.com/news/contextual-retrieval) - Technique for improving RAG precision
- [Pinecone: Hybrid Search](https://docs.pinecone.io/docs/hybrid-search) - Dense + sparse vector search
- [LangChain: RAG Techniques](https://python.langchain.com/docs/tutorials/rag/) - Query expansion, reranking patterns
- [Neo4j: Graph RAG](https://neo4j.com/developer-blog/knowledge-graph-rag-application/) - Knowledge graph augmented retrieval
