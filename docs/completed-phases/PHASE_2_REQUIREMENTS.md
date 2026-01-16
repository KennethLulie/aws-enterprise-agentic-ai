# Phase 2: Core Agent Tools - Requirements Planning Document

> **Status:** ARCHIVED (How-to guides completed)
> **Created:** 2026-01-13
> **Updated:** 2026-01-15 (archived after how-to guides completed)
> **Purpose:** Historical reference for Phase 2 planning decisions

**This document has been archived.** The implementation details are now in:
- `docs/PHASE_2A_HOW_TO_GUIDE.md` - Data Foundation & Basic Tools
- `docs/PHASE_2B_HOW_TO_GUIDE.md` - Intelligence Layer & Full Integration

**Related Documentation:**
- `docs/RAG_README.md` - Detailed RAG architecture, design decisions, and alternatives

---

## Table of Contents

- [Phase 2 Scope Summary](#phase-2-scope-summary)
- [Why Batch Script (Not Lambda)](#why-batch-script-not-lambda)
- [SQL Tool Requirements](#sql-tool-2b-requirements)
- [RAG Tool Requirements](#rag-tool-2c-requirements)
- [Knowledge Graph Requirements](#knowledge-graph-2c-kg-requirements)
- [Data Lifecycle Management](#data-lifecycle-management)
- [Infrastructure Requirements](#infrastructure-requirements)
- [Sample Data Strategy](#sample-data-strategy)
- [Cost Estimates](#cost-estimates)
- [Success Criteria](#success-criteria)
- [Implementation Order](#implementation-order)
- [Design Decisions (Resolved)](#design-decisions-resolved)
- [Enterprise Scaling (Future)](#enterprise-scaling-future)

---

## Phase 2 Scope Summary

### Already Completed (Phase 0)

These tools are **NOT part of Phase 2** - already working:

| Tool | Status | Notes |
|------|--------|-------|
| Tavily Search | ✅ Complete | Real API with mock fallback |
| Market Data (FMP) | ✅ Complete | Real API with mock fallback |

### Phase 2 Scope - To Implement

| Component | Description | Sub-phase |
|-----------|-------------|-----------|
| **VLM Document Extraction** | Claude Vision extracts structured data from ALL documents | 2a |
| **SQL Tool** | Query 10-K financial metrics from PostgreSQL | 2a |
| **RAG Tool (Basic)** | Dense vector search in Pinecone | 2a |
| **Knowledge Graph** | Neo4j entity extraction and graph queries | 2b |
| **Advanced RAG** | Hybrid search, query expansion, reranking, RRF | 2b |

> **Note:** We use VLM extraction for ALL documents (not just 10-Ks) and batch scripts for processing. Lambda auto-ingestion is deferred as an enterprise scaling pattern. See [Why Batch Script](#why-batch-script-not-lambda) for rationale.

### Key Technology Decisions

| Component | Technology | Notes |
|-----------|------------|-------|
| **VLM Extraction** | Claude Vision (via Bedrock) | Extracts structured data from ALL documents |
| **Dense Embeddings** | Bedrock Titan Embeddings | 1536 dimensions, ~$0.0001/1K tokens |
| **Vector Store** | Pinecone Serverless | Free tier, hybrid search (dense + BM25) |
| **Graph Database** | Neo4j AuraDB Free | 200K nodes, entity relationships |
| **SQL Database** | Neon PostgreSQL | Already set up in Phase 1b |
| **Processing Method** | Local batch script | Simple, no Lambda timeouts, easier debugging |

### VLM Extraction → All Systems

Claude Vision extracts structured data from 10-K PDFs, which populates **all three data stores**:

```
┌─────────────────────────────────────────────────────────────────┐
│                 10-K PDF (via Claude Vision VLM)                │
│                                                                  │
│  Extracts:                                                       │
│  • Financial tables (revenue, margins, metrics)                 │
│  • Text content (risk factors, MD&A narrative)                  │
│  • Entities (companies, people, regulations, concepts)          │
└───────────────────────────┬─────────────────────────────────────┘
                            │
         ┌──────────────────┼──────────────────┐
         ▼                  ▼                  ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│   PostgreSQL    │ │    Pinecone     │ │     Neo4j       │
│   (SQL Tool)    │ │   (RAG Tool)    │ │ (Knowledge Graph)│
├─────────────────┤ ├─────────────────┤ ├─────────────────┤
│ Financial       │ │ Text chunks     │ │ Entities:       │
│ metrics:        │ │ embedded via    │ │ • Companies     │
│ • Revenue       │ │ Bedrock Titan   │ │ • People        │
│ • Net income    │ │ (1536 dims)     │ │ • Regulations   │
│ • Margins       │ │                 │ │ • Concepts      │
│ • Segments      │ │ Enables:        │ │                 │
│ • Risks         │ │ "What are the   │ │ Enables:        │
│                 │ │  supply chain   │ │ "Find all docs  │
│ Enables:        │ │  risks?"        │ │  mentioning     │
│ "Which company  │ │                 │ │  Tim Cook"      │
│  had highest    │ │                 │ │                 │
│  revenue?"      │ │                 │ │                 │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

### Phase 2a vs 2b Split

| Phase 2a: Foundation | Phase 2b: Intelligence |
|---------------------|------------------------|
| External services setup | Knowledge Graph implementation |
| VLM extraction (batch script) | Advanced retrieval features |
| SQL tool with 10-K data | BM25 + RRF + Reranking |
| Basic RAG (dense search via Titan) | Full integration testing |
| Manual document loading | Multi-tool query orchestration |

**Exit Criteria 2a:** SQL and basic RAG work with manually loaded data  
**Exit Criteria 2b:** Full hybrid retrieval with Knowledge Graph integration

> **Deferred:** Lambda auto-ingestion is documented in [Enterprise Scaling](#enterprise-scaling-future) but not implemented for this demo.

---

## Why Batch Script (Not Lambda)

### The Decision

For this demo, we use **VLM extraction for ALL documents** and **local batch scripts** instead of Lambda auto-ingestion.

### Why VLM for Everything

| Factor | VLM for All | Mixed (VLM + pdfplumber) |
|--------|-------------|--------------------------|
| **Code complexity** | ✅ One extraction path | ❌ Two extraction paths |
| **Output consistency** | ✅ Same format for all | ❌ Different formats |
| **Maintenance** | ✅ Single pipeline | ❌ Two pipelines to debug |
| **Quality** | ✅ Best for any layout | 🟡 pdfplumber struggles with columns |

**Cost for demo:** ~$40-60 total (one-time) for ~30-40 documents. This is negligible.

### Why Batch Script (Not Lambda)

| Factor | Batch Script | Lambda Auto-Ingestion |
|--------|--------------|----------------------|
| **Timeout** | ✅ No limit | ⚠️ 15 min max (60s typical) |
| **Debugging** | ✅ Run locally, see logs | ❌ CloudWatch, harder to debug |
| **Complexity** | ✅ Simple Python script | ❌ Lambda + S3 events + IAM |
| **Cost** | ✅ Free (your computer) | 🟡 ~$0.10/month |
| **Triggering** | Manual (`python script.py`) | Automatic (S3 upload) |

### When This Approach Works

✅ **Good for:**
- Demo/prototype with ~30-50 documents
- Infrequent document additions (monthly/quarterly)
- Single developer/small team
- When you control when documents are added

### The Workflow

```
1. Download document (10-K from EDGAR, news article, etc.)
2. Place in local folder: ./documents/raw/
3. Run script: python scripts/extract_and_index.py
4. Wait for completion (1-5 minutes depending on pages)
5. Document is now searchable in the agent
```

### Enterprise Alternative

For production systems with continuous document flow, see [Enterprise Scaling](#enterprise-scaling-future) for the Lambda-based approach with:
- Automatic S3 → Lambda triggers
- Tiered extraction (VLM for complex, pdfplumber for simple)
- Queue-based processing for large documents
- Parallel processing at scale

---

## SQL Tool (2b) Requirements

### Database Technology

**Decision: Keep Neon PostgreSQL** ✅

The SQL tool uses the existing Neon PostgreSQL database from Phase 1b (already working for checkpointing).

| Consideration | Assessment |
|---------------|------------|
| Already integrated | ✅ Phase 1b has connection working |
| Free tier sufficient | ✅ 0.5GB storage, plenty for 10-K data |
| Financial queries | ✅ PostgreSQL excels at numerical analysis |
| Additional cost | ✅ $0 - same database as checkpoints |
| Setup effort | ✅ None - just add tables via Alembic |

### Integrated Data Model

**Key Change:** SQL tables are populated from **real 10-K data** extracted by VLM, not synthetic Faker data. This creates a cohesive system where SQL, RAG, and Knowledge Graph all query the same source documents.

```
┌─────────────────────────────────────────────────────────────────┐
│                    10-K Document (PDF)                          │
└───────────────────────────┬─────────────────────────────────────┘
                            │ VLM Extraction
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Structured JSON Output                        │
│  {                                                               │
│    "company": "Apple Inc.",                                      │
│    "ticker": "AAPL",                                             │
│    "fiscal_year": 2024,                                          │
│    "financials": { "revenue": 394328, "net_income": 93736 },    │
│    "segments": [{ "name": "iPhone", "revenue": 200583 }, ...],  │
│    "risks": [{ "category": "Supply Chain", "summary": "..." }]  │
│  }                                                               │
└───────────────────────────┬─────────────────────────────────────┘
                            │
         ┌──────────────────┼──────────────────┐
         ▼                  ▼                  ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ PostgreSQL  │    │  Pinecone   │    │   Neo4j     │
│ (structured │    │  (text for  │    │ (entities & │
│  metrics)   │    │  semantic)  │    │  relations) │
└─────────────┘    └─────────────┘    └─────────────┘
```

### Database Schema Design

#### Tables

```sql
-- Companies (one row per 10-K filing)
CREATE TABLE companies (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    sector VARCHAR(100),
    fiscal_year_end DATE,
    filing_date DATE,
    document_id VARCHAR(100),  -- Links to RAG document in Pinecone
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Annual financial metrics (from income statement, balance sheet, cash flow)
CREATE TABLE financial_metrics (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
    fiscal_year INTEGER NOT NULL,
    -- Income Statement (in millions USD)
    revenue DECIMAL(15, 2),
    cost_of_revenue DECIMAL(15, 2),
    gross_profit DECIMAL(15, 2),
    operating_expenses DECIMAL(15, 2),
    operating_income DECIMAL(15, 2),
    net_income DECIMAL(15, 2),
    -- Balance Sheet (in millions USD)
    total_assets DECIMAL(15, 2),
    total_liabilities DECIMAL(15, 2),
    total_equity DECIMAL(15, 2),
    cash_and_equivalents DECIMAL(15, 2),
    long_term_debt DECIMAL(15, 2),
    -- Calculated margins (percentages)
    gross_margin DECIMAL(5, 2),
    operating_margin DECIMAL(5, 2),
    net_margin DECIMAL(5, 2),
    -- Per share data
    earnings_per_share DECIMAL(10, 4),
    diluted_eps DECIMAL(10, 4),
    -- Metadata
    currency VARCHAR(3) DEFAULT 'USD',
    UNIQUE(company_id, fiscal_year)
);

-- Business segment revenue breakdown
CREATE TABLE segment_revenue (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
    fiscal_year INTEGER NOT NULL,
    segment_name VARCHAR(100) NOT NULL,
    revenue DECIMAL(15, 2),
    percentage_of_total DECIMAL(5, 2),
    yoy_growth DECIMAL(5, 2)  -- Year-over-year growth percentage
);

-- Geographic revenue breakdown
CREATE TABLE geographic_revenue (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
    fiscal_year INTEGER NOT NULL,
    region VARCHAR(100) NOT NULL,  -- e.g., "Americas", "Europe", "Greater China"
    revenue DECIMAL(15, 2),
    percentage_of_total DECIMAL(5, 2),
    yoy_growth DECIMAL(5, 2)
);

-- Risk factors (extracted from Item 1A)
CREATE TABLE risk_factors (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
    fiscal_year INTEGER NOT NULL,
    category VARCHAR(100),  -- e.g., "Supply Chain", "Regulatory", "Competition", "Macroeconomic"
    title VARCHAR(500),
    summary TEXT,
    severity VARCHAR(20) CHECK (severity IN ('high', 'medium', 'low')),
    page_number INTEGER
);

-- Indexes for common queries
CREATE INDEX idx_financial_metrics_company ON financial_metrics(company_id);
CREATE INDEX idx_financial_metrics_year ON financial_metrics(fiscal_year);
CREATE INDEX idx_segment_revenue_company ON segment_revenue(company_id);
CREATE INDEX idx_geographic_revenue_company ON geographic_revenue(company_id);
CREATE INDEX idx_risk_factors_company ON risk_factors(company_id);
CREATE INDEX idx_risk_factors_category ON risk_factors(category);
CREATE INDEX idx_companies_ticker ON companies(ticker);
```

### Data Population Strategy

Data is populated from VLM extraction output, NOT Faker:

| Table | Source | Extraction Method |
|-------|--------|-------------------|
| companies | 10-K cover page | VLM identifies company name, ticker, dates |
| financial_metrics | Financial statements | VLM extracts tables from Item 8 |
| segment_revenue | Segment disclosures | VLM extracts from MD&A or notes |
| geographic_revenue | Geographic disclosures | VLM extracts from MD&A or notes |
| risk_factors | Item 1A | VLM categorizes and summarizes risks |

### Expected Data Volume

| Table | Rows | Notes |
|-------|------|-------|
| companies | 7 | One per 10-K (AAPL, MSFT, AMZN, GOOGL, TSLA, JPM, NVDA) |
| financial_metrics | 14 | 2 years per company (2023, 2024) |
| segment_revenue | ~35 | ~5 segments per company |
| geographic_revenue | ~28 | ~4 regions per company |
| risk_factors | ~70 | ~10 categorized risks per company |

### SQL Tool Implementation

#### ALLOWED_TABLES Whitelist

```python
ALLOWED_TABLES = {
    "companies",
    "financial_metrics",
    "segment_revenue",
    "geographic_revenue",
    "risk_factors"
}

ALLOWED_COLUMNS = {
    "companies": ["id", "ticker", "name", "sector", "fiscal_year_end", "filing_date", "document_id"],
    "financial_metrics": ["id", "company_id", "fiscal_year", "revenue", "cost_of_revenue", "gross_profit", 
                          "operating_expenses", "operating_income", "net_income", "total_assets", 
                          "total_liabilities", "total_equity", "cash_and_equivalents", "long_term_debt",
                          "gross_margin", "operating_margin", "net_margin", "earnings_per_share", "diluted_eps"],
    "segment_revenue": ["id", "company_id", "fiscal_year", "segment_name", "revenue", "percentage_of_total", "yoy_growth"],
    "geographic_revenue": ["id", "company_id", "fiscal_year", "region", "revenue", "percentage_of_total", "yoy_growth"],
    "risk_factors": ["id", "company_id", "fiscal_year", "category", "title", "summary", "severity", "page_number"]
}
```

#### Natural Language to SQL Prompt

```
You are a SQL query generator for a 10-K financial database containing data from SEC filings.

Available tables and their purpose:
- companies: Company info (ticker, name, sector, filing dates)
- financial_metrics: Income statement, balance sheet metrics by year
- segment_revenue: Revenue breakdown by business segment
- geographic_revenue: Revenue breakdown by geographic region
- risk_factors: Categorized risk factors from Item 1A

Key columns:
- companies: ticker, name, sector, fiscal_year_end
- financial_metrics: revenue, net_income, gross_margin, operating_margin, net_margin, eps
- segment_revenue: segment_name, revenue, percentage_of_total, yoy_growth
- geographic_revenue: region, revenue, percentage_of_total, yoy_growth
- risk_factors: category, title, summary, severity

Rules:
1. Only use SELECT statements (no INSERT, UPDATE, DELETE, DROP)
2. JOIN companies table to get ticker/name when querying other tables
3. Use fiscal_year to compare years (e.g., 2024 vs 2023)
4. Limit results to 100 rows maximum
5. Use parameterized placeholders (:param_name) for user values

User query: {user_query}

Generate a safe, read-only SQL query:
```

#### Safety Checks

1. **Query validation:** Parse and validate SQL before execution
2. **Read-only enforcement:** Only allow SELECT statements
3. **Table whitelisting:** Reject queries with unlisted tables
4. **Result limits:** Cap at 1000 rows, default 100
5. **Timeout:** 30 second query timeout
6. **Parameterization:** All user values must be parameterized

### Files to Create

| File | Purpose |
|------|---------|
| `backend/alembic/versions/002_10k_schema.py` | Schema migration for 10-K tables |
| `backend/src/agent/tools/sql.py` | SQL tool implementation (upgrade stub) |
| `backend/src/agent/tools/sql_safety.py` | ALLOWED_TABLES, query validation |
| `scripts/load_10k_to_sql.py` | Script to load VLM output into PostgreSQL |

### Sample Queries the Agent Should Handle

**Financial Comparisons:**
- "Which company had the highest revenue in 2024?"
- "Compare gross margins across all tech companies"
- "What was Apple's revenue growth from 2023 to 2024?"
- "List companies by net margin, highest to lowest"

**Segment Analysis:**
- "What percentage of Apple's revenue comes from iPhone?"
- "Which company has the most diversified revenue by segment?"
- "Show me Amazon's segment revenue breakdown"

**Geographic Analysis:**
- "What percentage of Microsoft's revenue comes from outside the US?"
- "Which company has the highest exposure to Greater China?"
- "Compare geographic revenue distribution across companies"

**Risk Analysis:**
- "Which companies have supply chain risks?"
- "List all high-severity risk factors"
- "What regulatory risks does Tesla face?"
- "Compare risk factor categories across companies"

**Cross-Tool Queries (SQL + RAG):**
- "What's Apple's China revenue, and what does the 10-K say about China risks?" 
  → SQL for the number, RAG for the narrative context

---

## RAG Tool (2c) Requirements

### 2026 State-of-the-Art Architecture

The RAG implementation uses modern techniques for maximum retrieval quality.

> **Full Architecture Details:** See `docs/RAG_README.md` for comprehensive architecture documentation including enterprise features, alternatives, and in-depth explanations.

#### Retrieval Quality Techniques

| Technique | Impact | Cost |
|-----------|--------|------|
| Semantic Chunking | +10-15% relevance | $0 (ingestion time) |
| Contextual Retrieval | +15-20% precision | $0 (ingestion time) |
| Hybrid Search (Dense + BM25) | +20-30% recall | $0 |
| Query Expansion | +20-30% recall | ~$0.005/query |
| Cross-Encoder Reranking | +20-25% precision | ~$0.015/query |
| Knowledge Graph | +15-25% precision | ~$0.01/query |
| **Total Query Cost** | | **~$0.03-0.04/query** |

### Embedding Technology

| Component | Technology | Details |
|-----------|------------|---------|
| **Dense Embeddings** | AWS Bedrock Titan Embeddings | 1536 dimensions |
| **Model ID** | `amazon.titan-embed-text-v1` | Text embedding model |
| **Cost** | ~$0.0001 per 1K tokens | Very cost-effective |
| **Batch Support** | Yes | Process multiple chunks per API call |

The dense embeddings enable semantic similarity search - finding content that *means* the same thing even with different words.

### Document Types

Phase 2 uses VLM extraction for ALL documents (unified pipeline):

| Category | Documents | Extraction | Populates |
|----------|-----------|------------|-----------|
| **SEC 10-K Filings** | ~7 company 10-Ks | VLM (Claude Vision) | SQL + Pinecone + Neo4j |
| **Reference Documents** | News, research, policies | VLM (Claude Vision) | Pinecone + Neo4j |

> **Why VLM for everything?** Simpler codebase (one extraction path), consistent output format, and ~$40-60 total cost for ~30 documents is negligible for a demo. See [Why Batch Script](#why-batch-script-not-lambda) for full rationale.

### VLM Extraction for Complex Documents (10-Ks)

**Decision:** Use Vision Language Model (Claude via Bedrock) for 10-K extraction.

**Why VLM for 10-Ks:**
- Financial statements are 80%+ tables with precise alignment
- Multi-column year-over-year comparisons
- Cross-references ("See Note 12") require context understanding
- $30-50 one-time cost for ~10 documents is acceptable
- Simplest implementation (no fallback logic needed)

**VLM Extraction Process:**

```
┌─────────────────────────────────────────────────────────────────┐
│                        10-K PDF File                             │
│                    (80-150 pages typical)                        │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PDF to Images (150 DPI)                       │
│               pdf2image + Pillow for preprocessing               │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│               Claude Vision (Bedrock Claude 3.5)                 │
│                                                                  │
│  Prompt: "Extract all content from this 10-K page.               │
│           For tables, preserve structure as markdown.            │
│           Identify: section name, page type (narrative/table),   │
│           and any cross-references."                             │
│                                                                  │
│  Output: Structured JSON per page                                │
│   {                                                              │
│     "page_number": 45,                                           │
│     "section": "Item 8: Financial Statements",                   │
│     "content_type": "table",                                     │
│     "text": "...",                                               │
│     "tables": [{ "name": "Balance Sheet", "data": [...] }],     │
│     "cross_references": ["Note 12", "See Item 7"]               │
│   }                                                              │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Store Extracted JSON                          │
│              S3: s3://bucket/extracted/{doc_id}.json            │
└─────────────────────────────────────────────────────────────────┘
```

### Ingestion Pipeline Architecture (Batch Script)

```
┌─────────────────────────────────────────────────────────────────┐
│                    Local Document Folder                         │
│                ./documents/raw/*.pdf                            │
└───────────────────────────┬─────────────────────────────────────┘
                            │ python scripts/extract_and_index.py
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                Batch Extraction Script                           │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                 VLM Extraction (All Documents)            │   │
│  │           Claude Vision via Bedrock (~$0.03-0.05/page)   │   │
│  │                                                           │   │
│  │  • PDF → Images (150 DPI)                                │   │
│  │  • Each page → Claude Vision                             │   │
│  │  • Output: Structured JSON per document                  │   │
│  └──────────────────────────────────────────────────────────┘   │
│                            │                                     │
│                            ▼                                     │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                   Semantic Chunking                       │   │
│  │  • spaCy sentence boundary detection                     │   │
│  │  • Paragraph-aware splitting                              │   │
│  │  • Max chunk size: 512 tokens                            │   │
│  │  • Overlap: 50 tokens                                     │   │
│  └──────────────────────────────────────────────────────────┘   │
│                            │                                     │
│                            ▼                                     │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                Contextual Enrichment                      │   │
│  │  • Prepend: [Document: Apple 10-K 2024]                  │   │
│  │  • Add: [Section: Item 1A: Risk Factors]                 │   │
│  │  • Include: [Page: 15]                                    │   │
│  │  Format: "[Doc] [Section] [Page] {chunk}"                │   │
│  └──────────────────────────────────────────────────────────┘   │
│                            │                                     │
│          ┌─────────────────┼─────────────────┐                  │
│          ▼                 ▼                 ▼                  │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐           │
│  │ Dense Embed │   │ Sparse/BM25 │   │ NLP Entity  │           │
│  │ (Titan)     │   │ Index       │   │ Extraction  │           │
│  └──────┬──────┘   └──────┬──────┘   └──────┬──────┘           │
│         │                 │                 │                   │
│         ▼                 ▼                 ▼                   │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐           │
│  │  Pinecone   │   │  Pinecone   │   │ Neo4j       │           │
│  │  (vectors)  │   │  (sparse)   │   │ AuraDB      │           │
│  └─────────────┘   └─────────────┘   └─────────────┘           │
│                            │                                     │
│                            ▼ (10-Ks only)                       │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              SQL Data Loading (scripts/load_10k_to_sql.py)│   │
│  │            Financial metrics → Neon PostgreSQL            │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

**Key Benefits of Batch Script Approach:**
- ✅ No timeout limits (process any size document)
- ✅ One extraction path (VLM for everything)
- ✅ Easy debugging (run locally, see all logs)
- ✅ No infrastructure to maintain (no Lambda, no S3 events)

### Query Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Query                               │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Query Expansion                               │
│            (Generate 3 alternative phrasings)                    │
│                     via Nova Lite                                │
│                                                                  │
│  Original: "What is the refund policy?"                         │
│  Variant 1: "How can I get a refund?"                           │
│  Variant 2: "What are the terms for returning a product?"       │
│  Variant 3: "Refund and return procedures"                      │
└───────────────────────────┬─────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Dense Search│     │ BM25 Search │     │  KG Lookup  │
│ (Pinecone)  │     │ (Pinecone)  │     │ (Neo4j)     │
│             │     │             │     │             │
│ top_k=15    │     │ top_k=15    │     │ 1-2 hops    │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       └───────────────────┼───────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    RRF Fusion                                    │
│         (Reciprocal Rank Fusion - merge all results)            │
│                                                                  │
│  Score = Σ 1/(k + rank) for each result across all sources      │
│  k = 60 (standard constant)                                     │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                 Cross-Encoder Reranking                          │
│              (LLM scores top 15 for relevance)                   │
│                                                                  │
│  Prompt: "Rate relevance 1-10: Query: {q}, Document: {d}"       │
│  Return: top 5 highest scoring                                   │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                Contextual Compression                            │
│           (Extract only relevant portions)                       │
│                                                                  │
│  LLMChainExtractor: Keep sentences relevant to query            │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Final Results                                 │
│                                                                  │
│  • Relevant text chunks                                         │
│  • Source citations (document, page, section)                   │
│  • Confidence scores                                            │
└─────────────────────────────────────────────────────────────────┘
```

### Pinecone Index Configuration

```python
# Index specification
index_name = "enterprise-agentic-ai"
dimension = 1536  # Titan embeddings
metric = "cosine"
cloud = "aws"
region = "us-east-1"

# Metadata fields to store
metadata_fields = [
    "document_id",      # Unique document identifier
    "document_title",   # Document title
    "document_type",    # policy, regulation, faq, product_doc
    "section",          # Section header if available
    "page_number",      # Page number for PDFs
    "chunk_index",      # Position within document
    "created_date",     # Document creation date
    "source_url",       # S3 URL for source
]

# Sparse vector for hybrid search
# Uses Pinecone's built-in sparse-dense hybrid
```

### Files to Create

| File | Purpose |
|------|---------|
| **Extraction Pipeline** | |
| `backend/src/ingestion/document_processor.py` | Main document processing orchestrator |
| `backend/src/ingestion/vlm_extractor.py` | Claude Vision extraction for ALL documents |
| **Chunking & Enrichment** | |
| `backend/src/ingestion/semantic_chunking.py` | spaCy-based semantic chunking |
| `backend/src/ingestion/contextual_chunking.py` | Context prepending for chunks |
| `backend/src/ingestion/chunking.py` | Parent document retriever pattern |
| **Query Pipeline** | |
| `backend/src/ingestion/query_expansion.py` | Query expansion via LLM |
| `backend/src/utils/embeddings.py` | Bedrock Titan embedding wrapper |
| `backend/src/utils/rrf.py` | Reciprocal Rank Fusion implementation |
| `backend/src/utils/reranker.py` | Cross-encoder reranking |
| **Tool Integration** | |
| `backend/src/agent/tools/rag.py` | RAG tool (upgrade from stub) |
| **Scripts** | |
| `scripts/extract_and_index.py` | Main batch script: extract → chunk → index |
| `scripts/load_10k_to_sql.py` | Load 10-K financial metrics to PostgreSQL |

> **Note:** All extraction runs via batch script, not Lambda. This keeps the codebase simple and avoids timeout issues. See [Why Batch Script](#why-batch-script-not-lambda) for rationale and [Enterprise Scaling](#enterprise-scaling-future) for how to add auto-ingestion later.

---

## Knowledge Graph (2c-KG) Requirements

### Neo4j AuraDB Setup

| Attribute | Value |
|-----------|-------|
| Service | Neo4j AuraDB Free |
| Node Limit | 200,000 |
| Relationship Limit | 400,000 |
| Cost | $0/month |
| Region | Should match us-east-1 if available |

### Local Development

```yaml
# docker-compose.yml addition
services:
  neo4j:
    image: neo4j:5-community
    ports:
      - "7474:7474"  # HTTP
      - "7687:7687"  # Bolt
    environment:
      - NEO4J_AUTH=neo4j/localdevpassword
      - NEO4J_PLUGINS=["apoc"]
    volumes:
      - neo4j_data:/data
```

### Financial Domain Ontology

#### Entity Types

```
┌─────────────────────────────────────────────────────────────────┐
│                        ENTITY TYPES                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Document ─────── Source document in RAG system                 │
│     │              (PDF, policy, FAQ, etc.)                     │
│     │                                                            │
│  Policy ─────────  Company policy or procedure                  │
│     │              (refund policy, privacy policy)              │
│     │                                                            │
│  Regulation ─────  External regulation or law                   │
│     │              (SEC, FINRA, GDPR)                           │
│     │                                                            │
│  Concept ────────  Financial concept or term                    │
│     │              (APR, compound interest, ETF)                │
│     │                                                            │
│  Product ────────  Financial product                            │
│     │              (checking account, credit card)              │
│     │                                                            │
│  Person ─────────  Named person mentioned                       │
│     │              (executives, contacts)                        │
│     │                                                            │
│  Organization ───  Company or institution                       │
│                    (partner banks, regulators)                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### Relationship Types

```
┌─────────────────────────────────────────────────────────────────┐
│                     RELATIONSHIP TYPES                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  MENTIONS ────────  Document mentions an entity                 │
│                     (Document)-[:MENTIONS]->(Entity)            │
│                                                                  │
│  DEFINES ─────────  Document defines a concept                  │
│                     (Document)-[:DEFINES]->(Concept)            │
│                                                                  │
│  GOVERNED_BY ─────  Entity governed by regulation               │
│                     (Product)-[:GOVERNED_BY]->(Regulation)      │
│                                                                  │
│  APPLIES_TO ──────  Policy applies to product/customer          │
│                     (Policy)-[:APPLIES_TO]->(Product)           │
│                                                                  │
│  RELATED_TO ──────  Generic relationship between entities       │
│                     (Entity)-[:RELATED_TO]->(Entity)            │
│                                                                  │
│  SIMILAR_TO ──────  Concept similarity                          │
│                     (Concept)-[:SIMILAR_TO]->(Concept)          │
│                                                                  │
│  SUPERSEDES ──────  Newer policy replaces older                 │
│                     (Policy)-[:SUPERSEDES]->(Policy)            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### NLP Entity Extraction (spaCy-based)

Using spaCy instead of LLM for cost efficiency:

```python
# spaCy NER entity types to extract
SPACY_ENTITY_TYPES = [
    "PERSON",      # People, including fictional
    "ORG",         # Companies, agencies, institutions
    "GPE",         # Countries, cities, states
    "DATE",        # Dates or periods
    "MONEY",       # Monetary values
    "PERCENT",     # Percentages
    "LAW",         # Named documents made into laws
    "PRODUCT",     # Objects, vehicles, foods, etc.
]

# Custom patterns for financial domain
FINANCIAL_PATTERNS = [
    {"label": "REGULATION", "pattern": [{"TEXT": {"REGEX": r"(SEC|FINRA|FDIC|OCC|CFPB)"}}]},
    {"label": "PRODUCT", "pattern": [{"LOWER": {"IN": ["checking", "savings", "credit", "debit"]}}, {"LOWER": {"IN": ["account", "card"]}}]},
    {"label": "CONCEPT", "pattern": [{"LOWER": {"IN": ["apr", "apy", "interest", "fee", "balance"]}}]},
]
```

### Cost Comparison

| Method | Cost per Document | 1000 Documents |
|--------|-------------------|----------------|
| LLM-based extraction | $0.02-0.05 | $20-50 |
| spaCy NLP extraction | ~$0.001 | ~$1 |
| **Savings** | **95-98%** | **$19-49** |

### Files to Create

| File | Purpose |
|------|---------|
| `backend/src/knowledge_graph/__init__.py` | Package exports |
| `backend/src/knowledge_graph/efficient_extractor.py` | spaCy NER + custom patterns |
| `backend/src/knowledge_graph/store.py` | Neo4j connection and CRUD |
| `backend/src/knowledge_graph/ontology.py` | Entity and relationship types |
| `backend/src/knowledge_graph/queries.py` | Graph traversal queries |

---

---

## Data Lifecycle Management

### SQL Data Management (from 10-K VLM Extraction)

```
┌─────────────────────────────────────────────────────────────────┐
│                    SQL DATA LIFECYCLE                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Initial Setup (Phase 2a):                                       │
│  1. Run VLM extraction: scripts/extract_10k.py                  │
│  2. Run Alembic migration: 002_10k_schema.py                    │
│  3. Load extracted data: scripts/load_10k_to_sql.py             │
│  4. Verify: SELECT COUNT(*) FROM each table                     │
│                                                                  │
│  Adding New 10-Ks:                                               │
│  1. Download new 10-K PDF                                       │
│  2. Run VLM extraction script                                   │
│  3. Run SQL load script                                         │
│  (Manual process - 10-Ks are annual, infrequent)               │
│                                                                  │
│  Reset/Refresh:                                                  │
│  1. alembic downgrade base                                       │
│  2. alembic upgrade head                                         │
│  3. Re-run load script                                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### RAG Document Management

```
┌─────────────────────────────────────────────────────────────────┐
│                  RAG DOCUMENT LIFECYCLE                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Document Processing (Batch Script):                            │
│  1. Place document in ./documents/raw/                          │
│  2. Run: python scripts/extract_and_index.py                    │
│  3. VLM extracts structured content                             │
│  4. Chunks embedded via Bedrock Titan                           │
│  5. Vectors stored in Pinecone                                  │
│  6. Entities extracted and stored in Neo4j                      │
│                                                                  │
│  Supported Formats:                                              │
│  • PDF (.pdf) - VLM extraction for all                          │
│  • Text (.txt) - direct text processing                         │
│  • Markdown (.md) - rendered then processed                     │
│                                                                  │
│  Document Update:                                                │
│  1. Replace file in ./documents/raw/                            │
│  2. Re-run extraction script                                    │
│  3. Script deletes old vectors by document_id                   │
│  4. Re-processes and re-indexes                                 │
│                                                                  │
│  Document Delete:                                                │
│  1. Delete file from ./documents/raw/                           │
│  2. Run cleanup script: python scripts/cleanup_document.py      │
│  3. Removes vectors from Pinecone by document_id                │
│  4. Removes KG nodes from Neo4j by document_id                  │
│                                                                  │
│  Metadata Storage (Pinecone):                                   │
│  • document_id, title, type, section, page, chunk_index         │
│  • Enables filtering: type="10k", company="AAPL"                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Knowledge Graph Management

```
┌─────────────────────────────────────────────────────────────────┐
│               KNOWLEDGE GRAPH LIFECYCLE                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Auto-Population:                                                │
│  • Entities extracted during document ingestion                 │
│  • Relationships inferred from co-occurrence                    │
│  • No manual maintenance required                               │
│                                                                  │
│  Entity Deduplication:                                          │
│  • Fuzzy matching on entity names (Levenshtein distance)        │
│  • Merge similar entities (e.g., "SEC" and "S.E.C.")           │
│  • Canonical name resolution                                    │
│                                                                  │
│  Relationship Inference:                                        │
│  • Co-occurrence: entities in same chunk = RELATED_TO          │
│  • Pattern-based: "governed by" → GOVERNED_BY                   │
│  • Temporal: newer policy → SUPERSEDES older                    │
│                                                                  │
│  Graph Queries:                                                  │
│  • 1-hop: Find all documents mentioning entity X                │
│  • 2-hop: Find entities related to entities in query            │
│  • Path: Find connection between two entities                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Infrastructure Requirements

### New AWS Resources (Minimal)

| Resource | Purpose | Cost Estimate |
|----------|---------|---------------|
| S3 Bucket (optional) | Extracted JSON storage | ~$0.10/month |

> **Note:** For this demo, documents are processed locally via batch script. No Lambda infrastructure is needed. S3 is optional for storing extracted JSON output, but local files work fine.

### Local Processing Requirements

| Requirement | Purpose |
|-------------|---------|
| Python 3.11+ | Batch script runtime |
| Poppler | PDF to image conversion (`apt-get install poppler-utils`) |
| 8GB+ RAM | Claude Vision API calls + spaCy model |
| Internet | Bedrock, Pinecone, Neo4j API calls |

### External Services Setup

#### Pinecone (Free Tier)

1. Create account at https://pinecone.io
2. Create serverless index:
   - Name: `enterprise-agentic-ai`
   - Dimensions: 1536
   - Metric: cosine
   - Cloud: AWS
   - Region: us-east-1
3. Copy API key to `.env` and Secrets Manager

#### Neo4j AuraDB (Free Tier)

1. Create account at https://neo4j.com/cloud/aura-free/
2. Create free instance:
   - Name: `enterprise-agentic-ai`
   - Region: Closest to us-east-1
3. Note connection URI, username, password
4. Add to `.env` and Secrets Manager

### New Environment Variables

```bash
# Add to .env.example and Secrets Manager

# Pinecone (Vector Store)
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_INDEX_NAME=enterprise-agentic-ai
PINECONE_ENVIRONMENT=us-east-1  # or gcp-starter for free

# Neo4j (Knowledge Graph)
NEO4J_URI=neo4j+s://xxxxx.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_neo4j_password

# Document Storage
DOCUMENTS_BUCKET_NAME=enterprise-agentic-ai-documents-xxxxx
```

### New Python Dependencies

Add to `backend/requirements.txt`:

```bash
# =============================================================================
# Document Processing (Phase 2)
# =============================================================================
pdf2image~=1.17.0           # Convert PDF pages to images for VLM
Pillow~=10.4.0              # Image processing
python-magic~=0.4.27        # File type detection (optional)
pinecone-client~=3.0.0      # Vector store
neo4j~=5.15.0               # Knowledge graph

# Note: pdf2image requires poppler-utils system package
# Dockerfile: apt-get install -y poppler-utils
# Local: apt-get install poppler-utils (Ubuntu) or brew install poppler (Mac)
```

### Docker Compose Updates

Add Neo4j for local development:

```yaml
# Add to docker-compose.yml
services:
  # ... existing services ...
  
  neo4j:
    image: neo4j:5-community
    ports:
      - "7474:7474"  # HTTP browser
      - "7687:7687"  # Bolt protocol
    environment:
      - NEO4J_AUTH=neo4j/localdevpassword
      - NEO4J_PLUGINS=["apoc"]
    volumes:
      - neo4j_data:/data
    healthcheck:
      test: ["CMD", "wget", "-q", "--spider", "http://localhost:7474"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  neo4j_data:
```

### Backend Dockerfile Updates

Add system dependencies for PDF processing:

```dockerfile
# Add to backend/Dockerfile.dev and backend/Dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Download spaCy model
RUN python -m spacy download en_core_web_sm
```

---

## Sample Data Strategy

### SQL Sample Data (Faker-generated)

```python
# Seed data generation approach
from faker import Faker
import random

fake = Faker()

# Customers: 500 with realistic names, emails
customers = [
    {
        "name": fake.name(),
        "email": fake.email(),
        "phone": fake.phone_number(),
        "risk_profile": random.choice(["conservative", "moderate", "aggressive"]),
        "status": random.choice(["active"] * 9 + ["inactive"])  # 90% active
    }
    for _ in range(500)
]

# Accounts: ~3 per customer
# Transactions: ~20 per account over 12 months
# Portfolios: Only for aggressive/moderate customers
# Trades: Random stock trades (AAPL, MSFT, GOOGL, AMZN, TSLA, META, NVDA)
```

### RAG Sample Documents

#### SEC 10-K Filings (VLM Extracted)

| Company | Ticker | Fiscal Year | Pages | Why Included |
|---------|--------|-------------|-------|--------------|
| Apple Inc. | AAPL | 2024 | ~85 | Tech, supply chain, China exposure |
| Microsoft | MSFT | 2024 | ~100 | Cloud, AI, enterprise software |
| Amazon | AMZN | 2024 | ~90 | E-commerce, AWS, logistics |
| Google (Alphabet) | GOOGL | 2024 | ~110 | Advertising, AI, antitrust |
| Tesla | TSLA | 2024 | ~120 | EV, manufacturing, Elon risk |
| JPMorgan Chase | JPM | 2024 | ~150 | Banking, credit, regulations |
| Nvidia | NVDA | 2024 | ~95 | AI chips, supply chain |
| **Total** | | | **~750 pages** | **~$25-40 extraction cost** |

**10-K Source:** Download from SEC EDGAR at https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany

**Primary Use Case:** 
- "What are Apple's supply chain risks?"
- "How did Microsoft's cloud revenue change?"
- "Compare gross margins across tech companies"
- "Does this news align with what the company disclosed?"

#### Reference Documents (VLM Extraction)

| Category | Documents | Description |
|----------|-----------|-------------|
| News Articles | 5-10 | Financial news about portfolio companies |
| Research Reports | 3-5 | Analyst reports, market analysis |
| **Total** | **~10-15** | **~$5-10 VLM extraction cost** |

Sample reference document examples:
- `aapl-earnings-news-2024.pdf` - Apple earnings coverage
- `ai-chip-market-analysis.pdf` - Semiconductor industry analysis  
- `ev-market-outlook.pdf` - Electric vehicle market trends
- `tech-regulation-update.pdf` - Regulatory developments
- `china-trade-impact.pdf` - China trade policy analysis

> **Note:** All documents use VLM extraction for consistency. The cost difference is negligible (~$0.10-0.15 per news article vs $0 for pdfplumber) but we gain a single, simpler codebase.

---

## Cost Estimates

### Phase 2 One-Time Costs

| Component | Cost | Notes |
|-----------|------|-------|
| **VLM 10-K Extraction** | ~$25-40 | ~750 pages × $0.03-0.05/page (Claude Vision) |
| **spaCy model download** | $0 | en_core_web_sm (~15MB) |
| **Total One-Time** | **~$25-40** | |

### Phase 2 Additional Monthly Costs

| Component | Monthly Cost | Notes |
|-----------|--------------|-------|
| Pinecone Free | $0 | 100K vectors included |
| Neo4j AuraDB Free | $0 | 200K nodes included |
| S3 (optional) | ~$0.10 | Extracted JSON storage only |
| Bedrock embeddings | ~$1-3 | ~$0.0001/1K tokens |
| Bedrock reranking | ~$0.50-1 | ~$0.015/query × queries |
| **Total Phase 2 Addition** | **~$2-4/month** | |

> **Note:** No Lambda costs because we use local batch scripts for document processing.

### Running Total

| Phase | One-Time | Monthly Cost |
|-------|----------|--------------|
| Phase 1b (current) | - | ~$10-25 |
| Phase 2 additions | ~$25-40 | ~$2-5 |
| **Total** | **~$25-40** | **~$12-30** |

Still well under the $50/month target! VLM extraction is a one-time cost.

---

## Success Criteria

### Phase 2a: Data Foundation & Basic Tools

**VLM Extraction:**
- [ ] VLM extraction script runs successfully on 7 10-K PDFs
- [ ] Extracted JSON contains financial metrics, segments, risks
- [ ] Table structure preserved in extraction output

**SQL Tool:**
- [ ] 10-K schema deployed to Neon PostgreSQL
- [ ] 10-K data loaded (7 companies, ~150 rows total)
- [ ] Natural language queries return correct SQL
- [ ] ALLOWED_TABLES whitelist enforced
- [ ] "Which company had highest revenue?" returns correct answer

**Basic RAG Tool:**
- [ ] Pinecone index created and populated
- [ ] 10-K text chunks indexed with metadata
- [ ] Dense vector search returns relevant results
- [ ] "What are Apple's supply chain risks?" returns relevant passages
- [ ] Source citations include document and page number

**Phase 2a Exit Test:**
- [ ] Agent answers: "Compare gross margins across tech companies" (SQL)
- [ ] Agent answers: "What does Microsoft say about AI competition?" (RAG)

---

### Phase 2b: Advanced Features & Automation

**Knowledge Graph:**
- [ ] Neo4j AuraDB connected and working
- [ ] spaCy extracts entities from documents
- [ ] Entities stored in graph with relationships
- [ ] 1-hop queries return relevant documents
- [ ] 2-hop traversal finds related entities

**Advanced RAG:**
- [ ] Hybrid search (dense + BM25) works
- [ ] Query expansion generates 3 variants
- [ ] RRF fusion merges results correctly
- [ ] Cross-encoder reranking improves relevance
- [ ] Knowledge Graph enhances retrieval

**Automatic Ingestion:**
- [ ] S3 bucket created with event trigger
- [ ] Lambda function deployed and working
- [ ] Upload simple PDF → automatically indexed
- [ ] New document queryable within 2 minutes

**Phase 2b Exit Test:**
- [ ] Upload new policy PDF → query it immediately
- [ ] "What's Apple's China revenue and what risks do they disclose about China?" (SQL + RAG combined)

---

### Integration (Both Phases)

- [ ] All tools registered in LangGraph agent
- [ ] Agent selects appropriate tool for query
- [ ] Multi-tool queries work (SQL + RAG combined)
- [ ] Streaming responses include tool usage
- [ ] Error recovery handles tool failures gracefully

### Quality Metrics (Deferred to Phase 4)

**Note:** RAGAS evaluation and Arize Phoenix tracing are implemented in Phases 3-4, not Phase 2. Phase 2 focuses on functional tool implementation.

Phase 2 quality validation:
- [ ] Manual testing of RAG retrieval quality
- [ ] Spot-check 10-K extraction accuracy (tables preserved)
- [ ] Verify entity extraction captures key entities

Phase 4 automated metrics (for reference):
- [ ] RAGAS Faithfulness > 0.7
- [ ] RAGAS Answer Relevancy > 0.7
- [ ] RAGAS Context Precision > 0.7
- [ ] RAGAS Context Recall > 0.7

---

## Implementation Order

### Phase 2a: Data Foundation & Basic Tools

**Goal:** Get data extracted, loaded, and basic queries working

#### Step 1: External Services Setup
1. Create Pinecone index (free tier, via console)
2. Create Neo4j AuraDB instance (free tier, via console)
3. Add Neo4j to docker-compose for local dev
4. Add new environment variables to `.env.example`

#### Step 2: Document Extraction Pipeline
1. Add PDF processing dependencies (`pdf2image`, `Pillow`)
2. Update Dockerfile with `poppler-utils`, spaCy model download
3. Implement VLM extractor (`backend/src/ingestion/vlm_extractor.py`)
4. Create unified extraction script (`scripts/extract_and_index.py`)
5. Download 7 SEC 10-K filings from EDGAR
6. Run VLM extraction → structured JSON output
7. Test with a few reference documents (news articles, policies)

#### Step 3: SQL Tool with 10-K Data
1. Create Alembic migration for 10-K schema (`002_10k_schema.py`)
2. Create script to load VLM JSON → PostgreSQL (`scripts/load_10k_to_sql.py`)
3. Implement SQL tool with safety checks (`ALLOWED_TABLES`)
4. Test natural language to SQL queries
5. Integrate with LangGraph agent

#### Step 4: Basic RAG Tool
1. Implement Bedrock Titan embeddings wrapper
2. Implement semantic chunking (spaCy)
3. Implement contextual enrichment
4. Integrate indexing into `scripts/extract_and_index.py`
5. Index extracted document chunks to Pinecone
6. Implement basic RAG tool (dense search only)
7. Test retrieval queries

**Phase 2a Exit Criteria:**
- [ ] SQL tool answers "Which company had highest revenue?"
- [ ] RAG tool answers "What are Apple's supply chain risks?"
- [ ] Both tools integrated in agent

---

### Phase 2b: Advanced Features & Intelligence

**Goal:** Add retrieval intelligence and multi-tool orchestration

#### Step 5: Knowledge Graph
1. Implement spaCy entity extractor with financial patterns
2. Implement Neo4j graph store adapter
3. Create entity indexing script
4. Index entities from all documents
5. Implement graph queries (1-2 hop)

#### Step 6: Advanced RAG Features
1. Add BM25 sparse vectors (Pinecone hybrid search)
2. Implement RRF fusion algorithm
3. Add query expansion (3 variants via Nova Lite)
4. Implement cross-encoder reranking
5. Integrate Knowledge Graph lookup into retrieval pipeline
6. Update RAG tool with full hybrid retrieval

#### Step 7: Integration & Testing
1. Register all upgraded tools in agent
2. End-to-end testing (chat → tool → response)
3. Test multi-tool queries (SQL + RAG combined)
4. Test streaming with tool results
5. Documentation and cleanup

**Phase 2b Exit Criteria:**
- [ ] Hybrid search (dense + BM25 + KG) returns better results
- [ ] Knowledge graph enhances entity queries
- [ ] Multi-tool queries work (SQL + RAG combined)
- [ ] "Compare Apple's China revenue to their disclosed risks" works

---

**Note:** RAGAS evaluation setup deferred to Phase 4. Phase 2 focuses on functional tools.

---

## Design Decisions (Resolved)

These decisions have been made based on project requirements and RAG README analysis.

### Document Extraction

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **All document extraction** | VLM (Claude Vision via Bedrock) | One code path, consistent output, best quality, acceptable cost (~$50) |
| **Execution method** | Local batch script | No timeout limits, easy debugging, no infrastructure needed |
| **Not using pdfplumber** | Intentional | Adds code complexity for minimal cost savings |
| **Not using Lambda** | Intentional | Timeout issues, harder debugging, unnecessary for demo |

### RAG Architecture

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Chunk size** | 512 tokens, 50 overlap | Standard best practice, tune via RAGAS |
| **Reranking model** | Nova Lite via Bedrock | Cost-effective, simplifies deployment |
| **Parent document retriever** | Contextual enrichment only | Simpler, captures most benefit |
| **Vector store** | Pinecone Serverless (free tier) | Managed, hybrid search built-in |

### Knowledge Graph

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Graph database** | Neo4j AuraDB Free | Free tier, native graph queries, better than pgvector |
| **Entity extraction** | spaCy NER + custom patterns | 20-50x cheaper than LLM extraction |
| **Entity deduplication** | Levenshtein distance ≤ 2 | Balance between matching and false positives |

### SQL Tool

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Read-only enforcement** | Query validation + ALLOWED_TABLES | Simpler than separate DB user |
| **Query explanation** | Include in response | Transparency for users |

### Infrastructure

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Document processing** | Local batch script | No Lambda complexity, no timeouts |
| **Neo4j local** | Docker (neo4j:5-community) | Match AuraDB version |
| **S3 usage** | Optional (for JSON output) | Local files work fine for demo |

### Future Phases (Not Phase 2)

| Feature | Phase | Notes |
|---------|-------|-------|
| Arize Phoenix tracing | Phase 3 | Already in PROJECT_PLAN.md |
| RAGAS evaluation | Phase 4 | Golden dataset + automated eval |
| Input/Output verification | Phase 6 | Nova Lite guardrails |
| Inference caching | Phase 7 | DynamoDB cache |

---

## Enterprise Scaling (Future)

> **This section documents how to scale document ingestion for production.** These features are NOT implemented in Phase 2, but are documented here for reference and future implementation.

### When You Need Auto-Ingestion

| Scenario | Our Demo Approach | Enterprise Need |
|----------|-------------------|-----------------|
| Document volume | ~30 documents total | 1000s of documents |
| Update frequency | Monthly/quarterly | Daily/continuous |
| Team size | Single developer | Multiple teams uploading |
| Processing control | You decide when | Users upload anytime |

### Architecture: Lambda Auto-Ingestion

For enterprise workloads, add automatic ingestion via S3 → Lambda:

```
┌─────────────────────────────────────────────────────────────────┐
│                    S3 Document Bucket                            │
│         s3://enterprise-agentic-ai-documents-{env}/             │
│                                                                  │
│  /raw/           - Original uploaded documents                  │
│  /extracted/     - Extraction output (JSON)                     │
│  /processed/     - Processing status/logs                       │
└───────────────────────────┬─────────────────────────────────────┘
                            │ S3 Event (ObjectCreated)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              Lambda: document-ingestion-handler                  │
│                                                                  │
│  Timeout: 60 seconds (for simple docs)                          │
│  Memory: 1GB (for spaCy model)                                  │
│                                                                  │
│  Process:                                                        │
│  1. Download document from S3                                   │
│  2. Detect document type                                        │
│  3. Simple docs: pdfplumber extraction                          │
│  4. Complex docs: Queue for batch processing                    │
│  5. Chunk, embed, index to Pinecone                            │
│  6. Extract entities to Neo4j                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Tiered Extraction Strategy

| Document Type | Detection | Extraction Method | Timing |
|---------------|-----------|-------------------|--------|
| **Simple** (< 20 pages, text-heavy) | Page count, text density | pdfplumber | Lambda (real-time) |
| **Complex** (tables, forms, 10-Ks) | Filename pattern, heuristics | VLM | Step Functions (async) |
| **Large** (> 50 pages) | Page count | Chunked VLM | Step Functions (async) |

### Lambda Function Specification

| Attribute | Value |
|-----------|-------|
| Runtime | Python 3.11 |
| Handler | `handler.lambda_handler` |
| Timeout | 60 seconds |
| Memory | 1024 MB |
| Trigger | S3 ObjectCreated events |
| Layers | spaCy model layer |

### Terraform Resources to Create

```
terraform/modules/
├── documents-s3/
│   ├── main.tf           # S3 bucket
│   ├── notifications.tf  # Lambda trigger
│   ├── variables.tf
│   └── outputs.tf
└── document-lambda/
    ├── main.tf           # Lambda function
    ├── iam.tf            # Permissions
    ├── layer.tf          # spaCy layer
    ├── variables.tf
    └── outputs.tf
```

### Cost Impact

| Component | Demo (Batch) | Enterprise (Lambda) |
|-----------|--------------|---------------------|
| Lambda | $0 | ~$0.10-1/month |
| S3 | ~$0.10/month | ~$1-5/month |
| Step Functions | $0 | ~$0.50/month |
| Total Infrastructure | **~$0.10** | **~$2-7/month** |

### Why We Don't Need This for Demo

1. **Low volume:** ~30 documents vs thousands
2. **Controlled timing:** We decide when to add documents
3. **Simpler debugging:** Local scripts easier than CloudWatch
4. **Cost savings:** Minor, but removes infrastructure complexity
5. **Faster iteration:** No deploy cycle for extraction changes

### When to Implement

Add Lambda auto-ingestion when:
- [ ] Users need to upload documents directly
- [ ] Document volume exceeds ~100/month
- [ ] Multiple team members need to add documents
- [ ] Real-time indexing becomes a requirement

---

## References

### Project Documentation
- [PROJECT_PLAN.md](../PROJECT_PLAN.md) - Phase 2 section, overall architecture
- [DEVELOPMENT_REFERENCE.md](../DEVELOPMENT_REFERENCE.md) - Phase 2 tech specs
- [RAG_README.md](./RAG_README.md) - **RAG architecture deep-dive, alternatives, enterprise features**

### Cursor Rules
- [backend.mdc](../.cursor/rules/backend.mdc) - Python patterns
- [agent.mdc](../.cursor/rules/agent.mdc) - LangGraph patterns
- [_security.mdc](../.cursor/rules/_security.mdc) - SQL safety patterns
- [infrastructure.mdc](../.cursor/rules/infrastructure.mdc) - Terraform patterns

### External Resources
- [Anthropic: Contextual Retrieval](https://www.anthropic.com/news/contextual-retrieval) - Technique we're using
- [Pinecone Hybrid Search](https://docs.pinecone.io/docs/hybrid-search) - Dense + sparse vectors
- [SEC EDGAR](https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany) - 10-K download source

---

*This document will be used as the basis for PHASE_2_HOW_TO_GUIDE.md*
