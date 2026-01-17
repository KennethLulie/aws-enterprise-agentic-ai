# Development Reference Guide

**Purpose:** This document serves as the authoritative reference for implementation details, technology specifications, and development order throughout all phases. Consult this document before implementing any feature to ensure consistency, completeness, and proper integration.  Make sure this document is updated as needed as the project proceeds.

**Last Updated:** 2026-01-15 (Phase 2 how-to guides complete) - Implementation guides ready: `docs/PHASE_2A_HOW_TO_GUIDE.md` (Data Foundation) and `docs/PHASE_2B_HOW_TO_GUIDE.md` (Intelligence Layer). See `docs/RAG_README.md` for architecture.

---

## Table of Contents

1. [Global Configuration](#global-configuration)
2. [Phase 0: Local Development Environment](#phase-0-local-development-environment)
3. [Phase 1a: Minimal MVP](#phase-1a-minimal-mvp)
4. [Phase 1b: Production Hardening](#phase-1b-production-hardening)
5. [Phase 2: Core Agent Tools](#phase-2-core-agent-tools)
6. [Phase 3: Observability with Arize Phoenix](#phase-3-observability-with-arize-phoenix)
7. [Phase 4: RAG Evaluation with RAGAS](#phase-4-rag-evaluation-with-ragas)
8. [Phase 5: Enhanced UI and Thought Process Streaming](#phase-5-enhanced-ui-and-thought-process-streaming)
9. [Phase 6: Input/Output Verification](#phase-6-inputoutput-verification)
10. [Phase 7: Inference Caching](#phase-7-inference-caching)
11. [Implementation Order Guidelines](#implementation-order-guidelines)
12. [Consistency Checks](#consistency-checks)

---

## Global Configuration

### AWS Region
- **Region:** `us-east-1` (N. Virginia - closest to Austin, TX)
- **All AWS resources:** Must use `us-east-1` unless explicitly stated otherwise
- **Pinecone:** Use `us-east-1` region. Fallback: `us-west-2` (the only other US region Pinecone Serverless supports)

### Environment Variables & Secrets Management

**IMPORTANT: Never commit real API keys or secrets to the repository.**

This project uses a two-tier secrets management approach:

| Environment | Secrets Storage | Configuration |
|-------------|-----------------|---------------|
| **Local Development** | `.env` file (gitignored) | Copy from `.env.example`, fill in your values |
| **AWS Production** | AWS Secrets Manager | Loaded automatically when `ENVIRONMENT=aws` |
| **CI/CD Pipelines** | GitHub Secrets | Configured in repository settings |

**Setup for Local Development:**
1. Copy the template: `cp .env.example .env`
2. Edit `.env` and fill in your actual API keys
3. The `.env` file is gitignored and will never be committed

**Required Variables:** See [`.env.example`](.env.example) for the complete list of environment variables with descriptions and where to obtain each key. For Phase 0 auth, set:
- `DEMO_PASSWORD` – demo login password
- `AUTH_TOKEN_SECRET` – HMAC secret for signing the session cookie
- `AUTH_TOKEN_EXPIRES_MINUTES` – session lifetime (default 1440)
- `AUTH_COOKIE_NAME` – cookie name for the signed session token

**For Production Deployment:** See [`docs/SECURITY.md`](docs/SECURITY.md) for AWS Secrets Manager configuration.

### Project Structure
**Base Path:** `aws-enterprise-agentic-ai/`

**Key Directories:**
- `backend/src/` - Python backend source code
- `frontend/src/` - Next.js frontend source code
- `terraform/` - Infrastructure as Code
- `scripts/` - Development and deployment scripts
- `docs/` - Documentation
- `lambda/` - Lambda function code
- `.github/workflows/` - CI/CD pipelines

---

## Phase 0: Local Development Environment

### Goal
Fully working agent locally before any AWS deployment.

### Technology Specifications

#### Backend Stack
- **Language:** Python 3.11+
- **Framework:** FastAPI
- **ASGI Server:** Uvicorn (with `--reload` for hot reload)
- **Agent Framework:** LangGraph (real, with tool orchestration)
- **LLM:** AWS Bedrock (Nova Pro/Lite, Titan Embeddings, Claude fallback)
- **Checkpointing:** MemorySaver (in-memory, no DB)
- **Web Search:** Real Tavily API (with mock fallback when API key not set) - **Phase 2a completed early**
- **Market Data:** Real FMP API (with mock fallback when API key not set) - **Phase 2d completed early**
- **Database:** Stub-only in Phase 0 (SQL tool returns mock data); real DB in Phase 2b
- **Vector Store:** Stub-only in Phase 0 (RAG tool returns mock data); real retrieval in Phase 2c
- **Logging:** Basic Python logging (upgrade to structlog in Phase 1b)

#### Frontend Stack
- **Framework:** Next.js 16 (App Router, static export)
- **Language:** TypeScript (TS 5)
- **UI Library:** shadcn/ui + Radix primitives
- **SSE Client:** Native EventSource API (no Vercel AI SDK)
- **Styling:** Tailwind CSS 4
- **Advanced Features:** Includes Phase 5 thought process streaming and enhanced UX (implementation ahead of Phase 0 baseline)

#### Docker Compose
- **Services:**
  - `backend`: FastAPI on port 8000
  - `frontend`: Next.js dev server on port 3000
- **No local database/vector/KG services in Phase 0** (SQL and RAG tools return mock data)
- **External APIs:** Tavily (search) and FMP (market data) are real API calls to external managed services
- **Vector Store:** Pinecone Serverless (external managed service, not local)
- **Volume Mounts:** `./backend:/app`, `./frontend:/app` (hot reload)
- **Startup Time Target:** 5-10 seconds

#### Local Python Tooling (Optional)

For better IDE support (autocomplete, type checking, import resolution), you can install Python dependencies locally while still running the application in Docker:

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

Configure Cursor/VS Code to use `.venv/bin/python` as the Python interpreter. This does not change the Docker-first workflow - it's purely for IDE tooling support. See PHASE_0_HOW_TO_GUIDE.md section 1.7 for detailed instructions.

### Implementation Order

#### Step 1: Project Structure Setup
1. Create directory structure per PROJECT_PLAN.md
2. Initialize Git repository
3. Create `.gitignore` (Python, Node.js, .env, etc.)
4. Create `.env.example` with all required variables

#### Step 2: Backend Foundation
1. **Configuration** (`backend/src/config/settings.py`)
   - Pydantic Settings class
   - Environment variable loading
   - Local vs AWS detection
   - Validation on startup

2. **FastAPI App** (`backend/src/api/main.py`)
   - FastAPI instance creation
   - CORS middleware (allow localhost:3000)
   - Basic error handling
   - Health check endpoint (`/health`)

3. **Dependencies** (`backend/requirements.txt`)
   - Pin all versions
   - Core: fastapi, uvicorn, langgraph, boto3
   - Add comments for each phase's dependencies

#### Step 3: LangGraph Agent Core
1. **State Schema** (`backend/src/agent/state.py`)
   - Define state structure
   - Use TypedDict or Pydantic model
   - Include: messages, conversation_id, tools_used, etc.

2. **Graph Definition** (`backend/src/agent/graph.py`)
   - Create LangGraph graph
   - Use MemorySaver for checkpointing
   - Basic nodes: chat, tools, error_recovery
   - Streaming configuration

3. **Chat Node** (`backend/src/agent/nodes/chat.py`)
   - LLM invocation (Bedrock Nova Pro)
   - Fallback to Claude if Nova fails
   - Message handling
   - Tool calling setup

4. **Tool Execution Node** (`backend/src/agent/nodes/tools.py`)
   - Tool selection logic
   - Tool execution wrapper
   - Result formatting

5. **Error Recovery Node** (`backend/src/agent/nodes/error_recovery.py`)
   - Error handling
   - Retry logic
   - User-friendly error messages

#### Step 4: Basic Tools
1. **Tool Base** (`backend/src/agent/tools/__init__.py`)
   - Tool interface/base class
   - Common error handling
   - Circuit breaker base

2. **Tools** (Phase 0 implementation)
   - `search.py` - Real Tavily API (with mock fallback when API key not set)
   - `market_data.py` - Real FMP API (with mock fallback when API key not set)
   - `sql.py` - Stub returning mock data (real Neon PostgreSQL in Phase 2)
   - `rag.py` - Stub returning mock data (real Pinecone in Phase 2)

#### Step 5: Frontend Foundation
1. **Next.js Setup** (`frontend/`)
   - Initialize Next.js with TypeScript
   - Configure for static export
   - Install shadcn/ui
   - Setup Tailwind CSS

2. **Login Page** (`frontend/src/app/login/page.tsx`)
   - Password input form
   - Use HTTP-only cookies for secure session management
   - Redirect to chat on success

3. **Chat Page** (`frontend/src/app/page.tsx`)
   - Chat interface layout
   - Message display area with thinking/reasoning sections (Phase 5 feature)
   - Input field
   - SSE connection setup (EventSource) with advanced reconnection logic

4. **API Client** (`frontend/src/lib/api.ts`)
   - SSE connection function
   - Message sending function
   - Error handling

#### Step 6: Docker Compose
1. **docker-compose.yml**
   - Backend service (FastAPI)
   - Frontend service (Next.js)
   - Volume mounts for hot reload
   - Environment variables
   - Note: No database services in Phase 0 (SQL/RAG tools return mock data)

2. **Backend Dockerfile.dev**
   - Multi-stage build
   - Development stage with hot reload
   - Volume mount support

3. **Frontend Dockerfile.dev**
   - Node.js base
   - Development dependencies
   - Hot reload enabled

#### Step 7: Development Scripts
1. **scripts/setup.sh**
   - Validate Docker installation
   - Validate AWS CLI
   - Create .env from .env.example
   - Pre-pull Docker images

2. **scripts/validate_setup.py**
   - Check all prerequisites
   - Validate .env variables
   - Test AWS credentials
   - Test external API keys

3. **scripts/dev.sh**
   - Commands: start, stop, logs, test, shell, db

#### Step 8: Testing Foundation
1. **backend/tests/test_agent.py**
   - Basic agent tests
   - Mock Bedrock calls
   - Test graph execution

2. **pytest.ini**
   - Test configuration
   - Coverage settings

#### Step 9: Pre-commit Hooks
1. **.pre-commit-config.yaml**
   - black (formatting)
   - ruff (linting)
   - mypy (type checking)
   - pytest (tests)

### Phase 0 Deliverables Checklist
- [ ] LangGraph agent with streaming responses
- [ ] MemorySaver checkpointing working
- [ ] Chat UI with real-time streaming
- [ ] Basic conversation flow validated
- [ ] All tools have stub implementations
- [ ] Environment variable config working
- [ ] Docker Compose starts in 5-10 seconds
- [ ] Requirements.txt with pinned versions
- [ ] Basic unit tests passing
- [ ] Setup scripts working
- [ ] Health check endpoint responding
- [ ] Pre-commit hooks configured

### Consistency Checks
- [ ] All imports use absolute paths from `backend/src/`
- [ ] All environment variables have defaults or validation
- [ ] Error messages are user-friendly
- [ ] Type hints on all functions
- [ ] Docstrings on all classes and functions
- [ ] Logging statements use appropriate levels

---

## Phase 1a: Minimal MVP

### Goal
Deployed chatbot accessible via password-protected website with streaming responses.

### Technology Specifications

#### Infrastructure (Terraform)
- **Region:** us-east-1
- **VPC:** Two public subnets (no private subnets, no NAT Gateway)
- **App Runner:** 
  - Scales to 0 (minimum instances: 0)
  - Maximum instances: 10
  - No VPC connector yet
  - Public internet access
- **S3:** Frontend static files bucket
- **CloudFront:** Distribution for S3
- **Secrets Manager:** Password storage
- **ECR:** Container registry
- **CloudWatch Logs:** Application logging

#### Backend Changes
- **Checkpointing:** MemorySaver (no database yet)
- **Logging:** Basic Python logging → CloudWatch Logs
- **API Endpoint:** `/api/chat` (no versioning yet)
- **Health Check:** `/health` (simple, no dependency checks)

#### Frontend Changes
- **Build:** Next.js static export
- **Deployment:** S3 + CloudFront
- **API Calls:** Direct to App Runner URL (CORS enabled)

### Implementation Order

#### Step 1: Terraform Infrastructure
1. **Terraform State Setup**
   - Create S3 bucket for state
   - Create DynamoDB table for locking
   - Configure backend.tf

2. **Networking Module** (`terraform/modules/networking/`)
   - VPC with 2 public subnets
   - Internet Gateway
   - Route tables
   - Security groups (basic)

3. **ECR Module** (`terraform/modules/ecr/`)
   - ECR repository for backend

4. **App Runner Module** (`terraform/modules/app-runner/`)
   - App Runner service
   - IAM role
   - Environment variables
   - No VPC connector

5. **S3 + CloudFront Module** (`terraform/modules/s3-cloudfront/`)
   - S3 bucket for frontend
   - CloudFront distribution
   - Bucket policy for CloudFront access

6. **Secrets Manager** (`terraform/modules/secrets/`)
   - Password secret
   - IAM policy for App Runner to read

#### Step 2: Backend Updates for AWS
1. **Environment Detection** (`backend/src/config/settings.py`)
   - Detect AWS vs local
   - Load Secrets Manager password in AWS
   - Load .env password locally

2. **CORS Configuration** (`backend/src/api/main.py`)
   - Allow CloudFront origin
   - Allow localhost for development

3. **CloudWatch Logging** (`backend/src/api/middleware/logging.py`)
   - Basic CloudWatch Logs integration
   - Log level configuration

4. **Health Endpoint** (`backend/src/api/routes/health.py`)
   - Simple health check
   - Return {"status": "ok"}

#### Step 3: Frontend Updates for Static Export
1. **next.config.js**
   - `output: 'export'`
   - Disable API routes
   - Configure base path if needed

2. **API Client** (`frontend/src/lib/api.ts`)
   - Use App Runner URL (from environment)
   - Handle CORS
   - Error handling for cold starts

3. **Cold Start UX** (`frontend/src/components/cold-start/WarmupIndicator.tsx`)
   - Loading indicator
   - "Warming up..." message
   - Estimated wait time

#### Step 4: Docker Production Build
1. **Backend Dockerfile** (`backend/Dockerfile`)
   - Multi-stage build
   - Production stage
   - No hot reload
   - Optimized layers

2. **Build and Push**
   - Build Docker image
   - Tag for ECR
   - Push to ECR

#### Step 5: Deployment
1. **Terraform Apply**
   - Apply networking
   - Apply ECR
   - Apply App Runner
   - Apply S3 + CloudFront
   - Apply Secrets Manager

2. **Frontend Build and Upload**
   - `npm run build` (creates `out/` directory)
   - Upload to S3: `aws s3 sync out/ s3://<bucket>/`

3. **CloudFront Invalidation**
   - Invalidate cache: `aws cloudfront create-invalidation`

### Phase 1a Deliverables Checklist
- [ ] Working chat interface at CloudFront URL
- [ ] Streaming responses visible in real-time
- [ ] Cold start loading indicator
- [ ] Conversation persistence (in-memory)
- [ ] Manual deployment process documented
- [ ] Terraform infrastructure deployed
- [ ] App Runner service running
- [ ] CloudFront distribution active

### Consistency Checks
- [ ] All AWS resources use us-east-1
- [ ] CORS allows CloudFront origin
- [ ] Password auth works in AWS
- [ ] Health endpoint accessible
- [ ] Logs appear in CloudWatch
- [ ] Frontend loads from CloudFront

---

## Phase 1b: Production Hardening

### Goal
Add production-grade features: persistent state, CI/CD, observability, security hardening.

### Technology Specifications

#### Infrastructure Additions
- **Neon PostgreSQL (External Service):**
  - Free tier (0.5GB storage, 190 compute hours/month)
  - PostgreSQL 16
  - Connection via public internet (SSL encrypted)
  - No VPC connector needed
  - DATABASE_URL stored in AWS Secrets Manager
- **GitHub Actions:**
  - **Phase gating:** Workflows added in Phase 1b (none active in Phase 0).
  - **CI (`pull_request`):** black, ruff, mypy; ESLint/Prettier/tsc; pytest; Docker test builds; Terraform fmt/validate/plan (no apply); security scans (Bandit, Checkov, gitleaks).
  - **CD (`push` to `main`):** Build/push backend image to ECR; Next.js static export; upload to S3; Terraform apply (manual approval for prod); CloudFront invalidate; smoke/health checks.
  - **Evaluation (scheduled/dispatch):** RAGAS run against eval dataset; publish metrics to Arize Phoenix/CloudWatch; fail/alert on regressions.
  - **Secrets (GitHub):** `AWS_REGION` (us-east-1), AWS creds with ECR/Terraform perms, `AWS_ACCOUNT_ID`, `PINECONE_API_KEY`, `TAVILY_API_KEY`, Bedrock access via IAM, and any eval dataset bucket refs. Store all in GitHub Secrets; never commit.

#### Backend Changes
- **Checkpointing:** PostgresSaver (migrate from MemorySaver)
- **Database:** Alembic migrations
- **Logging:** structlog with JSON output
- **API:** Version to `/api/v1/chat`
- **Health:** Enhanced with dependency checks
- **Rate Limiting:** slowapi middleware
- **Error Handling:** Comprehensive with retry logic

### Implementation Order

#### Step 1: Neon Database Setup
1. **Neon Account & Project:**
   - Create free tier account at neon.tech
   - Create project in us-east-1 (AWS)
   - Copy connection string from dashboard

2. **AWS Secrets Manager:**
   - Create `enterprise-agentic-ai/database-url` secret
   - Store Neon connection string
   - Update App Runner to read DATABASE_URL secret

#### Step 2: Database Setup
1. **Alembic Setup** (`backend/alembic/`)
   - Initialize Alembic for future app migrations
   - Configure env.py for dynamic DATABASE_URL
   - Note: Checkpoint tables handled by PostgresSaver.setup()

2. **Database Connection** (`backend/src/db/session.py`)
   - SQLAlchemy engine
   - Connection pooling (5 connections, max overflow 10)
   - Session management

3. **PostgresSaver Integration** (`backend/src/agent/graph.py`)
   - Replace MemorySaver with PostgresSaver
   - PostgresSaver.setup() creates checkpoint tables automatically
   - Test checkpointing

#### Step 3: Structured Logging
1. **structlog Configuration** (`backend/src/api/middleware/logging.py`)
   - Configure structlog processors
   - JSON output format
   - CloudWatch integration
   - Context variables

2. **Update All Logging** (throughout backend)
   - Replace print() with logger
   - Add structured fields
   - Consistent log levels

#### Step 4: Enhanced Features
1. **API Versioning** (`backend/src/api/routes/v1/chat.py`)
   - Move `/api/chat` to `/api/v1/chat`
   - Update frontend API calls

2. **Enhanced Health Check** (`backend/src/api/routes/health.py`)
   - Check Neon database connection
   - Check Bedrock access
   - Return dependency status

3. **Rate Limiting** (`backend/src/api/middleware/rate_limit.py`)
   - slowapi middleware
   - 10 requests/minute per IP
   - Configurable limits

4. **Error Handling** (`backend/src/api/middleware/error_handler.py`)
   - Global error handler
   - User-friendly messages
   - Error logging

#### Step 5: GitHub Actions CI/CD
1. **CI Pipeline** (`.github/workflows/ci.yml`)
   - Triggers: push to main AND pull_request to main
   - Lint (black, ruff)
   - Type check (mypy)
   - Test (pytest)
   - Terraform validate
   - Security scan

2. **CD Pipeline** (`.github/workflows/deploy.yml`)
   - Triggers: workflow_dispatch (manual trigger via GitHub Actions UI)
   - Build Docker image
   - Push to ECR
   - Build frontend
   - Upload to S3
   - CloudFront invalidation
   - Health check

3. **GitHub Secrets Setup**
   - AWS_ACCESS_KEY_ID
   - AWS_SECRET_ACCESS_KEY
   - AWS_REGION
   - TAVILY_API_KEY
   - PINECONE_API_KEY
   - FMP_API_KEY

### Phase 1b Deliverables Checklist
- [ ] Conversation state persists across restarts
- [ ] Automated deployment pipeline
- [ ] Enhanced monitoring and logging
- [ ] Production-ready security
- [ ] Neon database connected
- [ ] DATABASE_URL secret configured
- [ ] GitHub Actions workflows working

### Consistency Checks
- [ ] PostgresSaver configured with DATABASE_URL (uses psycopg3, separate from SQLAlchemy pool)
- [ ] All logs use structlog with JSON format
- [ ] API versioning consistent across all endpoints
- [ ] Rate limiting applied to all API routes
- [ ] Error messages are user-friendly
- [ ] Health check validates all dependencies

---

## Phase 2: Core Agent Tools

### Goal
Agent can search the web, query SQL databases, and retrieve from documents.

**Note:** Tools 2a (Tavily Search) and 2d (Market Data) were completed ahead of schedule in Phase 0. Phase 2 focuses on implementing 2b (SQL Query) and 2c (RAG Retrieval).

### Data Flow Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    python scripts/extract_and_index.py                       │
│                         (Local Batch Processing)                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      Claude VLM (Bedrock) - ALL Documents                    │
│                 10-Ks, news articles, research reports, etc.                │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ Clean structured text + tables
                                      │
         ┌────────────────────────────┼────────────────────────────┐
         ▼                            ▼                            ▼
┌─────────────────┐        ┌─────────────────┐        ┌─────────────────┐
│  Titan Embed    │        │   spaCy NER     │        │  Parse Tables   │
│  + BM25 Index   │        │                 │        │  (10-Ks only)   │
│                 │        │                 │        │                 │
│ → Pinecone      │        │ → Neo4j         │        │ → PostgreSQL    │
│   (RAG Tool)    │        │   (KG queries)  │        │   (SQL Tool)    │
└─────────────────┘        └─────────────────┘        └─────────────────┘
```

**Key Decisions:**
- **VLM for ALL documents** - One extraction pipeline, consistent output
- **Batch scripts** - No Lambda, no timeouts, easier debugging
- **spaCy for NER** - 20-50x cheaper than LLM for entity extraction

**Implementation Guides:**
- `docs/PHASE_2A_HOW_TO_GUIDE.md` - Data Foundation (VLM, SQL tool, basic RAG)
- `docs/PHASE_2B_HOW_TO_GUIDE.md` - Intelligence Layer (Knowledge Graph, hybrid retrieval, multi-tool)
- `docs/RAG_README.md` - Architecture overview and design decisions

### Technology Specifications

#### Tool 2a: Tavily Search ✅ *COMPLETED IN PHASE 0*
- **API:** Tavily Search API
- **Rate Limit:** 1,000 searches/month (free tier)
- **Error Handling:** Retry with exponential backoff
- **Circuit Breaker:** 5 failures → open, recover after 60s
- **Logging:** Structured logging of queries and results
- **Implementation:** `backend/src/agent/tools/search.py`
- **Status:** Fully functional with mock fallback when API key not set

#### Tool 2b: SQL Query 🚧 *TO BE IMPLEMENTED*
- **Database:** Neon PostgreSQL (from Phase 1b)
- **Data Source:** Real 10-K financial metrics extracted via VLM
- **Tables:** companies, financial_metrics, segment_revenue, geographic_revenue, risk_factors
- **ORM:** SQLAlchemy
- **Connection Pooling:** Built-in (5 connections, max overflow 10)
- **Security:** Parameterized queries, ALLOWED_TABLES whitelisting
- **Safety:** Read-only, max 1000 rows, 30s query timeout
- **Use Cases:** "Compare revenue growth", "Which company has highest margins?", "Show segment breakdown"

#### Tool 2c: RAG Retrieval (2026 SOTA)

> **Full Architecture:** See `docs/RAG_README.md` for comprehensive architecture, alternatives, and enterprise features.

**Document Extraction:**
- **All Documents:** VLM extraction (Claude Vision via Bedrock) - one code path for simplicity
- **Processing:** Local batch script (no Lambda timeouts or complexity)
- **Extraction Cost:** ~$0.03-0.05/page for VLM
- **One-Time Cost:** ~$40-60 for ~30-40 documents total (10-Ks + reference docs)

**Sample Documents:**
- **10-K Filings (~7):** AAPL, MSFT, AMZN, GOOGL, TSLA, JPM, NVDA (FY2024)
- **Reference Docs (~10-15):** News articles, research reports, market analysis
- **Source:** SEC EDGAR for 10-Ks, financial news sites for reference docs
- **See:** `docs/PHASE_2A_HOW_TO_GUIDE.md` Section 3 for document acquisition details

> **Why VLM for everything?** Simpler codebase (one extraction path), consistent output, negligible cost difference for demo volume. See `docs/PHASE_2A_HOW_TO_GUIDE.md` Section 5 for VLM extraction details.

**Vector Store & Search:**
- **Vector Store:** Pinecone Serverless (free tier, 100K vectors)
- **Embeddings:** Bedrock Titan Embeddings (1536 dimensions)
- **Hybrid Search:** Dense + sparse vectors with RRF fusion

**Ingestion Pipeline:**
- **Semantic Chunking:** spaCy sentence boundary detection (replaces fixed-size)
- **Contextual Retrieval:** Prepend doc title/type/section to chunks before embedding
- **Parent Document Retriever:** Small chunks for search, large context for response

**Query Pipeline:**
- **Query Expansion:** Generate 3 alternative phrasings (+20-30% recall)
- **Cross-Encoder Reranking:** Nova Lite scores relevance after RRF (+20-25% precision)
- **Compression:** LLMChainExtractor for contextual compression

#### Tool 2c-KG: Knowledge Graph Integration
- **Store:** Neo4j AuraDB Free (200K nodes, 400K relationships, $0/month)
- **Entity Extraction:** spaCy NER + custom financial patterns (no LLM needed)
- **Entity Types:** Document, Organization, Person, Location, Regulation, Concept, Product, Metric
- **Relationship Types:** MENTIONS, RELATED_TO, GOVERNED_BY, REPORTED
- **Traversal:** 1-2 hop relationship queries
- **Cost:** ~$0.001/doc ingestion, $0/query (free tier)
- **See:** `docs/RAG_README.md` Knowledge Graph section for full ontology

#### Tool 2d: Market Data (FMP via MCP) ✅ *COMPLETED IN PHASE 0*
- **API:** Financial Modeling Prep (free tier ~250 calls/day; batch quotes supported)
- **Error Handling:** Retry with exponential backoff; handle 429s gracefully
- **Circuit Breaker:** 5 failures → open, recover after 60s
- **Input Validation:** Ticker list (1..N), uppercased, trimmed
- **Output:** price, change, change%, open, previous close, day high/low, volume, currency, exchange, timestamp
- **Implementation:** `backend/src/agent/tools/market_data.py`
- **Status:** Fully functional with mock fallback when API key not set

#### Infrastructure Additions

**AWS Resources:**
- **S3 Bucket (optional):** Document storage, extracted JSON backup
- **IAM Policies:** Tool access permissions, Bedrock Claude access

> **Note:** No Lambda infrastructure for document ingestion. All documents processed via local batch script for simplicity. See `docs/completed-phases/PHASE_2_REQUIREMENTS.md` "Enterprise Scaling" for Lambda-based approach.

**External Services:**
- **Neo4j AuraDB Free:** Knowledge graph storage (200K nodes, $0/month)
- **Pinecone Serverless:** Vector store (free tier, 100K vectors)

**Local Development:**
- **Neo4j Docker:** neo4j:5-community for local graph database
- **spaCy Model:** en_core_web_sm for NLP entity extraction

**New Python Dependencies (Phase 2):**
```
# Document Processing
pdf2image~=1.17.0           # PDF to images for VLM extraction
Pillow~=10.4.0              # Image processing
python-magic~=0.4.27        # File type detection

# Vector Store & Knowledge Graph
pinecone-client~=5.0.0      # Vector store (matches Package Versions section)
neo4j~=5.25.0               # Knowledge graph (matches Package Versions section)
spacy~=3.8.0                # NLP for entity extraction and chunking
```

**Note:** Version numbers should match the [Package Versions](#package-versions) section. If updating, change both places.

**System Dependencies (Dockerfile):**
```dockerfile
# PDF processing and file type detection
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# spaCy model for entity extraction and sentence boundary detection
RUN python -m spacy download en_core_web_sm
```

**Local Development (if not using Docker):**
```bash
# Ubuntu/Debian
sudo apt-get install poppler-utils

# macOS  
brew install poppler

# spaCy model (required for NER and chunking)
python -m spacy download en_core_web_sm
```

**Docker Compose Addition:**
```yaml
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
```

**Phase 2 Environment Variables:**

Add to `.env.example` and `.env`:

```bash
# =============================================================================
# Phase 2: Vector Store & Knowledge Graph
# =============================================================================

# Pinecone (Vector Store)
PINECONE_API_KEY=your_pinecone_api_key        # From https://pinecone.io console
PINECONE_INDEX_NAME=enterprise-agentic-ai     # Create in Pinecone console
PINECONE_ENVIRONMENT=us-east-1                # AWS region

# Neo4j (Knowledge Graph)
NEO4J_URI=neo4j://localhost:7687              # Local Docker (or neo4j+s://xxx.databases.neo4j.io for AuraDB)
NEO4J_USER=neo4j                              # Default user
NEO4J_PASSWORD=localdevpassword               # Match docker-compose (or AuraDB password)
```

**AWS Secrets Manager (Production):**

| Secret Name | Key | Purpose |
|-------------|-----|---------|
| `enterprise-agentic-ai/pinecone` | `api_key` | Pinecone API key |
| `enterprise-agentic-ai/neo4j` | `uri`, `user`, `password` | Neo4j connection |

#### Security Hardening (Phase 2)

**SQL Tool Security:**
- Parameterized queries only (SQLAlchemy `text()` with parameters)
- `ALLOWED_TABLES` whitelist for query validation
- Read-only database user for SQL tool queries
- Query timeout: 30 seconds max
- Result limit: 1000 rows max
- Never use string formatting for SQL

**Conversation Security (Checkpoint Protection):**
- UUID format validation for `conversation_id` at API layer
- Session-to-conversation binding (map conversation_id → user session)
- Access control: users can only access their own conversations
- Reject non-UUID conversation_ids to prevent enumeration attacks

**Implementation:**
```python
from uuid import UUID
from pydantic import field_validator

class SendMessageRequest(BaseModel):
    conversation_id: str | None = None

    @field_validator('conversation_id')
    @classmethod
    def validate_uuid(cls, v: str | None) -> str | None:
        if v is None:
            return v
        try:
            UUID(v)
            return v
        except ValueError:
            raise ValueError("conversation_id must be a valid UUID")
```

**Reference:** See `[_security.mdc]` for complete patterns

### Implementation Order

#### Step 1: Tavily Search Tool ✅ *COMPLETED IN PHASE 0*
1. **Tool Implementation** (`backend/src/agent/tools/search.py`) ✅
   - Tavily API client
   - Tool definition for LangGraph
   - Result formatting with citations
   - Error handling with retry
   - Mock fallback when API key not set
   - Structured logging

2. **Circuit Breaker** - Simplified implementation in Phase 0 (full implementation in Phase 2)

#### Step 2: SQL Query Tool 🚧 *PHASE 2 PRIORITY*

**Data Source:** Real 10-K financial metrics extracted via VLM (not synthetic Faker data).

1. **Database Schema** (`backend/alembic/versions/001_10k_financial_schema.py`)
   - `companies` - Company info (ticker, name, sector, filing dates)
   - `financial_metrics` - Revenue, net income, margins, EPS by year
   - `segment_revenue` - Revenue breakdown by business segment
   - `geographic_revenue` - Revenue breakdown by region
   - `risk_factors` - Categorized risks from Item 1A

2. **Data Loading** (`scripts/load_10k_to_sql.py`)
   - Parses VLM extraction JSON output
   - Populates all tables from 10-K data
   - Handles ~7 companies, ~150 total rows

3. **Tool Implementation** (`backend/src/agent/tools/sql.py`)
   - SQLAlchemy connection
   - Natural language to SQL (via LLM with schema context)
   - Query execution with safety checks
   - Parameterized queries only
   - Table whitelisting (ALLOWED_TABLES)
   - Result formatting
   - Error handling

4. **SQL Safety** (`backend/src/agent/tools/sql_safety.py`)
   - ALLOWED_TABLES: companies, financial_metrics, segment_revenue, geographic_revenue, risk_factors
   - Query validation function
   - SQL injection prevention
   - Read-only enforcement

**Sample Queries:**
- "Which company had the highest revenue in 2024?"
- "Compare gross margins across tech companies"
- "What percentage of Apple's revenue comes from iPhone?"
- "Which companies have supply chain risks?"

#### Step 3: RAG Retrieval Tool (2026 SOTA)

> **Reference:** See `docs/RAG_README.md` for architecture, `docs/PHASE_2A_HOW_TO_GUIDE.md` for basic RAG, and `docs/PHASE_2B_HOW_TO_GUIDE.md` for hybrid retrieval.

**3a. Document Extraction (VLM for All Documents):**

1. **VLM Extractor** (`backend/src/ingestion/vlm_extractor.py`)
   - Claude Vision via Bedrock for ALL documents
   - Converts PDF pages to images (150 DPI)
   - Extracts structured JSON per page
   - Preserves table structure as markdown
   - Identifies sections and cross-references
   - Cost: ~$0.03-0.05/page

2. **Unified Extraction Script** (`scripts/extract_and_index.py`)
   - Main batch processing script for all documents
   - Runs locally (no Lambda timeouts)
   - Orchestrates: extract → chunk → embed → index
   - Handles both 10-Ks and reference documents

> **Why VLM for everything?** One code path, consistent output format, and ~$50 total cost for the demo is negligible. See `docs/PHASE_2A_HOW_TO_GUIDE.md` Section 5 for VLM extraction implementation.

**3b. Ingestion Pipeline:**

3. **Document Processor** (`backend/src/ingestion/document_processor.py`)
   - Orchestrates VLM extraction
   - Manages chunking and indexing
   - Metadata extraction

5. **Semantic Chunking** (`backend/src/ingestion/semantic_chunking.py`)
   - spaCy sentence boundary detection
   - Grammar-aware splitting
   - Max chunk size: 512 tokens, overlap: 50 tokens
   - Preserves complete thoughts

6. **Contextual Chunking** (`backend/src/ingestion/contextual_chunking.py`)
   - Prepend document title to each chunk
   - Add section header context
   - Include document type metadata
   - Impact: +15-20% precision

7. **Parent Document Retriever** (`backend/src/ingestion/chunking.py`)
   - Small chunks for retrieval
   - Large context for response
   - Metadata preservation

**3c. Knowledge Graph Pipeline:**

8. **Efficient Entity Extraction** (`backend/src/knowledge_graph/efficient_extractor.py`)
   - spaCy NER (PERSON, ORG, DATE, MONEY, etc.)
   - Custom financial domain patterns
   - Dependency parsing for relationships
   - Cost: ~$0.001/doc (vs $0.02-0.05 with LLM)

9. **Knowledge Graph Store** (`backend/src/knowledge_graph/store.py`)
   - Neo4j adapter (AuraDB Free in production, Docker locally)
   - Connection pooling
   - Entity/relationship CRUD

10. **Graph Ontology** (`backend/src/knowledge_graph/ontology.py`)
    - Entity types: Document, Organization, Person, Location, Regulation, Concept, Product, Metric
    - Relationship types: MENTIONS, RELATED_TO, GOVERNED_BY, REPORTED
    - See `docs/RAG_README.md` Knowledge Graph section for full ontology

11. **Graph Queries** (`backend/src/knowledge_graph/queries.py`)
    - 1-hop entity lookup
    - 2-hop relationship traversal
    - Entity-to-document linking

**3d. Query Pipeline:**

12. **Query Expansion** (`backend/src/ingestion/query_expansion.py`)
    - Generate 3 alternative phrasings via Nova Lite
    - Multi-query retrieval
    - Parallel searches
    - Impact: +20-30% recall

13. **Embeddings** (`backend/src/utils/embeddings.py`)
    - Bedrock Titan integration (1536 dimensions)
    - Batch embedding generation
    - Caching

14. **RRF Implementation** (`backend/src/utils/rrf.py`)
    - Reciprocal Rank Fusion algorithm
    - Merge vector + sparse + KG results
    - Score = Σ (1 / (k + rank)), k=60
    - Score normalization

15. **Cross-Encoder Reranking** (`backend/src/utils/reranker.py`)
    - Nova Lite relevance scoring
    - Score top 15 results
    - Return top 5
    - Impact: +20-25% precision
    - Cost: ~$0.015/query

16. **Tool Implementation** (`backend/src/agent/tools/rag.py`)
    - Pinecone client for vector search
    - BM25 for sparse search (Pinecone hybrid)
    - KG lookup integration
    - RRF fusion of all results
    - Cross-encoder reranking
    - Contextual compression
    - Source citation with page numbers
    - Error handling with fallbacks

#### Step 4: Market Data Tool ✅ *COMPLETED IN PHASE 0*
1. **Tool Implementation** (`backend/src/agent/tools/market_data.py`) ✅
   - FMP client exposed via MCP (mock mode when no API key)
   - Tool definition for LangGraph
   - Input validation (ticker list)
   - Result formatting
   - **Status:** Fully functional with mock fallback when API key not set
   - Basic batching guidance (comma-separated tickers)
   - Error handling with retry
   - Circuit breaker
   - Structured logging

#### Step 5: Tool Registration
1. **Update Graph** (`backend/src/agent/graph.py`)
   - Register all tools
   - Tool selection logic
   - Tool execution flow

2. **Tool Tests** (`backend/tests/test_tools.py`)
   - Unit tests for each tool
   - Mock external APIs
   - Error scenario tests

#### Step 6: Document Storage & Scripts

**Note:** All documents processed via local batch script. No Lambda infrastructure for this demo. See `docs/completed-phases/PHASE_2_REQUIREMENTS.md` "Enterprise Scaling" for Lambda-based approach if needed later.

1. **S3 Bucket (Optional)** (`terraform/modules/documents-s3/main.tf`)
   - S3 bucket for extracted JSON backup
   - Not required - local files work fine for demo
   - Folders: `/extracted/`, `/indexed/` (if used)

2. **Unified Extraction Script** (`scripts/extract_and_index.py`)
   - Main CLI for all document extraction
   - VLM extraction via Claude Vision (Bedrock)
   - Semantic chunking → Pinecone indexing
   - Entity extraction → Neo4j indexing
   - Handles both 10-Ks and reference documents
   - Run locally - no timeouts, easy debugging

3. **SQL Loading Script** (`scripts/load_10k_to_sql.py`)
   - Loads extracted 10-K financial metrics to PostgreSQL
   - Parses VLM JSON output for structured data
   - Populates companies, financial_metrics, segments, risks tables

### Phase 2 Deliverables Checklist

**Tools:**
- [x] Agent can search the web and cite sources (Phase 0)
- [ ] Agent can query SQL database with natural language
- [ ] Agent can retrieve relevant documents from vector store
- [x] Agent can retrieve current market data (Phase 0)

**Document Extraction:**
- [ ] VLM extraction working for ALL documents
- [ ] ~7 company 10-Ks extracted and indexed
- [ ] ~10-15 reference documents extracted and indexed
- [ ] Semantic chunking with spaCy
- [ ] Contextual enrichment applied

**Infrastructure:**
- [ ] Pinecone index created and populated
- [ ] Neo4j AuraDB connected
- [ ] Batch extraction script (`scripts/extract_and_index.py`) working
- [ ] SQL loading script (`scripts/load_10k_to_sql.py`) working
- [ ] Neo4j in docker-compose for local dev

**Quality:**
- [ ] Tool selection is intelligent and contextual
- [ ] All tools have structured logging
- [ ] SQL tool uses ALLOWED_TABLES whitelist
- [ ] RAG returns citations with page numbers

### Consistency Checks
- [ ] All tools follow same error handling pattern
- [ ] SQL tool queries 10-K financial metrics (not synthetic data)
- [ ] SQL tool uses parameterized queries only
- [ ] RAG tool uses hybrid search (dense + BM25) with RRF
- [ ] Knowledge graph entities extracted via spaCy (not LLM)
- [ ] All documents processed via VLM (single extraction path)
- [ ] Tool results include source citations
- [ ] VLM extraction preserves table structure

---

## Phase 3: Observability with Arize Phoenix

### Goal
Full tracing and monitoring of agent execution.

### Technology Specifications

#### Arize Phoenix
- **Deployment:** ECS Fargate (self-hosted)
- **Storage:** EFS (persistent)
- **Access:** Internal ALB with password protection
- **Integration:** LangGraph native callbacks (LangChainTracer)

#### Observability Features
- **Distributed Tracing:** Complete agent execution paths
- **Metrics:** Token usage, latency, costs, errors
- **Logging:** Structured logs to CloudWatch
- **Dashboards:** CloudWatch dashboards

### Implementation Order

#### Step 1: Phoenix Infrastructure
1. **ECS Fargate Task** (`terraform/modules/observability/phoenix.tf`)
   - ECS cluster
   - Fargate task definition
   - EFS mount
   - Security groups

2. **EFS** (`terraform/modules/observability/efs.tf`)
   - EFS file system
   - Mount targets (public subnets)
   - Security groups

3. **ALB** (`terraform/modules/observability/alb.tf`)
   - Internal ALB
   - Target group (Phoenix)
   - Security groups

#### Step 2: Phoenix Integration
1. **LangChain Tracer** (`backend/src/agent/observability.py`)
   - LangChainTracer setup
   - Phoenix endpoint configuration
   - Trace collection

2. **Update Graph** (`backend/src/agent/graph.py`)
   - Add callbacks to graph
   - Trace all agent executions
   - Tool execution tracing

#### Step 3: Metrics Collection
1. **Metrics Middleware** (`backend/src/api/middleware/metrics.py`)
   - Token usage tracking
   - Latency measurement
   - Cost calculation
   - Error rate tracking
   - CloudWatch metrics

#### Step 4: Dashboards
1. **CloudWatch Dashboard** (`terraform/modules/observability/dashboard.tf`)
   - Key metrics visualization
   - Cost tracking
   - Error rates
   - Tool usage

### Phase 3 Deliverables Checklist
- [ ] Full trace of every agent execution
- [ ] Latency breakdown visible
- [ ] Token usage tracked
- [ ] Error rates monitored
- [ ] Tool usage analytics
- [ ] Phoenix dashboard accessible
- [ ] CloudWatch dashboards created

### Consistency Checks
- [ ] All agent executions are traced
- [ ] Metrics are collected consistently
- [ ] Traces include tool calls
- [ ] Cost tracking is accurate
- [ ] Dashboards show key metrics

---

## Phase 4: RAG Evaluation with RAGAS

### Goal
Automated quality measurement for RAG responses.

### Technology Specifications

#### RAGAS
- **Metrics:** Faithfulness, answer relevancy, context precision, context recall
- **Execution:** Lambda (scheduled) + GitHub Actions (on PR)
- **Storage:** S3 (evaluation datasets)
- **Reporting:** Phoenix dashboard + CloudWatch alarms

### Implementation Order

#### Step 1: Evaluation Infrastructure
1. **S3 Bucket** (`terraform/modules/s3/evaluation.tf`)
   - S3 bucket for evaluation datasets
   - Separate from document storage

2. **Lambda Function** (`lambda/ragas-evaluation/handler.py`)
   - RAGAS evaluation logic
   - Load test dataset from S3
   - Run evaluations
   - Upload results to Phoenix
   - Check for regressions

3. **Lambda Terraform** (`terraform/modules/lambda/ragas-evaluation.tf`)
   - Lambda function
   - EventBridge schedule (daily/weekly)
   - IAM permissions
   - Environment variables

#### Step 2: RAGAS Integration
1. **Evaluation Module** (`backend/src/evaluation/ragas.py`)
   - RAGAS setup
   - Metric calculation
   - Result formatting
   - Regression detection

2. **Test Dataset** (`evaluation/datasets/`)
   - Sample Q&A pairs
   - Ground truth data
   - Upload to S3

#### Step 3: GitHub Actions Integration
1. **Evaluation Workflow** (`.github/workflows/evaluate.yml`)
   - Run RAGAS on PR
   - Check for regressions
   - Fail PR if quality drops
   - Upload metrics

#### Step 4: Alarms
1. **CloudWatch Alarms** (`terraform/modules/observability/alarms.tf`)
   - Quality regression alarms
   - Threshold configuration
   - SNS notifications (optional)

### Phase 4 Deliverables Checklist
- [ ] Automated RAG quality evaluation
- [ ] Metrics visible in dashboard
- [ ] Alerts on quality regression
- [ ] Evaluation reports generated
- [ ] Lambda scheduled evaluations working
- [ ] GitHub Actions evaluation on PR

### Consistency Checks
- [ ] RAGAS metrics are calculated correctly
- [ ] Evaluation datasets are in S3
- [ ] Regression detection works
- [ ] Alarms trigger on quality drops
- [ ] Results are uploaded to Phoenix

---

## Phase 5: Enhanced UI and Thought Process Streaming

### Goal
Polished user experience with visible agent reasoning.

### Technology Specifications

#### UI Features
- **Thought Process:** Real-time display of agent reasoning
- **Tool Execution:** Visible tool calls and results
- **Citations:** Source cards with links
- **History:** Conversation persistence
- **Responsive:** Mobile-friendly design

### Implementation Order

#### Step 1: Thought Process Display
1. **Thought Timeline Component** (`frontend/src/components/thought-process/ThoughtTimeline.tsx`)
   - Display agent reasoning steps
   - Tool execution cards
   - Loading states

2. **Tool Execution Component** (`frontend/src/components/thought-process/ToolExecution.tsx`)
   - Show tool name
   - Show input/output
   - Show execution time
   - Show success/failure

#### Step 2: Enhanced Chat UI
1. **Chat Message Component** (`frontend/src/components/chat/ChatMessage.tsx`)
   - Message bubbles
   - Citations
   - Tool references
   - Timestamps

2. **Source Citations** (`frontend/src/components/chat/SourceCitation.tsx`)
   - Citation cards
   - Links to sources
   - Page/section numbers

#### Step 3: Conversation History
1. **History Component** (`frontend/src/components/chat/ChatHistory.tsx`)
   - Load from backend
   - Display previous conversations
   - Search/filter

#### Step 4: UI Polish
1. **Loading States** (`frontend/src/components/ui/`)
   - Skeleton loaders
   - Progress indicators
   - Error toasts

2. **Responsive Design** (`frontend/src/styles/`)
   - Mobile breakpoints
   - Tablet optimization
   - Desktop layout

### Phase 5 Deliverables Checklist
- [ ] Beautiful, professional UI
- [ ] Thought process visible in real-time
- [ ] Sources clearly cited
- [ ] Conversation history persists
- [ ] Mobile-friendly design
- [ ] Error handling in UI
- [ ] Loading states for all async operations

### Consistency Checks
- [ ] UI matches design system (shadcn/ui)
- [ ] Thought process updates in real-time
- [ ] Citations are clickable
- [ ] Mobile layout works correctly
- [ ] Error messages are user-friendly

---

## Phase 6: Input/Output Verification

### Goal
SLM guards validate user inputs and agent outputs for safety/quality.

### Technology Specifications

#### Verification Models
- **Input Verification:** Nova Lite (`amazon.nova-lite-v1:0`)
- **Output Verification:** Nova Lite (`amazon.nova-lite-v1:0`)
- **Policy Levels:** strict, moderate, permissive

#### Verification Features
- **Input:** Prompt injection detection, jailbreak detection, content policy
- **Output:** Hallucination scoring, PII detection, citation verification, quality checks

### Implementation Order

#### Step 1: Verification Nodes
1. **Input Verification Node** (`backend/src/agent/nodes/verification.py`)
   - Input validation logic
   - Nova Lite invocation
   - Policy enforcement
   - Classification (safe/unsafe/needs-review)

2. **Output Verification Node** (`backend/src/agent/nodes/verification.py`)
   - Output validation logic
   - Hallucination scoring
   - PII detection
   - Citation verification
   - Quality checks

#### Step 2: Verification Policies
1. **Policy Configuration** (`backend/src/config/verification.py`)
   - Policy definitions
   - Sensitivity levels
   - Configurable thresholds

2. **Policy Enforcement** (`backend/src/agent/nodes/verification.py`)
   - Apply policies
   - Bypass logic for trusted requests
   - Logging of flagged content

#### Step 3: Graph Integration
1. **Update Graph** (`backend/src/agent/graph.py`)
   - Add verification nodes
   - Input verification before chat
   - Output verification after response
   - Conditional routing based on verification results

#### Step 4: Metrics and Logging
1. **Verification Metrics** (`backend/src/api/middleware/logging.py`)
   - Track pass/fail rates
   - Log flagged content to CloudWatch
   - Metrics for monitoring

### Phase 6 Deliverables Checklist
- [ ] Input verification blocks malicious prompts
- [ ] Output verification ensures quality responses
- [ ] Verification metrics visible in monitoring
- [ ] Configurable policy levels
- [ ] Flagged content logged to CloudWatch

### Consistency Checks
- [ ] Verification uses Nova Lite (not Nova Pro)
- [ ] Policies are configurable
- [ ] Verification results are logged
- [ ] Metrics are tracked
- [ ] Bypass logic works for trusted requests

---

## Phase 7: Inference Caching

### Goal
Reduce costs and latency by caching repeated queries.

### Technology Specifications

#### Cache Storage
- **Database:** DynamoDB (on-demand pricing)
- **TTL:** 7 days (configurable)
- **Key Generation:** Bedrock Titan embeddings (semantic similarity)
- **Similarity Threshold:** Cosine similarity > 0.95

#### Cache Features
- **Semantic Matching:** Not just exact text match
- **Automatic Cleanup:** DynamoDB TTL
- **Cache Invalidation:** On document updates
- **Metrics:** Hit/miss rates tracked in CloudWatch

### Implementation Order

#### Step 1: DynamoDB Infrastructure
1. **DynamoDB Table** (`terraform/modules/dynamodb/cache.tf`)
   - Table definition
   - TTL attribute
   - On-demand pricing
   - IAM policies for App Runner

#### Step 2: Cache Implementation
1. **Cache Module** (`backend/src/cache/inference_cache.py`)
   - DynamoDB client
   - Embedding-based key generation
   - Similarity matching
   - Cache read/write
   - TTL handling

2. **Cache Integration** (`backend/src/agent/nodes/chat.py`)
   - Check cache before LLM call
   - Write to cache after response
   - Cache hit/miss logging

#### Step 3: Cache Invalidation
1. **Document Update Handler** (`backend/src/cache/inference_cache.py`)
   - Invalidate cache on document updates
   - Pattern matching for invalidation
   - Batch invalidation

#### Step 4: Metrics
1. **Cache Metrics** (`backend/src/api/middleware/logging.py`)
   - Track cache hits/misses
   - Calculate hit rate
   - Cost savings tracking
   - CloudWatch metrics

### Phase 7 Deliverables Checklist
- [ ] Repeated queries return instantly from cache
- [ ] Cache hit rate > 30% for typical usage
- [ ] Cost savings visible in dashboard
- [ ] Cache invalidation works correctly
- [ ] DynamoDB table provisioned
- [ ] TTL cleanup working

### Consistency Checks
- [ ] Cache uses semantic similarity (not exact match)
- [ ] Embedding generation uses Bedrock Titan
- [ ] TTL is configured correctly
- [ ] Cache invalidation triggers on document updates
- [ ] Metrics are tracked accurately

---

## Implementation Order Guidelines

### General Principles
1. **Foundation First:** Always implement infrastructure and configuration before features
2. **Local Before Cloud:** Test locally (Phase 0) before deploying (Phase 1a+)
3. **Core Before Advanced:** Implement basic functionality before optimizations
4. **Dependencies First:** Implement dependencies before dependent features
5. **Test As You Go:** Write tests alongside implementation

### Phase Implementation Order
1. **Phase 0:** Complete all steps before moving to Phase 1a
2. **Phase 1a:** Deploy basic MVP before Phase 1b
3. **Phase 1b:** Add production features before Phase 2
4. **Phase 2:** Implement all tools before Phase 3+
5. **Phase 3-7:** Can be implemented in parallel if dependencies are met

### Within Each Phase
1. **Infrastructure** → **Configuration** → **Core Logic** → **Integration** → **Testing**
2. **Backend** → **Frontend** (for API-dependent features)
3. **Basic** → **Enhanced** (for feature iterations)

---

## Consistency Checks

### Code Consistency
- [ ] All Python code uses type hints
- [ ] All functions have docstrings
- [ ] Error handling follows same pattern
- [ ] Logging uses structlog (Phase 1b+)
- [ ] Environment variables have defaults
- [ ] Configuration uses Pydantic Settings

### Architecture Consistency
- [ ] All AWS resources use us-east-1
- [ ] All tools follow same interface
- [ ] All tools use circuit breakers
- [ ] All tools have structured logging
- [ ] All API endpoints follow versioning (Phase 1b+)
- [ ] All database queries are parameterized

### Testing Consistency
- [ ] Unit tests for all tools
- [ ] Integration tests for agent flow
- [ ] Mock external APIs in tests
- [ ] Test error scenarios
- [ ] Test fallback mechanisms

### Documentation Consistency
- [ ] All modules have docstrings
- [ ] README updated for each phase
- [ ] API documentation updated
- [ ] Architecture diagrams updated
- [ ] Troubleshooting guide updated

---

## Technology Version Reference

### Python Packages (backend/requirements.txt)

**Version Philosophy:** Use `~=` (compatible release) to allow patch updates while preventing breaking changes. Versions chosen balance stability (2-3 months of bug fixes) with features.

```
# Core Framework
fastapi~=0.115.0
uvicorn[standard]~=0.32.0
pydantic~=2.9.0
pydantic-settings~=2.6.0

# Agent Framework
langgraph~=0.2.50
langchain~=0.3.0
langchain-community~=0.3.0
langchain-aws~=0.2.0

# AWS SDK
boto3~=1.35.0
botocore~=1.35.0

# Database
sqlalchemy~=2.0.35
alembic~=1.13.0
psycopg2-binary~=2.9.9
psycopg[binary]~=3.2.0  # Required by langgraph-checkpoint-postgres
langgraph-checkpoint-postgres~=2.0.0

# Vector Store
pinecone-client~=5.0.0
chromadb~=0.5.15

# Knowledge Graph
neo4j~=5.25.0
spacy~=3.8.0

# Logging
structlog~=24.4.0

# HTTP Clients
httpx~=0.27.0
requests~=2.32.0

# Utilities
python-dotenv~=1.0.0
tenacity~=9.0.0  # Retry logic

# Rate Limiting
slowapi~=0.1.9

# Testing
pytest~=8.3.0
pytest-asyncio~=0.24.0
pytest-cov~=5.0.0
pytest-mock~=3.14.0

# Code Quality
black~=24.10.0
ruff~=0.7.0
mypy~=1.13.0

# Type Stubs
types-requests~=2.32.0
```

### Node.js Packages (frontend/package.json)

**Version Philosophy:** Mirror the current codebase (Next.js 16 / React 19 / Tailwind 4). Keep semver-compatible ranges where possible, but Next/React are pinned to exact versions for stability during the major upgrade.

```json
{
  "dependencies": {
    "@radix-ui/react-dialog": "^1.1.15",
    "@radix-ui/react-slot": "^1.2.4",
    "class-variance-authority": "^0.7.1",
    "clsx": "^2.1.1",
    "lucide-react": "^0.559.0",
    "next": "16.0.8",
    "next-themes": "^0.4.6",
    "react": "19.2.1",
    "react-dom": "19.2.1",
    "sonner": "^2.0.7",
    "tailwind-merge": "^3.4.0",
    "tailwindcss": "^4.0.0",
    "typescript": "^5.0.0"
  },
  "devDependencies": {
    "@tailwindcss/postcss": "^4",
    "@types/node": "^20",
    "@types/react": "^19",
    "@types/react-dom": "^19",
    "eslint": "^9",
    "eslint-config-next": "16.0.8",
    "tailwindcss": "^4",
    "tw-animate-css": "^1.4.0",
    "typescript": "^5"
  }
}
```

### Terraform Versions
```hcl
terraform {
  required_version = ">= 1.5.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}
```

---

## External Service Configuration

### Pinecone
- **Index Name:** `demo-index`
- **Dimensions:** 1536 (Bedrock Titan)
- **Metric:** cosine
- **Region:** us-east-1 (AWS region)
- **Tier:** Serverless (free tier: 100K vectors)

### Tavily
- **API Endpoint:** https://api.tavily.com/search
- **Free Tier:** 1,000 searches/month
- **Rate Limit:** Respect API limits

### Financial Modeling Prep (FMP)
- **API Endpoint:** https://financialmodelingprep.com/api/v3 (used for market data via MCP)
- **Free Tier:** ~250 calls/day, batch quote endpoint supports multiple tickers
- **Rate Limit Guidance:** Keep requests modest (e.g., 5–10 per minute) and batch tickers when possible; mock mode is used when no API key is provided in Phase 0

### AWS Bedrock
- **Region:** us-east-1
- **Models:**
  - Nova Pro: `amazon.nova-pro-v1:0`
  - Nova Lite: `amazon.nova-lite-v1:0`
  - Titan Embeddings: `amazon.titan-embed-text-v1`
  - Claude Sonnet 4.5 (Primary VLM): `us.anthropic.claude-sonnet-4-5-20250929-v1:0` (released Sep 2025, current recommended)
  - Claude Fallback (Deprecated): `anthropic.claude-3-5-sonnet-20241022-v2:0` (retired Oct 2025, shutdown Feb 2026)

### Neo4j AuraDB (Knowledge Graph)
- **Tier:** Free (200K nodes, 400K relationships)
- **Region:** us-east-1 (if available) or closest
- **Connection:** Bolt protocol (neo4j+s://)
- **Local Dev:** Docker image `neo4j:5-community`

### spaCy (NLP Entity Extraction)
- **Model:** en_core_web_sm (small English model)
- **Download:** `python -m spacy download en_core_web_sm`
- **Entities:** PERSON, ORG, DATE, MONEY, GPE, etc.
- **Usage:** Semantic chunking + entity extraction

---

## File Naming Conventions

### Python Files
- **Snake_case:** `document_processor.py`
- **Modules:** `backend/src/agent/tools/search.py`
- **Tests:** `backend/tests/test_tools.py`

### TypeScript Files
- **PascalCase for components:** `ChatMessage.tsx`
- **camelCase for utilities:** `api.ts`
- **kebab-case for pages:** `frontend/src/app/login/page.tsx`

### Terraform Files
- **Snake_case:** `vpc.tf`, `app_runner.tf`
- **Modules:** `terraform/modules/networking/main.tf`

---

## Error Handling Patterns

### Backend Error Handling
```python
# Pattern for all tools
try:
    result = external_api_call()
    logger.info("tool_executed", tool="search", success=True)
    return result
except ExternalAPIError as e:
    logger.error("tool_failed", tool="search", error=str(e))
    if circuit_breaker.should_attempt():
        raise ToolUnavailableError("Search service temporarily unavailable")
    raise
```

### Frontend Error Handling
```typescript
// Pattern for all API calls
try {
    const response = await fetch(apiUrl, options);
    if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
    }
    return await response.json();
} catch (error) {
    showErrorToast("Failed to connect. Please try again.");
    logger.error("API call failed", { error });
}
```

---

## Logging Patterns

### Structured Logging (Phase 1b+)
```python
# Pattern for all logging
logger.info(
    "event_name",
    key1=value1,
    key2=value2,
    conversation_id=conversation_id,
    tool="tool_name"
)
```

### Log Levels
- **DEBUG:** Detailed information for debugging
- **INFO:** General informational messages
- **WARN:** Warning messages (non-critical issues)
- **ERROR:** Error messages (failures that need attention)

---

## Testing Patterns

### Unit Test Structure
```python
def test_tool_execution():
    # Arrange
    tool = SearchTool()
    query = "test query"
    
    # Act
    result = tool.execute(query)
    
    # Assert
    assert result is not None
    assert "sources" in result
```

### Integration Test Structure
```python
def test_agent_with_tool():
    # Arrange
    agent = create_agent()
    message = "Search for AI news"
    
    # Act
    response = agent.invoke({"messages": [message]})
    
    # Assert
    assert response["messages"][-1].content
    assert "sources" in response
```

---

## Security Checklist

### Input Validation
- [ ] All user inputs validated with Pydantic
- [ ] SQL queries use parameterized statements
- [ ] Table/column whitelisting for SQL
- [ ] Rate limiting on all API endpoints
- [ ] CORS properly configured

### Authentication
- [ ] Password stored in Secrets Manager (AWS)
- [ ] Password hashed (if storing locally)
- [ ] Auth middleware on protected routes
- [ ] Session management

### Data Protection
- [ ] No PII in logs
- [ ] Encryption at rest (AWS default)
- [ ] Encryption in transit (HTTPS)
- [ ] Secrets not in code or logs

---

## Performance Checklist

### Backend
- [ ] Connection pooling configured
- [ ] Circuit breakers prevent cascade failures
- [ ] Retry logic with exponential backoff
- [ ] Cache implemented (Phase 7+)
- [ ] Async operations where appropriate

### Frontend
- [ ] Static export for fast loading
- [ ] Code splitting
- [ ] Image optimization
- [ ] Lazy loading where appropriate

### Infrastructure
- [ ] Auto-scaling configured
- [ ] Health checks enabled
- [ ] CloudFront caching

---

## Cost Optimization Checklist

### Infrastructure
- [ ] App Runner scales to 0
- [ ] Neon free tier usage verified
- [ ] DynamoDB on-demand pricing
- [ ] S3 Intelligent-Tiering
- [ ] No RDS Proxy (use SQLAlchemy pooling)
- [ ] Pinecone free tier (100K vectors)
- [ ] Neo4j AuraDB free tier (200K nodes)

### Phase 2 Costs
- [ ] VLM extraction for ALL docs: One-time ~$40-60 (not monthly)
- [ ] No Lambda infrastructure (batch scripts instead)
- [ ] spaCy NER instead of LLM (20-50x cheaper)
- [ ] Nova Lite for reranking (cheaper than Nova Pro)
- [ ] Batch embeddings (reduce API calls)

### Application
- [ ] Inference caching (Phase 7+)
- [ ] Semantic similarity matching
- [ ] TTL-based cache expiration
- [ ] Efficient embedding generation

---

## Documentation Requirements

### Code Documentation
- [ ] All functions have docstrings
- [ ] All classes have docstrings
- [ ] Complex logic has inline comments
- [ ] Type hints on all functions

### API Documentation
- [ ] OpenAPI/Swagger spec (FastAPI auto-generates)
- [ ] Endpoint descriptions
- [ ] Request/response examples
- [ ] Error codes documented

### Architecture Documentation
- [ ] Architecture diagrams updated
- [ ] Component descriptions
- [ ] Data flow diagrams
- [ ] Deployment procedures

---

## End of Development Reference

**Remember:** This document should be consulted before implementing any feature. If you find inconsistencies or missing information, update this document first, then proceed with implementation.

**Last Review:** Before starting each phase, review the relevant section to ensure all specifications are understood and all dependencies are met.
