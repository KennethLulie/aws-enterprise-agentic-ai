# Phase 2: Core Agent Tools - Requirements Planning Document

> **Status:** Planning Document (Pre-Implementation)
> **Created:** 2026-01-13
> **Purpose:** Capture all detailed requirements before creating PHASE_2_HOW_TO_GUIDE.md

**This is a temporary planning document.** Once the how-to guide is created and Phase 2 is complete, this file should be archived or deleted.

---

## Table of Contents

- [Phase 2 Scope Summary](#phase-2-scope-summary)
- [SQL Tool (2b) Requirements](#sql-tool-2b-requirements)
- [RAG Tool (2c) Requirements](#rag-tool-2c-requirements)
- [Knowledge Graph (2c-KG) Requirements](#knowledge-graph-2c-kg-requirements)
- [Data Lifecycle Management](#data-lifecycle-management)
- [Infrastructure Requirements](#infrastructure-requirements)
- [Sample Data Strategy](#sample-data-strategy)
- [Cost Estimates](#cost-estimates)
- [Success Criteria](#success-criteria)
- [Implementation Order](#implementation-order)
- [Open Questions](#open-questions)

---

## Phase 2 Scope Summary

| Tool | Status | Description |
|------|--------|-------------|
| **2a. Tavily Search** | ✅ DONE (Phase 0) | Web search with mock fallback |
| **2b. SQL Query** | 🚧 TO IMPLEMENT | Natural language to SQL with Neon PostgreSQL |
| **2c. RAG Document** | 🚧 TO IMPLEMENT | Hybrid search with Pinecone + 2026 SOTA techniques |
| **2c-KG. Knowledge Graph** | 🚧 TO IMPLEMENT | Neo4j AuraDB with NLP entity extraction |
| **2d. Market Data** | ✅ DONE (Phase 0) | FMP API with mock fallback |

**Focus for Phase 2:** Implementing 2b (SQL), 2c (RAG), and 2c-KG (Knowledge Graph)

---

## SQL Tool (2b) Requirements

### Database Schema Design

The SQL tool uses the existing Neon PostgreSQL database from Phase 1b. We need to create the financial demo schema and seed it with realistic synthetic data.

#### Tables

```sql
-- Customers table
CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(20),
    risk_profile VARCHAR(20) CHECK (risk_profile IN ('conservative', 'moderate', 'aggressive')),
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'suspended'))
);

-- Accounts table
CREATE TABLE accounts (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    account_number VARCHAR(20) UNIQUE NOT NULL,
    account_type VARCHAR(20) CHECK (account_type IN ('checking', 'savings', 'investment', 'credit')),
    balance DECIMAL(15, 2) DEFAULT 0.00,
    currency VARCHAR(3) DEFAULT 'USD',
    opened_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'closed', 'frozen'))
);

-- Transactions table
CREATE TABLE transactions (
    id SERIAL PRIMARY KEY,
    account_id INTEGER REFERENCES accounts(id),
    amount DECIMAL(15, 2) NOT NULL,
    transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    type VARCHAR(20) CHECK (type IN ('debit', 'credit', 'transfer')),
    description VARCHAR(255),
    category VARCHAR(50),
    reference_number VARCHAR(50)
);

-- Portfolios table
CREATE TABLE portfolios (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    name VARCHAR(100) NOT NULL,
    total_value DECIMAL(15, 2) DEFAULT 0.00,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    risk_level VARCHAR(20) CHECK (risk_level IN ('low', 'medium', 'high'))
);

-- Trades table
CREATE TABLE trades (
    id SERIAL PRIMARY KEY,
    portfolio_id INTEGER REFERENCES portfolios(id),
    symbol VARCHAR(10) NOT NULL,
    quantity INTEGER NOT NULL,
    price DECIMAL(10, 4) NOT NULL,
    trade_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    trade_type VARCHAR(10) CHECK (trade_type IN ('buy', 'sell')),
    status VARCHAR(20) DEFAULT 'completed' CHECK (status IN ('pending', 'completed', 'cancelled'))
);

-- Indexes for common queries
CREATE INDEX idx_transactions_account_id ON transactions(account_id);
CREATE INDEX idx_transactions_date ON transactions(transaction_date);
CREATE INDEX idx_accounts_customer_id ON accounts(customer_id);
CREATE INDEX idx_trades_portfolio_id ON trades(portfolio_id);
CREATE INDEX idx_trades_symbol ON trades(symbol);
```

### Sample Data Volume

| Table | Row Count | Generation Strategy |
|-------|-----------|---------------------|
| customers | ~500 | Faker names, emails, varied risk profiles |
| accounts | ~1,500 | 3 accounts per customer average |
| transactions | ~10,000 | Random transactions over 12 months |
| portfolios | ~200 | Investment customers only |
| trades | ~5,000 | Stock trades (AAPL, MSFT, GOOGL, AMZN, etc.) |

### SQL Tool Implementation

#### ALLOWED_TABLES Whitelist

```python
ALLOWED_TABLES = {
    "customers",
    "accounts", 
    "transactions",
    "portfolios",
    "trades"
}

ALLOWED_COLUMNS = {
    "customers": ["id", "name", "email", "phone", "risk_profile", "created_date", "status"],
    "accounts": ["id", "customer_id", "account_number", "account_type", "balance", "currency", "opened_date", "status"],
    "transactions": ["id", "account_id", "amount", "transaction_date", "type", "description", "category", "reference_number"],
    "portfolios": ["id", "customer_id", "name", "total_value", "last_updated", "risk_level"],
    "trades": ["id", "portfolio_id", "symbol", "quantity", "price", "trade_date", "trade_type", "status"]
}
```

#### Natural Language to SQL Prompt

```
You are a SQL query generator for a financial database.

Available tables and columns:
- customers: id, name, email, phone, risk_profile, created_date, status
- accounts: id, customer_id, account_number, account_type, balance, currency, opened_date, status
- transactions: id, account_id, amount, transaction_date, type, description, category, reference_number
- portfolios: id, customer_id, name, total_value, last_updated, risk_level
- trades: id, portfolio_id, symbol, quantity, price, trade_date, trade_type, status

Rules:
1. Only use SELECT statements (no INSERT, UPDATE, DELETE, DROP, etc.)
2. Only query the tables listed above
3. Use proper JOINs when relating tables
4. Limit results to 100 rows maximum
5. Use parameterized placeholders (:param_name) for any user-provided values

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
| `backend/alembic/versions/002_financial_schema.py` | Schema migration |
| `backend/alembic/versions/003_seed_data.py` | Seed data migration with Faker |
| `backend/src/agent/tools/sql.py` | SQL tool implementation (upgrade stub) |
| `backend/src/agent/tools/sql_safety.py` | ALLOWED_TABLES, query validation |

### Sample Queries the Agent Should Handle

- "What's the total balance for customer John Doe?"
- "Show me all transactions over $1000 last month"
- "Which customers have investment accounts?"
- "What's the portfolio value for customer ID 123?"
- "Show me all trades for AAPL in the last 30 days"
- "List the top 10 customers by total account balance"
- "How many transactions happened yesterday?"
- "What's the average trade size for MSFT?"

---

## RAG Tool (2c) Requirements

### 2026 State-of-the-Art Architecture

The RAG implementation uses modern techniques for maximum retrieval quality:

| Technique | Impact | Cost |
|-----------|--------|------|
| Semantic Chunking | +10-15% relevance | $0 (ingestion time) |
| Contextual Retrieval | +15-20% precision | $0 (ingestion time) |
| Hybrid Search (Dense + BM25) | +20-30% recall | $0 |
| Query Expansion | +20-30% recall | ~$0.005/query |
| Cross-Encoder Reranking | +20-25% precision | ~$0.015/query |
| Knowledge Graph | +15-25% precision | ~$0.01/query |
| **Total Query Cost** | | **~$0.03-0.04/query** |

### Ingestion Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        S3 Document Upload                        │
│                    (PDF, TXT, MD, HTML)                          │
└───────────────────────────┬─────────────────────────────────────┘
                            │ S3 Event Notification
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Lambda: Document Ingestion                    │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                   Document Processor                      │   │
│  │  • PDF parsing (PyPDF2 or pdfplumber)                    │   │
│  │  • Text extraction                                        │   │
│  │  • Metadata extraction (title, author, date, type)       │   │
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
│  │  • Prepend document title                                 │   │
│  │  • Add section header                                     │   │
│  │  • Include document type                                  │   │
│  │  Format: "[Title: X] [Section: Y] [Type: Z] {chunk}"     │   │
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
└─────────────────────────────────────────────────────────────────┘
```

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
| `backend/src/ingestion/document_processor.py` | Main document processing orchestrator |
| `backend/src/ingestion/semantic_chunking.py` | spaCy-based semantic chunking |
| `backend/src/ingestion/contextual_chunking.py` | Context prepending for chunks |
| `backend/src/ingestion/chunking.py` | Parent document retriever pattern |
| `backend/src/ingestion/query_expansion.py` | Query expansion via LLM |
| `backend/src/utils/embeddings.py` | Bedrock Titan embedding wrapper |
| `backend/src/utils/rrf.py` | Reciprocal Rank Fusion implementation |
| `backend/src/utils/reranker.py` | Cross-encoder reranking |
| `backend/src/agent/tools/rag.py` | RAG tool (upgrade from stub) |
| `lambda/document-ingestion/handler.py` | S3 trigger Lambda handler |
| `lambda/document-ingestion/requirements.txt` | Lambda dependencies |

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

## Data Lifecycle Management

### SQL Data Management

```
┌─────────────────────────────────────────────────────────────────┐
│                    SQL DATA LIFECYCLE                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Initial Setup:                                                  │
│  1. Run Alembic migration: 002_financial_schema.py              │
│  2. Run Alembic migration: 003_seed_data.py                     │
│  3. Verify: SELECT COUNT(*) FROM each table                     │
│                                                                  │
│  Data Updates:                                                   │
│  • Manual via new Alembic migrations                            │
│  • No auto-update mechanism needed for demo                     │
│                                                                  │
│  Reset/Refresh:                                                  │
│  1. alembic downgrade base                                       │
│  2. alembic upgrade head                                         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### RAG Document Management

```
┌─────────────────────────────────────────────────────────────────┐
│                  RAG DOCUMENT LIFECYCLE                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Document Upload:                                                │
│  1. Upload to S3 bucket: s3://enterprise-agentic-ai-docs/       │
│  2. Lambda automatically triggered                               │
│  3. Document processed, chunked, embedded                       │
│  4. Vectors stored in Pinecone                                  │
│  5. Entities extracted and stored in Neo4j                      │
│                                                                  │
│  Supported Formats:                                              │
│  • PDF (.pdf) - parsed with PyPDF2/pdfplumber                   │
│  • Text (.txt) - direct text processing                         │
│  • Markdown (.md) - rendered then processed                     │
│  • HTML (.html) - BeautifulSoup extraction                      │
│                                                                  │
│  Document Update:                                                │
│  1. Upload new version with same name (overwrites)              │
│  2. Lambda deletes old vectors by document_id                   │
│  3. Re-processes and re-indexes                                 │
│                                                                  │
│  Document Delete:                                                │
│  1. Delete from S3                                               │
│  2. Manual cleanup: delete vectors by document_id               │
│  3. Manual cleanup: delete KG nodes by document_id              │
│                                                                  │
│  Metadata Storage (Pinecone):                                   │
│  • document_id, title, type, section, page, chunk_index         │
│  • Enables filtering: type="policy", date > "2024-01-01"        │
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

### New AWS Resources

| Resource | Purpose | Cost Estimate |
|----------|---------|---------------|
| S3 Bucket | Document storage | ~$0.50/month |
| Lambda Function | Document ingestion | ~$0.10/month |
| IAM Policies | Lambda permissions | $0 |

### Terraform Modules to Create

```
terraform/modules/
├── documents-s3/
│   ├── main.tf      # S3 bucket with Lambda trigger
│   ├── variables.tf
│   └── outputs.tf
└── document-lambda/
    ├── main.tf      # Lambda function
    ├── variables.tf
    └── outputs.tf
```

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

| Category | Documents | Description |
|----------|-----------|-------------|
| Company Policies | 5 | Refund, privacy, terms, security, compliance |
| Financial Regulations | 3 | SEC guidelines, FINRA rules, banking regs |
| Product Documentation | 5 | Account types, credit cards, investment products |
| FAQs | 3 | Common questions, troubleshooting, how-tos |
| **Total** | **16** | |

Sample document titles:
- `refund-policy.pdf` - Company refund and return policy
- `privacy-policy.pdf` - Data privacy and protection
- `terms-of-service.pdf` - Terms and conditions
- `sec-regulation-summary.pdf` - SEC compliance overview
- `checking-account-guide.pdf` - Checking account features
- `investment-products.pdf` - Investment options guide
- `credit-card-terms.pdf` - Credit card terms and fees
- `faq-account-management.pdf` - Account FAQ
- `faq-transactions.pdf` - Transaction FAQ
- `security-guidelines.pdf` - Security best practices

---

## Cost Estimates

### Phase 2 Additional Monthly Costs

| Component | Monthly Cost | Notes |
|-----------|--------------|-------|
| Pinecone Free | $0 | 100K vectors included |
| Neo4j AuraDB Free | $0 | 200K nodes included |
| S3 (documents) | ~$0.50 | <1GB storage |
| Lambda invocations | ~$0.10 | ~1000 invocations |
| Bedrock embeddings | ~$1-3 | ~$0.0001/1K tokens |
| Bedrock reranking | ~$0.50-1 | ~$0.015/query × queries |
| **Total Phase 2 Addition** | **~$2-5** | |

### Running Total

| Phase | Monthly Cost |
|-------|--------------|
| Phase 1b (current) | ~$10-25 |
| Phase 2 additions | ~$2-5 |
| **Total** | **~$12-30** |

Still well under the $50/month target!

---

## Success Criteria

### SQL Tool (2b)

- [ ] Schema deployed to Neon PostgreSQL
- [ ] Seed data populated (~500 customers, ~10K transactions)
- [ ] Natural language queries return correct SQL
- [ ] ALLOWED_TABLES whitelist enforced
- [ ] Parameterized queries only (no SQL injection)
- [ ] Query timeout and result limits work
- [ ] Error messages are user-friendly

### RAG Tool (2c)

- [ ] Documents can be uploaded to S3
- [ ] Lambda processes documents automatically
- [ ] Chunks stored in Pinecone with metadata
- [ ] Hybrid search (dense + sparse) works
- [ ] Query expansion generates 3 variants
- [ ] Cross-encoder reranking improves relevance
- [ ] Source citations included in results
- [ ] Fallback works when Pinecone unavailable

### Knowledge Graph (2c-KG)

- [ ] Neo4j AuraDB connected and working
- [ ] spaCy extracts entities from documents
- [ ] Entities stored in graph with relationships
- [ ] 1-hop queries return relevant documents
- [ ] 2-hop traversal finds related entities
- [ ] Graph enhances RAG retrieval quality

### Integration

- [ ] All tools registered in LangGraph agent
- [ ] Agent selects appropriate tool for query
- [ ] Multi-tool queries work (e.g., SQL + RAG)
- [ ] Streaming responses include tool usage
- [ ] Error recovery handles tool failures gracefully

### Quality Metrics

- [ ] RAGAS Faithfulness > 0.7
- [ ] RAGAS Answer Relevancy > 0.7
- [ ] RAGAS Context Precision > 0.7
- [ ] RAGAS Context Recall > 0.7

---

## Implementation Order

### Phase 2a: SQL Tool (Week 1)

1. Create Alembic migration for schema
2. Create Alembic migration for seed data
3. Implement SQL tool with safety checks
4. Test natural language to SQL queries
5. Integrate with LangGraph agent

### Phase 2b: Basic RAG (Week 2)

1. Set up Pinecone index
2. Implement document processor
3. Implement semantic chunking
4. Implement contextual enrichment
5. Create basic RAG tool (dense search only)

### Phase 2c: Document Ingestion (Week 2-3)

1. Create S3 bucket with Terraform
2. Create Lambda function
3. Connect S3 trigger to Lambda
4. Test document upload → indexing flow

### Phase 2d: Knowledge Graph (Week 3)

1. Set up Neo4j AuraDB
2. Implement spaCy entity extractor
3. Implement graph store adapter
4. Connect to ingestion pipeline

### Phase 2e: Advanced RAG (Week 3-4)

1. Add BM25 sparse vectors
2. Implement RRF fusion
3. Add query expansion
4. Implement cross-encoder reranking
5. Add contextual compression

### Phase 2f: Integration & Testing (Week 4)

1. Register all tools in agent
2. End-to-end testing
3. RAGAS evaluation
4. Documentation and cleanup

---

## Open Questions

> These questions should be resolved before or during implementation.

### SQL Tool

1. **Read-only user:** Should we create a separate Neon user with SELECT-only permissions, or use query validation?
   - **Recommendation:** Query validation is simpler; create read-only user only if time permits

2. **Query explanation:** Should the agent explain the SQL it generates to users?
   - **Recommendation:** Yes, include in tool response for transparency

### RAG Tool

3. **Chunk size:** 512 tokens with 50 overlap, or different values?
   - **Recommendation:** Start with 512/50, tune based on RAGAS metrics

4. **Reranking model:** Use Nova Lite or a dedicated cross-encoder model?
   - **Recommendation:** Nova Lite for simplicity; switch to dedicated model if quality insufficient

5. **Parent document retriever:** Implement full pattern or simplified version?
   - **Recommendation:** Simplified first (contextual enrichment covers most benefit)

### Knowledge Graph

6. **Neo4j vs PostgreSQL:** Final decision on graph store?
   - **Decision:** Neo4j AuraDB Free (as per user choice)

7. **Entity deduplication:** How aggressive should fuzzy matching be?
   - **Recommendation:** Levenshtein distance ≤ 2 for matching

### Infrastructure

8. **Lambda timeout:** 15 seconds default or longer for large PDFs?
   - **Recommendation:** 60 seconds to handle larger documents

9. **Lambda memory:** 256MB default or more for spaCy?
   - **Recommendation:** 512MB-1GB for spaCy model loading

---

## References

- [PROJECT_PLAN.md](../PROJECT_PLAN.md) - Phase 2 section
- [DEVELOPMENT_REFERENCE.md](../DEVELOPMENT_REFERENCE.md) - Phase 2 specs
- [backend.mdc](../.cursor/rules/backend.mdc) - Python patterns
- [agent.mdc](../.cursor/rules/agent.mdc) - LangGraph patterns
- [_security.mdc](../.cursor/rules/_security.mdc) - SQL safety patterns
- [infrastructure.mdc](../.cursor/rules/infrastructure.mdc) - Terraform patterns

---

*This document will be used as the basis for PHASE_2_HOW_TO_GUIDE.md*
