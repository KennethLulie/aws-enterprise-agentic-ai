# Enterprise Agentic AI Demo - Complete Project Plan

## Executive Summary

This project builds an enterprise-grade agentic AI system on AWS demonstrating:
- Multi-tool agent orchestration (Web Search, SQL, RAG, Market Data API)
- Input/output verification with SLMs
- Streaming thought process visualization
- Inference caching for cost optimization
- Full observability with Arize Phoenix
- RAG evaluation with RAGAS
- VLM document extraction (Claude Vision for all documents)
- Hybrid RAG with Knowledge Graph (Neo4j)
- Password-protected web interface
- Infrastructure as Code with Terraform
- CI/CD with GitHub Actions

**Target Cost:** Under $50/month for low-use portfolio demo
**Architecture:** Scalable, enterprise-ready, cost-optimized
**AWS Region:** us-east-1 (N. Virginia - closest to Austin, TX)
**Domain:** App Runner generated URL (no custom domain)

---

## Architecture Overview

```
┌───────────────────────────────────────────────────────────────────────┐
│                    DEVOPS & DEPLOYMENT                                │
│  ┌──────────────────────┐         ┌──────────────────────┐            │
│  │   GitHub Actions     │────▶    │      Terraform       │            │
│  │   (CI/CD Pipeline)   │         │   (Infrastructure)   │            │
│  │  • Build & Test      │         │  • AWS Resources     │            │
│  │  • Deploy            │         │  • State Management  │            │
│  │  • RAGAS Evaluation  │         │                      │            │
│  └──────────────────────┘         └──────────────────────┘            │
│           │                                                           │
│           └────────────────── Deploys ────────────────────────────────┘
│
┌─────────────────────────────────────────────────────────────────────────┐
│                    FRONTEND (Next.js Static Export)                     │
│         CloudFront → S3 Static Hosting (no Next.js server)              │
│              shadcn/ui + Native SSE Client (EventSource)                │
│              Calls App Runner API directly (CORS enabled)               │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                           Password Gate (Secrets Manager)
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      BACKEND (AWS App Runner)                           │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    LangGraph Agent Orchestrator                 │    │
│  │    ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │    │
│  │    │ Bedrock  │  │  Input/  │  │ Inference│  │  Arize   │       │    │
│  │    │   Nova   │  │  Output  │  │   Cache  │  │ Tracing  │       │    │
│  │    │  (Main)  │  │  Verify  │  │(DynamoDB)│  │          │       │    │
│  │    └──────────┘  └──────────┘  └──────────┘  └──────────┘       │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  ┌─────────────────────  TOOLS  ───────────────────────────────────┐    │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐ │    │
│  │  │   Tavily   │  │    SQL     │  │    RAG     │  │  Market    │ │    │
│  │  │   Search   │  │   Query    │  │  Retrieval │  │   Data     │ │    │
│  │  │            │  │  (Neon)    │  │ (Pinecone) │  │   (MCP)    │ │    │
│  │  └────────────┘  └────────────┘  └────────────┘  └────────────┘ │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
          ┌─────────────────────────┼─────────────────────────┐
          ▼                         ▼                         ▼
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│ Neon PostgreSQL  │    │     Pinecone     │    │     Neo4j        │
│  (Free Tier)     │    │    Serverless    │    │    AuraDB        │
│ (10-K Metrics)   │    │  (Vector Store)  │    │(Knowledge Graph) │
└──────────────────┘    └──────────────────┘    └──────────────────┘
         ▲                       ▲                       ▲
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌────────────────────────┐
                    │   Document Ingestion    │
                    │   (VLM Extraction via   │
                    │   Claude Vision/Bedrock)│
                    │   Local Batch Script    │
                    └────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                    EVALUATION & MONITORING                              │
│  ┌──────────────────────┐         ┌──────────────────────┐            │
│  │       RAGAS          │────────▶│   Arize Phoenix     │            │
│  │  (RAG Evaluation)    │         │   (Observability)    │            │
│  │  • Lambda Scheduled  │         │  • Trace Analysis    │            │
│  │  • GitHub Actions    │         │  • Metrics Dashboard │            │
│  │  • Quality Metrics   │         │  • Cost Tracking     │            │
│  └──────────────────────┘         └──────────────────────┘            │
│           │                                    │                        │
│           │                                    │                        │
│           ▼                                    ▼                        │
│  ┌──────────────────┐              ┌──────────────────┐                │
│  │  S3 Eval Dataset  │              │  CloudWatch      │                │
│  │  (Test Cases)     │              │  (Metrics/Logs) │                │
│  └──────────────────┘              └──────────────────┘                │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Technology Stack

| Component | Technology | Cost Optimization | Rationale |
|-----------|------------|-------------------|-----------|
| **LLM (Main)** | AWS Bedrock - Amazon Nova Pro | Pay-per-token, no idle cost | Latest AWS model, cost-effective |
| **LLM (Verification)** | AWS Bedrock - Amazon Nova Lite | Smaller model, cheaper | Sufficient for guardrails |
| **Agent Framework** | LangGraph | Open source | Industry standard, excellent streaming |
| **Vector Store** | Pinecone Serverless | Free tier (100K vectors) | Fully managed, better than pgvector |
| **SQL Database** | Neon PostgreSQL (external) | Free tier (0.5GB storage) | PostgreSQL-compatible, cost-free |
| **Compute** | AWS App Runner | Scales to 0, pay-per-use | No timeout limits, simple deployment |
| **Frontend Hosting** | CloudFront + S3 | Minimal cost for static | Next.js Static Export → S3 (no server needed) |
| **Inference Cache** | DynamoDB | Pay-per-request, free tier | No minimum cost |
| **File Storage** | S3 | Minimal cost | Standard AWS storage |
| **Auth** | Secrets Manager + middleware | Single secret cost | Simple for demo |
| **Observability** | Arize Phoenix (self-hosted) | Open source | Full-featured, free |
| **Evaluation** | RAGAS | Open source | Industry standard RAG eval |
| **IaC** | Terraform | Free | Infrastructure as Code |
| **CI/CD** | GitHub Actions | Free tier | Automated deployment |

**Estimated Monthly Cost (idle/low-use): $20-50/month**

---

## Development Workflow & Best Practices

### Local Development Strategy (Phase 0)

**Critical Principle: Docker Compose for ALL development (consistency over speed)**

**Why Docker for Development:**
- ✅ **Exact match to production** - No "works on my machine" issues
- ✅ **Consistent environment** - Same Python/Node versions, same dependencies
- ✅ **Volume mounts enable hot reload** - Code changes reflect in ~2-3 seconds
- ✅ **One command to start** - `docker-compose up` starts everything
- ✅ **Isolated dependencies** - No conflicts with system packages
- ✅ **Easier onboarding** - New developers just run `docker-compose up`

**Development Setup:**
```bash
# One command to start everything
docker-compose up

# Or run in background
docker-compose up -d

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend

# Stop everything
docker-compose down
```

**Docker Compose Configuration (Optimized for Fast Startup):**
- **Pre-built base images** with cached dependency layers
- **Docker BuildKit** enabled for parallel builds
- **Health checks** with fast intervals (2s) for dependency management
- **Volume mounts:** `./backend:/app` and `./frontend:/app` (hot reload enabled)
- **Cache volumes:** Persist pip/npm caches between restarts
- **Alpine images:** Smaller, faster pulls (postgres:15-alpine)
- **Environment variables:** `PYTHONDONTWRITEBYTECODE=1` for faster startup
- Backend: `uvicorn --reload` (watches for file changes)
- Frontend: `npm run dev` (Next.js hot reload)
- **Startup time:** 5-10 seconds (optimized from 30-60s)
- **Hot reload time:** ~2-3 seconds (acceptable trade-off for consistency)

**When to Use Docker:**
- ✅ **All development** - Docker Compose with volume mounts
- ✅ **CI/CD pipeline** - Docker builds
- ✅ **Production deployment** - Docker containers

**Development Philosophy:**
- **Consistency > Speed** - Match production exactly, avoid environment bugs
- **Volume mounts** - Enable hot reload while maintaining consistency
- **One command** - `docker-compose up` starts everything

### Docker Build Optimization (For Deployment & Development)

**Multi-Stage Dockerfile Strategy:**
```dockerfile
# Stage 1: Base with dependencies (cached layer, rarely changes)
FROM python:3.11-slim as base
RUN apt-get update && apt-get install -y --no-install-recommends curl
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Development (code mounted via volume)
FROM base as dev
WORKDIR /app
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# Stage 3: Production (copies code)
FROM base as prod
COPY . /app
WORKDIR /app
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Docker Compose Optimizations:**
- **BuildKit:** `COMPOSE_DOCKER_CLI_BUILD=1` and `DOCKER_BUILDKIT=1`
- **Health checks:** Fast intervals (2s) with proper start periods
- **Cache volumes:** Persist pip/npm caches (`backend_cache`, `frontend_cache`)
- **Pre-pull images:** Setup script pre-pulls base images
- **Alpine variants:** Use alpine images where possible (smaller, faster)

**GitHub Actions Caching:**
- Cache Docker layers between builds
- Cache npm/pip dependencies
- Only rebuild changed layers
- Use BuildKit cache mounts for faster builds

**Development Scripts:**
- `scripts/dev.sh` - Quick commands (start, logs, test, shell, db)
- `scripts/setup.sh` - Pre-pulls images, validates setup
- Pre-commit hooks for code quality checks

---

## Phase Breakdown

**Execution approach:** Within each phase, land one feature at a time and add a short checkpoint (build + smoke test) before moving to the next feature. This keeps the demo shippable at every step and limits blast radius when debugging.

### Phase 0: Local Development Environment
**Goal:** Fully working agent locally before any AWS deployment

**Why Local First:**
- Instant iteration (hot reload in ~1 second vs minutes for cloud deploy)
- Free development (no AWS costs)
- Easier debugging with full log access
- Validate core logic before infrastructure complexity

**Local Stack (Docker Compose):**
```
┌─────────────────────────────────────────────────────────┐
│  Docker Compose - All Services Containerized            │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Frontend: Next.js (npm run dev) on :3000        │  │
│  │  Volume: ./frontend:/app (hot reload enabled)    │  │
│  └───────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Backend: FastAPI (uvicorn --reload) on :8000     │  │
│  │  Volume: ./backend:/app (hot reload enabled)     │  │
│  └───────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Frontend: Next.js (npm run dev) on :3000         │  │
│  │  Volume: ./frontend:/app (hot reload enabled)     │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
                    Bedrock API (AWS)
```

**Development Workflow (Docker Compose with Hot Reload):**
1. `./scripts/setup.sh` - One-time setup (validates Docker, creates .env)
2. `docker-compose up` - Start backend and frontend (no local DB/vector services)
3. Code changes reflect automatically (~2-3 seconds hot reload via volume mounts)
4. `docker-compose logs -f` - View logs from all services
5. `docker-compose down` - Stop everything cleanly

**Tool Status in Phase 0:**
- Search: Real Tavily API (with mock fallback)
- Market Data: Real FMP API (with mock fallback)
- SQL: Stub (mock data) - real Neon PostgreSQL in Phase 2
- RAG: Stub (mock data) - real Pinecone in Phase 2

**Hot Reload Configuration:**
- Backend: Volume mount `./backend:/app` + `uvicorn --reload`
- Frontend: Volume mount `./frontend:/app` + `npm run dev`
- Changes detected automatically, no manual rebuild needed
- Reload time: ~2-3 seconds (acceptable for consistency benefit)

**Local Service Substitutes (All in Docker Compose):**
| AWS Service | Local Dev | Container |
|-------------|-----------|-----------|
| Neon PostgreSQL | N/A in Phase 0 (SQL tool stub) | N/A |
| Pinecone | N/A in Phase 0 (RAG tool stub) | N/A |
| S3 file upload | Local `./uploads` folder | Volume mount |
| DynamoDB cache | In-memory dict or SQLite | Python in-memory |
| Secrets Manager | `.env` file | Environment variables |
| Bedrock Nova | Bedrock API (real AWS call) | External API call |
| Tavily Search | Tavily API (real call) | External API call |
| FMP Market Data | FMP API (real call) | External API call |

**Docker Compose Services:**
- `backend`: FastAPI app with hot reload
- `frontend`: Next.js app with hot reload
- No local database or vector store in Phase 0 (SQL and RAG tools return mock data)
- External API calls: Tavily (search), FMP (market data), Bedrock (LLM)

**Phase 0 Deliverables:**
- Working LangGraph agent with streaming responses
- **LangGraph checkpointing:**
  - **Development:** MemorySaver (no DB dependency, faster)
  - **Production:** PostgresSaver with Neon PostgreSQL (state persistence)
  - Connection pooling via SQLAlchemy (no RDS Proxy needed for demo)
- **Error recovery nodes** for graceful failure handling
- **Built-in tool calling** via LangGraph tool binding (with Bedrock compatibility check)
- **Model fallback:** Nova Pro → Claude Sonnet 4.5 (with Claude 3.5 Sonnet V2 as deprecated fallback until Feb 2026)
- **Real tool integration (Phase 2a and 2d completed ahead of schedule):**
  - ✅ Tavily web search (real API with mock fallback) - Phase 2a complete
  - ✅ FMP market data (real API with mock fallback) - Phase 2d complete
  - SQL and RAG tools stubbed (real implementations in Phase 2b/2c)
- Chat UI with real-time streaming
- Basic conversation flow validated
- Environment variable config for local/cloud switching
- **Optimized Docker Compose** (5-10s startup time)
- Requirements.txt and package.json with all dependencies
- Basic unit tests for core agent logic
- **Setup scripts** (`scripts/setup.sh`, `scripts/validate_setup.py`, `scripts/dev.sh`)
- **Comprehensive error handling** with clear error messages
- **Configuration validation** on startup
- **Health check endpoint** (`/health`)
- **Pre-commit hooks** configured (.pre-commit-config.yaml)
- **Troubleshooting guide** in docs/

**Prerequisites on Your Computer:**
- **Docker Desktop** (required - all services run in Docker Compose)
- **Python 3.11+** (required - runs setup/validation scripts locally)
- **Node.js 20+** (optional - only needed for npm commands outside Docker)
- **AWS CLI v2** configured with credentials (for Bedrock API access)
- Git
- VS Code or preferred editor (optional: VS Code dev containers)

**AWS Account Prerequisites (Before Starting):**
1. **Bedrock Model Access (REQUIRED):**
   - Go to AWS Console → Bedrock → Model access
   - Request access to: Amazon Nova Pro, Nova Lite, Titan Embeddings
   - Also request: Anthropic Claude Sonnet 4.5 (primary VLM model) + Claude 3.5 Sonnet V2 (deprecated fallback until Feb 2026)
   - Wait for approval (usually instant, can take 1-24 hours)
   - **Common Issue:** Forgetting this step causes "AccessDeniedException"

2. **Service Quotas (verify defaults are sufficient):**
   - App Runner services: 10 (default, sufficient)
   - Note: Neon is external, no AWS DB cluster quotas needed
   - ECR repositories: 10,000 (default, sufficient)

3. **IAM Permissions (for deployment):**
   - Admin access recommended for initial setup
   - Or custom policy with: AppRunner, RDS, S3, CloudFront, ECR, Lambda, DynamoDB, SecretsManager, CloudWatch, IAM

**External Service Setup (Before Phase 0):**

**Security Note:** All API keys should be stored in your local `.env` file (gitignored, never committed). See [`.env.example`](.env.example) for the template and [`docs/SECURITY.md`](docs/SECURITY.md) for the complete secrets management approach.

1. **Pinecone (free tier):**
   - Create account at https://pinecone.io
   - Create index: name=`demo-index`, dimensions=1024, metric=dotproduct
   - Region: **AWS us-east-1** (same as rest of stack). If us-east-1 temporarily unavailable, use us-west-2 and expect +20‑30 ms latency plus minimal data-transfer charges.
   - Copy API key to your `.env` file (see `.env.example` for the variable name)
   - Note: Uses Titan v2 embeddings (1024 dims) with dotproduct metric for optimal hybrid search

2. **Tavily (free tier):**
   - Create account at https://tavily.com
   - Get API key from dashboard
   - Free tier: 1,000 searches/month (sufficient for demo)
   - Copy API key to your `.env` file

3. **Financial Modeling Prep (FMP) for Market Data via MCP:**
   - Create account at https://financialmodelingprep.com (no credit card)
   - Get API key from dashboard (free tier: ~250 calls/day, batch quotes supported)
   - Copy API key to your `.env` file
   - Note: Phase 0 can run in mock mode; the API key enables live quotes.

**Setup Process:**
```bash
# One-command setup (pre-pulls images, validates)
./scripts/setup.sh

# Validates everything is configured correctly
python scripts/validate_setup.py

# Start development (optimized Docker Compose)
docker-compose up

# Or use dev script for convenience
./scripts/dev.sh start      # Start services
./scripts/dev.sh logs       # View logs
./scripts/dev.sh test       # Run tests
./scripts/dev.sh shell      # Open backend shell
./scripts/dev.sh db         # Open database shell
```

**Error Prevention:**
- Pydantic settings with sensible defaults
- Auto-detection of local vs AWS environment
- Clear error messages with fix suggestions
- Type hints and validation throughout
- Pre-commit hooks for code quality (black, ruff, mypy, tests)
- **Input validation** with Pydantic validators
- **SQL injection prevention** (parameterized queries, table whitelisting)
- **Rate limiting** middleware (slowapi)
- **CORS** properly configured
- **Circuit breakers** for external service calls
- **Fallback mechanisms** for tool failures

**Testing Strategy:**
- Unit tests for agent nodes and tools
- Integration tests for tool interactions
- **Model compatibility tests:** Verify Bedrock Nova tool calling works
- **Fallback tests:** Verify Claude fallback works if Nova unavailable
- Manual testing for UI/UX
- E2E tests added in later phases
- **Cold start testing:** Verify health endpoint works during cold start

**Common Issues (Phase 0)**
| Symptom | Root Cause | Fix |
|---------|------------|-----|
| `AccessDeniedException` from Bedrock | Model access not approved | Re-run Bedrock model access request for Nova Pro/Lite + Titan Embeddings + Claude fallback |
| `docker-compose up` fails with permissions error | Docker Desktop not running or user not in docker group | Start Docker Desktop / run `sudo usermod -aG docker $USER` then re-login |
| Pinecone 401 on startup | Missing API key in `.env` | Add `PINECONE_API_KEY` and restart backend |
| Tavily tool fails immediately | Free-tier rate limit hit | Wait 60s, set `TAVILY_API_KEY` correctly, or upgrade plan |
| Market Data API returns 401 | Missing or invalid API key | Set `FMP_API_KEY` in `.env` or use mock mode (no key required for Phase 0) |
| Terraform state lock message | Previous `terraform apply` exited abruptly | Delete lock entry from DynamoDB table `terraform-state-lock` using AWS Console |

---

### Phase 1a: Minimal MVP - AWS Cloud Deployment
**Goal:** Deployed chatbot to AWS accessible via password-protected website with streaming responses (simplified for easy debugging)

**Why Split Phase 1:** Phase 1a focuses on getting a working demo quickly with minimal complexity. Phase 1b adds production hardening. This makes debugging much easier - if something breaks, fewer moving parts to check.

**Features (Minimal Set):**
- **Next.js Static Export** frontend with shadcn/ui chat interface
  - Deployed to S3 + CloudFront (no Next.js server)
  - Uses native EventSource for SSE (no Vercel AI SDK dependency)
  - Calls App Runner API directly via CORS
- Simple password protection (shared password via Secrets Manager)
- App Runner backend with basic LangGraph agent
- **LangGraph checkpointing:**
  - **MemorySaver only** (no database yet - simplifies deployment)
  - Conversation state stored in memory (lost on restart, acceptable for MVP)
  - Upgrade to PostgresSaver in Phase 1b
- **LangGraph native streaming** with proper event handling
- Bedrock Nova integration with fallback:
  - Primary: `amazon.nova-pro-v1:0` (verify availability in us-east-1 - N. Virginia)
  - Fallback: `us.anthropic.claude-sonnet-4-5-20250929-v1:0` (Claude Sonnet 4.5 - current recommended model)
  - Deprecated fallback: `anthropic.claude-3-5-sonnet-20241022-v2:0` (retired Oct 2025, shutdown Feb 2026)
- Server-Sent Events (SSE) streaming from FastAPI to frontend
- **Cold start UX:** Loading indicator with "Warming up..." message (10-30s estimate). Accept ~30s cold start to minimize cost.
- **Conversation persistence:** conversation_id in localStorage (state in MemorySaver)
- **Basic Terraform infrastructure** (networking, App Runner, S3, CloudFront, Secrets Manager, ECR)
- **Manual deployment** (no CI/CD yet - deploy via `terraform apply` and manual S3 upload)
- **Basic error handling** (try/catch with user-friendly messages)
- **Basic logging** (print statements + CloudWatch Logs)
- **Health check endpoint** (`/health`) - simple version (no dependency checks yet)
- **Input validation** with Pydantic models (basic)
- **No API versioning yet** (use `/api/chat` - add versioning in Phase 1b)
- **No database migrations** (no database yet)

**Infrastructure (Terraform) - Minimal:**
- **Networking:** VPC with two public subnets
- App Runner service (no VPC connector yet - uses public internet)
- S3 bucket for frontend static files
- CloudFront distribution
- Secrets Manager for password
- ECR repository
- CloudWatch Logs
- **No database yet** (saves cost, simplifies deployment)

**Deliverables:**
- Working chat interface at CloudFront URL
- Streaming responses visible in real-time
- Cold start loading indicator
- Conversation persistence (in-memory, lost on restart)
- Manual deployment process documented

**Success Criteria:**
- User can access site with password
- Chat messages stream in real-time
- Cold start UX works (loading indicator)
- Responses are coherent and relevant
- **Deployment is manual but repeatable** (terraform apply + S3 upload)

---

### Phase 1b: Production Hardening
**Goal:** Add production-grade features: persistent state, CI/CD, observability, security hardening

**Features (Add to Phase 1a):**
- **PostgresSaver checkpointing** with Neon PostgreSQL (external service):
  - Create Neon account and project (free tier)
  - Store connection string in AWS Secrets Manager
  - No VPC connector needed (external service over internet)
  - Migrate from MemorySaver to PostgresSaver
  - PostgresSaver.setup() creates checkpoint tables automatically
- **Database migrations:** Alembic for future app schema (SQLAlchemy with connection pooling)
- **GitHub Actions CI/CD:** Automated build, test, deploy
- **Structured logging:** structlog with JSON output
- **Comprehensive error handling:** Graceful degradation, retry logic
- **Health check endpoint:** Enhanced with dependency checks (Neon database, Bedrock)
- **Rate limiting:** slowapi middleware (10 req/min per IP)
- **API versioning:** `/api/v1/chat` (allows future `/api/v2/chat`)
- **User-friendly error messages:** Map technical errors to friendly messages

**Infrastructure Additions:**
- Neon PostgreSQL project (external, free tier)
- DATABASE_URL in AWS Secrets Manager

**Deliverables:**
- Conversation state persists across restarts
- Automated deployment pipeline
- Enhanced monitoring and logging
- Production-ready security

**Success Criteria:**
- Conversation history persists across App Runner restarts
- Deployment is automated via GitHub Actions
- Enhanced observability (structured logs, metrics)
- Security hardened (rate limiting, input validation)

**Infrastructure (Terraform):**
- **Networking (Public-Only Demo Topology):**
  - Provision a VPC with **two public subnets** (no private subnets, NAT Gateway, or VPC endpoints).
  - ECS/Fargate (later phases), and EFS mount targets will live in these public subnets but are locked down via security groups.
  - Note: Phase 1b uses Neon PostgreSQL (external service), so no VPC connector needed for database access.
  - App Runner VPC Connector is optional for Phase 1b but will be needed for Phase 3 (Phoenix self-hosted) and future AWS services.
  - Document the upgrade path: add private subnets + VPC endpoints later for production hardening.
- App Runner service with auto-scaling:
  - **Minimum instances: 0** (scales to zero when idle, saves cost)
  - Maximum instances: 10 (auto-scales on demand)
  - **Cold start: 10-30 seconds** (acceptable for portfolio demo)
  - **Request timeout:** Set `instance_configuration.connection_drain_timeout` to 900 seconds so SSE streams are not dropped during long toolchains.
- S3 bucket for frontend static files (us-east-1)
- CloudFront distribution with HTTPS
- Secrets Manager for password (us-east-1)
- IAM roles and policies (least privilege)
- ECR repository for container images (us-east-1)
- CloudWatch Logs for monitoring (us-east-1)

**Security (Public-Subnet Demo Mode):**
- HTTPS only (CloudFront)
- Password stored in Secrets Manager (encrypted)
- IAM roles with minimal permissions
- Neon uses SSL-encrypted connections over public internet (no VPC needed)
- ECS/EFS (Phase 5) security groups scoped to VPC connector CIDR blocks
- **Rate limiting** (slowapi middleware, 10 req/min per IP)
- **SQL injection prevention** (parameterized queries, table whitelisting)
- **Input validation** (Pydantic validators, message length limits)
- **CORS** properly configured (specific origins, methods, headers)
- **SQL tool safety:** Read-only connections, result limits, query validation

**Deliverables:**
- Working chat interface at CloudFront URL (e.g., `https://xxxxx.cloudfront.net`)
  - Frontend: S3 + CloudFront (static Next.js export)
  - Backend API: App Runner URL (e.g., `https://xxxxx.us-east-1.awsapprunner.com`)
  - Frontend calls backend API via CORS
- Streaming responses visible in real-time (SSE from FastAPI)
- Cold start loading indicator ("Warming up...")
- Conversation persistence (conversation_id in localStorage)
- Automated deployment pipeline
- Basic monitoring dashboard
- Database migrations (Alembic) for schema management

**Success Criteria:**
- User can access site with password
- Chat messages stream in real-time
- **Cold start UX:** 
  - Loading indicator shows "Warming up services..." with estimated wait time
  - Health check endpoint responds quickly even during cold start
  - User sees progress, not blank screen
- **Load time: 10-30 seconds on first request** (cold start acceptable for demo)
- Subsequent requests: <2 seconds (instance warmed up)
- Responses are coherent and relevant
- Conversation history persists across page refreshes
- Deployment is automated via GitHub Actions
- Setup process is smooth with clear error messages

**Common Issues (Phase 1a - Minimal MVP)**
| Symptom | Root Cause | Fix |
|---------|------------|-----|
| Health endpoint reachable but chat API blocked (CORS) | CloudFront origin header not whitelisted | Update FastAPI CORS middleware `allow_origins` to include CloudFront domain |
| Docker image push fails | ECR login expired or wrong region | Re-run `aws ecr get-login-password` and verify region matches |
| App Runner deployment fails | Docker image not found in ECR | Verify image exists: `aws ecr describe-images --repository-name backend` |
| CloudFront shows "Access Denied" | S3 bucket permissions incorrect | Set bucket policy for public read: `aws s3api put-bucket-policy --bucket <name> --policy file://bucket-policy.json` |
| SSE stream closes immediately | App Runner timeout too short | Increase timeout in Terraform: `instance_configuration.connection_drain_timeout = 900` |
| Terraform state lock error | Previous apply exited abruptly | Delete lock: `aws dynamodb delete-item --table-name terraform-state-lock --key '{"LockID":{"S":"<lock-id>"}}'` |

**Debugging Workflow (Phase 1a):**

If something isn't working, follow this systematic debugging process:

1. **Issue: Chat API returns error**
   ```bash
   # Check App Runner logs
   aws logs tail /aws/apprunner/<service-name> --follow
   
   # Test endpoint directly (bypass CloudFront)
   curl https://<app-runner-url>/api/chat \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <password>" \
     -d '{"message": "test"}'
   
   # Check backend logs locally (if testing locally)
   docker-compose logs backend
   ```

2. **Issue: CORS error in browser**
   ```bash
   # Check browser console for exact CORS error
   # Verify FastAPI CORS config includes CloudFront origin
   
   # Test with curl (simulate browser request)
   curl -H "Origin: https://xxxxx.cloudfront.net" \
        -H "Access-Control-Request-Method: POST" \
        -X OPTIONS \
        https://<app-runner-url>/api/chat
   ```

3. **Issue: Frontend doesn't load**
   ```bash
   # Check S3 bucket contents
   aws s3 ls s3://<frontend-bucket-name>/
   
   # Check CloudFront distribution status
   aws cloudfront get-distribution --id <distribution-id>
   
   # Invalidate CloudFront cache (if needed)
   aws cloudfront create-invalidation --distribution-id <id> --paths "/*"
   ```

4. **Issue: Terraform apply fails**
   ```bash
   # Check Terraform state
   terraform state list
   
   # Check for state lock
   aws dynamodb scan --table-name terraform-state-lock
   
   # Review error message, fix issue, retry
   # If stuck, destroy and recreate:
   terraform destroy -target=<failed-module>
   terraform apply -target=<failed-module>
   ```

5. **Issue: Docker build fails**
   ```bash
   # Build locally first to see errors
   docker build -t backend:test -f backend/Dockerfile .
   
   # Check Dockerfile syntax
   docker build --no-cache -t backend:test -f backend/Dockerfile .
   
   # Test image locally before pushing
   docker run -p 8000:8000 --env-file .env backend:test
   ```

**Common Issues (Phase 1b - Production Hardening)**
| Symptom | Root Cause | Fix |
|---------|------------|-----|
| App Runner cannot reach Neon (`could not connect to server`) | DATABASE_URL incorrect or missing | Verify DATABASE_URL secret in Secrets Manager, check Neon dashboard for correct connection string |
| Terraform apply fails on App Runner VPC connector | Subnets not tagged or already in use | Ensure two public subnets exist and pass IDs to connector module |
| Alembic migration fails | Database connection string incorrect | Verify `DATABASE_URL` in App Runner environment variables matches Neon endpoint |
| GitHub Actions deploy fails | Missing secrets or IAM permissions | Verify all secrets are set and IAM user has required permissions |

---

### Phase 2: Core Agent Tools
**Goal:** Agent can search the web, query SQL databases, and retrieve from documents

> **Implementation Guides:** 
> - `docs/PHASE_2A_HOW_TO_GUIDE.md` - Data Foundation & Basic Tools (VLM, SQL, basic RAG)
> - `docs/PHASE_2B_HOW_TO_GUIDE.md` - Intelligence Layer (Knowledge Graph, hybrid retrieval, multi-tool orchestration)

**Features:**

**2a. Tavily Search Tool** ✅ *COMPLETED IN PHASE 0*
- Tavily API integration
- Tool definition in LangGraph (using built-in tool binding)
- Result formatting and citation
- **Comprehensive error handling** with retry logic and exponential backoff
- **Fallback mechanisms:** Graceful degradation if Tavily unavailable (mock fallback)
- **Circuit breaker pattern:** Stop trying after 3 failures, recover after 30s
- Rate limiting (respect API limits)
- **Structured logging** of search queries and results
- *Implementation:* `backend/src/agent/tools/search.py`

**2b. SQL Query Tool** ✅ *COMPLETED IN PHASE 2a*
- **Uses existing Neon PostgreSQL** from Phase 1b (no new provisioning needed)
- **Data Source:** Real 10-K financial metrics extracted via VLM (not synthetic data)
- **Tables:** companies, financial_metrics, segment_revenue, geographic_revenue, risk_factors
- **Connection Pooling:** SQLAlchemy built-in (skip RDS Proxy for demo cost savings)
- Natural language to SQL via LLM with schema context
- Query execution with result limits/safety (max 1000 rows, read-only, 30s timeout)
- **SQL Injection Prevention (Critical):**
  - Parameterized queries only (SQLAlchemy `text()` with parameters)
  - Table/column whitelisting (ALLOWED_TABLES set)
  - Never use string formatting for SQL
  - Query validation before execution
- Query explanation/justification
- **Sample Queries:**
  - "Which company had the highest revenue in 2024?"
  - "Compare gross margins across tech companies"
  - "What percentage of Apple's revenue comes from iPhone?"
- **Error handling:** Graceful failures with helpful error messages
- **Circuit breaker:** Prevent repeated failures from overwhelming database
- *Implementation:* `backend/src/agent/tools/sql.py`

**2c. RAG Document Tool (2026 SOTA Hybrid Search + Knowledge Graph)** ✅ *BASIC COMPLETE, HYBRID IN PROGRESS*

> **Status:** Basic RAG (dense search) ✅ completed in Phase 2a. Knowledge Graph indexing ✅ complete. Hybrid retrieval + KG integration 🔄 in progress (Phase 2b).
> 
> **Full Architecture:** See `docs/RAG_README.md` for comprehensive architecture. Implementation details in `docs/PHASE_2A_HOW_TO_GUIDE.md` (basic RAG) and `docs/PHASE_2B_HOW_TO_GUIDE.md` (hybrid retrieval, knowledge graph).
> 
> **KG Enhancement Plan:** See `docs/KNOWLEDGE_GRAPH_UPDATE_PLAN.md` for detailed KG integration enhancements.

**Key Decisions:**
- **VLM for ALL documents** - Claude Vision extracts clean text from all PDFs (10-Ks and reference docs)
- **Batch script processing** - No Lambda, no timeouts, easier debugging
- **spaCy for entity extraction** - 20-50x cheaper than LLM for Knowledge Graph population
- **One-time cost:** ~$40-60 for ~30-40 documents total

**January 2026 State-of-the-Art Techniques:**

- **Semantic Chunking with Parent-Child Architecture:**
  - Split at sentence/paragraph boundaries using spaCy
  - Parent chunks: 1024 tokens (non-overlapping, section-aware)
  - Child chunks: 256 tokens (50-token overlap within same parent)
  - Children embedded for precise search, parents retrieved for LLM context
  - Section-aware boundaries: Never crosses 10-K Item sections
  - Impact: +10-15% retrieval relevance
  - Cost: $0 (ingestion time only)

- **Contextual Retrieval (Anthropic technique):**
  - Prepend document title, type, section to each chunk before embedding
  - Chunks carry their context, improving disambiguation
  - Impact: +15-20% precision, +67% combined with BM25
  - Cost: $0 (ingestion time only)

- **Efficient Knowledge Graph Construction (NLP-based):**
  - Use spaCy NER + dependency parsing instead of LLM calls
  - Custom patterns for financial domain entities
  - Extract entities and relationships at 20-50x lower cost
  - Storage: Neo4j AuraDB Free tier (200K nodes, $0/month)
  - Impact: Same coverage as LLM, ~$0.001/doc vs $0.02-0.05/doc

- **Cross-Encoder Reranking:**
  - LLM scores query-document relevance after RRF fusion
  - Applied before contextual compression
  - Impact: +20-25% precision on top-k results
  - Cost: ~$0.01-0.015/query

- **Knowledge Graph Integration (January 2026 Best Practices):**
  - Infrastructure: Neo4j AuraDB Free (200K nodes, $0/month)
  - 1-hop for simple queries, 2-hop for complex queries (2+ entities)
  - Base ontology: 10 entity types (Organization, Person, Location, Regulation, Concept, etc.)
  - **Entity Evidence for Explainability:** KG returns WHY docs matched (entity, type, match_type, pages)
  - **Page-Level Boosting:** +0.1 boost to chunks from KG-matched pages (not entire documents)
  - **Fallback:** Document-level boost for content without page info (news articles)
  - **LLM Context:** Entity evidence included in citations for transparency
  - Impact: +10-15% precision on entity-specific queries

**Ingestion Pipeline (Batch Script):**
```
PDF → Claude VLM → Clean Text → ┬→ Semantic Chunking → Titan Embed → Pinecone
                                ├→ BM25 Index → Pinecone (sparse)
                                ├→ spaCy NER → Neo4j (entities)
                                └→ Parse Tables → PostgreSQL (10-Ks only)
```

1. Document → VLM Extraction (Claude Vision via Bedrock)
2. Clean text → Semantic Chunking (spaCy sentence boundaries)
3. Each chunk → Add Context (title, section, page)
4. Contextualized chunks → Embed (Titan) + BM25 → Store (Pinecone)
5. Clean text → spaCy NER → Store entities in Knowledge Graph (Neo4j)
6. (10-Ks only) Parsed tables → Store metrics in PostgreSQL

**Query Pipeline (8 steps):**
1. Query Analysis (Nova Lite, single call) → 3 variants + KG complexity ("simple"/"complex")
2. Parallel retrieval:
   - Dense search (Pinecone) → chunks
   - BM25 search (Pinecone sparse) → chunks
   - KG entity lookup (Neo4j, uses complexity) → 1-hop if simple, +2-hop if complex
3. RRF Fusion (merge dense + BM25 chunks)
4. **KG Boost** (apply +0.1 to chunks from KG-matched docs, attach entity evidence)
5. Cross-Encoder Rerank (Nova Lite scores relevance)
6. Contextual Compression (extract relevant sentences)
7. Format response with KG evidence for explainability
8. Return with source citations

**Costs:**
- One-time VLM extraction: ~$40-60 for ~30-40 documents
- Per-query: ~$0.035-0.04

**Core Features:**
- Pinecone serverless index with hybrid search (dense + sparse via BM25)
- Document embedding pipeline (Bedrock Titan Embeddings v2, 1024 dimensions)
- **VLM extraction** (Claude Vision) for all documents via batch script
- Query expansion (3 alternative phrasings via Nova Lite, +20-30% recall)
- RRF (Reciprocal Rank Fusion) for combining semantic + keyword chunk results
- **KG Boost** (page-level boosting from KG entity matches, with document-level fallback)
- **KG Evidence** (entity context attached to results for LLM explainability)
- Cross-encoder reranking (Nova Lite scores relevance, +20-25% precision)
- Contextual Compression (LLMChainExtractor)
- Source citation with page/section numbers and KG match info
- Metadata filtering (document_type, company, section, etc.)
- **Fallback mechanisms:** Graceful degradation if Pinecone/KG unavailable
- *Implementation:* `backend/src/agent/tools/rag.py` (basic in Phase 2a, hybrid in Phase 2b)

**2d. Market Data Tool (FMP via MCP)** ✅ *COMPLETED IN PHASE 0*
- Financial Modeling Prep integration exposed via MCP (live calls optional; mock mode when no API key)
- Tool definition in LangGraph (using built-in tool binding)
- Result formatting with price, change, change%, open/close, day high/low, volume, currency, exchange, timestamp
- **Comprehensive error handling** with retry logic and exponential backoff
- **Fallback mechanisms:** Graceful degradation if API unavailable (mock fallback)
- **Circuit breaker pattern:** Stop trying after 3 failures, recover after 30s
- Rate limiting guidance for free tier (~250 calls/day) with batching for multiple tickers
- **Structured logging** of market data queries and results
- Input validation (ticker list, uppercase, comma-separated)
- **Error handling:** User-friendly messages for invalid tickers
- **No infrastructure required:** Uses existing App Runner backend, no new AWS services
- *Implementation:* `backend/src/agent/tools/market_data.py`

**Infrastructure Additions:**
- **Note:** Uses existing Neon PostgreSQL from Phase 1b (no new provisioning needed)
- **Connection Pooling Strategy (Cost-Conscious):**
  - **Skip RDS Proxy** ($15-20/month) - too expensive for demo
  - Use SQLAlchemy connection pooling instead (free, built-in)
  - Pool size: 5 connections (sufficient for demo)
  - Max overflow: 10 connections
  - Fine for low-use demo, upgrade to RDS Proxy only if scaling
- Pinecone index (via console or API, free tier)
- S3 bucket (optional) for extracted JSON backup
- **No Lambda for document ingestion** - batch script approach instead (simpler, no timeouts)
- Additional IAM policies for tool access (Bedrock Claude for VLM)
- **Knowledge Graph Infrastructure:**
  - Neo4j AuraDB Free tier (200K nodes, 400K relationships, $0/month)
  - Neo4j in Docker for local development
  - spaCy for NLP-based entity extraction (no LLM cost, 20-50x cheaper)

**Document Processing (Batch Script):**
- `scripts/extract_and_index.py` - Main extraction and indexing script
- `scripts/load_10k_to_sql.py` - Load 10-K financial metrics to PostgreSQL
- Runs locally (no Lambda timeouts, easier debugging)
- See `docs/completed-phases/PHASE_2_REQUIREMENTS.md` "Enterprise Scaling" for Lambda approach if needed later

**Sample Data:**

**SQL Database Schema (10-K Financial Metrics - VLM Extracted):**
```sql
-- Companies (one row per 10-K filing)
companies (id, ticker, name, sector, fiscal_year_end, filing_date, document_id)
-- ~7 companies: AAPL, MSFT, AMZN, GOOGL, TSLA, JPM, NVDA

-- Annual financial metrics (from income statement, balance sheet)
financial_metrics (id, company_id, fiscal_year, revenue, net_income, gross_margin, 
                   operating_margin, net_margin, total_assets, earnings_per_share)

-- Business segment revenue breakdown
segment_revenue (id, company_id, fiscal_year, segment_name, revenue, percentage_of_total)
-- e.g., iPhone, Mac, Services for Apple

-- Geographic revenue breakdown
geographic_revenue (id, company_id, fiscal_year, region, revenue, percentage_of_total)
-- e.g., Americas, Europe, Greater China

-- Risk factors (from Item 1A)
risk_factors (id, company_id, fiscal_year, category, title, summary, severity)
-- category: 'Supply Chain', 'Regulatory', 'Competition', 'Macroeconomic'

-- Sample queries the agent should handle:
-- "Which company had the highest revenue in 2024?"
-- "Compare gross margins across tech companies"
-- "What percentage of Apple's revenue comes from iPhone?"
-- "Which companies have supply chain risks?"
-- "Show me Tesla's geographic revenue breakdown"
```

**RAG Document Store (VLM Extracted):**
- **10-K Filings (~7):** AAPL, MSFT, AMZN, GOOGL, TSLA, JPM, NVDA (FY2024)
- **Reference Documents (~10-15):** News articles, research reports, market analysis
- **Source:** SEC EDGAR for 10-Ks, financial news for reference docs
- **See:** `docs/PHASE_2A_HOW_TO_GUIDE.md` Section 3 for document acquisition details

**Security Hardening (Phase 2):**
- **SQL Tool Security:**
  - Parameterized queries only (never string formatting)
  - ALLOWED_TABLES whitelist for query validation
  - Read-only database connections for SQL tool
  - Query timeout limits (30 seconds max)
  - Result set limits (1000 rows max)
- **Conversation Security (Checkpoint Protection):**
  - UUID validation for conversation_id (reject non-UUID formats at API layer)
  - Session-to-conversation binding (store mapping of conversation_id to user session)
  - Access control verification (users can only access their own conversations)
  - Prevent conversation enumeration attacks
- **Input Validation:**
  - Pydantic validators on all API inputs
  - Message length limits (4000 chars)
  - Conversation ID format validation (UUID only)
- **Reference:** See `[_security.mdc]` for implementation patterns

**Deliverables:**
- Agent can search the web and cite sources
- Agent can query SQL database (10-K financial metrics) with natural language
- Agent can retrieve relevant documents from vector store (hybrid search + KG)
- Agent can retrieve current market data (FMP) for requested tickers
- VLM extraction script processes all documents (batch, not Lambda)
- Knowledge Graph populated with entities from all documents
- Tool selection is intelligent and contextual
- Combined queries work (e.g., "Compare Apple's China revenue to their disclosed risks")

**Future Optimizations (Deferred - Acceptable at Demo Scale):**

| Optimization | Current State | Impact | When to Revisit |
|--------------|---------------|--------|-----------------|
| **Neo4j TEXT index** | BTREE index on `e.text`, queries use `toLower()` which bypasses index | ~10-50ms full scan on 3K entities (acceptable) | If entity count > 50K or query times > 200ms |
| **Neo4j query timeout** | No explicit timeout configured | Relies on driver default (30s) | If Neo4j latency issues observed |

*Note: These are pre-existing patterns in `queries.py` that work well at demo scale (~3K entities). TEXT indexes (Neo4j 5.9+) provide case-insensitive matching without `toLower()` function calls.*

---

### Phase 3: Observability with Arize Phoenix
**Goal:** Full tracing and monitoring of agent execution

**Features:**
- Arize Phoenix self-hosted deployment (ECS Fargate, scales to minimal)
- LangGraph native callbacks (LangChainTracer) for built-in observability
- OpenTelemetry integration with LangGraph
- Structured logging (structlog) with JSON output for CloudWatch
- Trace visualization for agent runs
- Comprehensive metrics tracking:
  - Token usage (input/output tokens per request)
  - Latency breakdown (LLM call time, tool execution time, total time)
  - Tool success rate (which tools succeed/fail)
  - Cache hit rate (inference cache effectiveness)
  - Cost per request (actual AWS costs)
  - Error rate by type (timeout, API error, validation error, etc.)
  - **Knowledge Graph metrics (from Phase 2b):**
    - KG hit rate (% of queries where KG found matches, target: >60%)
    - Boost impact (avg position change of KG-boosted chunks, target: +2-3)
    - 2-hop usage (% of complex queries triggering 2-hop, target: 20-40%)
    - KG latency (time in `_kg_search()`, target: <200ms)
    - KG failure rate (% of queries where KG fails, target: <5%)
- Error rate monitoring
- Tool usage analytics
- Cost tracking per conversation
- Log aggregation: centralized logging in CloudWatch with structured JSON

**Infrastructure:**
- ECS Fargate task for Phoenix (minimal instance) running in the same public subnets created in Phase 1a (still no NAT/VPC endpoints)
- Persistent storage (EFS for Phoenix data) with mount targets in those public subnets and security groups restricted to the Phoenix task + App Runner VPC connector
- Internal ALB for Phoenix UI
- Password protection for Phoenix dashboard
- CloudWatch integration
- CloudWatch Logs Insights queries for log analysis
- CloudWatch Dashboards for key metrics visualization

**Deliverables:**
- Full trace of every agent execution
- Latency breakdown visible
- Token usage tracked
- Error rates monitored
- Tool usage analytics

---

### Phase 4: RAG Evaluation with RAGAS
**Goal:** Automated quality measurement for RAG responses

**Features:**
- RAGAS integration for evaluation metrics:
  - Faithfulness (factual accuracy)
  - Answer relevancy
  - Context precision
  - Context recall
- Evaluation dataset management (S3)
- Scheduled evaluation runs (daily/weekly via EventBridge)
- Metrics dashboard in Phoenix
+- Regression alerts (CloudWatch alarms)
+- Evaluation on document updates

**Implementation:**
- Lambda function for scheduled evaluations
- S3 bucket for evaluation datasets (separate from document storage bucket for better organization)
- CloudWatch metrics and alarms
- Integration with GitHub Actions for PR checks (optional)
- Evaluation report generation

**Infrastructure Additions:**
- S3 bucket for RAGAS evaluation datasets (separate from Phase 2 document storage bucket)
- Lambda function for scheduled RAGAS evaluations (EventBridge trigger)
- IAM policies for Lambda to access S3 evaluation datasets and Phoenix
- CloudWatch alarms for quality regression detection

**Deliverables:**
- Automated RAG quality evaluation
- Metrics visible in dashboard
- Alerts on quality regression
- Evaluation reports generated

---

### Phase 5: Enhanced UI and Thought Process Streaming
**Goal:** Polished user experience with visible agent reasoning

**Features:**
- Real-time thought process display:
  - "Searching the web for..."
  - "Querying database..."
  - "Analyzing documents..."
  - Tool input/output visibility
- Collapsible reasoning panels
- Source citations with links
- Conversation history (DynamoDB)
- Dark/light mode toggle
- Mobile responsive design
- Loading states and animations
- Error message display
- Retry functionality

**UI Components:**
- Chat message bubbles
- Thought process timeline
- Source citation cards
- Tool execution cards
- Loading skeletons
- Error toast notifications

**Deliverables:**
- Beautiful, professional UI
- Thought process visible in real-time
- Sources clearly cited
- Conversation history persists
- Mobile-friendly design (cache metrics dashboard ships with Phase 7)

---

### Phase 6: Input/Output Verification
**Goal:** SLM guards validate user inputs and agent outputs for safety/quality

**Features:**

**Input Verification:**
- Nova Lite as verification SLM
- Prompt injection detection
- Content policy enforcement (no harmful content)
- Jailbreak attempt detection
- Request classification (safe/unsafe/needs-review)
- Configurable sensitivity levels

**Output Verification:**
- Hallucination risk scoring
- PII detection and redaction
- Response quality checks (coherence, relevance)
- Citation verification for RAG responses
- Fact-checking for critical claims

**Implementation:**
- Verification nodes in LangGraph workflow
- Configurable policies (strict/moderate/permissive)
- Bypass for trusted internal requests
- Logging of flagged content to CloudWatch
- Metrics for verification pass/fail rates

**Deliverables:**
- Input verification blocks malicious prompts
- Output verification ensures quality responses
- Verification metrics visible in monitoring
- Configurable policy levels

---

### Phase 7: Inference Caching
**Goal:** Reduce costs and latency by caching repeated queries

**Features:**
- Semantic similarity caching (not just exact match)
- DynamoDB table for cache storage (on-demand pricing)
- **DynamoDB TTL** for automatic cache cleanup (no manual deletion needed)
- Embedding-based cache key generation (Bedrock Titan)
- TTL-based cache expiration (configurable, default 7 days)
- Cache hit/miss metrics (tracked in CloudWatch)
- Configurable similarity threshold (cosine similarity > 0.95)
- Cache invalidation on document updates
- **Cost tracking:** Monitor cache effectiveness and cost savings
- Cost savings dashboard (cache hit/miss, tokens saved, $ saved)

**Implementation:**
- Cache check before LLM call
- Cache write after successful response
- Cache invalidation on document updates
- Cost savings dashboard (tokens saved, $ saved)
- Metrics feed/API from cache layer to dashboard (CloudWatch + app endpoint)
- Wire Phase 5 dashboard UI to metrics feed once cache is live

**Infrastructure Additions:**
- DynamoDB table for inference cache (on-demand pricing, TTL enabled)
- IAM policies for App Runner to read/write DynamoDB cache table
- CloudWatch metrics for cache hit/miss rates

**Deliverables:**
- Repeated queries return instantly from cache
- Cache hit rate > 30% for typical usage
- Cost savings visible in dashboard
- Cache invalidation works correctly
- Dashboard shows cache hit/miss and savings, driven by Phase 7 metrics feed

---

### Phase 8: Future RAG Improvements (Reference)
**Goal:** Document advanced RAG techniques for future enhancement phases

This phase serves as a reference guide for potential improvements beyond the initial implementation. Each technique is rated on Power (quality), Speed (latency), and Cost.

**Query Enhancement Techniques:**

| Technique | What It Does | Power | Speed | Cost | Complexity |
|-----------|--------------|-------|-------|------|------------|
| Query Expansion (Phase 2) | Generate 3 alternative phrasings | +20-30% recall | -50ms | $0.01/q | Low |
| HyDE | Generate hypothetical answer, embed that | +10-15% precision | -300ms | $0.005/q | Low |
| Query Decomposition | Break complex query into sub-queries | +15-20% complex queries | -500ms | $0.02/q | Medium |
| Step-back Prompting | Abstract to higher-level concept first | +10-15% reasoning | -200ms | $0.01/q | Medium |

**Indexing/Chunking Techniques:**

| Technique | What It Does | Power | Speed | Cost | Complexity |
|-----------|--------------|-------|-------|------|------------|
| Semantic Chunking (Phase 2) | Split at sentence boundaries | +10-15% relevance | +0ms | $0 | Low |
| Contextual Retrieval (Phase 2) | Prepend doc context to chunks | +15-20% precision | +0ms | $0 | Very Low |
| Parent Doc Retriever (Phase 2) | Small chunks search, large context return | +15-20% context | +0ms | $0 | Low |
| Late Chunking | Embed full doc, then chunk | +10-15% context | +0ms | $0 | Medium |
| Proposition Indexing | Convert to factual statements | +20-25% precision | +0ms | $0.05/doc | High |

**Retrieval Techniques:**

| Technique | What It Does | Power | Speed | Cost | Complexity |
|-----------|--------------|-------|-------|------|------------|
| Hybrid Search (Phase 2) | Dense + BM25 sparse | +20-30% recall | +0ms | $0 | Low |
| RRF Fusion (Phase 2) | Merge multiple result sets | +10-15% | +0ms | $0 | Low |
| KG 1-2 Hop (Phase 2) | Entity relationship traversal | +15-25% precision | +50ms | $0.01/q | Medium |
| Multi-index Search | Search by doc type | +10% diverse | +100ms | $0 | Medium |

**Post-Retrieval Techniques:**

| Technique | What It Does | Power | Speed | Cost | Complexity |
|-----------|--------------|-------|-------|------|------------|
| Cross-Encoder Rerank (Phase 2) | LLM scores relevance | +20-25% precision | -300ms | $0.015/q | Low |
| Contextual Compression (Phase 2) | Extract relevant portions | +10-15% relevance | -200ms | $0.01/q | Low |
| Diversity Reranking (MMR) | Ensure diverse results | +5-10% coverage | +0ms | $0 | Low |
| Lost-in-Middle Reorder | Best docs at start/end | +5% attention | +0ms | $0 | Very Low |

**Advanced/Agentic Techniques (Future):**

| Technique | What It Does | Power | Speed | Cost | Complexity |
|-----------|--------------|-------|-------|------|------------|
| KG-R1 (arXiv 2509.26383) | RL agent learns optimal KG traversal | +15-25% accuracy | -100ms | Training cost | High |
| NodeRAG (arXiv 2504.11544) | Heterogeneous graph nodes | +20% efficiency | +0ms | $0 | Medium |
| Speculative RAG (ICLR 2025) | Small model drafts, large verifies | Same quality | 2-3x faster | Lower | Medium-High |
| KERAG (EMNLP 2025) | Subgraph retrieval + CoT reasoning | +7% over SOTA | -500ms | $0.03/q | High |
| TAdaRAG (arXiv 2511.12520) | On-the-fly task-adaptive KG | Better generalization | -300ms | $0.02/q | High |
| Self-RAG | LLM critiques and re-retrieves | +25% accuracy | -1000ms | $0.05/q | High |
| Agentic RAG | LLM decides strategy dynamically | +30% complex | -500ms | $0.05/q | Very High |

**Optimization Tradeoff Guide:**

*Optimize for POWER (Best Quality):*
1. Contextual Retrieval + Semantic Chunking (free)
2. Cross-Encoder Reranking ($0.015/q)
3. KG-enhanced retrieval ($0.01/q)
4. KERAG subgraph reasoning ($0.03/q)
5. Self-RAG with re-retrieval ($0.05/q)

*Optimize for SPEED (Lowest Latency):*
1. Speculative RAG (2-3x faster)
2. Skip HyDE (save 300ms)
3. Efficient NLP extraction (10ms vs 500ms)
4. Pre-computed KG paths
5. Smaller reranking batch

*Optimize for COST (Cheapest):*
1. NLP entity extraction ($0.001 vs $0.05/doc)
2. Skip HyDE ($0.005 saved/query)
3. Smaller query expansion (2 vs 3 variants)
4. Contextual Retrieval + Semantic Chunking ($0)
5. PostgreSQL instead of Neo4j ($0)

**Deliverables:**
- Reference documentation for future improvements
- Benchmarks for technique comparison
- Migration guides for implementing advanced techniques

---

## Project Structure

```
aws-enterprise-agentic-ai/
├── terraform/
│   ├── environments/
│   │   ├── dev/
│   │   │   ├── terraform.tfvars
│   │   │   └── backend.tf
│   │   └── prod/
│   │       ├── terraform.tfvars
│   │       └── backend.tf
│   ├── modules/
│   │   ├── networking/
│   │   │   ├── main.tf
│   │   │   ├── vpc.tf
│   │   │   └── outputs.tf
│   │   ├── app-runner/
│   │   │   ├── main.tf
│   │   │   ├── service.tf
│   │   │   └── outputs.tf
│   │   # Note: No aurora/ module - using Neon PostgreSQL (external)
│   │   ├── s3-cloudfront/
│   │   │   ├── main.tf
│   │   │   ├── s3.tf
│   │   │   ├── cloudfront.tf
│   │   │   └── outputs.tf
│   │   ├── lambda/
│   │   │   ├── main.tf
│   │   │   ├── document-ingestion.tf
│   │   │   └── outputs.tf
│   │   └── observability/
│   │       ├── main.tf
│   │       ├── phoenix.tf
│   │       └── outputs.tf
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   └── versions.tf
├── backend/
│   ├── src/
│   │   ├── agent/
│   │   │   ├── graph.py          # LangGraph definition
│   │   │   ├── state.py          # State schema
│   │   │   ├── nodes/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── chat.py       # Main chat node
│   │   │   │   ├── tools.py      # Tool execution node
│   │   │   │   ├── verification.py  # I/O verification
│   │   │   │   └── error_recovery.py  # Error recovery node
│   │   │   └── tools/
│   │   │       ├── __init__.py
│   │   │       ├── search.py     # Tavily search (with fallback, circuit breaker)
│   │   │       ├── sql.py        # Neon query (SQL injection prevention)
│   │   │       ├── rag.py        # Pinecone retrieval (query expansion, RRF, compression)
│   │   │       └── market_data.py # Market data (FMP via MCP, circuit breaker)
│   │   ├── cache/
│   │   │   ├── __init__.py
│   │   │   └── inference_cache.py
│   │   ├── ingestion/
│   │   │   ├── __init__.py
│   │   │   ├── document_processor.py
│   │   │   ├── semantic_chunking.py  # Grammar-aware chunking (spaCy)
│   │   │   ├── contextual_chunking.py  # Context prepending for chunks
│   │   │   ├── chunking.py       # Parent document retriever strategy
│   │   │   └── query_expansion.py  # Query expansion for RAG
│   │   ├── knowledge_graph/
│   │   │   ├── __init__.py
│   │   │   ├── ontology.py       # Financial domain ontology (EntityType, RelationType)
│   │   │   ├── extractor.py      # NLP-based entity extraction (spaCy + financial patterns)
│   │   │   ├── store.py          # Neo4j adapter with connection pooling, batch ops
│   │   │   └── queries.py        # Graph traversal queries (1-hop, 2-hop, fuzzy search)
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── main.py           # FastAPI app
│   │   │   ├── routes/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── v1/           # API versioning
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   └── chat.py   # /api/v1/chat endpoint
│   │   │   │   └── health.py     # Health check (with dependency checks)
│   │   │   └── middleware/
│   │   │       ├── __init__.py
│   │   │       ├── auth.py       # Password auth (abstracted for future Cognito migration)
│   │   │       ├── rate_limit.py # Rate limiting (slowapi)
│   │   │       ├── logging.py    # Structured logging (structlog)
│   │   │       └── error_handler.py  # User-friendly error messages
│   │   ├── config/
│   │   │   ├── __init__.py
│   │   │   ├── settings.py       # Pydantic settings (with fallback models)
│   │   │   └── container.py      # Dependency injection container
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── embeddings.py
│   │       ├── circuit_breaker.py  # Circuit breaker pattern
│   │       ├── rrf.py              # Reciprocal Rank Fusion
│   │       └── reranker.py         # Cross-encoder reranking (LLM-based)
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_agent.py
│   │   ├── test_tools.py
│   │   └── test_api.py
│   ├── Dockerfile              # Production multi-stage
│   ├── Dockerfile.dev          # Development (with hot reload)
│   ├── requirements.txt        # Pinned versions (langgraph~=0.2.50, etc.)
│   ├── alembic/                # Database migrations
│   │   ├── versions/
│   │   │   └── 001_initial_schema.py
│   │   └── alembic.ini
│   ├── .dockerignore
│   └── pytest.ini
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx          # Chat interface (with cold start loading state)
│   │   │   ├── login/
│   │   │   │   └── page.tsx      # Login page
│   │   │   └── components/
│   │   │       └── cold-start/   # Cold start loading indicator
│   │   │           └── WarmupIndicator.tsx
│   │   ├── components/
│   │   │   ├── chat/
│   │   │   │   ├── ChatMessage.tsx
│   │   │   │   ├── ChatInput.tsx
│   │   │   │   └── ChatHistory.tsx
│   │   │   ├── thought-process/
│   │   │   │   ├── ThoughtTimeline.tsx
│   │   │   │   └── ToolExecution.tsx
│   │   │   └── ui/               # shadcn components
│   │   │       ├── button.tsx
│   │   │       ├── card.tsx
│   │   │       └── ...
│   │   ├── lib/
│   │   │   ├── utils.ts
│   │   │   ├── api.ts            # API client (calls App Runner, not Next.js API routes)
│   │   │   └── sse.ts            # SSE client using native EventSource
│   │   └── styles/
│   │       └── globals.css
│   ├── public/
│   ├── package.json
│   ├── tailwind.config.js
│   ├── next.config.js            # Configured for static export
│   │                             # output: 'export', no API routes
│   └── tsconfig.json
├── lambda/
│   └── document-ingestion/
│       ├── handler.py
│       ├── requirements.txt
│       └── Dockerfile (if needed)
├── .github/
│   └── workflows/
│       ├── ci.yml                # PR checks
│       ├── deploy-dev.yml
│       ├── deploy-prod.yml
│       └── evaluate.yml          # RAGAS evaluation
├── docker-compose.yml            # Full stack development (optimized, 5-10s startup)
├── docker-compose.override.yml  # Local overrides (optional)
├── .pre-commit-config.yaml      # Pre-commit hooks (black, ruff, mypy, tests)
├── .devcontainer/                # VS Code dev container config (optional)
│   └── devcontainer.json
├── docs/
│   ├── architecture.md
│   ├── deployment.md
│   └── api.md
├── .env.example
├── .gitignore
└── README.md
```

---

## GitHub Actions Workflows

**Phase gating:** Introduced in Phase 1b (no CI/CD in Phase 0). Triggers are `push` to `main` + `pull_request` (CI), `workflow_dispatch` manual trigger (CD), and scheduled/manual dispatch (evaluation).

### CI Pipeline (on push to main & PRs):
1. Lint and format check (Python: black, ruff | TypeScript: ESLint, tsc)
2. Unit tests (pytest for Python)
3. Terraform validate and plan (no apply)
4. Security scanning (Bandit for Python, gitleaks for secrets)
5. Build Docker image (test build, don't push)

### CD Pipeline (manual trigger via GitHub Actions UI):
1. Build backend Docker image
2. Push to ECR
3. Build frontend (Next.js build)
4. Upload frontend to S3
5. Invalidate CloudFront cache
6. Health check (verify deployment)
7. Run smoke tests

**How to deploy:** Go to GitHub → Actions tab → Select "Deploy" workflow → Click "Run workflow" button

### Evaluation Pipeline (scheduled/manual):
1. Pull evaluation dataset from S3
2. Run RAGAS evaluation
3. Upload metrics to Phoenix
4. Check for regressions
5. Alert on quality degradation

---

## Cost Breakdown (Estimated Monthly - Low Usage)

| Service | Base Cost | Variable Cost | Notes |
|---------|-----------|---------------|-------|
| App Runner | $5-15 | $0 | Scales to zero when idle (cold start 10-30s) |
| Neon PostgreSQL | $0 | $0 | Free tier (0.5GB, 190 compute hours) |
| Bedrock Nova | $0 | $2-10 | Pay-per-token, varies by usage |
| Pinecone | $0 | $0 | Free tier (100K vectors) |
| Neo4j AuraDB | $0 | $0 | Free tier (200K nodes) |
| S3 + CloudFront | $0 | $1-2 | First 1GB free, then $0.023/GB storage + $0.085/GB transfer |
| Secrets Manager | $0.40 | $0 | 1 secret |
| DynamoDB | $0 | $0-2 | Free tier + minimal usage, TTL for auto-cleanup |
| ECS Fargate (Phoenix) | $0 | $3-8 | Minimal instance, scales down when idle |
| EFS (Phoenix storage) | $0 | $0.30 | Minimal storage (~1GB) |
| Tavily API | $0 | $0-10 | Free tier: 1000 searches/month |
| Bedrock Embeddings | $0 | $1-3 | $0.0001/1K tokens (query expansion uses 4x) |
| ECR Storage | $0 | $0-1 | First 500MB free, then $0.10/GB |
| CloudWatch Logs | $0 | $0-2 | First 5GB free, set 7-day retention |
| **Phase 2 One-Time:** |
| VLM Extraction | **$40-60** | $0 | One-time cost for ~30-40 documents (Claude Vision) |
| **VPC Costs (OPTIONAL - Skip for Demo):** |
| RDS Proxy | $15-20 | $0 | **SKIP** - Use SQLAlchemy pooling instead |
| VPC Endpoints | $7-10 each | $0 | **SKIP** - Use public subnets for demo |
| NAT Gateway | $32 | $0.045/GB | **SKIP** - Not needed with public subnets |
| Data Transfer Out | $0 | $0.09/GB | First 100GB free/month (usually $0 for demo) |
| **Total (Minimal VPC)** | **$20-50/month** | | Optimized for <$50 with light usage |
| **Total (With VPC Security)** | **$40-80/month** | | If using VPC endpoints + RDS Proxy |

**Cost Optimization Strategies (Demo-Focused):**
- **Skip expensive VPC components:**
  - ❌ RDS Proxy ($15-20/month) → Use SQLAlchemy connection pooling (free)
  - ❌ VPC Endpoints ($7-10 each) → Use public subnets (free, less secure but fine for demo)
  - ❌ NAT Gateway ($32/month) → Not needed with public subnets
- **Batch script vs Lambda:** No Lambda infrastructure for document ingestion (simpler, no cost)
- Neon free tier provides 0.5GB storage and 190 compute hours/month
- Neo4j AuraDB free tier provides 200K nodes (plenty for demo)
- App Runner scales to zero when idle
- DynamoDB on-demand pricing with TTL (no minimum, automatic cleanup)
- Phoenix on minimal Fargate instance (can skip entirely for MVP)
- CloudFront caching reduces origin requests
- Inference cache reduces Bedrock API calls by 30-40%
- **Bedrock on-demand** (not provisioned throughput) for cost flexibility
- **VLM extraction is one-time cost** (~$40-60) not monthly
- **Cost tracking:** Monitor and alert on cost thresholds ($50/month alarm)

**Cost Savings for Demo:**
- Public subnets instead of VPC endpoints: **Save $20-30/month**
- SQLAlchemy pooling instead of RDS Proxy: **Save $15-20/month**
- **Total savings: $35-50/month** (keeps demo under $20-30/month)

---

## Security Considerations

1. **Network Security (Cost-Conscious for Demo):**
   - **Demo Option:** Public subnets only (no VPC endpoints, no NAT Gateway)
     - Cost: $0 extra
     - Security: Less secure, but acceptable for portfolio demo
     - App Runner uses public internet for AWS services
   - **Production Option:** VPC with private subnets + VPC endpoints
     - Cost: +$20-30/month
     - More secure, better for production
   - Security groups with least privilege (regardless of subnet choice)
   - **Recommendation:** Start with public subnets for demo, document upgrade path

2. **Access Control:**
   - IAM roles with minimal permissions
   - Secrets Manager for sensitive data
   - **Password authentication (abstracted for future migration):**
     - Abstract auth behind `AuthProvider` interface
     - Current: `SimplePasswordAuth` implementation
     - Future: Easy to swap to `CognitoAuth` without code changes
     - Migration path documented in ADR

3. **Data Protection:**
   - Encryption at rest (S3, RDS, DynamoDB)
   - Encryption in transit (HTTPS/TLS)
   - No PII in logs (redaction)

4. **Application Security:**
   - **SQL injection prevention** (parameterized queries with SQLAlchemy `text()`, table whitelisting)
   - **Input validation** (Pydantic validators, message length limits, content sanitization)
   - **Rate limiting** (slowapi middleware, 10 requests/minute per IP, configurable)
   - **CORS configuration** (specific origins, methods, headers)
   - **Circuit breakers** for external service calls (prevent cascade failures)
   - **Error message sanitization** (don't expose internal errors to users)

---

## Monitoring & Alerting

1. **CloudWatch Metrics:**
   - API request count and latency
   - Error rates (by type: timeout, API error, validation error)
   - Cache hit/miss rates
   - Token usage (input/output tokens per request)
   - Cost tracking (per request, per conversation)
   - Tool success rates (which tools succeed/fail)
   - Latency breakdown (LLM call time, tool execution time, total time)

2. **CloudWatch Alarms:**
   - High error rate (>5%)
   - High latency (>10s)
   - Cost threshold ($50/month)
   - Service health checks

3. **Arize Phoenix:**
   - Agent execution traces
   - Tool usage analytics
   - Latency breakdown
   - Quality metrics

4. **Logging:**
   - **Structured logging** (structlog with JSON output)
   - Log levels (DEBUG, INFO, WARN, ERROR)
   - CloudWatch Logs integration
   - **CloudWatch Logs Insights** queries for analysis
   - Log retention (30 days)
   - **Structured fields:** user_query, tools_used, tokens_used, latency_ms, cost_usd, cache_hit

---

## Testing Strategy

**Approach:** Balanced - Best practices with minimal overhead

### Unit Tests (Core Logic):
- Agent nodes (chat, tools, verification) - Critical paths only
- Individual tools (search, SQL, RAG, market data) - Main functionality
- Cache logic - Core caching behavior
- Utility functions - Reusable helpers

**Testing Tools:**
- Python: pytest with pytest-cov (aim for 70%+ coverage on critical paths)
- TypeScript: Jest for frontend components
- Mock external services (Bedrock, Tavily, Pinecone, FMP) for unit tests

### Integration Tests (Key Flows):
- Tool interactions - Verify tools work together
- End-to-end agent flow - Complete conversation flow
- API endpoints - Request/response validation
- Database queries - SQL generation and execution

**Integration Test Approach:**
- Use test database (local Postgres)
- Mock external APIs (Bedrock, Tavily) for consistency
- Test real Pinecone interactions (use test index)

### Manual Testing:
- UI/UX validation - Visual and interaction testing
- Edge cases - Error scenarios, boundary conditions
- Performance testing - Response times, streaming behavior
- Security testing - Input validation, SQL injection attempts

### Test Organization:
- `backend/tests/` - Unit and integration tests
- `frontend/__tests__/` - Component tests
- `tests/e2e/` - End-to-end tests (Phase 7+)
- Focus on critical paths, not exhaustive coverage

---

## Documentation Requirements

**Strategy:** Comprehensive documentation alongside basic quick-start guides

### Basic Documentation (Quick Reference):

1. **README.md:**
   - Project overview and goals
   - Quick start guide (5-minute setup)
   - Local development setup
   - Basic architecture overview
   - Links to comprehensive docs

2. **QUICKSTART.md:**
   - Minimal setup steps
   - Essential commands
   - Common troubleshooting

### Comprehensive Documentation (Detailed Reference):

3. **docs/architecture.md:**
   - Detailed architecture diagrams
   - Component descriptions and interactions
   - Data flow diagrams
   - Technology choices rationale
   - Design decisions and trade-offs
   - Scalability considerations

4. **docs/deployment.md:**
   - AWS setup prerequisites
   - Terraform deployment steps (detailed)
   - Environment configuration (all options)
   - Troubleshooting guide (comprehensive)
   - Rollback procedures
   - Disaster recovery

5. **docs/api.md:**
   - Complete API reference
   - Request/response formats (with examples)
   - Authentication flow
   - Error handling (all error codes)
   - Rate limiting
   - WebSocket/SSE streaming details

6. **docs/development.md:**
   - Development workflow
   - Code structure explanation
   - Adding new tools guide
   - Testing guidelines
   - Contributing guidelines

7. **docs/operations.md:**
   - Monitoring and alerting setup
   - Log analysis guide
   - Performance tuning
   - Cost optimization tips
   - Security best practices

8. **docs/adr/** (Architecture Decision Records):
   - 001-use-langgraph.md
   - 002-use-docker-compose.md
   - 003-use-pinecone.md
   - 004-use-bedrock-nova.md
   - 005-use-rrf-for-rag.md
   - 006-public-subnets-for-demo.md (cost optimization)
   - 007-sqlalchemy-pooling-vs-rds-proxy.md (cost optimization)
   - 008-nextjs-static-export.md (architecture clarification)

9. **docs/runbooks/** (Operational Runbooks):
    - database-connection-issues.md
    - bedrock-rate-limits.md
    - docker-startup-slow.md
    - rag-quality-poor.md
    - cost-optimization.md

10. **docs/examples/** (Code Examples):
    - chat_api_example.py
    - tool_usage_example.py
    - streaming_example.py
    - error_handling_example.py

### Code Documentation:

9. **Code Comments:**
   - Comprehensive docstrings for all functions/classes
   - Inline comments for complex logic
   - Type hints (Python) and types (TypeScript)
   - API documentation strings (OpenAPI/Swagger)

### Documentation Standards:
- Markdown format for all docs
- Code examples in all relevant languages
- Diagrams using Mermaid or ASCII art
- Keep README concise, detailed info in docs/
- Update docs alongside code changes

---

## Risk Mitigation

1. **Cost Overruns:**
   - CloudWatch billing alarms
   - Cost tracking dashboard
   - Usage limits where possible

2. **Service Failures:**
   - **Health checks** (`/health` endpoint with dependency checks)
   - **Graceful error handling** with user-friendly messages
   - **Fallback mechanisms** for each tool (search, SQL, RAG, market data)
   - **Circuit breakers** to prevent cascade failures
   - **Retry logic** with exponential backoff
   - **Auto-restart** via App Runner health checks

3. **Security Issues:**
   - Regular security scanning
   - Input validation
   - Least privilege IAM

4. **Deployment Issues:**
   - Staged deployments (dev → prod)
   - Rollback procedures
   - Health checks before traffic

---

## Success Metrics

1. **Functionality:**
   - All tools working correctly
   - Streaming responses functional
   - Document ingestion automatic
   - Verification working

2. **Performance:**
   - Response time < 10s for typical queries
   - Cache hit rate > 30%
   - Uptime > 99%

3. **Cost:**
   - Monthly cost < $50
   - Cost per query < $0.10

4. **Quality:**
   - RAGAS scores > 0.8
   - User satisfaction (subjective)
   - Error rate < 1%

---

## Current Status

### ✅ Phase 0: Local Development Environment - COMPLETED

Fully working local development environment with:
- LangGraph agent with Bedrock (Nova Pro) and streaming responses
- ✅ Tavily search tool with mock fallback (Phase 2a completed ahead of schedule)
- ✅ FMP market data tool with mock fallback (Phase 2d completed ahead of schedule)
- SQL and RAG tools stubbed (real implementations in Phase 2b/2c)
- Docker Compose for all services with hot reload
- Password-protected web interface

### ✅ Phase 1a: AWS Cloud Deployment - COMPLETED (January 2, 2026)

Deployed to AWS with:
- App Runner backend with LangGraph agent and Bedrock integration
- CloudFront + S3 static frontend hosting
- Secrets Manager for secure credential storage
- Real-time streaming chat with Server-Sent Events
- Password-protected demo access
- Infrastructure as Code with Terraform
- Cost-optimized (~$10-25/month when active)

### ✅ Phase 1b: Production Hardening - COMPLETED (January 13, 2026)

Production-ready infrastructure with:
- Neon PostgreSQL integration for persistent state (free tier)
- PostgresSaver checkpointing for conversation persistence
- GitHub Actions CI/CD pipelines (CI on push/PR, CD manual trigger)
- Structured logging with structlog (CloudWatch-compatible JSON)
- Enhanced rate limiting (slowapi, 10 req/min per IP)
- API versioning (/api/v1/ routes)
- Database migrations ready (Alembic configured)
- Comprehensive health checks with dependency validation

### ✅ Phase 2a: Data Foundation & Basic Tools - COMPLETED (January 19, 2026)

Data foundation and core agent tools implemented:
- ✅ SQL Query Tool with real Neon PostgreSQL integration
  - Natural language to SQL conversion using Bedrock Claude
  - SQL injection prevention with query validation and table whitelisting
  - 10-K financial data loaded (7 companies, ~150 rows)
- ✅ RAG Retrieval Tool with real Pinecone integration
  - VLM document extraction using Claude Vision
  - Parent/child chunking (1024/256 tokens)
  - Contextual enrichment prepending metadata
  - Semantic search with deduplication
  - ~352 vectors indexed (NVIDIA 10-K + 2 reference docs)
- ✅ Document Processing Pipeline
  - VLM extraction with `extract_and_index.py` batch script
  - Semantic chunking with spaCy (section-aware)
  - BedrockEmbeddings with Titan v2 (1024d)
  - Pinecone indexing with parent/child architecture
- ✅ Agent Integration
  - All 4 tools registered (tavily_search, sql_query, rag_retrieval, market_data)
  - Improved tool descriptions for better tool selection
  - Graceful fallback to Tavily when RAG has no documents
- ✅ Health Check Enhancement
  - Pinecone status with vector count included

### ✅ Phase 2b: Intelligence Layer - COMPLETED (January 20, 2026)

Advanced RAG with hybrid search and knowledge graph:
- ✅ Knowledge Graph with Neo4j AuraDB
  - spaCy NER for cost-efficient entity extraction
  - Entity types: Organization, Person, Location, Concept, etc.
  - MENTIONS relationships with page-level tracking
  - 1-hop and 2-hop graph traversal queries
- ✅ Hybrid Search Pipeline (HybridRetriever)
  - Dense vectors (Titan v2 1024d) + BM25 sparse vectors
  - Query expansion via Nova Lite (3 variants, +20-30% recall)
  - RRF (Reciprocal Rank Fusion) for multi-source merging
  - KG boost with page-level precision
  - Cross-encoder reranking (+20-25% precision)
  - Contextual compression for focused context
- ✅ Multi-tool Orchestration
  - SQL + RAG combined queries
  - Optimized system prompt with complexity detection
  - Citation format guidance
- ✅ AWS Secrets Configuration
  - Pinecone API key and index name in Secrets Manager
  - Neo4j URI, user, password in Secrets Manager
  - App Runner deployment with new secrets
- ✅ Production Verification
  - Pinecone health check: 781 vectors indexed
  - HybridRetriever with graceful degradation (hybrid=True default)

---

## Next Steps

**All Configuration Decisions Confirmed:**
- ✅ AWS Region: us-east-1 (N. Virginia - closest to Austin, TX)
- ✅ Domain: CloudFront URL (frontend) + App Runner URL (backend API)
- ✅ Testing: Balanced approach
- ✅ Sample Data: 10-K financial metrics (VLM extracted, not synthetic)
- ✅ Documentation: Comprehensive + basic
- ✅ Docker: Optimized Compose (5-10s startup)
- ✅ LangGraph: Checkpointing (MemorySaver dev, PostgresSaver prod) + native streaming
- ✅ RAG: Query expansion + RRF + contextual compression
- ✅ Security: SQL injection prevention + rate limiting + input validation
- ✅ Observability: Structured logging + comprehensive metrics
- ✅ Error Handling: Fallbacks + circuit breakers + graceful degradation
- ✅ **Cost Optimization:** Public subnets (skip VPC endpoints), SQLAlchemy pooling (skip RDS Proxy)
- ✅ **Frontend:** Next.js static export (no server), native SSE client
- ✅ **Model Fallback:** Nova Pro → Claude Sonnet 4.5 (with Claude 3.5 Sonnet V2 as deprecated fallback)
- ✅ **Cold Start UX:** Loading indicator for 10-30s cold starts
- ✅ **API Versioning:** /api/v1/ for future compatibility
- ✅ **Database Migrations:** Alembic for schema management

**Phase 2: Core Agent Tools - COMPLETED**

All Phase 2 components are now production-ready:
- ✅ `docs/completed-phases/PHASE_2A_HOW_TO_GUIDE.md` - Data Foundation (VLM extraction, SQL tool, basic RAG)
- ✅ `docs/completed-phases/PHASE_2B_HOW_TO_GUIDE.md` - Intelligence Layer (Knowledge Graph, hybrid retrieval, multi-tool orchestration)

Phase 2 component status:
- ✅ **2a. Tavily Search Tool** - Completed in Phase 0
- ✅ **2b. SQL Query Tool** - Completed in Phase 2a (January 19, 2026)
- ✅ **2c. RAG Document Tool** - Completed in Phase 2a (January 19, 2026)
- ✅ **2d. Market Data Tool** - Completed in Phase 0
- ✅ **Knowledge Graph** - Completed in Phase 2b (January 20, 2026)
- ✅ **Hybrid Search** - Completed in Phase 2b (BM25 + dense embeddings + RRF fusion)
- ✅ **Cross-encoder Reranking** - Completed in Phase 2b (Nova Lite)

**Ready for Phase 3: Observability with Arize Phoenix**

**Pre-Phase 0 Checklist (Completed):**
- [x] Docker Desktop installed and running
- [x] Python 3.11+ installed
- [x] AWS CLI v2 installed and configured (`aws configure`)
- [x] Bedrock model access approved (check in console)
- [x] Pinecone account created, index created, API key copied
- [x] Tavily account created, API key copied
- [x] FMP account created, API key copied (optional; mock mode without key)
- [x] Git installed

1. **Set up local development environment:**
   - Clone/initialize repository
   - Copy `.env.example` to `.env`
   - Fill in API keys (Tavily, Pinecone, FMP, AWS)
   - Run `./scripts/setup.sh` to validate prerequisites
   - Run `docker-compose up` to start services

2. **Initialize project structure:**
   - Create directory structure per project layout
   - Set up basic configuration files
   - Initialize Git repository
   - Create initial README.md

3. **Create basic LangGraph agent:**
   - Set up LangGraph graph structure
   - Integrate Bedrock Nova (test model access first!)
   - Implement streaming response handler
   - Add basic chat node
   - **Test fallback:** Verify Claude fallback works if Nova fails

4. **Build streaming chat UI:**
   - Set up Next.js with shadcn/ui
   - Create chat interface component
   - Implement SSE streaming connection (native EventSource)
   - Add password protection UI
   - Add cold start loading indicator

5. **Test locally:**
   - Verify agent responds correctly
   - Test streaming functionality
   - Validate UI interactions
   - Test each tool type
   - Run initial test suite

**Then proceed to Phase 1a (AWS Deployment - Minimal MVP):**

**Terraform State Setup (One-Time, Before First Deploy):**
```bash
# Create S3 bucket for Terraform state
aws s3 mb s3://your-project-terraform-state --region us-east-1

# Create DynamoDB table for state locking
aws dynamodb create-table \
  --table-name terraform-state-lock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1

# Update terraform/environments/dev/backend.tf with bucket name
```

**GitHub Actions Secrets (Required for Phase 1b CI/CD):**
- `AWS_ACCESS_KEY_ID` - IAM user access key
- `AWS_SECRET_ACCESS_KEY` - IAM user secret key
- `AWS_REGION` - us-east-1
- `TAVILY_API_KEY` - For web search tool (Phase 2)
- `PINECONE_API_KEY` - For vector store (Phase 2)
- `PINECONE_INDEX_NAME` - demo-index (Phase 2)
- `FMP_API_KEY` - For market data tool (FMP via MCP; mock mode without key)
- **Note:** `DEMO_PASSWORD` is stored in Secrets Manager, not GitHub (Lambda reads from Secrets Manager)

**Phase 1a Deployment Order (Minimal MVP):**

**Pre-Deployment Testing (Do This First):**
```bash
# 1. Test Docker image locally
docker build -t backend:test -f backend/Dockerfile .
docker run -p 8000:8000 --env-file .env backend:test
# In another terminal:
curl http://localhost:8000/health  # Should return {"status": "ok"}

# 2. Test frontend build locally
cd frontend
npm run build
# Verify out/ folder exists with HTML files

# 3. Verify environment variables
python scripts/validate_setup.py --env=aws
# Should pass all checks
```

**Deployment Steps (with Verification):**

1. **Terraform State Setup (One-Time):**
   ```bash
   # Create S3 bucket for state
   aws s3 mb s3://your-project-terraform-state --region us-east-1
   
   # Create DynamoDB table for locking
   aws dynamodb create-table \
     --table-name terraform-state-lock \
     --attribute-definitions AttributeName=LockID,AttributeType=S \
     --key-schema AttributeName=LockID,KeyType=HASH \
     --billing-mode PAY_PER_REQUEST \
     --region us-east-1
   
   # Update terraform/environments/dev/backend.tf with bucket name
   ```
   ✅ **Verify:** Bucket and table exist in AWS Console

2. **Initialize Terraform:**
   ```bash
   cd terraform/environments/dev/
   terraform init
   ```
   ✅ **Verify:** No errors, `.terraform/` folder created

3. **Deploy Networking:**
   ```bash
   terraform apply -target=module.networking
   ```
   ✅ **Verify:** 
   - VPC exists in console
   - Two public subnets exist
   - Note subnet IDs for next steps

4. **Deploy ECR:**
   ```bash
   terraform apply -target=module.ecr
   ```
   ✅ **Verify:** ECR repository exists in console

5. **Build & Push Docker Image:**
   ```bash
   # Get ECR login token
   aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com
   
   # Build image
   docker build -t backend:latest -f backend/Dockerfile .
   
   # Tag for ECR
   docker tag backend:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/backend:latest
   
   # Push to ECR
   docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/backend:latest
   ```
   ✅ **Verify:** 
   - Image appears in ECR console
   - Image tag matches expected version

6. **Deploy App Runner:**
   ```bash
   terraform apply -target=module.app_runner
   ```
   ✅ **Verify:** 
   - Service status = "Running" in console
   - Health endpoint: `curl https://<app-runner-url>/health` returns `{"status": "ok"}`
   - Chat endpoint: `curl https://<app-runner-url>/api/chat` returns 401 (expected without auth)

7. **Build & Upload Frontend:**
   ```bash
   cd frontend
   npm run build
   # Verify out/ folder contains HTML files
   
   # Upload to S3 (get bucket name from Terraform output)
   aws s3 sync out/ s3://<frontend-bucket-name>/ --delete
   ```
   ✅ **Verify:** 
   - Files appear in S3 bucket
   - Correct permissions (public read for static files)

8. **Deploy CloudFront:**
   ```bash
   terraform apply -target=module.s3_cloudfront
   ```
   ✅ **Verify:** 
   - Distribution status = "Deployed" (may take 5-10 minutes)
   - Access CloudFront URL (should show login page)

9. **End-to-End Test:**
   - Access CloudFront URL
   - Login with password (from Secrets Manager)
   - Send test message: "Hello, how are you?"
   - Verify streaming response appears
   - Check browser console for errors
   - Check App Runner logs: `aws logs tail /aws/apprunner/<service-name> --follow`

**Rollback Procedures (If Deployment Fails):**

If any step fails:
```bash
# Rollback specific module
terraform destroy -target=module.app_runner
terraform destroy -target=module.s3_cloudfront
# Then retry from failed step

# Full rollback (start over)
terraform destroy  # Destroys all resources
# Then start fresh from step 1
```

**Phase 1b Deployment Order (Production Hardening):**

1. **Set up Neon database:**
   - Create Neon account at neon.tech (free tier)
   - Create project in us-east-1 region
   - Store connection string in AWS Secrets Manager
   ✅ **Verify:**
   - Neon project created
   - Test connection: `psql <neon_connection_string>`

2. **Update Terraform for DATABASE_URL:**
   ```bash
   terraform apply
   ```
   ✅ **Verify:** App Runner has DATABASE_URL environment variable
   - Run migrations: `alembic upgrade head`
   - App Runner can reach Neon (check logs)

3. **Set up GitHub Actions CI/CD:**
   - Add secrets to GitHub repository
   - Push code to trigger workflow
   - Verify deployment succeeds

---

## Configuration Decisions

**Confirmed Settings:**
1. **AWS Region:** us-east-1 (N. Virginia - closest to Austin, TX)
   - Good service availability
   - East Coast location (closest to Austin, TX)
   - Cost-effective

2. **Domain:** App Runner generated URL
   - Format: `https://xxxxx.us-east-1.awsapprunner.com`
   - No custom domain setup required
   - HTTPS included automatically

3. **Testing:** Balanced approach
   - Best practices with minimal overhead
   - Unit tests for core logic (70%+ coverage on critical paths)
   - Integration tests for key flows
   - Manual testing for UI/UX
   - Focus on critical paths, not exhaustive coverage

4. **Sample Data:** 10-K Financial Metrics (VLM Extracted)
   - Companies table (ticker, name, sector, fiscal_year_end, filing_date)
   - Financial_metrics table (revenue, net_income, margins, EPS by year)
   - Segment_revenue table (business segment breakdown)
   - Geographic_revenue table (regional revenue breakdown)
   - Risk_factors table (categorized risks from Item 1A)
   - Realistic financial queries: revenue comparisons, margin analysis, risk identification

5. **Documentation:** Comprehensive alongside basic
   - Basic: README.md + QUICKSTART.md (quick reference)
   - Comprehensive: Full docs/ folder with architecture, deployment, API, operations, troubleshooting
   - Code: Comprehensive docstrings and type hints

---

## Conclusion

This plan provides a comprehensive roadmap for building an enterprise-grade agentic AI demo system. The phased approach allows for incremental development and validation, starting locally and progressing to a fully deployed AWS solution.

The architecture is designed to be:
- **Scalable:** Can handle increased load
- **Cost-effective:** Optimized for low-use demo ($20-50/month with advanced optimizations)
- **Maintainable:** Clean code structure, comprehensive documentation
- **Enterprise-ready:** Security, monitoring, observability built-in
- **Portfolio-worthy:** Demonstrates modern AI/ML best practices
- **Developer-friendly:** Fast Docker startup (5-10s), hot reload, dev scripts

## Key Improvements Integrated (December 2025 SOTA)

### Performance Optimizations
- ✅ Docker Compose startup: **5-10 seconds** (down from 30-60s)
- ✅ RAG quality: **+30% improvement** with query expansion + RRF
- ✅ Cost optimization: **10-20% savings** with S3 Intelligent-Tiering, RDS Proxy

### Architecture Enhancements
- ✅ LangGraph checkpointing with Postgres (state persistence)
- ✅ Error recovery nodes for graceful failure handling
- ✅ Circuit breakers for external service calls
- ✅ Fallback mechanisms for all tools

### Security Hardening
- ✅ SQL injection prevention (parameterized queries, table whitelisting)
- ✅ Rate limiting (10 req/min per IP)
- ✅ Input validation (Pydantic validators)
- ✅ CORS properly configured

### Observability
- ✅ Structured logging (structlog with JSON)
- ✅ Comprehensive metrics (tokens, latency, costs, errors)
- ✅ Health checks with dependency validation
- ✅ LangGraph native callbacks

### Development Experience
- ✅ Dev scripts (`scripts/dev.sh`) for common tasks
- ✅ Pre-commit hooks (black, ruff, mypy, tests)
- ✅ VS Code dev containers (optional)
- ✅ Hot reload optimization

### Cost-Conscious Decisions for Demo
- ✅ **Public subnets** instead of VPC endpoints: **Save $20-30/month**
- ✅ **SQLAlchemy pooling** instead of RDS Proxy: **Save $15-20/month**
- ✅ **Next.js static export** (no server costs)
- ✅ **Skip NAT Gateway** (not needed with public subnets)
- ✅ **Total demo cost: $20-50/month** (down from $40-80 with full VPC)

**Trade-offs for Demo:**
- Less secure network (public subnets) - acceptable for portfolio demo
- Can upgrade to VPC endpoints + RDS Proxy later for production
- All upgrade paths documented in ADRs

---

## Expert Review Fixes Applied

**All critical issues from expert review have been addressed:**

1. ✅ **Frontend Architecture:** Clarified - Next.js static export → S3, API calls App Runner
2. ✅ **Docker Prerequisites:** Fixed - Docker Desktop required for all services
3. ✅ **Cold Start UX:** Added loading indicator for 10-30s cold starts
4. ✅ **Bedrock Nova:** Added fallback to Claude Sonnet 4.5 (with Claude 3.5 Sonnet V2 as deprecated fallback)
5. ✅ **Database Migrations:** Added Alembic for schema management
6. ✅ **LangGraph Checkpointing:** MemorySaver for dev, PostgresSaver for prod
7. ✅ **Pinecone Hybrid:** Clarified implementation strategy
8. ✅ **API Versioning:** Added /api/v1/ structure
9. ✅ **Dependency Injection:** Added container pattern
10. ✅ **Cost Estimates:** Updated with realistic costs + cheaper alternatives
11. ✅ **Auth Abstraction:** Designed for future Cognito migration
12. ✅ **Conversation Persistence:** Moved to Phase 1
13. ✅ **Version Pinning:** Added to requirements.txt
14. ✅ **User-Friendly Errors:** Added error handler middleware
15. ✅ **Model Compatibility:** Added fallback and testing strategy

---

## Demo Presentation Guide

### Reference Demo Plan (5 minutes)
#All updates must be consistent with this experience.
**1. Introduction (30 seconds):**
> "This is an enterprise-grade AI agent I built on AWS. It demonstrates multi-tool orchestration, RAG, real-time streaming, and cost-optimized architecture."

**2. Basic Chat (1 minute):**
- Ask a simple question
- Point out streaming responses
- Show thought process panel (if implemented)

**3. Tool Demonstration (2 minutes):**
- Web search: "Search for recent news about AI regulations"
- SQL query: "What's the total balance for customer John Doe?"
- RAG: "What does our company policy say about data retention?"

**4. Architecture Overview (1 minute):**
- Show architecture diagram
- Highlight: LangGraph, Bedrock, Pinecone, Neon, App Runner
- Mention: Cost optimization, security, observability

**5. Q&A Preparation:**
- "How does the RAG work?" → Query expansion, hybrid search, RRF
- "What's the monthly cost?" → $20-50/month for demo
- "How would you scale this?" → VPC endpoints, RDS Proxy, more instances

### Pre-Demo Checklist
- [ ] Warm up service 5 minutes before (visit health endpoint)
- [ ] Test each tool type once
- [ ] Clear conversation history (fresh start)
- [ ] Have backup screenshots ready
- [ ] Know fallback talking points if something breaks

### Demo Troubleshooting
| Issue | Cause | Solution |
|-------|-------|----------|
| Site doesn't load | Cold start | Wait 30 seconds, show architecture while waiting |
| Chat hangs | Bedrock rate limit | Wait 10 seconds, retry with simpler query |
| Tool fails | Circuit breaker | Explain graceful degradation, try different query |
| Streaming stops | SSE timeout | Refresh page, explain timeout handling |

---

## Future Improvements: HybridRetriever Production Readiness

The following potential issues were identified during code review of the `HybridRetriever` module. These are **not blockers** for the demo but should be addressed before scaling to production.

| Issue | Severity (Demo) | Severity (Production) | Description |
|-------|-----------------|----------------------|-------------|
| **No Overall Pipeline Timeout** | HIGH | HIGH | `retrieve()` method has no overall timeout. Individual components may each be within limits, but combined could exceed API gateway timeouts (30s). |
| **Neo4j Blocking Event Loop** | LOW | HIGH | `_kg_search()` uses synchronous Neo4j calls. Fine for single-user demo, blocks other requests under load. |
| **spaCy Cold Start Latency** | MEDIUM | MEDIUM | `EntityExtractor` lazy-loads spaCy model on first use, adding 1-2s to first query. Pre-load in `__init__` or startup event. |
| **No Pinecone Hybrid Index Validation** | MEDIUM | MEDIUM | BM25 search assumes Pinecone is configured with sparse vector support. No validation on startup - silent degradation if not configured. |
| **Duplicate Embedding API Calls** | LOW | LOW | Parallel variant searches may call `embed_text()` concurrently before cache is populated. Minor cost inefficiency. |

**Recommended Fixes (When Scaling):**

1. **Pipeline Timeout:** Add `asyncio.timeout(30.0)` wrapper around `retrieve()` method
2. **Neo4j Async:** Wrap sync calls with `asyncio.to_thread()` or migrate to async Neo4j driver
3. **spaCy Pre-load:** Call `_ = self._extractor.nlp` in `HybridRetriever.__init__()` to pre-warm
4. **Hybrid Index Check:** Add startup validation that tests sparse vector query
5. **Embedding Pre-compute:** Pre-embed all unique variants before parallel search

**For Demo:** Focus on #1 (timeout) and #3 (cold start) if any issues arise. Others can wait until multi-user production.

---

Ready to begin Phase 0 when you are!
