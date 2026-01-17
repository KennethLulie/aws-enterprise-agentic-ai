# Phase 2a: Data Foundation & Basic Tools - Complete How-To Guide

> 🚧 **PHASE 2a IN PROGRESS**
>
> | Component | URL |
> |-----------|-----|
> | **Frontend (CloudFront)** | `https://d2bhnqevtvjc7f.cloudfront.net` |
> | **Backend (App Runner)** | `https://yhvmf3inyx.us-east-1.awsapprunner.com` |
>
> Building on Phase 1b with core data tools.

**Purpose:** This guide implements the data foundation for the agent: VLM document extraction, SQL tool for 10-K financial queries, and basic RAG retrieval with dense vector search. By the end, the agent can answer questions using real financial data from SEC filings.

**Estimated Time:** 8-12 hours depending on familiarity with document processing and vector databases

**Prerequisites:** Phase 1b must be complete and verified before starting Phase 2a. This includes:
- Neon PostgreSQL database working with PostgresSaver
- Pinecone account created and index configured
- App Runner deployed with persistent conversation state
- CI/CD pipeline functional

**💰 Cost Estimate:** 
- One-time: ~$25-40 for VLM extraction of ~750 pages
- Monthly addition: ~$2-5 (Bedrock embeddings)
- Neo4j AuraDB: $0/month (free tier, set up now for Phase 2b)

**🖥️ Development Environment:** Continue using Windows with WSL 2 as in previous phases. All terminal commands run in your WSL terminal (Ubuntu).

---

## Table of Contents

- [Quick Start Workflow Summary](#quick-start-workflow-summary)
- [1. Prerequisites Verification](#1-prerequisites-verification)
- [2. Neo4j AuraDB Setup](#2-neo4j-auradb-setup)
- [3. Document Acquisition](#3-document-acquisition)
- [4. Document Processing Dependencies](#4-document-processing-dependencies)
- [5. VLM Extraction Pipeline](#5-vlm-extraction-pipeline)
- [6. SQL Schema and Data Loading](#6-sql-schema-and-data-loading)
- [7. SQL Tool Implementation](#7-sql-tool-implementation)
- [8. Embeddings and Chunking](#8-embeddings-and-chunking)
- [9. RAG Indexing Pipeline](#9-rag-indexing-pipeline)
- [10. Basic RAG Tool Implementation](#10-basic-rag-tool-implementation)
- [11. Agent Integration](#11-agent-integration)
- [12. End-to-End Verification](#12-end-to-end-verification)
- [Phase 2a Completion Checklist](#phase-2a-completion-checklist)
- [Common Issues and Solutions](#common-issues-and-solutions)
- [Files Created/Modified in Phase 2a](#files-createdmodified-in-phase-2a)
- [Branch Management and Next Steps](#branch-management-and-next-steps)

---

## Quick Start Workflow Summary

**📋 This guide is designed to be followed linearly.** Complete each section in order (1→2→3→...→12).

**Overall Phase 2a Workflow:**
1. **Prerequisites** (Section 1): Verify Phase 1b complete, Pinecone index exists
2. **Neo4j Setup** (Section 2): Create Neo4j AuraDB account and local Docker setup (infrastructure for Phase 2b)
3. **Documents** (Section 3): Download 10-K filings and reference documents
4. **Dependencies** (Section 4): Add PDF processing packages to requirements
5. **VLM Extraction** (Section 5): Build batch script for Claude Vision extraction
6. **SQL Schema** (Section 6): Create 10-K tables and load extracted data
7. **SQL Tool** (Section 7): Implement real SQL tool with safety checks
8. **Embeddings** (Section 8): Implement Titan embeddings and semantic chunking
9. **Indexing** (Section 9): Build pipeline to index chunks to Pinecone
10. **RAG Tool** (Section 10): Implement basic dense vector search
11. **Integration** (Section 11): Register tools in LangGraph agent
12. **Verification** (Section 12): End-to-end testing

**Key Principle:** Build the data foundation first, then the tools that query it. Each tool is testable independently before integration.

**Architecture Overview:**
```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Document Processing                              │
│                                                                          │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐               │
│  │  10-K PDFs   │    │ News Articles│    │ Research PDFs│               │
│  │  (SEC EDGAR) │    │  (saved PDF) │    │  (optional)  │               │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘               │
│         │                   │                   │                        │
│         └───────────────────┼───────────────────┘                        │
│                             ▼                                            │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │              VLM Extraction (Claude Vision via Bedrock)          │    │
│  │                   scripts/extract_and_index.py                   │    │
│  └─────────────────────────────┬───────────────────────────────────┘    │
│                                │                                         │
│         ┌──────────────────────┼──────────────────────┐                 │
│         ▼                      ▼                      ▼                 │
│  ┌─────────────┐        ┌─────────────┐        ┌─────────────┐         │
│  │ PostgreSQL  │        │  Pinecone   │        │   Neo4j     │         │
│  │ (SQL Tool)  │        │ (RAG Tool)  │        │ (Setup now, │         │
│  │             │        │             │        │  used in 2b)│         │
│  │ - companies │        │ - vectors   │        │             │         │
│  │ - metrics   │        │ - metadata  │        │ - entities  │         │
│  │ - segments  │        │             │        │ - relations │         │
│  └─────────────┘        └─────────────┘        └─────────────┘         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                         LangGraph Agent                                  │
│                                                                          │
│  User Query ──▶ Agent ──▶ Tool Selection ──▶ Response                   │
│                              │                                           │
│                   ┌──────────┼──────────┐                               │
│                   ▼          ▼          ▼                               │
│             ┌─────────┐ ┌─────────┐ ┌─────────┐                         │
│             │SQL Tool │ │RAG Tool │ │ Search  │                         │
│             │"Compare │ │"What are│ │ Market  │                         │
│             │revenues"│ │ risks?" │ │  Data   │                         │
│             └─────────┘ └─────────┘ └─────────┘                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Estimated Time:** 8-12 hours

---

## 1. Prerequisites Verification

### What We're Doing
Verifying Phase 1b is complete and all required services are accessible before building data tools.

### Why This Matters
- **Foundation:** Phase 2a builds on Phase 1b infrastructure (Neon, Pinecone)
- **Dependencies:** VLM extraction requires Bedrock access, tools require database connections
- **Cost Safety:** Verify services are on free tiers before processing documents

### 1.1 Verify Phase 1b Deployment

**Command (run in WSL terminal):**
```bash
cd ~/Projects/aws-enterprise-agentic-ai

# Test App Runner health endpoint
curl https://yhvmf3inyx.us-east-1.awsapprunner.com/health | jq
```

**Expected Output:**
```json
{
  "status": "ok",
  "environment": "aws",
  "version": "0.1.0",
  "api_version": "v1",
  "checks": {
    "database": {"status": "ok", "latency_ms": 50},
    "bedrock": {"status": "ok"}
  }
}
```

**If health check fails:** Complete Phase 1b first. See `docs/completed-phases/PHASE_1B_HOW_TO_GUIDE.md`.

### 1.2 Verify Neon PostgreSQL Connection

**Command:**
```bash
# Verify DATABASE_URL secret exists
aws secretsmanager describe-secret --secret-id enterprise-agentic-ai/database-url

# Test connection (replace with your connection string from Neon dashboard)
docker-compose exec backend python -c "
from src.config.settings import get_settings
settings = get_settings()
print(f'Database URL configured: {bool(settings.database_url)}')
"
```

**Expected Output:** Secret exists and database URL is configured.

### 1.3 Verify Pinecone Index

**Command:**
```bash
# Check Pinecone environment variables
docker-compose exec backend python -c "
from src.config.settings import get_settings
settings = get_settings()
print(f'Pinecone API Key: {\"configured\" if settings.pinecone_api_key else \"missing\"}')
print(f'Pinecone Index: {settings.pinecone_index_name}')
"
```

**Expected Output:** Pinecone API key configured and index name set.

**If Pinecone not configured:** Review Phase 1b Pinecone setup section.

### 1.4 Verify Bedrock Model Access

**Command:**
```bash
# Test Bedrock access for Claude Vision (used for VLM extraction)
aws bedrock list-foundation-models \
  --query "modelSummaries[?contains(modelId, 'claude')].modelId" \
  --output table
```

**Expected Output:** List includes `us.anthropic.claude-sonnet-4-5-*` (Claude Sonnet 4.5 - current recommended) or `anthropic.claude-3-5-sonnet-*` (deprecated, shutdown Feb 2026).

**If models not listed:** Request model access in AWS Console → Bedrock → Model access.

### 1.5 Verify AWS Credentials for Local Processing

**Command:**
```bash
# Verify AWS CLI configured for local batch script
aws sts get-caller-identity
aws configure get region
```

**Expected Output:** Your AWS account ID and `us-east-1` region.

### 1.6 Prerequisites Checklist

- [ ] App Runner health endpoint returns 200 with database "ok"
- [ ] Neon DATABASE_URL secret exists in Secrets Manager
- [ ] Pinecone API key and index name configured
- [ ] Bedrock Claude model access approved
- [ ] AWS CLI configured for us-east-1
- [ ] Docker Compose running (`docker-compose up -d`)

---

## 2. Neo4j AuraDB Setup (Infrastructure for Phase 2b)

### What We're Doing
Creating a Neo4j AuraDB free tier instance for the Knowledge Graph and setting up local Neo4j for development. We set this up now so the infrastructure is ready for Phase 2b's entity extraction and graph queries.

### Why This Matters
- **Infrastructure First:** Setting up Neo4j now avoids delays when implementing Phase 2b's Knowledge Graph
- **Free Tier:** Neo4j AuraDB free tier includes 200K nodes, sufficient for demo ($0/month)
- **Local Development:** Docker Neo4j allows offline development and testing
- **Phase 2b Usage:** Knowledge Graph will use Neo4j for entity storage, relationships, and graph traversal queries

### 2.1 Create Neo4j AuraDB Account

**Step 1: Create Account**

1. Open your browser and go to https://neo4j.com/cloud/aura-free/
2. Click **"Start Free"** or **"Get Started Free"**
3. Sign up with:
   - **GitHub** (recommended - fastest)
   - **Google**
   - **Email** (requires verification)
4. Complete the sign-up process

**No credit card required** - Neo4j AuraDB free tier includes:
- 200,000 nodes
- 400,000 relationships
- 1 database instance

**Step 2: Create Your Database Instance**

After signing up:

1. Click **"Create a Free Instance"** or **"New Instance"**
2. Configure the instance:
   - **Instance Name:** `enterprise-agentic-ai`
   - **Region:** Select **US East (N. Virginia)** or closest to us-east-1
   - **Instance Type:** Free (should be pre-selected)
3. Click **"Create"**
4. **IMPORTANT:** A popup will show your credentials - **save these immediately!**
   - **Username:** `neo4j` (default)
   - **Password:** (auto-generated, copy this!)
   - **Connection URI:** `neo4j+s://xxxxxxxx.databases.neo4j.io`

**Step 3: Save Connection Details**

Copy these values to a temporary secure location:

```
NEO4J_URI=neo4j+s://xxxxxxxx.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_generated_password
```

**Note:** The instance may take 2-3 minutes to provision. Status will change from "Creating" to "Running".

### 2.2 Create Neo4j Secret in AWS Secrets Manager

**Command (replace placeholders with your actual values):**
```bash
aws secretsmanager create-secret \
  --name enterprise-agentic-ai/neo4j \
  --description "Neo4j AuraDB connection credentials for Knowledge Graph" \
  --secret-string '{
    "uri": "neo4j+s://YOUR_INSTANCE_ID.databases.neo4j.io",
    "user": "neo4j",
    "password": "YOUR_NEO4J_PASSWORD"
  }'
```

**Verify the secret was created:**
```bash
aws secretsmanager describe-secret --secret-id enterprise-agentic-ai/neo4j
```

### 2.3 Add Neo4j to Docker Compose for Local Development

**Agent Prompt:**
```
Update `docker-compose.yml` to add Neo4j service for local development

Changes:
1. Add neo4j service under services section:
   - image: neo4j:5-community
   - ports: 7474:7474 (HTTP browser), 7687:7687 (Bolt protocol)
   - environment: NEO4J_AUTH=neo4j/localdevpassword, NEO4J_PLUGINS=["apoc"]
   - volumes: neo4j_data:/data
   - healthcheck: wget to localhost:7474

2. Add neo4j_data to volumes section at bottom of file

Configuration:
- Local password is "localdevpassword" (different from AuraDB for safety)
- APOC plugin enables advanced graph procedures
- Health check ensures service is ready before dependent services start

Reference:
- Existing docker-compose.yml structure
- Neo4j Docker documentation: https://neo4j.com/docs/operations-manual/current/docker/

Verify: docker-compose config (validates YAML syntax)
```

**Verify Docker Compose update:**
```bash
cd ~/Projects/aws-enterprise-agentic-ai
docker-compose config | grep -A 10 "neo4j:"
```

### 2.4 Start Neo4j Locally

**Command:**
```bash
# Start Neo4j container
docker-compose up -d neo4j

# Wait for it to be healthy (may take 30-60 seconds)
docker-compose ps neo4j

# Test connection
docker-compose exec neo4j cypher-shell -u neo4j -p localdevpassword "RETURN 1 as test"
```

**Expected Output:**
```
+------+
| test |
+------+
| 1    |
+------+
```

### 2.5 Add Neo4j Environment Variables

**Agent Prompt:**
```
Update `.env.example` to add Neo4j environment variables

Add these variables under a new "# Neo4j (Knowledge Graph - Phase 2)" section:

NEO4J_URI=neo4j://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=localdevpassword

Add comment: "# For AWS, use Secrets Manager: enterprise-agentic-ai/neo4j"

Reference:
- Existing .env.example structure
- Neo4j connection string format

Verify: File contains NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD variables
```

**Update your local `.env` file:**
```bash
# Add to your .env file (create if doesn't exist)
echo "" >> .env
echo "# Neo4j (Knowledge Graph)" >> .env
echo "NEO4J_URI=neo4j://localhost:7687" >> .env
echo "NEO4J_USER=neo4j" >> .env
echo "NEO4J_PASSWORD=localdevpassword" >> .env
```

### 2.6 Neo4j Setup Checklist

- [ ] Neo4j AuraDB account created (free tier)
- [ ] Database instance created in US East region
- [ ] Connection credentials saved (URI, user, password)
- [ ] AWS secret `enterprise-agentic-ai/neo4j` created
- [ ] Neo4j added to docker-compose.yml
- [ ] Local Neo4j container running and healthy
- [ ] .env.example updated with Neo4j variables
- [ ] Local .env updated with Neo4j credentials

---

## 3. Document Acquisition

### What We're Doing
Downloading SEC 10-K filings and reference documents that will be processed by the VLM extraction pipeline and indexed for RAG retrieval.

### Why This Matters
- **Real Data:** Using actual SEC filings provides realistic financial queries
- **Structured Source:** 10-Ks have consistent structure (financial statements, risk factors, MD&A)
- **Reference Context:** News articles provide additional context for cross-referencing

### 3.1 Create Document Directories

**Command:**
```bash
cd ~/Projects/aws-enterprise-agentic-ai

# Create directories for documents
mkdir -p documents/raw/10k
mkdir -p documents/raw/reference
mkdir -p documents/extracted
mkdir -p documents/processed
```

**Directory Structure:**
```
documents/
├── raw/
│   ├── 10k/           # Original 10-K PDFs from SEC EDGAR
│   └── reference/     # News articles, research saved as PDF
├── extracted/         # VLM extraction output (JSON)
└── processed/         # Processing status and logs
```

### 3.2 Download 10-K Filings from SEC EDGAR

**Instructions:**

1. Go to SEC EDGAR: https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany

2. For each company below, search and download the most recent 10-K:

| Company | Ticker | Search | File to Download |
|---------|--------|--------|------------------|
| Apple Inc. | AAPL | Search "Apple Inc" | 10-K filed ~Oct 2024 |
| Microsoft | MSFT | Search "Microsoft Corp" | 10-K filed ~Jul 2024 |
| Amazon | AMZN | Search "Amazon.com" | 10-K filed ~Feb 2024 |
| Alphabet (Google) | GOOGL | Search "Alphabet Inc" | 10-K filed ~Feb 2024 |
| Tesla | TSLA | Search "Tesla Inc" | 10-K filed ~Jan 2024 |
| JPMorgan Chase | JPM | Search "JPMorgan Chase" | 10-K filed ~Feb 2024 |
| Nvidia | NVDA | Search "NVIDIA Corp" | 10-K filed ~Feb 2024 |

**Step-by-step for each company:**

1. Enter company name in the "Company name" field
2. Click "Search"
3. Find the company in results, click the CIK number
4. In the "Filing Type" filter, enter "10-K"
5. Click on the most recent 10-K filing date
6. Click on the "10-K" document link (not the index)
7. Download the PDF (or print to PDF if HTML)
8. Save to `documents/raw/10k/` with naming convention: `{TICKER}_10K_2024.pdf`

**Example filenames:**
```
documents/raw/10k/
├── AAPL_10K_2024.pdf
├── MSFT_10K_2024.pdf
├── AMZN_10K_2024.pdf
├── GOOGL_10K_2024.pdf
├── TSLA_10K_2024.pdf
├── JPM_10K_2024.pdf
└── NVDA_10K_2024.pdf
```

**Alternative - Direct Links:**
- Apple: https://investor.apple.com/sec-filings/
- Microsoft: https://www.microsoft.com/en-us/investor/sec-filings
- Amazon: https://ir.aboutamazon.com/sec-filings
- Alphabet: https://abc.xyz/investor/
- Tesla: https://ir.tesla.com/sec-filings
- JPMorgan: https://investor.jpmorgan.com/sec-filings
- Nvidia: https://investor.nvidia.com/financial-info/sec-filings

### 3.3 Save Reference Documents

Reference documents provide context beyond 10-K filings. These can be news articles, research reports, industry analyses, or policy documents. The system handles all types through VLM extraction.

**Document Naming Convention (IMPORTANT):**

Use this naming pattern so the system can detect document type and extract metadata:

```
{TICKER}_{source}_{YYYY-MM-DD}.pdf    # For company-specific news/research
{topic}_{source}_{YYYY-MM-DD}.pdf      # For industry/market documents
{topic}_{type}.pdf                      # For policies or evergreen documents
```

**Examples:**

| Filename | Type | Purpose |
|----------|------|---------|
| `AAPL_reuters_2025-01-10.pdf` | News | Apple-specific news article |
| `NVDA_seeking-alpha_2025-01-05.pdf` | Research | NVIDIA analysis |
| `ai-chips_mckinsey_2024-12.pdf` | Industry | AI chip market analysis |
| `ev-market_bloomberg_2024-11.pdf` | Industry | EV market outlook |
| `tech-regulation_ft_2025-01.pdf` | News | Tech regulation update |

**Instructions:**

For each document, open in browser and save as PDF (Print → Save as PDF):

1. **Company-specific news** (at least 2-3 per major company)
   - Search for recent earnings news, analyst coverage, or major announcements
   - Examples:
     - `AAPL_reuters_2025-01-10.pdf` - Apple earnings coverage
     - `NVDA_bloomberg_2025-01-08.pdf` - NVIDIA AI chip demand news
     - `TSLA_ft_2025-01-05.pdf` - Tesla production news

2. **Industry analysis** (2-3 covering your portfolio sectors)
   - `ai-chips_mckinsey_2024-12.pdf` - Semiconductor industry analysis
   - `ev-market_bloomberg_2024-11.pdf` - Electric vehicle market trends
   - `cloud-computing_gartner_2024-10.pdf` - Cloud market overview

3. **Regulatory/policy documents** (1-2 relevant to portfolio)
   - `tech-regulation_ft_2025-01.pdf` - Big tech regulatory developments
   - `china-trade_reuters_2025-01.pdf` - China trade policy updates

**Suggested Sources:**
- **News:** Reuters, Financial Times, Bloomberg, WSJ
- **Research:** Seeking Alpha, Morningstar, analyst reports
- **Industry:** McKinsey, Gartner, industry associations
- **Policy:** Government announcements, regulatory filings

**Reference Document Structure:**
```
documents/raw/reference/
├── AAPL_reuters_2025-01-10.pdf       # Company news
├── NVDA_bloomberg_2025-01-08.pdf     # Company news
├── TSLA_ft_2025-01-05.pdf            # Company news
├── ai-chips_mckinsey_2024-12.pdf     # Industry analysis
├── ev-market_bloomberg_2024-11.pdf   # Industry analysis
└── tech-regulation_ft_2025-01.pdf    # Policy/regulatory
```

**Why This Matters for Demo:**

Reference documents enable powerful cross-source analysis:
- "Does this news about Apple's China concerns align with their 10-K disclosures?"
- "How does recent AI chip demand news compare to NVIDIA's risk factors?"
- "What regulatory risks are companies facing that aren't in their 10-Ks yet?"

### 3.4 Verify Document Collection

**Command:**
```bash
cd ~/Projects/aws-enterprise-agentic-ai

# Count documents
echo "10-K filings:"
ls -la documents/raw/10k/ | wc -l

echo "Reference documents:"
ls -la documents/raw/reference/ | wc -l

# List all documents
find documents/raw -name "*.pdf" -type f
```

**Expected Output:**
- 7 10-K filings
- 3-5 reference documents
- All files are PDFs

### 3.5 Document Acquisition Checklist

- [ ] Document directories created (raw/10k, raw/reference, extracted, processed)
- [ ] 7 10-K filings downloaded from SEC EDGAR (AAPL, MSFT, AMZN, GOOGL, TSLA, JPM, NVDA)
- [ ] 10-K files named consistently: `{TICKER}_10K_2024.pdf`
- [ ] 3-5 reference documents saved as PDF
- [ ] All documents verified as valid PDFs

---

## 4. Document Processing Dependencies

### What We're Doing
Adding Python packages and system dependencies required for PDF processing, VLM extraction, and vector embeddings.

### Why This Matters
- **PDF Processing:** pdf2image converts PDFs to images for Claude Vision
- **System Dependencies:** poppler-utils required by pdf2image
- **NLP:** spaCy for semantic chunking and entity extraction

### 4.1 Update Backend Requirements

**Agent Prompt:**
```
Update `backend/requirements.txt` to add document processing dependencies

Add a new section "# Document Processing (Phase 2)" with these packages:

pdf2image~=1.17.0           # Convert PDF pages to images for VLM
Pillow~=10.4.0              # Image processing (may already exist, verify version)
python-magic~=0.4.27        # File type detection

Note: The following packages are ALREADY in requirements.txt with correct versions:
- pinecone-client~=5.0.0    # Vector store client (already installed)
- neo4j~=5.25.0             # Knowledge graph driver (already installed)
- spacy~=3.8.0              # NLP for chunking and NER (already installed)

Only add packages that don't already exist. Verify versions match DEVELOPMENT_REFERENCE.md.

Add comment: "# Note: pdf2image requires poppler-utils system package"
Add comment: "# Note: Run 'python -m spacy download en_core_web_sm' after install"

Constraints:
- Check if Pillow or pinecone-client already exist, update version if needed
- Use ~= for compatible release versioning
- Versions must be compatible with Python 3.11

Reference:
- DEVELOPMENT_REFERENCE.md for version patterns
- Existing requirements.txt structure

Verify: docker-compose exec backend pip install -r requirements.txt --dry-run
```

### 4.2 Update Dockerfile for System Dependencies

**Agent Prompt:**
```
Update `backend/Dockerfile` to add system dependencies for PDF processing

Changes:
1. Add apt-get install commands for:
   - poppler-utils (required by pdf2image for PDF to image conversion)
   - libmagic1 (required by python-magic for file type detection)

2. Add spaCy model download:
   - RUN python -m spacy download en_core_web_sm

Location: Add after the existing apt-get commands, before pip install

Format:
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

Reference:
- Existing Dockerfile structure
- pdf2image documentation for system requirements

Verify: docker-compose build backend (should complete without errors)
```

**Agent Prompt:**
```
Update `backend/Dockerfile.dev` with the same system dependencies

Apply the same changes as backend/Dockerfile:
1. Add poppler-utils and libmagic1 via apt-get
2. Add spaCy model download

This ensures local development environment matches production.

Reference:
- Changes made to backend/Dockerfile
- Existing Dockerfile.dev structure

Verify: docker-compose build backend
```

### 4.3 Rebuild Backend Container

**Command:**
```bash
cd ~/Projects/aws-enterprise-agentic-ai

# Rebuild with new dependencies
docker-compose build backend

# Start updated container
docker-compose up -d backend

# Verify new packages installed
docker-compose exec backend pip list | grep -E "pdf2image|Pillow|spacy|neo4j"
```

**Expected Output:**
```
Pillow          10.4.0
neo4j           5.25.x
pdf2image       1.17.0
spacy           3.8.x
```

### 4.4 Verify spaCy Model

**Command:**
```bash
docker-compose exec backend python -c "
import spacy
nlp = spacy.load('en_core_web_sm')
doc = nlp('Apple Inc. reported revenue of $394 billion.')
print('Entities found:', [(ent.text, ent.label_) for ent in doc.ents])
"
```

**Expected Output:**
```
Entities found: [('Apple Inc.', 'ORG'), ('$394 billion', 'MONEY')]
```

### 4.5 Document Processing Dependencies Checklist

- [ ] requirements.txt updated with pdf2image, python-magic, neo4j, spacy
- [ ] Dockerfile updated with poppler-utils, libmagic1
- [ ] Dockerfile.dev updated with same dependencies
- [ ] Backend container rebuilt successfully
- [ ] pip list shows new packages installed
- [ ] spaCy en_core_web_sm model loads and extracts entities

---

## 5. VLM Extraction Pipeline

### What We're Doing
Building a batch script that uses Claude Vision (via Bedrock) to extract structured data from PDF documents. This creates JSON output that feeds into SQL, RAG, and Knowledge Graph systems.

### Why This Matters
- **Unified Extraction:** One pipeline for all documents (10-Ks and reference docs)
- **Structured Output:** JSON format enables loading to multiple data stores
- **Table Preservation:** VLM handles complex financial tables better than text extraction

### 5.1 Create VLM Extractor Module

**Agent Prompt:**
```
Create `backend/src/ingestion/vlm_extractor.py`

Requirements:
1. Import boto3 for Bedrock client
2. Import pdf2image for PDF to image conversion
3. Import base64 for image encoding
4. Import json, logging, pathlib

Structure:
- VLMExtractor class with:
  - __init__(self, model_id: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0", fallback_model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0")
  - _pdf_to_images(self, pdf_path: Path, dpi: int = 150) -> list[Image]
  - _encode_image(self, image: Image) -> str (base64 encoding)
  - _extract_page(self, image: Image, page_num: int, doc_type: str) -> dict
  - extract_document(self, pdf_path: Path, doc_type: str = "10k") -> dict
  - _get_extraction_prompt(self, doc_type: str, page_num: int) -> str

Key Features:
- Convert each PDF page to image at 150 DPI (balance quality/cost)
- Send each page image to Claude Vision via Bedrock
- **DIFFERENT prompts for different document types** (see below)
- Return consolidated JSON with all pages and extracted metadata

**Extraction Prompt for 10-K Filings (CRITICAL for SQL tool):**

"You are extracting structured data from a 10-K SEC filing page.

Extract ALL content from this page and return as JSON with these keys:

{
  "page_number": <int>,
  "section": "<section name, e.g., 'Item 1A: Risk Factors', 'Item 8: Financial Statements'>",
  "content_type": "<narrative|table|mixed>",
  "text": "<all narrative text on this page>",
  "tables": [
    {
      "table_name": "<descriptive name>",
      "table_type": "<income_statement|balance_sheet|cash_flow|segment_revenue|geographic_revenue|other>",
      "headers": ["Column1", "Column2", ...],
      "rows": [
        {"label": "Revenue", "values": {"2024": "394328", "2023": "383285"}},
        ...
      ]
    }
  ],
  "financial_metrics": {
    "fiscal_year": <int or null if not on this page>,
    "revenue": <number in millions or null>,
    "net_income": <number in millions or null>,
    "gross_profit": <number in millions or null>,
    "operating_income": <number in millions or null>,
    "total_assets": <number in millions or null>,
    "total_liabilities": <number in millions or null>,
    "earnings_per_share": <number or null>,
    "currency": "USD"
  },
  "segment_data": [
    {"segment_name": "iPhone", "revenue": 200583, "fiscal_year": 2024}
  ],
  "geographic_data": [
    {"region": "Americas", "revenue": 167045, "fiscal_year": 2024}
  ],
  "risk_factors": [
    {"category": "Supply Chain", "title": "Manufacturing concentration in Asia", "severity": "high"}
  ],
  "cross_references": ["Note 12", "See Item 7"]
}

IMPORTANT EXTRACTION RULES:
1. For financial tables: Parse EVERY row, preserve column headers for year identification
2. For numbers: Remove $ and commas, convert 'million'/'billion' to raw millions (e.g., '$394.3 billion' → 394300)
3. If a metric spans multiple years, include ALL years found
4. For segment/geographic data: Only extract if this page contains segment or geographic revenue breakdowns
5. Set fields to null if not present on THIS page (will be consolidated later)
6. For risk factors: Only extract from Item 1A pages, categorize by type (Supply Chain, Regulatory, Competition, Macroeconomic, Technology, Legal)"

**Extraction Prompt for Reference Documents (news, research, policies):**

"You are extracting content from a reference document (news article, research report, or policy document).

Extract ALL content from this page and return as JSON:

{
  "page_number": <int>,
  "document_type": "<news|research|policy|other>",
  "content_type": "<narrative|table|mixed>",
  "text": "<all text content>",
  "headline": "<main headline if this is page 1, else null>",
  "publication_date": "<YYYY-MM-DD if found, else null>",
  "source": "<publication name if found, e.g., 'Reuters', 'Financial Times'>",
  "key_claims": [
    {"claim": "<factual assertion that could be verified>", "entities": ["Entity1", "Entity2"]}
  ],
  "entities_mentioned": ["Apple", "Tim Cook", "China", ...],
  "tables": [<same structure as 10-K>],
  "cross_references": []
}

EXTRACTION RULES:
1. Extract ALL claims that could be verified against official sources (10-Ks, earnings reports)
2. Identify entities: companies, people, locations, financial metrics, dates
3. For key_claims: Focus on numerical claims and assertions about company performance"

Error Handling:
- Retry on throttling (exponential backoff, max 3 retries)
- Log progress for each page
- Handle corrupted pages gracefully (skip and log, add to errors list)
- If JSON parsing fails, log raw response and retry with stricter prompt

Cost Note:
- Claude Vision ~$0.003/image for input + $0.015/1K output tokens
- ~$0.03-0.05 per page typical for 10-K pages
- ~$0.02-0.03 per page for reference documents
- Add logging to track token usage

Reference:
- Bedrock Claude documentation
- pdf2image documentation: https://pdf2image.readthedocs.io/
- [backend.mdc] for Python patterns
- [agent.mdc] for Bedrock integration patterns

Verify: docker-compose exec backend python -c "from src.ingestion.vlm_extractor import VLMExtractor; print('OK')"
```

### 5.2 Create Document Processor Orchestrator

**Agent Prompt:**
```
Create `backend/src/ingestion/document_processor.py`

Requirements:
1. Import VLMExtractor from vlm_extractor
2. Import Path, json, logging
3. Import from typing: Optional, Literal

Structure:
- DocumentProcessor class with:
  - __init__(self, raw_dir: Path, extracted_dir: Path)
  - _detect_doc_type(self, filename: str) -> Literal["10k", "reference"]
  - _get_document_id(self, pdf_path: Path) -> str (unique ID from filename)
  - _get_file_hash(self, pdf_path: Path) -> str (MD5 hash for change detection)
  - process_document(self, pdf_path: Path) -> dict
  - process_all(self, doc_types: list[str] | None = None) -> list[dict]
  - save_extraction(self, doc_id: str, extraction: dict) -> Path
  - _load_manifest(self) -> dict (load or create manifest.json)
  - _save_manifest(self) -> None (persist manifest to disk)
  - _update_manifest(self, doc_id: str, pdf_path: Path, extraction: dict, cost: float) -> None
  - should_process(self, pdf_path: Path, force: bool = False, if_changed: bool = False) -> bool
  - **_consolidate_financial_data(self, pages: list[dict]) -> dict**  # Critical for SQL
  - **_consolidate_reference_data(self, pages: list[dict]) -> dict**  # For reference docs

Key Features:
- Detect document type from filename pattern (contains "_10K_" -> "10k")
- Generate unique document_id from filename (e.g., "AAPL_10K_2024")
- Process single document or batch all documents in raw_dir
- Save extraction results to extracted_dir as JSON
- **Manifest-based tracking** (documents/manifest.json):
  - Track file hash, extraction date, cost, indexing status
  - Skip already-processed documents unless --force
  - Detect content changes via MD5 hash (--if-changed flag)
- **NEW: Consolidate financial data from multiple pages into SQL-ready structure**

Manifest File Structure (documents/manifest.json):
{
  "documents": {
    "AAPL_10K_2024": {
      "source_file": "AAPL_10K_2024.pdf",
      "file_hash": "a1b2c3d4e5f6...",
      "file_size_bytes": 4523891,
      "extracted_at": "2025-01-15T10:30:00Z",
      "page_count": 85,
      "extraction_cost_usd": 3.82,
      "indexed_to_pinecone": false,
      "indexed_at": null,
      "chunk_count": null
    }
  },
  "totals": {
    "documents_extracted": 1,
    "documents_indexed": 0,
    "total_extraction_cost_usd": 3.82,
    "last_updated": "2025-01-15T10:30:00Z"
  }
}

File Hash Implementation:
import hashlib

def _get_file_hash(self, pdf_path: Path) -> str:
    """Compute MD5 hash of file for change detection."""
    hash_md5 = hashlib.md5()
    with open(pdf_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

Should Process Logic:
def should_process(self, pdf_path: Path, force: bool = False, if_changed: bool = False) -> bool:
    """Determine if document needs processing."""
    doc_id = self._get_document_id(pdf_path)
    
    # Force always processes
    if force:
        return True
    
    # Check manifest
    if doc_id not in self.manifest["documents"]:
        return True  # New document
    
    entry = self.manifest["documents"][doc_id]
    
    # If if_changed flag, check hash
    if if_changed:
        current_hash = self._get_file_hash(pdf_path)
        if current_hash != entry.get("file_hash"):
            logger.info(f"{doc_id}: Content changed, will re-extract")
            return True
    
    # Already processed and not changed
    if entry.get("extracted_at"):
        logger.info(f"{doc_id}: Already extracted, skipping")
        return False
    
    return True

Document Type Detection:
- If filename contains "_10K_" or "_10k_": type = "10k"
- Otherwise: type = "reference"

**CRITICAL: Financial Data Consolidation for 10-Ks**

The _consolidate_financial_data() method aggregates data from all pages:

def _consolidate_financial_data(self, pages: list[dict]) -> dict:
    """
    Aggregate financial data scattered across multiple pages into a single
    SQL-ready structure. Financial statements often span 3-5 pages.
    """
    consolidated = {
        "financial_metrics_by_year": {},  # {2024: {...}, 2023: {...}}
        "segment_revenue": [],
        "geographic_revenue": [],
        "risk_factors": []
    }
    
    for page in pages:
        # Aggregate financial metrics by fiscal year
        if metrics := page.get("financial_metrics"):
            year = metrics.get("fiscal_year")
            if year:
                if year not in consolidated["financial_metrics_by_year"]:
                    consolidated["financial_metrics_by_year"][year] = {}
                # Merge non-null values (later pages may have more complete data)
                for key, value in metrics.items():
                    if value is not None and key != "fiscal_year":
                        consolidated["financial_metrics_by_year"][year][key] = value
        
        # Aggregate segment data (deduplicate by segment_name + fiscal_year)
        for segment in page.get("segment_data", []):
            if segment not in consolidated["segment_revenue"]:
                consolidated["segment_revenue"].append(segment)
        
        # Aggregate geographic data
        for geo in page.get("geographic_data", []):
            if geo not in consolidated["geographic_revenue"]:
                consolidated["geographic_revenue"].append(geo)
        
        # Aggregate risk factors (deduplicate by title)
        for risk in page.get("risk_factors", []):
            existing_titles = [r["title"] for r in consolidated["risk_factors"]]
            if risk.get("title") and risk["title"] not in existing_titles:
                risk["page_number"] = page.get("page_number")
                consolidated["risk_factors"].append(risk)
    
    return consolidated

**CRITICAL: Reference Document Consolidation**

def _consolidate_reference_data(self, pages: list[dict]) -> dict:
    """
    Consolidate reference document data (news, research, policies).
    """
    consolidated = {
        "headline": None,
        "publication_date": None,
        "source": None,
        "key_claims": [],
        "entities_mentioned": set()
    }
    
    for page in pages:
        # First page usually has headline/date/source
        if page.get("page_number") == 1:
            consolidated["headline"] = page.get("headline")
            consolidated["publication_date"] = page.get("publication_date")
            consolidated["source"] = page.get("source")
        
        # Aggregate claims and entities from all pages
        consolidated["key_claims"].extend(page.get("key_claims", []))
        consolidated["entities_mentioned"].update(page.get("entities_mentioned", []))
    
    consolidated["entities_mentioned"] = list(consolidated["entities_mentioned"])
    return consolidated

Output JSON Structure for 10-K:
{
  "document_id": "AAPL_10K_2024",
  "document_type": "10k",
  "filename": "AAPL_10K_2024.pdf",
  "extraction_date": "2024-01-15T10:30:00Z",
  "total_pages": 85,
  "pages": [...],
  "metadata": {
    "company": "Apple Inc.",
    "ticker": "AAPL",
    "fiscal_year": 2024,
    "sector": "Technology"
  },
  "consolidated": {
    "financial_metrics_by_year": {
      "2024": {"revenue": 394328, "net_income": 93736, "gross_margin": 46.5, ...},
      "2023": {"revenue": 383285, "net_income": 96995, "gross_margin": 44.1, ...}
    },
    "segment_revenue": [
      {"segment_name": "iPhone", "revenue": 200583, "fiscal_year": 2024, "percentage_of_total": 52.2},
      {"segment_name": "Services", "revenue": 96169, "fiscal_year": 2024, "percentage_of_total": 25.0}
    ],
    "geographic_revenue": [
      {"region": "Americas", "revenue": 167045, "fiscal_year": 2024, "percentage_of_total": 43.5},
      {"region": "Greater China", "revenue": 66672, "fiscal_year": 2024, "percentage_of_total": 17.4}
    ],
    "risk_factors": [
      {"category": "Supply Chain", "title": "Manufacturing concentration in Asia", "severity": "high", "page_number": 15}
    ]
  }
}

Output JSON Structure for Reference Documents:
{
  "document_id": "AAPL_reuters_2025-01-10",
  "document_type": "reference",
  "filename": "AAPL_reuters_2025-01-10.pdf",
  "extraction_date": "2025-01-15T10:30:00Z",
  "total_pages": 3,
  "pages": [...],
  "metadata": {
    "headline": "Apple reports record services revenue amid China concerns",
    "publication_date": "2025-01-10",
    "source": "Reuters",
    "source_type": "news",
    "entities_mentioned": ["Apple", "Tim Cook", "China", "iPhone", "Services"]
  },
  "consolidated": {
    "key_claims": [
      {"claim": "Services revenue reached $96B, a record high", "entities": ["Apple", "Services"]},
      {"claim": "Greater China revenue declined 8% year-over-year", "entities": ["Apple", "China"]}
    ]
  }
}

Reference:
- VLMExtractor class from 5.1
- [backend.mdc] for Python patterns

Verify: docker-compose exec backend python -c "from src.ingestion.document_processor import DocumentProcessor; print('OK')"
```

### 5.3 Create Extraction Batch Script

**Agent Prompt:**
```
Create `scripts/extract_and_index.py`

Requirements:
1. Standalone script that runs locally (not in Docker)
2. Uses DocumentProcessor to extract all PDFs
3. Provides CLI with argparse for options
4. Handles interruption gracefully (save progress)

Structure:
- main() function with argparse:
  - --raw-dir: Path to raw documents (default: documents/raw)
  - --extracted-dir: Path for JSON output (default: documents/extracted)
  - --doc-types: Filter by type (10k, reference, or both)
  - --force: Re-extract even if already in manifest
  - --if-changed: Re-extract only if file hash changed
  - --dry-run: List documents without processing (shows what would be extracted)
  - --status: Show manifest status and exit (no API calls)
  - --doc: Process single document by ID (e.g., --doc AAPL_10K_2024)

Key Features:
- Load AWS credentials from environment
- Initialize DocumentProcessor with paths
- **Use manifest for skip/process decisions** (prevents duplicate extraction)
- Process documents with progress logging
- Save extraction results after each document (fault tolerance)
- **Update manifest after each successful extraction**
- Summary at end: documents processed, pages extracted, estimated cost

Status Output (--status):
"Document Extraction Status"
"=========================="
"Extracted: 5 documents"
"  - AAPL_10K_2024 (85 pages, $3.82, 2025-01-15)"
"  - MSFT_10K_2024 (92 pages, $4.14, 2025-01-15)"
"  - GOOGL_10K_2024 (78 pages, $3.51, 2025-01-15)"
"  - AMZN_10K_2024 (88 pages, $3.96, 2025-01-15)"
"  - META_10K_2024 (95 pages, $4.28, 2025-01-15)"
""
"Pending: 2 documents"
"  - NVDA_10K_2024.pdf (new)"
"  - TSLA_10K_2024.pdf (new)"
""
"Total extraction cost so far: $19.71"
"Estimated cost for pending: $8.00"

Progress Output:
"Processing AAPL_10K_2024.pdf..."
"  Page 1/85 extracted"
"  Page 2/85 extracted"
...
"  Saved to documents/extracted/AAPL_10K_2024.json"
"  Updated manifest (cost: $3.82)"
"Processing MSFT_10K_2024.pdf..."
...
"Summary: 7 documents, 623 pages, estimated cost: $28.50"

Error Handling:
- Catch and log errors per document
- Continue with next document on failure
- Final summary includes failed documents
- **Manifest only updated for successful extractions** (failed docs not marked as done)

Reference:
- DocumentProcessor from 5.2
- argparse documentation
- [backend.mdc] for script patterns

Verify: python scripts/extract_and_index.py --help
```

### 5.4 Update Ingestion Package Init

**Agent Prompt:**
```
Update `backend/src/ingestion/__init__.py`

Changes:
1. Import and export VLMExtractor from vlm_extractor
2. Import and export DocumentProcessor from document_processor
3. Add __all__ list with exported classes
4. Add module docstring explaining the ingestion package purpose

Reference:
- Existing __init__.py patterns in other packages
- [backend.mdc] for package structure

Verify: docker-compose exec backend python -c "from src.ingestion import VLMExtractor, DocumentProcessor; print('OK')"
```

### 5.5 Test VLM Extraction (Single Page)

**Command:**
```bash
cd ~/Projects/aws-enterprise-agentic-ai

# Test extraction on first page of one document
docker-compose exec backend python -c "
from src.ingestion import VLMExtractor
from pathlib import Path

extractor = VLMExtractor()
# This will process just the first page as a test
print('VLM Extractor initialized, ready for extraction')
print('To extract: python scripts/extract_and_index.py')
"
```

### 5.6 Run Full Extraction (Cost: ~$25-40)

**⚠️ Cost Warning:** This step will call Claude Vision API for all documents. Estimated cost: ~$25-40 for ~750 pages.


**note will run locally in venv, this helps avoid technical complexity for the demo** 
**Command:**
```bash
cd ~/Projects/aws-enterprise-agentic-ai

# Check current status first (no API calls, reads manifest)
# install any missing dependencies
python scripts/extract_and_index.py --status

# Dry run to see what will be processed
python scripts/extract_and_index.py --dry-run

# If satisfied, run full extraction
python scripts/extract_and_index.py

# Monitor progress and estimated cost in output
```

**Status Output (first run, nothing extracted yet):**
```
Document Extraction Status
==========================
Extracted: 0 documents

Pending: 11 documents
  - AAPL_10K_2024.pdf (new)
  - MSFT_10K_2024.pdf (new)
  - GOOGL_10K_2024.pdf (new)
  ...

Total extraction cost so far: $0.00
Estimated cost for pending: ~$31.28
```

**Expected Output (after full run):**
```
Processing 7 10-K documents and 4 reference documents...
Processing AAPL_10K_2024.pdf (85 pages)...
  ...
Saved: documents/extracted/AAPL_10K_2024.json
Updated manifest (cost: $3.82)
...
Summary:
  Documents processed: 11
  Total pages: 782
  Estimated cost: $31.28
  Output directory: documents/extracted/
  Manifest: documents/manifest.json
```

**Safe to Re-run:** If you run the script again, it will skip already-extracted documents:
```bash
python scripts/extract_and_index.py
# Output: "AAPL_10K_2024: Already extracted, skipping"
# Output: "MSFT_10K_2024: Already extracted, skipping"
# Output: "Summary: 0 documents processed (11 already extracted)"
```

**Force Re-extraction (if needed):**
```bash
# Re-extract single document
python scripts/extract_and_index.py --force --doc AAPL_10K_2024

# Re-extract only if PDF content changed
python scripts/extract_and_index.py --if-changed
```

### 5.7 Verify Extraction Results

**Command:**
```bash
# Check extracted JSON files exist
ls -la documents/extracted/

# View structure of one extraction
cat documents/extracted/AAPL_10K_2024.json | jq 'keys'
cat documents/extracted/AAPL_10K_2024.json | jq '.metadata'
cat documents/extracted/AAPL_10K_2024.json | jq '.pages | length'
```

**Expected Output:**
```
["document_id", "document_type", "extraction_date", "filename", "metadata", "pages", "total_pages"]
{"company": "Apple Inc.", "ticker": "AAPL", "fiscal_year": 2024}
85
```

### 5.8 Validate All Extractions (Required Before Proceeding)

**⚠️ Critical:** Run this validation before proceeding to SQL or RAG indexing. This catches extraction issues early.

**Command:**
```bash
cd ~/Projects/aws-enterprise-agentic-ai

# Validate all extracted JSON files have required structure
docker-compose exec backend python -c "
import json
from pathlib import Path

extracted_dir = Path('documents/extracted')
required_keys = {'document_id', 'document_type', 'pages', 'metadata'}
required_metadata = {'ticker', 'company'}

errors = []
valid_count = 0

for json_file in extracted_dir.glob('*.json'):
    try:
        with open(json_file) as f:
            data = json.load(f)
        
        # Check required keys
        missing = required_keys - set(data.keys())
        if missing:
            errors.append(f'{json_file.name}: Missing keys: {missing}')
            continue
        
        # Check pages not empty
        if not data.get('pages'):
            errors.append(f'{json_file.name}: No pages extracted')
            continue
        
        # Check metadata for 10-Ks
        if '10K' in json_file.name.upper() or '10k' in json_file.name:
            meta = data.get('metadata', {})
            missing_meta = required_metadata - set(meta.keys())
            if missing_meta:
                errors.append(f'{json_file.name}: Missing metadata: {missing_meta}')
                continue
        
        valid_count += 1
        print(f'✓ {json_file.name}: {len(data[\"pages\"])} pages, ticker={data.get(\"metadata\", {}).get(\"ticker\", \"N/A\")}')
        
    except json.JSONDecodeError as e:
        errors.append(f'{json_file.name}: Invalid JSON: {e}')
    except Exception as e:
        errors.append(f'{json_file.name}: Error: {e}')

print(f'\\n=== Summary ===')
print(f'Valid extractions: {valid_count}')
print(f'Errors: {len(errors)}')

if errors:
    print('\\n=== Errors (fix before proceeding) ===')
    for err in errors:
        print(f'✗ {err}')
    exit(1)
else:
    print('\\n✓ All extractions valid. Safe to proceed to SQL loading and indexing.')
"
```

**Expected Output:**
```
✓ AAPL_10K_2024.json: 85 pages, ticker=AAPL
✓ MSFT_10K_2024.json: 100 pages, ticker=MSFT
...

=== Summary ===
Valid extractions: 11
Errors: 0

✓ All extractions valid. Safe to proceed to SQL loading and indexing.
```

**If errors occur:** Re-run extraction for failed documents: `python scripts/extract_and_index.py --force --doc-types 10k`

### 5.9 VLM Extraction Pipeline Checklist

- [ ] vlm_extractor.py created with VLMExtractor class
- [ ] document_processor.py created with DocumentProcessor class
- [ ] extract_and_index.py script created with CLI (including --status, --force, --if-changed flags)
- [ ] ingestion/__init__.py updated with exports
- [ ] Test import successful
- [ ] `--status` shows pending documents correctly
- [ ] Dry run lists all documents correctly
- [ ] Full extraction completed (~$25-40 cost)
- [ ] JSON files created in documents/extracted/
- [ ] **Manifest created** (documents/manifest.json) with extraction tracking
- [ ] JSON structure contains metadata, pages, total_pages
- [ ] Re-running script skips already-extracted documents (verify with --status)

---

## 6. SQL Schema and Data Loading

### What We're Doing
Creating database tables for 10-K financial data and loading the VLM-extracted data into Neon PostgreSQL. This enables SQL queries against real financial metrics.

### Why This Matters
- **Structured Queries:** SQL enables precise questions like "Which company had highest revenue?"
- **Real Data:** Using actual 10-K data, not synthetic/Faker data
- **Integration:** Same data source as RAG enables cross-tool queries

### 6.1 Create Alembic Migration for 10-K Schema

> **Note:** This is the first Alembic migration for application tables. PostgresSaver checkpoint tables are created separately via `PostgresSaver.setup()` and don't use Alembic.

**Agent Prompt:**
```
Create `backend/alembic/versions/001_10k_financial_schema.py`

Requirements:
1. Alembic migration for 10-K financial data tables
2. Tables: companies, financial_metrics, segment_revenue, geographic_revenue, risk_factors
3. Proper foreign key relationships
4. Indexes for common query patterns

Tables to Create:

companies:
- id: SERIAL PRIMARY KEY
- ticker: VARCHAR(10) UNIQUE NOT NULL
- name: VARCHAR(255) NOT NULL
- sector: VARCHAR(100)
- fiscal_year_end: DATE
- filing_date: DATE
- document_id: VARCHAR(100) (links to Pinecone document)
- created_at: TIMESTAMP DEFAULT CURRENT_TIMESTAMP

financial_metrics:
- id: SERIAL PRIMARY KEY
- company_id: INTEGER REFERENCES companies(id) ON DELETE CASCADE
- fiscal_year: INTEGER NOT NULL
- revenue, cost_of_revenue, gross_profit: DECIMAL(15, 2)
- operating_expenses, operating_income, net_income: DECIMAL(15, 2)
- total_assets, total_liabilities, total_equity: DECIMAL(15, 2)
- cash_and_equivalents, long_term_debt: DECIMAL(15, 2)
- gross_margin, operating_margin, net_margin: DECIMAL(5, 2)
- earnings_per_share, diluted_eps: DECIMAL(10, 4)
- currency: VARCHAR(3) DEFAULT 'USD'
- UNIQUE(company_id, fiscal_year)

segment_revenue:
- id: SERIAL PRIMARY KEY
- company_id: INTEGER REFERENCES companies(id) ON DELETE CASCADE
- fiscal_year: INTEGER NOT NULL
- segment_name: VARCHAR(100) NOT NULL
- revenue: DECIMAL(15, 2)
- percentage_of_total: DECIMAL(5, 2)
- yoy_growth: DECIMAL(5, 2)

geographic_revenue:
- id: SERIAL PRIMARY KEY
- company_id: INTEGER REFERENCES companies(id) ON DELETE CASCADE
- fiscal_year: INTEGER NOT NULL
- region: VARCHAR(100) NOT NULL
- revenue: DECIMAL(15, 2)
- percentage_of_total: DECIMAL(5, 2)
- yoy_growth: DECIMAL(5, 2)

risk_factors:
- id: SERIAL PRIMARY KEY
- company_id: INTEGER REFERENCES companies(id) ON DELETE CASCADE
- fiscal_year: INTEGER NOT NULL
- category: VARCHAR(100)
- title: VARCHAR(500)
- summary: TEXT
- severity: VARCHAR(20) CHECK (severity IN ('high', 'medium', 'low'))
- page_number: INTEGER

Indexes:
- idx_financial_metrics_company ON financial_metrics(company_id)
- idx_financial_metrics_year ON financial_metrics(fiscal_year)
- idx_segment_revenue_company ON segment_revenue(company_id)
- idx_geographic_revenue_company ON geographic_revenue(company_id)
- idx_risk_factors_company ON risk_factors(company_id)
- idx_risk_factors_category ON risk_factors(category)
- idx_companies_ticker ON companies(ticker)

Downgrade:
- Drop all tables in reverse order (risk_factors, geographic_revenue, segment_revenue, financial_metrics, companies)

Reference:
- Alembic migration patterns
- PHASE_2_REQUIREMENTS.md SQL Schema section
- [_security.mdc] for SQL patterns

Verify: docker-compose exec backend alembic upgrade head
```

### 6.2 Verify Database Connection (Before Migration)

**⚠️ Important:** Verify database connection before running migrations or loading data.

**Command:**
```bash
cd ~/Projects/aws-enterprise-agentic-ai

# Verify database connection
docker-compose exec backend python -c "
from sqlalchemy import create_engine, text
from src.config.settings import get_settings

settings = get_settings()
print(f'Connecting to: {settings.database_url[:50]}...')

try:
    engine = create_engine(settings.database_url)
    with engine.connect() as conn:
        result = conn.execute(text('SELECT 1'))
        print('✓ Database connection successful')
except Exception as e:
    print(f'✗ Database connection failed: {e}')
    exit(1)
"
```

**Expected Output:**
```
Connecting to: postgresql://...
✓ Database connection successful
```

**If connection fails:** Check DATABASE_URL in .env, verify Neon PostgreSQL is accessible.

### 6.3 Run Migration

**Command:**
```bash
cd ~/Projects/aws-enterprise-agentic-ai

# Check current migration state
docker-compose exec backend alembic current

# Run migration
docker-compose exec backend alembic upgrade head

# Verify tables created
docker-compose exec backend python -c "
from sqlalchemy import create_engine, inspect
from src.config.settings import get_settings

engine = create_engine(get_settings().database_url)
inspector = inspect(engine)
tables = inspector.get_table_names()
expected = ['companies', 'financial_metrics', 'segment_revenue', 'geographic_revenue', 'risk_factors']
found = [t for t in tables if t in expected]
missing = set(expected) - set(found)

print('Tables created:', found)
if missing:
    print(f'✗ Missing tables: {missing}')
    exit(1)
else:
    print('✓ All expected tables exist')
"
```

**Expected Output:**
```
Tables created: ['companies', 'financial_metrics', 'geographic_revenue', 'risk_factors', 'segment_revenue']
✓ All expected tables exist
```

### 6.4 Create Data Loading Script

**Agent Prompt:**
```
Create `scripts/load_10k_to_sql.py`

Requirements:
1. Load VLM-extracted JSON into PostgreSQL tables
2. **Use the pre-consolidated data structure** (not raw page parsing)
3. Handle data validation and type conversion
4. Provide CLI for selective loading

Structure:
- DataLoader class with:
  - __init__(self, database_url: str)
  - _load_company(self, extraction: dict) -> int  # Returns company_id
  - _load_financial_metrics(self, consolidated: dict, company_id: int) -> int  # Returns rows inserted
  - _load_segments(self, consolidated: dict, company_id: int) -> int
  - _load_geographic(self, consolidated: dict, company_id: int) -> int
  - _load_risks(self, consolidated: dict, company_id: int) -> int
  - load_document(self, json_path: Path) -> dict  # Returns stats
  - load_all(self, extracted_dir: Path) -> dict
  - validate_extraction(self, extraction: dict) -> list[str]  # Returns list of warnings

CLI Arguments:
- --extracted-dir: Path to extracted JSON files
- --database-url: Override DATABASE_URL environment variable
- --ticker: Load specific ticker only
- --force: Drop and reload data for ticker
- --dry-run: Parse and validate without loading
- --validate-only: Run validation checks without loading

**CRITICAL: Use Consolidated Data Structure**

The VLM extraction now produces a `consolidated` key with SQL-ready data.
DO NOT parse raw pages - use the consolidated structure directly:

def _load_financial_metrics(self, consolidated: dict, company_id: int) -> int:
    """
    Load financial metrics from consolidated.financial_metrics_by_year.
    """
    metrics_by_year = consolidated.get("financial_metrics_by_year", {})
    rows_inserted = 0
    
    for fiscal_year, metrics in metrics_by_year.items():
        # Map consolidated keys to SQL columns
        row = {
            "company_id": company_id,
            "fiscal_year": int(fiscal_year),
            "revenue": metrics.get("revenue"),
            "net_income": metrics.get("net_income"),
            "gross_profit": metrics.get("gross_profit"),
            "operating_income": metrics.get("operating_income"),
            "cost_of_revenue": metrics.get("cost_of_revenue"),
            "operating_expenses": metrics.get("operating_expenses"),
            "total_assets": metrics.get("total_assets"),
            "total_liabilities": metrics.get("total_liabilities"),
            "total_equity": metrics.get("total_equity"),
            "cash_and_equivalents": metrics.get("cash_and_equivalents"),
            "long_term_debt": metrics.get("long_term_debt"),
            "gross_margin": metrics.get("gross_margin"),
            "operating_margin": metrics.get("operating_margin"),
            "net_margin": metrics.get("net_margin"),
            "earnings_per_share": metrics.get("earnings_per_share"),
            "diluted_eps": metrics.get("diluted_eps"),
            "currency": metrics.get("currency", "USD"),
        }
        
        # Insert or update (upsert on company_id + fiscal_year)
        self._upsert_financial_metric(row)
        rows_inserted += 1
    
    return rows_inserted

def _load_segments(self, consolidated: dict, company_id: int) -> int:
    """
    Load segment revenue from consolidated.segment_revenue.
    """
    segments = consolidated.get("segment_revenue", [])
    for segment in segments:
        row = {
            "company_id": company_id,
            "fiscal_year": segment.get("fiscal_year"),
            "segment_name": segment.get("segment_name"),
            "revenue": segment.get("revenue"),
            "percentage_of_total": segment.get("percentage_of_total"),
            "yoy_growth": segment.get("yoy_growth"),
        }
        self._insert_segment(row)
    return len(segments)

**Data Validation (Critical for SQL Tool Reliability)**

def validate_extraction(self, extraction: dict) -> list[str]:
    """
    Validate extraction has required data for SQL tool.
    Returns list of warnings (empty = valid).
    """
    warnings = []
    consolidated = extraction.get("consolidated", {})
    
    # Check financial metrics exist
    metrics_by_year = consolidated.get("financial_metrics_by_year", {})
    if not metrics_by_year:
        warnings.append("No financial metrics found - SQL queries for this company will fail")
    else:
        for year, metrics in metrics_by_year.items():
            if not metrics.get("revenue"):
                warnings.append(f"Missing revenue for year {year}")
    
    # Check segments exist (expected for most 10-Ks)
    segments = consolidated.get("segment_revenue", [])
    if not segments:
        warnings.append("No segment revenue found - segment queries will return empty")
    
    # Check geographic exists
    geographic = consolidated.get("geographic_revenue", [])
    if not geographic:
        warnings.append("No geographic revenue found - geographic queries will return empty")
    
    # Check risk factors exist
    risks = consolidated.get("risk_factors", [])
    if not risks:
        warnings.append("No risk factors found - risk queries will return empty")
    
    return warnings

**Dry Run Output with Validation:**

Dry run mode - validating consolidated data
Processing AAPL_10K_2024.json...
  Company: Apple Inc. (AAPL)
  Financial metrics: 2 years (2024, 2023)
    2024: revenue=$394,328M, net_income=$93,736M ✓
    2023: revenue=$383,285M, net_income=$96,995M ✓
  Segments: 5 found (iPhone, Services, Mac, iPad, Wearables) ✓
  Geographic regions: 4 found (Americas, Europe, Greater China, Rest of Asia) ✓
  Risk factors: 12 found ✓
  ✓ All validation checks passed

Processing MSFT_10K_2024.json...
  Company: Microsoft Corporation (MSFT)
  Financial metrics: 2 years (2024, 2023)
    2024: revenue=$236,584M, net_income=$88,136M ✓
    ⚠️ Warning: Missing gross_margin for 2024
  ...

Summary:
  Documents validated: 7
  Warnings: 3 (see above)
  Ready to load: Yes (warnings are non-blocking)

**Error Handling:**

- If consolidated is missing: Log error, skip document, report in summary
- If required fields missing: Insert NULL, log warning
- If type conversion fails: Log warning, skip that field
- If database constraint fails: Log error, rollback that document, continue with others

Reference:
- Consolidated JSON structure from Section 5.2
- SQLAlchemy patterns for bulk insert and upsert
- [backend.mdc] for database patterns

Verify (run locally): source .venv/bin/activate && python scripts/load_10k_to_sql.py --validate-only
```

### 6.5 Load Extracted Data

> **Note:** This script runs locally (not in Docker) because it reads from `documents/extracted/` which is not mounted in the container.

**Command:**
```bash
cd ~/Projects/aws-enterprise-agentic-ai
source .venv/bin/activate

# Dry run to validate parsing (catches issues before writing to DB)
python scripts/load_10k_to_sql.py --dry-run
```

**Expected Dry Run Output:**
```
✓ Database connection successful

Dry run - would load 3 documents:

  ○ reference_doc.json - Skip (not 10-K)
  ✓ NVDA_10K_2025.json
      Company: NVIDIA Corporation (NVDA)
      Would load: 1 years, 21 segments, 19 regions, 95 risks
```

**If parsing errors:** Fix the extraction or loading script before proceeding.

**Command (actual load):**
```bash
# Load all extracted 10-K data
python scripts/load_10k_to_sql.py
```

### 6.6 Verify Data Loaded Correctly

**⚠️ Important:** Always verify data counts after loading.

**Command:**
```bash
docker-compose exec backend python -c "
from sqlalchemy import create_engine, text
from src.config.settings import get_settings

engine = create_engine(get_settings().database_url)
with engine.connect() as conn:
    # Expected counts
    expected = {'companies': 7, 'financial_metrics': 14}
    
    # Check companies
    result = conn.execute(text('SELECT COUNT(*) FROM companies'))
    company_count = result.scalar()
    print(f'Companies: {company_count}')
    
    # Check financial_metrics  
    result = conn.execute(text('SELECT COUNT(*) FROM financial_metrics'))
    metrics_count = result.scalar()
    print(f'Financial metrics: {metrics_count}')
    
    # Check segments
    result = conn.execute(text('SELECT COUNT(*) FROM segment_revenue'))
    print(f'Segment records: {result.scalar()}')
    
    # Check geographic
    result = conn.execute(text('SELECT COUNT(*) FROM geographic_revenue'))
    print(f'Geographic records: {result.scalar()}')
    
    # Check risks
    result = conn.execute(text('SELECT COUNT(*) FROM risk_factors'))
    print(f'Risk factors: {result.scalar()}')
    
    # List companies
    print('\\nCompanies loaded:')
    result = conn.execute(text('SELECT ticker, name FROM companies ORDER BY ticker'))
    for row in result:
        print(f'  {row[0]}: {row[1]}')
    
    # Validation
    if company_count < expected['companies']:
        print(f'\\n⚠️ Warning: Expected {expected[\"companies\"]} companies, found {company_count}')
    else:
        print(f'\\n✓ Data loading verified: {company_count} companies, {metrics_count} metrics')
"
```

**Expected Output:**
```
Companies: 7
Financial metrics: 14
Segment records: 35
Geographic records: 28
Risk factors: 70

Companies loaded:
  AAPL: Apple Inc.
  AMZN: Amazon.com Inc.
  GOOGL: Alphabet Inc.
  JPM: JPMorgan Chase & Co.
  MSFT: Microsoft Corporation
  NVDA: NVIDIA Corporation
  TSLA: Tesla Inc.

✓ Data loading verified: 7 companies, 14 metrics
```

### 6.7 SQL Schema and Data Loading Checklist

- [ ] Alembic migration 001_10k_financial_schema.py created
- [ ] Migration runs successfully (alembic upgrade head)
- [ ] All 5 tables created (companies, financial_metrics, segment_revenue, geographic_revenue, risk_factors)
- [ ] load_10k_to_sql.py script created
- [ ] Dry run validates JSON parsing
- [ ] Data loaded for 7 companies
- [ ] Financial metrics populated (~14 rows for 2 years each)

---

## 7. SQL Tool Implementation

### What We're Doing
Upgrading the SQL tool stub to a real implementation that converts natural language to SQL queries with proper safety measures.

### Why This Matters
- **Real Queries:** Agent can now answer "Which company had highest revenue?"
- **Security:** ALLOWED_TABLES and parameterization prevent SQL injection
- **Integration:** Works with real 10-K data just loaded

### 7.1 Create SQL Safety Module

**Agent Prompt:**
```
Create `backend/src/agent/tools/sql_safety.py`

Requirements:
1. Define ALLOWED_TABLES whitelist
2. Define ALLOWED_COLUMNS per table
3. Implement query validation functions
4. Implement query sanitization

Structure:
- ALLOWED_TABLES: set of permitted table names
  {"companies", "financial_metrics", "segment_revenue", "geographic_revenue", "risk_factors"}

- ALLOWED_COLUMNS: dict mapping table to permitted columns
  {
    "companies": ["id", "ticker", "name", "sector", "fiscal_year_end", "filing_date", "document_id"],
    "financial_metrics": ["id", "company_id", "fiscal_year", "revenue", "cost_of_revenue", 
                          "gross_profit", "operating_expenses", "operating_income", "net_income",
                          "total_assets", "total_liabilities", "total_equity", "cash_and_equivalents",
                          "long_term_debt", "gross_margin", "operating_margin", "net_margin",
                          "earnings_per_share", "diluted_eps"],
    "segment_revenue": ["id", "company_id", "fiscal_year", "segment_name", "revenue", 
                        "percentage_of_total", "yoy_growth"],
    "geographic_revenue": ["id", "company_id", "fiscal_year", "region", "revenue",
                           "percentage_of_total", "yoy_growth"],
    "risk_factors": ["id", "company_id", "fiscal_year", "category", "title", "summary",
                     "severity", "page_number"]
  }

Functions:
- validate_query(sql: str) -> tuple[bool, str | None]:
  - Returns (True, None) if valid
  - Returns (False, error_message) if invalid
  - Checks: only SELECT, tables in whitelist, no dangerous keywords

- is_read_only(sql: str) -> bool:
  - Returns True if query is SELECT only
  - Rejects INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE

- extract_tables(sql: str) -> set[str]:
  - Parse SQL to find referenced tables
  - Use simple regex or sqlparse library

- sanitize_query(sql: str) -> str:
  - Add LIMIT 100 if no LIMIT clause
  - Strip comments
  - Normalize whitespace

Key Security Rules:
- Only SELECT statements allowed
- Only whitelisted tables/columns
- Maximum 100 rows returned
- 30 second query timeout
- Parameterized values only (no string interpolation)

Reference:
- [_security.mdc] SQL Safety section
- PHASE_2_REQUIREMENTS.md ALLOWED_TABLES
- sqlparse library documentation

Verify: docker-compose exec backend python -c "from src.agent.tools.sql_safety import validate_query, ALLOWED_TABLES; print('OK')"
```

### 7.2 Update SQL Tool Implementation

**Agent Prompt:**
```
Update `backend/src/agent/tools/sql.py` to implement real SQL queries

Current State: The file contains a stub that returns mock data

Changes:
1. Replace mock implementation with real database queries
2. Add natural language to SQL conversion using LLM
3. Implement safety checks using sql_safety module
4. Add proper error handling and logging

Structure:
- Import from sql_safety: validate_query, sanitize_query, ALLOWED_TABLES, ALLOWED_COLUMNS
- Import from sqlalchemy: create_engine, text
- Import ChatBedrock for NL-to-SQL conversion

Functions to Update:
- sql_query(query: str) -> str:
  - Step 1: Convert natural language to SQL using LLM
  - Step 2: Validate SQL with sql_safety.validate_query()
  - Step 3: If invalid, return error message to user
  - Step 4: Execute query with timeout (30 seconds)
  - Step 5: Format results as readable response
  - Step 6: Include the generated SQL in response for transparency

NL-to-SQL Prompt:
"You are a SQL query generator for a 10-K financial database.

Available tables:
- companies (ticker, name, sector, fiscal_year_end, filing_date)
- financial_metrics (company_id, fiscal_year, revenue, net_income, margins, etc.)
- segment_revenue (company_id, fiscal_year, segment_name, revenue, percentage)
- geographic_revenue (company_id, fiscal_year, region, revenue, percentage)
- risk_factors (company_id, fiscal_year, category, title, summary, severity)

Rules:
1. Only use SELECT statements
2. JOIN companies table to get ticker/name when needed
3. Use fiscal_year for time comparisons
4. LIMIT results to 100 rows
5. Use parameterized placeholders (:param) for user values

User question: {query}

Generate a safe SQL query:"

Error Handling:
- Query validation fails: Return helpful message about what's not allowed
- Query timeout: Return "Query took too long, please simplify"
- No results: Return "No data found matching your query"
- Database error: Log error, return generic user-friendly message

Response Format:
"Based on the data, [answer to question]

Details:
[formatted table or list of results]

Query used: [SQL query for transparency]"

Reference:
- sql_safety module from 7.1
- Existing sql.py stub structure
- [backend.mdc] for Python patterns
- [agent.mdc] for tool patterns

Verify: docker-compose exec backend python -c "from src.agent.tools.sql import sql_query; print('OK')"
```

### 7.3 Test SQL Tool Manually

**Command:**
```bash
cd ~/Projects/aws-enterprise-agentic-ai

# Test SQL tool directly (async tool requires asyncio)
docker-compose exec backend python -c "
import asyncio
from src.agent.tools.sql import sql_query

async def test():
    result = await sql_query.ainvoke({'query': 'Which company had the highest revenue?'})
    print(result)

asyncio.run(test())
"
```

**Expected Output:**
```
Based on the financial data, Apple Inc. (AAPL) had the highest revenue in 2024 at $394.33 billion.

Top 5 companies by revenue (2024):
1. Apple Inc. (AAPL): $394.33B
2. Amazon.com Inc. (AMZN): $574.79B
3. ...

Query used: SELECT c.ticker, c.name, fm.revenue FROM companies c JOIN financial_metrics fm ON c.id = fm.company_id WHERE fm.fiscal_year = 2024 ORDER BY fm.revenue DESC LIMIT 5
```

### 7.4 SQL Tool Implementation Checklist

- [ ] sql_safety.py created with ALLOWED_TABLES and validation functions
- [ ] sql.py updated with real database queries
- [ ] NL-to-SQL conversion using LLM implemented
- [ ] Query validation prevents SQL injection
- [ ] Query timeout set to 30 seconds
- [ ] Results limited to 100 rows
- [ ] Test query returns correct results
- [ ] Generated SQL included in response for transparency

---

## 8. Embeddings and Chunking

### What We're Doing
Implementing Bedrock Titan embeddings and semantic chunking to prepare document text for vector indexing in Pinecone.

### Why This Matters
- **Semantic Search:** Embeddings enable finding content by meaning, not just keywords
- **Quality Chunks:** Proper chunking preserves context and improves retrieval
- **Contextual Enrichment:** Prepending metadata helps retrieval understand document structure

### 8.1 Create Embeddings Utility

**Agent Prompt:**
```
Create `backend/src/utils/embeddings.py`

Requirements:
1. Bedrock Titan embeddings wrapper
2. Batch embedding support for efficiency
3. Caching for repeated embeddings (optional)

Structure:
- BedrockEmbeddings class with:
  - __init__(self, model_id: str = "amazon.titan-embed-text-v1")
  - embed_text(self, text: str) -> list[float] (single text)
  - embed_batch(self, texts: list[str], batch_size: int = 25) -> list[list[float]]
  - get_dimension(self) -> int (returns 1536 for Titan)

Key Features:
- Use boto3 Bedrock runtime client
- Model: amazon.titan-embed-text-v1 (1536 dimensions)
- Batch processing: group texts into batches of 25 for efficiency
- Input text normalization: strip whitespace, truncate to max tokens
- Error handling: retry on throttling, log failures

API Call Format (Bedrock Titan):
body = json.dumps({"inputText": text})
response = bedrock.invoke_model(
    modelId="amazon.titan-embed-text-v1",
    body=body
)
embedding = json.loads(response["body"].read())["embedding"]

Cost Note:
- Titan embeddings: ~$0.0001 per 1K tokens
- Log token usage for cost tracking

Reference:
- Bedrock Titan documentation
- [backend.mdc] for Python patterns

Verify: docker-compose exec backend python -c "from src.utils.embeddings import BedrockEmbeddings; e = BedrockEmbeddings(); print(f'Dimension: {e.get_dimension()}')"
```

### 8.2 Create Semantic Chunking Module

**Agent Prompt:**
```
Create `backend/src/ingestion/semantic_chunking.py`

Requirements:
1. Use spaCy for sentence boundary detection
2. Paragraph-aware splitting
3. Configurable chunk size and overlap
4. Token counting for chunk limits

Structure:
- SemanticChunker class with:
  - __init__(self, max_tokens: int = 512, overlap_tokens: int = 50)
  - _count_tokens(self, text: str) -> int (approximate using words/4)
  - _split_sentences(self, text: str) -> list[str] (using spaCy)
  - chunk_text(self, text: str) -> list[str]
  - chunk_document(self, pages: list[dict]) -> list[dict]

Chunking Algorithm:
1. Split text into sentences using spaCy nlp
2. Group sentences into paragraphs (split on double newlines)
3. Build chunks by adding sentences until max_tokens reached
4. Include overlap_tokens from previous chunk at start
5. Never split mid-sentence

Output Chunk Format:
{
  "text": "The chunk content...",
  "token_count": 487,
  "start_page": 15,
  "end_page": 15,
  "chunk_index": 42
}

Key Features:
- Respect sentence boundaries (never cut mid-sentence)
- Respect paragraph boundaries when possible
- Include source page numbers in chunk metadata
- Handle edge cases: very long sentences, empty paragraphs

Reference:
- spaCy documentation: https://spacy.io/
- PHASE_2_REQUIREMENTS.md semantic chunking section
- [backend.mdc] for Python patterns

Verify: docker-compose exec backend python -c "from src.ingestion.semantic_chunking import SemanticChunker; c = SemanticChunker(); print('OK')"
```

### 8.3 Create Contextual Enrichment Module

**Agent Prompt:**
```
Create `backend/src/ingestion/contextual_chunking.py`

Requirements:
1. Prepend document/section context to each chunk
2. Format: "[Document: X] [Section: Y] [Page: Z] {chunk text}"
3. This improves retrieval by adding searchable context

Structure:
- ContextualEnricher class with:
  - __init__(self)
  - enrich_chunk(self, chunk: dict, document_metadata: dict) -> dict
  - enrich_document(self, chunks: list[dict], document_metadata: dict) -> list[dict]

Enrichment Format:
"[Document: Apple 10-K 2024] [Section: Item 1A: Risk Factors] [Page: 15]

The Company's business, reputation, results of operations..."

Key Features:
- Prepend document title/type
- Prepend section name if available
- Prepend page number
- Keep original text after context prefix
- Update token count to include context

Document Metadata Fields Used:
- document_id: "AAPL_10K_2024"
- document_type: "10k" or "reference"
- company: "Apple Inc." (for 10-Ks)
- section: From page extraction (e.g., "Item 1A: Risk Factors")
- page_number: From chunk metadata

Reference:
- Anthropic Contextual Retrieval: https://www.anthropic.com/news/contextual-retrieval
- SemanticChunker output format from 8.2
- [backend.mdc] for Python patterns

Verify: docker-compose exec backend python -c "from src.ingestion.contextual_chunking import ContextualEnricher; print('OK')"
```

### 8.4 Test Chunking Pipeline

**Command:**
```bash
cd ~/Projects/aws-enterprise-agentic-ai

# Test chunking on sample text
docker-compose exec backend python -c "
from src.ingestion.semantic_chunking import SemanticChunker
from src.ingestion.contextual_chunking import ContextualEnricher

# Sample text
text = '''
Apple Inc. reported record revenue of \$394 billion for fiscal 2024.
The company's iPhone segment generated \$200 billion, representing 51% of total revenue.
Services revenue grew 15% year-over-year to reach \$85 billion.

Risk factors include supply chain concentration in China and regulatory scrutiny.
The company faces ongoing antitrust investigations in multiple jurisdictions.
'''

chunker = SemanticChunker(max_tokens=100, overlap_tokens=20)
chunks = chunker.chunk_text(text)
print(f'Created {len(chunks)} chunks')

enricher = ContextualEnricher()
enriched = enricher.enrich_chunk(
    {'text': chunks[0], 'chunk_index': 0, 'start_page': 1},
    {'document_id': 'AAPL_10K_2024', 'document_type': '10k', 'company': 'Apple Inc.'}
)
print(f'Enriched chunk preview: {enriched[\"text\"][:200]}...')
"
```

### 8.5 Embeddings and Chunking Checklist

- [ ] embeddings.py created with BedrockEmbeddings class
- [ ] semantic_chunking.py created with SemanticChunker class
- [ ] contextual_chunking.py created with ContextualEnricher class
- [ ] Embeddings return 1536-dimension vectors
- [ ] Chunking respects sentence boundaries
- [ ] Contextual enrichment prepends document metadata
- [ ] Test pipeline produces enriched chunks

---

## 9. RAG Indexing Pipeline

### What We're Doing
Building the pipeline to process extracted documents into embeddings and index them in Pinecone for vector search.

### Why This Matters
- **Searchable Documents:** Indexed chunks enable semantic search over 10-Ks
- **Metadata Filtering:** Pinecone metadata allows filtering by company, year, section
- **Scalability:** Pipeline handles batch indexing efficiently

### 9.1 Create Pinecone Client Wrapper

**Agent Prompt:**
```
Create `backend/src/utils/pinecone_client.py`

Requirements:
1. Pinecone client wrapper for index operations
2. Support for upsert, query, and delete operations
3. Metadata handling for filtering

Structure:
- PineconeClient class with:
  - __init__(self, api_key: str, index_name: str, environment: str = "us-east-1")
  - _get_index(self) -> pinecone.Index
  - upsert_vectors(self, vectors: list[dict]) -> dict (batch upsert)
  - query(self, vector: list[float], top_k: int = 10, filter: dict = None) -> list[dict]
  - delete_by_metadata(self, filter: dict) -> dict
  - get_stats(self) -> dict

Vector Format for Upsert (10-K Documents):
{
  "id": "AAPL_10K_2024_chunk_42",
  "values": [0.1, 0.2, ...],  # 1536 floats
  "metadata": {
    "document_id": "AAPL_10K_2024",
    "document_type": "10k",
    "source_type": "official",        # NEW: official | news | research | policy
    "company": "Apple Inc.",
    "ticker": "AAPL",
    "fiscal_year": 2024,              # NEW: For temporal filtering
    "section": "Item 1A: Risk Factors",
    "page_number": 15,
    "chunk_index": 42,
    "text": "The chunk text for retrieval..."
  }
}

Vector Format for Upsert (Reference Documents):
{
  "id": "AAPL_reuters_2025-01-10_chunk_3",
  "values": [0.1, 0.2, ...],
  "metadata": {
    "document_id": "AAPL_reuters_2025-01-10",
    "document_type": "reference",
    "source_type": "news",            # NEW: news | research | policy | other
    "source": "Reuters",              # NEW: Publication name
    "publication_date": "2025-01-10", # NEW: For temporal filtering
    "ticker": "AAPL",                 # NEW: Can be null for industry docs
    "headline": "Apple reports record services revenue...",  # NEW: For context
    "page_number": 1,
    "chunk_index": 3,
    "text": "The chunk text for retrieval..."
  }
}

Key Features:
- Batch upsert (100 vectors per batch for efficiency)
- Query with optional metadata filter
- **Delete-before-upsert pattern** - always delete existing vectors by document_id before upserting (prevents duplicates on re-indexing)
- Connection pooling and retry logic

Delete-Before-Upsert Pattern:
def upsert_document(self, document_id: str, vectors: list[dict]) -> dict:
    """Safely upsert vectors, removing any existing ones first."""
    # Delete existing vectors for this document
    self.delete_by_metadata({"document_id": document_id})
    
    # Then upsert new vectors
    return self.upsert_vectors(vectors)

**Metadata Fields by Document Type:**

| Field | 10-K | Reference | Purpose |
|-------|------|-----------|---------|
| document_id | ✓ | ✓ | Unique identifier |
| document_type | "10k" | "reference" | Primary type filter |
| source_type | "official" | "news"/"research"/"policy" | Authority level for cross-referencing |
| company | ✓ | if applicable | Company name |
| ticker | ✓ | if applicable | Stock ticker for filtering |
| fiscal_year | ✓ | - | 10-K fiscal year |
| publication_date | - | ✓ | When document was published |
| source | - | ✓ | Publication name (Reuters, FT, etc.) |
| headline | - | ✓ (page 1) | For context in search results |
| section | ✓ | - | 10-K section (Item 1A, etc.) |
| page_number | ✓ | ✓ | Page reference |
| chunk_index | ✓ | ✓ | Chunk position |
| text | ✓ | ✓ | Actual content for retrieval |

**Why source_type Matters:**

Enables filtering by authority level:
- `source_type: "official"` → 10-K filings (authoritative)
- `source_type: "news"` → News articles (third-party reporting)
- `source_type: "research"` → Analyst reports (expert opinion)
- `source_type: "policy"` → Regulatory documents

Reference:
- Pinecone Python client: https://docs.pinecone.io/docs/python-client
- Existing Pinecone configuration from Phase 1b
- [backend.mdc] for Python patterns

Verify: docker-compose exec backend python -c "from src.utils.pinecone_client import PineconeClient; print('OK')"
```

### 9.2 Verify Pinecone Connection (Before Indexing)

**⚠️ Important:** Verify Pinecone is accessible before starting the long-running indexing process.

**Command:**
```bash
docker-compose exec backend python -c "
from src.config.settings import get_settings
from pinecone import Pinecone

settings = get_settings()
print(f'Connecting to Pinecone index: {settings.pinecone_index_name}')

try:
    pc = Pinecone(api_key=settings.pinecone_api_key)
    index = pc.Index(settings.pinecone_index_name)
    stats = index.describe_index_stats()
    print(f'✓ Pinecone connected')
    print(f'  Current vectors: {stats.total_vector_count}')
    print(f'  Dimension: {stats.dimension}')
except Exception as e:
    print(f'✗ Pinecone connection failed: {e}')
    print('  Check PINECONE_API_KEY and PINECONE_INDEX_NAME in .env')
    exit(1)
"
```

**Expected Output:**
```
Connecting to Pinecone index: enterprise-agentic-ai
✓ Pinecone connected
  Current vectors: 0
  Dimension: 1536
```

**If connection fails:** Verify PINECONE_API_KEY and PINECONE_INDEX_NAME in .env match your Pinecone console.

### 9.3 Create RAG Indexing Script

**Agent Prompt:**
```
Update `scripts/extract_and_index.py` to add indexing step

Changes:
1. After extraction, process JSON through chunking pipeline
2. Generate embeddings for each chunk
3. Upsert to Pinecone with metadata
4. Add --index-only flag to skip extraction and just index

New Functions:
- index_document(json_path: Path, pinecone_client, embeddings_client) -> dict
- index_all(extracted_dir: Path) -> dict

Indexing Pipeline Per Document:
1. Load extracted JSON
2. Check manifest - skip if already indexed (unless --reindex)
3. Chunk pages using SemanticChunker
4. Enrich chunks using ContextualEnricher
5. Generate embeddings using BedrockEmbeddings
6. **Delete existing vectors for document_id** (prevents duplicates)
7. Upsert to Pinecone with metadata
8. **Update manifest** (indexed_to_pinecone=true, indexed_at, chunk_count)
9. Log progress and stats

CLI Updates:
- --index-only: Skip extraction, just index existing JSON (checks manifest for unindexed docs)
- --reindex: Delete existing vectors and re-index all documents
- --index-doc: Index single document by ID (e.g., --index-doc AAPL_10K_2024)

Progress Output:
"Indexing AAPL_10K_2024.json..."
"  Chunked into 127 chunks"
"  Generated 127 embeddings"
"  Upserting to Pinecone..."
"  Done: 127 vectors indexed"

Summary Output:
"Indexing Summary:
  Documents indexed: 11
  Total chunks: 1,423
  Total vectors: 1,423
  Pinecone index stats: 1,423 vectors in 1 namespace"

Reference:
- SemanticChunker, ContextualEnricher from Section 8
- BedrockEmbeddings from Section 8
- PineconeClient from 9.1

Verify: python scripts/extract_and_index.py --help (should show --index-only flag)
```

### 9.4 Run Indexing Pipeline

**Command:**
```bash
cd ~/Projects/aws-enterprise-agentic-ai

# Run indexing (inside Docker for access to modules)
docker-compose exec backend python scripts/extract_and_index.py --index-only
```

**Expected Output:**
```
Indexing AAPL_10K_2024.json...
  Chunked into 127 chunks
  Generated 127 embeddings
  Upserting to Pinecone...
  Done: 127 vectors indexed
...
Indexing Summary:
  Documents indexed: 11
  Total chunks: 1,423
  Total vectors: 1,423
```

### 9.5 Verify Vectors in Pinecone

**⚠️ Important:** Verify indexing succeeded before proceeding to RAG tool testing.

**Command:**
```bash
docker-compose exec backend python -c "
from src.utils.pinecone_client import PineconeClient
from src.config.settings import get_settings

settings = get_settings()
client = PineconeClient(
    api_key=settings.pinecone_api_key,
    index_name=settings.pinecone_index_name
)
stats = client.get_stats()

vector_count = stats.get('total_vector_count', 0)
print(f'Total vectors indexed: {vector_count}')

# Validate minimum expected
expected_min = 1000  # ~100 chunks per document × 10 documents
if vector_count < expected_min:
    print(f'⚠️ Warning: Expected at least {expected_min} vectors, found {vector_count}')
    print('  Some documents may not have been indexed. Check logs.')
else:
    print(f'✓ Indexing verified: {vector_count} vectors (expected ~1400)')
"
```

**Expected Output:**
```
Total vectors indexed: 1423
✓ Indexing verified: 1423 vectors (expected ~1400)
```

### 9.6 Test Vector Search

**Command:**
```bash
cd ~/Projects/aws-enterprise-agentic-ai

# Test a search query
docker-compose exec backend python -c "
from src.utils.pinecone_client import PineconeClient
from src.utils.embeddings import BedrockEmbeddings
from src.config.settings import get_settings

settings = get_settings()
embeddings = BedrockEmbeddings()
client = PineconeClient(
    api_key=settings.pinecone_api_key,
    index_name=settings.pinecone_index_name
)

# Search for supply chain risks
query = 'What are the supply chain risks?'
query_vector = embeddings.embed_text(query)
results = client.query(query_vector, top_k=3)

print(f'Query: {query}')
print(f'Top {len(results)} results:')
for i, r in enumerate(results):
    print(f'{i+1}. [{r[\"metadata\"][\"ticker\"]}] {r[\"metadata\"][\"section\"]}: {r[\"metadata\"][\"text\"][:100]}...')
"
```

### 9.7 RAG Indexing Pipeline Checklist

- [ ] Pinecone connection verified before indexing
- [ ] pinecone_client.py created with PineconeClient class (with delete-before-upsert pattern)
- [ ] extract_and_index.py updated with indexing step
- [ ] --index-only flag works
- [ ] All documents indexed (check Pinecone stats shows 1400+ vectors)
- [ ] **Manifest updated** - all documents show `indexed_to_pinecone: true`
- [ ] Vector search returns relevant results
- [ ] Metadata (ticker, section, page) included in results
- [ ] Re-running --index-only skips already-indexed documents

---

## 10. Basic RAG Tool Implementation

### What We're Doing
Upgrading the RAG tool stub to use real Pinecone vector search for document retrieval.

### Why This Matters
- **Semantic Search:** Agent can find information by meaning, not just keywords
- **Source Citations:** Results include document, page, and section for verification
- **Integration:** Works with real 10-K data just indexed

### 10.1 Update RAG Tool Implementation

**Agent Prompt:**
```
Update `backend/src/agent/tools/rag.py` to implement real retrieval

Current State: The file contains a stub that returns mock documents

Changes:
1. Replace mock implementation with real Pinecone search
2. Use BedrockEmbeddings for query embedding
3. Format results with citations
4. Add metadata filtering support

Structure:
- Import BedrockEmbeddings from src.utils.embeddings
- Import PineconeClient from src.utils.pinecone_client
- Import get_settings from src.config.settings

Functions to Update:
- retrieve_documents(query: str, top_k: int = 5, filters: dict = None) -> str:
  - Step 1: Embed the query using BedrockEmbeddings
  - Step 2: Search Pinecone with query vector
  - Step 3: Apply optional metadata filters (ticker, document_type, section)
  - Step 4: Format results with citations
  - Return formatted response

Response Format:
"Found {n} relevant passages:

[1] Source: Apple 10-K 2024, Item 1A: Risk Factors, Page 15
The Company's business, results of operations, financial condition, and stock price 
may be adversely affected by supply chain issues...

[2] Source: Microsoft 10-K 2024, Item 1A: Risk Factors, Page 22
Our global operations and supply chain expose us to risks...

..."

Key Features:
- Dense vector search (no hybrid yet - that's Phase 2b)
  > **Note:** "Dense" search uses semantic embeddings to find similar meanings.
  > Phase 2b adds "hybrid" search which combines dense + BM25 keyword search for better recall.
- Top-k results (default 5)
- Optional filtering by ticker, document_type
- Include source citation for each result
- Return "No relevant documents found" if empty results

Metadata Filter Support:
- filters={"ticker": "AAPL"} - only Apple documents
- filters={"document_type": "10k"} - only 10-K filings
- filters={"section": "Risk Factors"} - specific sections

Reference:
- PineconeClient from 9.1
- BedrockEmbeddings from 8.1
- Existing rag.py stub structure
- [agent.mdc] for tool patterns

Verify: docker-compose exec backend python -c "from src.agent.tools.rag import retrieve_documents; print('OK')"
```

### 10.2 Test RAG Tool Manually

**Command:**
```bash
cd ~/Projects/aws-enterprise-agentic-ai

# Test RAG tool directly
docker-compose exec backend python -c "
from src.agent.tools.rag import retrieve_documents

# Test query
result = retrieve_documents('What are Apple\\'s supply chain risks?')
print(result)
"
```

**Expected Output:**
```
Found 5 relevant passages:

[1] Source: Apple 10-K 2024, Item 1A: Risk Factors, Page 15
The Company's business, results of operations, and financial condition depend on its 
ability to source adequate supplies of components...

[2] Source: Apple 10-K 2024, Item 1A: Risk Factors, Page 16
Supply chain disruptions, whether due to geopolitical tensions, natural disasters, 
or global health events, could adversely impact...

...
```

### 10.3 Basic RAG Tool Implementation Checklist

- [ ] rag.py updated with real Pinecone search
- [ ] Query embedding using BedrockEmbeddings
- [ ] Results formatted with source citations
- [ ] Metadata filtering works (ticker, document_type)
- [ ] Test query returns relevant results
- [ ] "No relevant documents found" for empty results

---

## 11. Agent Integration

### What We're Doing
Registering the updated SQL and RAG tools in the LangGraph agent and ensuring they work together.

### Why This Matters
- **Tool Selection:** Agent chooses appropriate tool based on query
- **Combined Queries:** Some questions need both SQL and RAG
- **Seamless Experience:** User doesn't need to specify which tool to use

### 11.1 Verify Tool Registration

**Agent Prompt:**
```
Update `backend/src/agent/tools/__init__.py` to ensure SQL and RAG tools are exported

Verify the file exports:
1. sql_query from sql module
2. retrieve_documents from rag module
3. Any existing tools (search, market_data)

Structure:
from src.agent.tools.sql import sql_query
from src.agent.tools.rag import retrieve_documents
from src.agent.tools.search import web_search  # existing
from src.agent.tools.market_data import get_market_data  # existing

__all__ = ["sql_query", "retrieve_documents", "web_search", "get_market_data"]

Reference:
- Existing tools/__init__.py structure
- Updated sql.py and rag.py from previous sections

Verify: docker-compose exec backend python -c "from src.agent.tools import sql_query, retrieve_documents; print('OK')"
```

### 11.2 Verify Agent Graph Has Tools

**Command:**
```bash
cd ~/Projects/aws-enterprise-agentic-ai

# Check registered tools in agent
docker-compose exec backend python -c "
from src.agent.graph import get_registered_tools

tools = get_registered_tools()
print('Registered tools:')
for tool in tools:
    print(f'  - {tool.name}: {tool.description[:50]}...')
"
```

**Expected Output:**
```
Registered tools:
  - sql_query: Query financial data from 10-K SEC filings...
  - retrieve_documents: Search documents for relevant inform...
  - web_search: Search the web for current information...
  - get_market_data: Get current stock prices and market da...
```

### 11.3 Test Agent with SQL Tool

**Command:**
```bash
# Test agent using SQL tool
docker-compose exec backend python -c "
from src.agent.graph import graph

result = graph.invoke({
    'messages': [{'role': 'user', 'content': 'Which company had the highest revenue in 2024?'}]
})
print(result['messages'][-1].content)
"
```

### 11.4 Test Agent with RAG Tool

**Command:**
```bash
# Test agent using RAG tool
docker-compose exec backend python -c "
from src.agent.graph import graph

result = graph.invoke({
    'messages': [{'role': 'user', 'content': 'What are the main risk factors for Tesla?'}]
})
print(result['messages'][-1].content)
"
```

### 11.5 Agent Integration Checklist

- [ ] tools/__init__.py exports sql_query and retrieve_documents
- [ ] get_registered_tools() shows all 4 tools
- [ ] Agent correctly uses SQL tool for financial queries
- [ ] Agent correctly uses RAG tool for document queries
- [ ] Agent selects appropriate tool automatically

---

## 12. End-to-End Verification

### What We're Doing
Testing all Phase 2a features together to verify the data foundation and basic tools work correctly.

### Why This Matters
- **Integration:** Verify all components work together
- **Real Queries:** Test with actual questions users would ask
- **Readiness:** Confirm Phase 2a exit criteria met

### 12.1 SQL Tool Verification

**Test Queries:**

```bash
cd ~/Projects/aws-enterprise-agentic-ai

# Start fresh Docker environment
docker-compose down && docker-compose up -d

# Test 1: Revenue comparison
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Which company had the highest revenue in 2024?"}'

# Test 2: Margin analysis
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Compare gross margins across all tech companies"}'

# Test 3: Segment breakdown
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What percentage of Apple revenue comes from iPhone?"}'
```

**Expected Results:**
- Revenue comparison returns correct ranking
- Margin analysis shows comparison table
- Segment breakdown shows percentage

### 12.2 RAG Tool Verification

**Test Queries:**

```bash
# Test 1: Risk factors
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What are the main supply chain risks mentioned in Apple 10-K?"}'

# Test 2: Business description
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "How does Tesla describe their competitive advantages?"}'

# Test 3: Regulatory risks
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What regulatory risks does JPMorgan face?"}'
```

**Expected Results:**
- Returns relevant passages with citations
- Citations include document, page, section
- Content matches the query topic

### 12.3 Combined Tool Usage

**Test Queries:**

```bash
# Test: Query that could use both tools
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is Apples China revenue and what risks do they mention about China?"}'
```

**Expected Result:**
- Agent should use SQL for revenue number
- Agent should use RAG for risk narrative
- Response combines both data sources

### 12.4 Health Check with New Components

**Command:**
```bash
curl http://localhost:8000/health | jq
```

**Expected Output:**
```json
{
  "status": "ok",
  "environment": "local",
  "version": "0.1.0",
  "api_version": "v1",
  "checks": {
    "database": {"status": "ok", "latency_ms": 45},
    "bedrock": {"status": "ok"},
    "pinecone": {"status": "ok", "vector_count": 1423}
  }
}
```

### 12.5 Deploy and Test on AWS

**Commands:**
```bash
cd ~/Projects/aws-enterprise-agentic-ai

# Build and push updated backend
docker build -t backend -f backend/Dockerfile backend/
docker tag backend:latest YOUR_ECR_URL:latest
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin YOUR_ECR_URL
docker push YOUR_ECR_URL:latest

# Trigger App Runner deployment
aws apprunner start-deployment --service-arn YOUR_SERVICE_ARN

# Wait for deployment (2-3 minutes)
sleep 180

# Test on AWS
curl https://yhvmf3inyx.us-east-1.awsapprunner.com/health
curl -X POST https://yhvmf3inyx.us-east-1.awsapprunner.com/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Which company had the highest revenue?"}'
```

### 12.6 End-to-End Verification Checklist

- [ ] SQL tool returns correct financial data
- [ ] RAG tool returns relevant passages with citations
- [ ] Agent selects appropriate tool for queries
- [ ] Combined queries use both tools when needed
- [ ] Health check shows all components healthy
- [ ] AWS deployment works with new features
- [ ] Frontend can interact with new tools

---

## Phase 2a Completion Checklist

### Infrastructure
- [ ] Neo4j AuraDB account created (free tier, $0/month - for Phase 2b)
- [ ] Neo4j secret in AWS Secrets Manager
- [ ] Neo4j added to docker-compose.yml for local development
- [ ] Document directories created

### Document Processing
- [ ] 7 10-K filings downloaded from SEC EDGAR
- [ ] 3-5 reference documents saved
- [ ] Document processing dependencies installed
- [ ] VLM extraction pipeline working
- [ ] All documents extracted to JSON

### SQL Tool
- [ ] 10-K schema migration created and applied
- [ ] Data loaded into PostgreSQL (7 companies, ~150 rows)
- [ ] SQL safety module with ALLOWED_TABLES
- [ ] SQL tool converts NL to SQL
- [ ] SQL tool returns correct results

### RAG Tool
- [ ] Bedrock Titan embeddings working
- [ ] Semantic chunking with spaCy
- [ ] Contextual enrichment prepends metadata
- [ ] Documents indexed in Pinecone (~1400 vectors)
- [ ] RAG tool returns relevant results with citations

### Agent Integration
- [ ] SQL and RAG tools registered in agent
- [ ] Agent selects appropriate tool
- [ ] End-to-end queries work locally
- [ ] Deployed to AWS and working

### Documentation
- [ ] REPO_STATE.md updated with new files
- [ ] .env.example updated with new variables

---

## Common Issues and Solutions

### Issue: VLM extraction fails with throttling error

**Symptoms:**
- "ThrottlingException" in extraction logs
- Extraction stops mid-document

**Solution:**
```bash
# Add retry with exponential backoff in vlm_extractor.py
# Or reduce batch size and add delays between pages
python scripts/extract_and_index.py --delay 2
```

### Issue: Pinecone upsert fails with dimension mismatch

**Symptoms:**
- "Dimension mismatch" error during indexing
- Vectors not appearing in Pinecone

**Solution:**
```bash
# Verify embedding dimension matches index
docker-compose exec backend python -c "
from src.utils.embeddings import BedrockEmbeddings
e = BedrockEmbeddings()
print(f'Embedding dimension: {e.get_dimension()}')
# Should be 1536
"
# Verify Pinecone index was created with 1536 dimensions
```

### Issue: SQL query returns empty results

**Symptoms:**
- "No data found" for valid queries
- Tables exist but appear empty

**Solution:**
```bash
# Verify data was loaded
docker-compose exec backend python -c "
from sqlalchemy import create_engine, text
from src.config.settings import get_settings
engine = create_engine(get_settings().database_url)
with engine.connect() as conn:
    result = conn.execute(text('SELECT COUNT(*) FROM companies'))
    print(f'Companies: {result.scalar()}')
"
# If 0, re-run: python scripts/load_10k_to_sql.py
```

### Issue: RAG returns irrelevant results

**Symptoms:**
- Search results don't match query
- Low relevance scores

**Solution:**
- Check embedding model is Titan (1536 dims)
- Verify contextual enrichment is applied
- Try more specific queries
- Check Pinecone filter syntax

### Issue: Agent doesn't use correct tool

**Symptoms:**
- SQL query triggers RAG tool
- RAG query triggers SQL tool

**Solution:**
- Review tool descriptions in tool definitions
- Make descriptions more distinct
- SQL: "Query structured financial metrics and numbers"
- RAG: "Search document text for information and context"

---

## Files Created/Modified in Phase 2a

### New Files Created

| File | Purpose |
|------|---------|
| `backend/src/ingestion/vlm_extractor.py` | Claude Vision extraction |
| `backend/src/ingestion/document_processor.py` | Document processing orchestrator |
| `backend/src/ingestion/semantic_chunking.py` | spaCy-based chunking |
| `backend/src/ingestion/contextual_chunking.py` | Context enrichment |
| `backend/src/utils/embeddings.py` | Bedrock Titan embeddings |
| `backend/src/utils/pinecone_client.py` | Pinecone client wrapper |
| `backend/src/agent/tools/sql_safety.py` | SQL validation and whitelisting |
| `backend/alembic/versions/001_10k_financial_schema.py` | 10-K database schema (first Alembic migration) |
| `scripts/extract_and_index.py` | Batch extraction and indexing |
| `scripts/load_10k_to_sql.py` | Load data to PostgreSQL |
| `documents/raw/10k/*.pdf` | Downloaded 10-K filings |
| `documents/raw/reference/*.pdf` | Reference documents |
| `documents/extracted/*.json` | VLM extraction output |
| `documents/manifest.json` | Extraction/indexing state tracking (prevents duplicate API calls) |

### Files Modified

| File | Changes |
|------|---------|
| `docker-compose.yml` | Added Neo4j service |
| `backend/requirements.txt` | Added document processing packages |
| `backend/Dockerfile` | Added poppler-utils, spaCy model |
| `backend/Dockerfile.dev` | Added poppler-utils, spaCy model |
| `backend/src/ingestion/__init__.py` | Export new classes |
| `backend/src/agent/tools/sql.py` | Real SQL implementation |
| `backend/src/agent/tools/rag.py` | Real RAG implementation |
| `backend/src/agent/tools/__init__.py` | Export updated tools |
| `.env.example` | Added Neo4j variables |
| `REPO_STATE.md` | Updated file inventory |

### AWS Resources Created

| Resource | Purpose |
|----------|---------|
| Secrets Manager: enterprise-agentic-ai/neo4j | Neo4j connection credentials |

### External Accounts Created

| Service | Purpose | Tier |
|---------|---------|------|
| Neo4j AuraDB | Knowledge Graph database | Free (200K nodes) |

---

## Branch Management and Next Steps

### Save Phase 2a Work

**Commands:**
```bash
cd ~/Projects/aws-enterprise-agentic-ai

# Stage all changes
git add .

# Commit with descriptive message
git commit -m "Complete Phase 2a: Data foundation with SQL and basic RAG tools

- VLM extraction pipeline for 10-K documents
- SQL tool with real financial queries
- Basic RAG with Pinecone dense search
- Neo4j AuraDB setup for Phase 2b
- Document processing dependencies"

# Tag Phase 2a completion
git tag -a v0.4.0-phase2a -m "Phase 2a complete - Data Foundation"

# Push to remote
git push origin main
git push origin v0.4.0-phase2a
```

### Prepare for Phase 2b

Phase 2b adds (using Neo4j infrastructure set up in Phase 2a):
- **Knowledge Graph:** spaCy entity extraction, Neo4j storage, graph queries
- **Advanced RAG:** BM25 sparse vectors (hybrid search), query expansion, RRF fusion
- **Cross-encoder Reranking:** LLM-based relevance scoring
- **Multi-tool Orchestration:** Combined SQL + RAG queries

**Create Phase 2b branch:**
```bash
git checkout -b phase-2b-intelligence-layer
```

---

## Summary

Phase 2a establishes the data foundation with:
- ✅ VLM extraction pipeline for 10-K and reference documents
- ✅ SQL tool querying real financial data from SEC filings
- ✅ Basic RAG with dense vector search in Pinecone
- ✅ Neo4j AuraDB infrastructure ready for Phase 2b Knowledge Graph
- ✅ Agent integration with tool selection

**Key Achievements:**
- Real financial queries: "Which company had highest revenue?"
- Document search: "What are Apple's supply chain risks?"
- Source citations for all RAG results
- SQL injection prevention with ALLOWED_TABLES

**Next Phase (2b):** Add intelligence layer (uses Neo4j from Phase 2a):
- Knowledge Graph with spaCy entity extraction → Neo4j storage
- Hybrid search (dense embeddings + BM25 keyword search)
- Query expansion and cross-encoder reranking
- Multi-tool query orchestration (SQL + RAG combined)

**Estimated Time for Phase 2a:** 8-12 hours

**Success Criteria:** ✅ SQL tool answers financial queries correctly, RAG tool returns relevant passages with citations, agent selects appropriate tool automatically.
