# Enterprise Agentic AI Demo - Complete Project Plan

## Executive Summary

This project builds an enterprise-grade agentic AI system on AWS demonstrating:
- Multi-tool agent orchestration (Search, SQL, RAG)
- Input/output verification with SLMs
- Streaming thought process visualization
- Inference caching for cost optimization
- Full observability with Arize Phoenix
- RAG evaluation with RAGAS
- Automated document ingestion from S3
- Password-protected web interface
- Infrastructure as Code with Terraform
- CI/CD with GitHub Actions

**Target Cost:** Under $50/month for low-use portfolio demo
**Architecture:** Scalable, enterprise-ready, cost-optimized
**AWS Region:** us-east-2 (Ohio - Central US)
**Domain:** App Runner generated URL (no custom domain)

---

## Architecture Overview

```
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
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    LangGraph Agent Orchestrator                  │   │
│  │    ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐      │   │
│  │    │ Bedrock  │  │  Input/  │  │ Inference│  │  Arize   │      │   │
│  │    │   Nova   │  │  Output  │  │   Cache  │  │ Tracing  │      │   │
│  │    │  (Main)  │  │  Verify  │  │(DynamoDB)│  │          │      │   │
│  │    └──────────┘  └──────────┘  └──────────┘  └──────────┘      │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────  TOOLS  ───────────────────────────────────┐   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐                 │   │
│  │  │   Tavily   │  │    SQL     │  │    RAG     │                 │   │
│  │  │   Search   │  │   Query    │  │  Retrieval │                 │   │
│  │  │            │  │  (Aurora)  │  │ (Pinecone) │                 │   │
│  │  └────────────┘  └────────────┘  └────────────┘                 │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
          ┌─────────────────────────┼─────────────────────────┐
          ▼                         ▼                         ▼
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│  Aurora Serverless│    │     Pinecone     │    │   S3 Document    │
│   v2 PostgreSQL  │    │    Serverless    │    │     Bucket       │
│   (SQL Data)     │    │  (Vector Store)  │    │  (File Upload)   │
└──────────────────┘    └──────────────────┘    └──────────────────┘
                                                         │
                                                         ▼
                                               ┌──────────────────┐
                                               │  Lambda Trigger  │
                                               │  (Auto-Ingest)   │
                                               └──────────────────┘
```

---

## Technology Stack

| Component | Technology | Cost Optimization | Rationale |
|-----------|------------|-------------------|-----------|
| **LLM (Main)** | AWS Bedrock - Amazon Nova Pro | Pay-per-token, no idle cost | Latest AWS model, cost-effective |
| **LLM (Verification)** | AWS Bedrock - Amazon Nova Lite | Smaller model, cheaper | Sufficient for guardrails |
| **Agent Framework** | LangGraph | Open source | Industry standard, excellent streaming |
| **Vector Store** | Pinecone Serverless | Free tier (100K vectors) | Fully managed, better than pgvector |
| **SQL Database** | Aurora Serverless v2 PostgreSQL | Scales to 0.5 ACU minimum | Enterprise-grade, cost-optimized |
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
│  │  PostgreSQL: Docker container                    │  │
│  └───────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Chroma: Local vector store (Docker)             │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
                    Bedrock API (AWS)
```

**Development Workflow (Docker Compose with Hot Reload):**
1. `./scripts/setup.sh` - One-time setup (validates Docker, creates .env)
2. `docker-compose up` - Start everything (backend, frontend, postgres)
3. Code changes reflect automatically (~2-3 seconds hot reload via volume mounts)
4. `docker-compose logs -f` - View logs from all services
5. `docker-compose down` - Stop everything cleanly

**Hot Reload Configuration:**
- Backend: Volume mount `./backend:/app` + `uvicorn --reload`
- Frontend: Volume mount `./frontend:/app` + `npm run dev`
- Changes detected automatically, no manual rebuild needed
- Reload time: ~2-3 seconds (acceptable for consistency benefit)

**Local Service Substitutes (All in Docker Compose):**
| AWS Service | Local Dev | Container |
|-------------|-----------|-----------|
| Aurora PostgreSQL | Docker PostgreSQL | `postgres:15` |
| Pinecone | Chroma (embedded) | `chromadb/chroma` |
| S3 file upload | Local `./uploads` folder | Volume mount |
| DynamoDB cache | In-memory dict or SQLite | Python in-memory |
| Secrets Manager | `.env` file | Environment variables |
| Bedrock Nova | Bedrock API (still AWS) | External API call |

**Docker Compose Services:**
- `backend`: FastAPI app with hot reload
- `frontend`: Next.js app with hot reload
- `postgres`: PostgreSQL database
- `chroma`: Vector store (optional, can use Pinecone free tier)

**Phase 0 Deliverables:**
- Working LangGraph agent with streaming responses
- **LangGraph checkpointing:**
  - **Development:** MemorySaver (no DB dependency, faster)
  - **Production:** PostgresSaver with Aurora (state persistence)
  - Connection pooling via SQLAlchemy (no RDS Proxy needed for demo)
- **Error recovery nodes** for graceful failure handling
- **Built-in tool calling** via LangGraph tool binding (with Bedrock compatibility check)
- **Model fallback:** Nova Pro → Claude 3.5 Sonnet if Nova unavailable
- Chat UI with real-time streaming
- Basic conversation flow validated
- All tools working with local substitutes
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
   - Also request: Anthropic Claude 3.5 Sonnet (fallback)
   - Wait for approval (usually instant, can take 1-24 hours)
   - **Common Issue:** Forgetting this step causes "AccessDeniedException"

2. **Service Quotas (verify defaults are sufficient):**
   - App Runner services: 10 (default, sufficient)
   - Aurora DB clusters: 40 (default, sufficient)
   - ECR repositories: 10,000 (default, sufficient)

3. **IAM Permissions (for deployment):**
   - Admin access recommended for initial setup
   - Or custom policy with: AppRunner, RDS, S3, CloudFront, ECR, Lambda, DynamoDB, SecretsManager, CloudWatch, IAM

**External Service Setup (Before Phase 0):**
1. **Pinecone (free tier):**
   - Create account at https://pinecone.io
   - Create index: name=`demo-index`, dimensions=1536, metric=cosine
   - Region: **AWS us-east-2** (same as rest of stack). If us-east-2 temporarily unavailable, use us-east-1 and expect +10‑20 ms latency plus minimal data-transfer charges.
   - Copy API key to `.env`

2. **Tavily (free tier):**
   - Create account at https://tavily.com
   - Get API key from dashboard
   - Free tier: 1,000 searches/month (sufficient for demo)
   - Copy API key to `.env`

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
- **Cold start testing:** Verify warmup endpoint works

**Common Issues (Phase 0)**
| Symptom | Root Cause | Fix |
|---------|------------|-----|
| `AccessDeniedException` from Bedrock | Model access not approved | Re-run Bedrock model access request for Nova Pro/Lite + Titan Embeddings + Claude fallback |
| `docker-compose up` fails with permissions error | Docker Desktop not running or user not in docker group | Start Docker Desktop / run `sudo usermod -aG docker $USER` then re-login |
| Pinecone 401 on startup | Missing API key in `.env` | Add `PINECONE_API_KEY` and restart backend |
| Tavily tool fails immediately | Free-tier rate limit hit | Wait 60s, set `TAVILY_API_KEY` correctly, or upgrade plan |
| Terraform state lock message | Previous `terraform apply` exited abruptly | Delete lock entry from DynamoDB table `terraform-state-lock` using AWS Console |

---

### Phase 1a: Minimal MVP - Basic Chat Interface
**Goal:** Deployed chatbot accessible via password-protected website with streaming responses (simplified for easy debugging)

**Why Split Phase 1:** Phase 1a focuses on getting a working demo quickly with minimal complexity. Phase 1b adds production hardening. This makes debugging much easier - if something breaks, fewer moving parts to check.

**Features (Minimal Set):**
- **Next.js Static Export** frontend with shadcn/ui chat interface
  - Deployed to S3 + CloudFront (no Next.js server)
  - Uses native EventSource for SSE (no Vercel AI SDK dependency)
  - Calls App Runner API directly via CORS
- Simple password protection (shared password via Secrets Manager)
- App Runner backend with basic LangGraph agent
- **LangGraph checkpointing:**
  - **MemorySaver only** (no Aurora yet - simplifies deployment)
  - Conversation state stored in memory (lost on restart, acceptable for MVP)
  - Upgrade to PostgresSaver in Phase 1b
- **LangGraph native streaming** with proper event handling
- Bedrock Nova integration with fallback:
  - Primary: `amazon.nova-pro-v1:0` (verify availability in us-east-2)
  - Fallback: `anthropic.claude-3-5-sonnet-20241022-v2:0` (more stable, proven)
- Server-Sent Events (SSE) streaming from FastAPI to frontend
- **Cold start UX:** Loading indicator with "Warming up..." message (10-30s estimate)
- **Conversation persistence:** conversation_id in localStorage (state in MemorySaver)
- **Basic Terraform infrastructure** (networking, App Runner, S3, CloudFront, Secrets Manager, ECR)
- **Manual deployment** (no CI/CD yet - deploy via `terraform apply` and manual S3 upload)
- **Basic error handling** (try/catch with user-friendly messages)
- **Basic logging** (print statements + CloudWatch Logs)
- **Health check endpoint** (`/health`) - simple version (no dependency checks yet)
- **Input validation** with Pydantic models (basic)
- **No API versioning yet** (use `/api/chat` - add versioning in Phase 1b)
- **No database migrations** (no Aurora yet)

**Infrastructure (Terraform) - Minimal:**
- **Networking:** VPC with two public subnets
- App Runner service (no VPC connector yet - uses public internet)
- S3 bucket for frontend static files
- CloudFront distribution
- Secrets Manager for password
- ECR repository
- CloudWatch Logs
- **No Aurora yet** (saves cost, simplifies deployment)

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
- **PostgresSaver checkpointing** with Aurora Serverless v2:
  - Provision Aurora in public subnets (same VPC as Phase 1a)
  - Add App Runner VPC connector for secure Aurora access
  - Migrate from MemorySaver to PostgresSaver
  - Connection pooling via SQLAlchemy
- **Database migrations:** Alembic for schema versioning
- **GitHub Actions CI/CD:** Automated build, test, deploy
- **Structured logging:** structlog with JSON output
- **Comprehensive error handling:** Graceful degradation, retry logic
- **Health check endpoint:** Enhanced with dependency checks (Aurora, Bedrock)
- **Warmup endpoint:** `/health/warmup` - triggers service initialization
- **Warmup Lambda:** CloudWatch Events → Lambda health check every 5 min
- **Rate limiting:** slowapi middleware (10 req/min per IP)
- **API versioning:** `/api/v1/chat` (allows future `/api/v2/chat`)
- **User-friendly error messages:** Map technical errors to friendly messages

**Infrastructure Additions:**
- Aurora Serverless v2 cluster (0.5 ACU minimum)
- App Runner VPC connector (for Aurora access)
- Lambda function for warmup (EventBridge schedule)
- Enhanced security groups (Aurora ingress from connector only)

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
  - Aurora Serverless v2, ECS/Fargate (later phases), and EFS mount targets all live in these public subnets but are locked down via security groups.
  - App Runner connects through a **VPC Connector** that targets the same public subnets. This avoids VPC endpoint costs while still giving App Runner a private path to Aurora, DynamoDB, etc.
  - Aurora must be created with `publicly_accessible = true`; restrict inbound traffic to the security group that App Runner’s VPC connector ENIs use (no 0.0.0.0/0).
  - Document the upgrade path: add private subnets + VPC endpoints later for production hardening.
- App Runner service with auto-scaling:
  - **Minimum instances: 0** (scales to zero when idle, saves cost)
  - Maximum instances: 10 (auto-scales on demand)
  - **Cold start: 10-30 seconds** (acceptable for portfolio demo)
  - **Keep-alive Lambda (details below):** CloudWatch Events → Lambda health check every 5 min
    - Cost: ~$0.50/month (free tier covers it)
    - Reduces cold starts by warming instance periodically
  - **Request timeout:** Set `instance_configuration.connection_drain_timeout` to 900 seconds so SSE streams are not dropped during long toolchains.
- S3 bucket for frontend static files (us-east-2)
- CloudFront distribution with HTTPS
- Secrets Manager for password (us-east-2)
- IAM roles and policies (least privilege)
- ECR repository for container images (us-east-2)
- CloudWatch Logs for monitoring (us-east-2)

**Keep-alive Lambda Details:**
- Purpose: hit the `/health/warmup` endpoint every 5 minutes to keep App Runner container warm.
- Implementation:
  ```python
  # lambda/warm_app_runner/handler.py
  import os, urllib.request

  APP_RUNNER_URL = os.environ["APP_RUNNER_URL"]

  def handler(event, context):
      req = urllib.request.Request(f"{APP_RUNNER_URL}/health/warmup", method="GET")
      req.add_header("Authorization", f"Bearer {os.environ['DEMO_PASSWORD']}")
      urllib.request.urlopen(req, timeout=10)
      return {"status": "ok"}
  ```
- Terraform: create a Lambda with the above handler, schedule it via EventBridge rule (`rate(5 minutes)`), and inject `APP_RUNNER_URL` + `DEMO_PASSWORD` as env vars (retrieved from Secrets Manager).

**Security (Public-Subnet Demo Mode):**
- HTTPS only (CloudFront)
- Password stored in Secrets Manager (encrypted)
- IAM roles with minimal permissions
- Aurora security group only allows ingress from App Runner VPC connector ENIs
- ECS/EFS (Phase 5) security groups scoped to VPC connector CIDR blocks
- **Rate limiting** (slowapi middleware, 10 req/min per IP)
- **SQL injection prevention** (parameterized queries, table whitelisting)
- **Input validation** (Pydantic validators, message length limits)
- **CORS** properly configured (specific origins, methods, headers)
- **SQL tool safety:** Read-only connections, result limits, query validation

**Deliverables:**
- Working chat interface at CloudFront URL (e.g., `https://xxxxx.cloudfront.net`)
  - Frontend: S3 + CloudFront (static Next.js export)
  - Backend API: App Runner URL (e.g., `https://xxxxx.us-east-2.awsapprunner.com`)
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
| App Runner cannot reach Aurora (`could not connect to server`) | Aurora SG not allowing App Runner VPC connector ENIs | Add inbound rule: source = connector security group; ensure Aurora `publicly_accessible=true` |
| Warmup Lambda fails with 401 | Missing password header | Pass `Authorization: Bearer <password>` or store password in Secrets Manager and inject into Lambda env vars |
| Terraform apply fails on App Runner VPC connector | Subnets not tagged or already in use | Ensure two public subnets exist and pass IDs to connector module |
| Alembic migration fails | Database connection string incorrect | Verify `DATABASE_URL` in App Runner environment variables matches Aurora endpoint |
| GitHub Actions deploy fails | Missing secrets or IAM permissions | Verify all secrets are set and IAM user has required permissions |

---

### Phase 2: Core Agent Tools
**Goal:** Agent can search the web, query SQL databases, and retrieve from documents

**Features:**

**2a. Tavily Search Tool**
- Tavily API integration
- Tool definition in LangGraph (using built-in tool binding)
- Result formatting and citation
- **Comprehensive error handling** with retry logic and exponential backoff
- **Fallback mechanisms:** Graceful degradation if Tavily unavailable
- **Circuit breaker pattern:** Stop trying after 5 failures, recover after 60s
- Rate limiting (respect API limits)
- **Structured logging** of search queries and results

**2b. SQL Query Tool**
- **Uses existing Aurora** from Phase 1b (no new provisioning needed)
- **Connection Pooling:** SQLAlchemy built-in (skip RDS Proxy for demo cost savings)
- Sample database with financial demo data (transactions, accounts, customers, portfolios)
- Natural language to SQL via LLM
- Query execution with result limits/safety (max rows, read-only)
- **SQL Injection Prevention (Critical):**
  - Parameterized queries only (SQLAlchemy `text()` with parameters)
  - Table/column whitelisting (ALLOWED_TABLES set)
  - Never use string formatting for SQL
  - Query validation before execution
- Query explanation/justification
- **Error handling:** Graceful failures with helpful error messages
- **Circuit breaker:** Prevent repeated failures from overwhelming database

**2c. RAG Document Tool (Advanced Hybrid Search + SOTA Techniques)**
- Pinecone serverless index with **Hybrid Search Strategy:**
  - **Option 1 (If Pinecone Serverless supports native hybrid):**
    - Use Pinecone's built-in hybrid search (sparse + dense)
    - Generate sparse vectors using BM25 or TF-IDF
  - **Option 2 (If native hybrid not available):**
    - Dense vectors: Bedrock Titan Embeddings
    - Sparse vectors: Store as metadata, use metadata filtering
    - Combine dense search + metadata filtering with RRF
  - **Implementation:** Start with Option 2 (more reliable), test Option 1
- Document embedding pipeline (Bedrock Titan Embeddings for dense vectors)
- Keyword extraction for sparse vectors (BM25-style using `rank-bm25` library)
- S3 bucket for document uploads
- Lambda trigger for automatic ingestion on upload
- **Advanced Chunking Strategy:**
  - **Parent Document Retriever:** Small chunks (200 chars) for retrieval, parent docs (1000 chars) for context
  - Recursive character splitter with 200 char overlap
  - Preserve metadata (source, page, section, document_type, parent_id)
- **Query Expansion (Critical for Quality):**
  - Generate 3 alternative phrasings using LLM
  - Multi-query retrieval with parallel searches
  - Improves recall by 20-30%
- **Hybrid Retrieval Method:**
  - Vector search (semantic similarity via dense embeddings)
  - Keyword search (exact matches, synonyms via sparse vectors)
  - Pinecone handles hybrid search natively OR combine with RRF
- **RRF (Reciprocal Rank Fusion)** for combining multiple retrieval results
- **Contextual Compression:** LLMChainExtractor to reduce noise in retrieved docs
- **Re-ranking option** (cross-encoder for top results - Phase 6 enhancement)
- Retrieval tool with relevance scoring and explanation
- Source citation in responses with page/section numbers
- Metadata filtering support (document_type, date_range, etc.)
- **Fallback mechanisms:** Graceful degradation if Pinecone unavailable

**Infrastructure Additions:**
- Aurora Serverless v2 cluster (0.5 ACU minimum)
- **Connection Pooling Strategy (Cost-Conscious):**
  - **Skip RDS Proxy** ($15-20/month) - too expensive for demo
  - Use SQLAlchemy connection pooling instead (free, built-in)
  - Pool size: 5 connections (sufficient for demo)
  - Max overflow: 10 connections
  - Fine for low-use demo, upgrade to RDS Proxy only if scaling
- Pinecone index (via Terraform provider or API)
- S3 bucket with Lambda trigger
- **S3 Intelligent-Tiering** for document storage (saves ~40% on storage costs)
- Lambda function for document processing
- Additional IAM policies for tool access

**Sample Data:**

**SQL Database Schema (Financial Dataset):**
```sql
-- Customers table
customers (id, name, email, risk_profile, created_date, status)

-- Accounts table  
accounts (id, customer_id, account_type, balance, opened_date, status)
-- account_type: 'checking', 'savings', 'investment', 'credit'

-- Transactions table
transactions (id, account_id, amount, transaction_date, type, description, category)
-- type: 'debit', 'credit', 'transfer'
-- category: 'purchase', 'salary', 'investment', 'fee', etc.

-- Portfolios table
portfolios (id, customer_id, name, total_value, last_updated, risk_level)

-- Trades table
trades (id, portfolio_id, symbol, quantity, price, trade_date, trade_type)
-- trade_type: 'buy', 'sell'
-- symbol: Stock ticker symbols (AAPL, MSFT, GOOGL, etc.)

-- Sample queries the agent should handle:
-- "What's the total balance for customer John Doe?"
-- "Show me all transactions over $1000 last month"
-- "Which customers have investment accounts?"
-- "What's the portfolio value for customer ID 123?"
-- "Show me all trades for AAPL in the last 30 days"
```

**RAG Document Store:**
- Technical documentation (API docs, system architecture)
- Company policies (financial policies, compliance docs)
- Financial reports (quarterly reports, market analysis)
- FAQs (common customer questions, account management)

**Deliverables:**
- Agent can search the web and cite sources
- Agent can query SQL database with natural language
- Agent can retrieve relevant documents from vector store
- Documents uploaded to S3 are automatically indexed
- Tool selection is intelligent and contextual

---

### Phase 3: Input/Output Verification
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

### Phase 4: Inference Caching
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

**Implementation:**
- Cache check before LLM call
- Cache write after successful response
- Cache invalidation on document updates
- Cost savings dashboard (tokens saved, $ saved)

**Deliverables:**
- Repeated queries return instantly from cache
- Cache hit rate > 30% for typical usage
- Cost savings visible in dashboard
- Cache invalidation works correctly

---

### Phase 5: Observability with Arize Phoenix
**Goal:** Full tracing and monitoring of agent execution

**Features:**
- Arize Phoenix self-hosted deployment (ECS Fargate, scales to minimal)
- **LangGraph native callbacks** (LangChainTracer) for built-in observability
- OpenTelemetry integration with LangGraph
- **Structured logging** (structlog) with JSON output for CloudWatch
- Trace visualization for agent runs
- **Comprehensive Metrics Tracking:**
  - Token usage (input/output tokens per request)
  - Latency breakdown (LLM call time, tool execution time, total time)
  - Tool success rate (which tools succeed/fail)
  - Cache hit rate (inference cache effectiveness)
  - Cost per request (actual AWS costs)
  - Error rate by type (timeout, API error, validation error, etc.)
- Error rate monitoring
- Tool usage analytics
- Cost tracking per conversation
- **Log aggregation:** Centralized logging in CloudWatch with structured JSON

-**Infrastructure:**
- ECS Fargate task for Phoenix (minimal instance) running in the same public subnets created in Phase 1a (still no NAT/VPC endpoints).
- Persistent storage (EFS for Phoenix data) with mount targets in those public subnets and security groups restricted to the Phoenix task + App Runner VPC connector.
- Internal ALB for Phoenix UI
- Password protection for Phoenix dashboard
- CloudWatch integration
- **CloudWatch Logs Insights** queries for log analysis
- **CloudWatch Dashboards** for key metrics visualization

**Deliverables:**
- Full trace of every agent execution
- Latency breakdown visible
- Token usage tracked
- Error rates monitored
- Tool usage analytics

---

### Phase 6: RAG Evaluation with RAGAS
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
- Regression alerts (CloudWatch alarms)
- Evaluation on document updates

**Implementation:**
- Lambda function for scheduled evaluations
- S3 storage for evaluation datasets
- CloudWatch metrics and alarms
- Integration with GitHub Actions for PR checks (optional)
- Evaluation report generation

**Deliverables:**
- Automated RAG quality evaluation
- Metrics visible in dashboard
- Alerts on quality regression
- Evaluation reports generated

---

### Phase 7: Enhanced UI and Thought Process Streaming
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
- Mobile-friendly design

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
│   │   ├── aurora/
│   │   │   ├── main.tf
│   │   │   ├── database.tf
│   │   │   └── outputs.tf
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
│   │   │       ├── sql.py        # Aurora query (SQL injection prevention)
│   │   │       └── rag.py        # Pinecone retrieval (query expansion, RRF, compression)
│   │   ├── cache/
│   │   │   ├── __init__.py
│   │   │   └── inference_cache.py
│   │   ├── ingestion/
│   │   │   ├── __init__.py
│   │   │   ├── document_processor.py
│   │   │   ├── chunking.py       # Parent document retriever strategy
│   │   │   └── query_expansion.py  # Query expansion for RAG
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── main.py           # FastAPI app
│   │   │   ├── routes/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── v1/           # API versioning
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   └── chat.py   # /api/v1/chat endpoint
│   │   │   │   ├── health.py     # Health check (with dependency checks)
│   │   │   │   └── warmup.py     # Warmup endpoint (reduces cold start)
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
│   │       └── rrf.py              # Reciprocal Rank Fusion
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_agent.py
│   │   ├── test_tools.py
│   │   └── test_api.py
│   ├── Dockerfile              # Production multi-stage
│   ├── Dockerfile.dev          # Development (with hot reload)
│   ├── requirements.txt        # Pinned versions (langgraph==0.2.0, etc.)
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

### CI Pipeline (on PR):
1. Lint and format check (Python: black, ruff | TypeScript: ESLint, Prettier)
2. Unit tests (pytest for Python, jest for TypeScript)
3. Terraform validate and plan (no apply)
4. Security scanning (Checkov for Terraform, Bandit for Python)
5. Build Docker image (test build, don't push)

### CD Pipeline (on merge to main):
1. Build backend Docker image
2. Push to ECR
3. Build frontend (Next.js build)
4. Upload frontend to S3
5. Terraform apply (with approval for prod)
6. Invalidate CloudFront cache
7. Health check (verify deployment)
8. Run smoke tests

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
| Aurora Serverless v2 | $10-20 | $0 | 0.5 ACU minimum, scales up on demand |
| Bedrock Nova | $0 | $2-10 | Pay-per-token, varies by usage |
| Pinecone | $0 | $0 | Free tier (100K vectors) |
| S3 + CloudFront | $0 | $1-2 | First 1GB free, then $0.023/GB storage + $0.085/GB transfer |
| Secrets Manager | $0.40 | $0 | 1 secret |
| Lambda (keep-alive) | $0 | $0 | Free tier (1M requests/month) |
| DynamoDB | $0 | $0-2 | Free tier + minimal usage, TTL for auto-cleanup |
| ECS Fargate (Phoenix) | $0 | $3-8 | Minimal instance, scales down when idle |
| EFS (Phoenix storage) | $0 | $0.30 | Minimal storage (~1GB) |
| Tavily API | $0 | $0-10 | Free tier: 1000 searches/month |
| Bedrock Embeddings | $0 | $1-3 | $0.0001/1K tokens (query expansion uses 4x) |
| ECR Storage | $0 | $0-1 | First 500MB free, then $0.10/GB |
| CloudWatch Logs | $0 | $0-2 | First 5GB free, set 7-day retention |
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
- Aurora scales to 0.5 ACU minimum (not zero, but minimal)
- App Runner scales to zero when idle
- DynamoDB on-demand pricing with TTL (no minimum, automatic cleanup)
- **S3 Intelligent-Tiering** for document storage (saves ~40% on storage)
- Phoenix on minimal Fargate instance (can skip entirely for MVP)
- CloudFront caching reduces origin requests
- Inference cache reduces Bedrock API calls by 30-40%
- **Bedrock on-demand** (not provisioned throughput) for cost flexibility
- **Cost tracking:** Monitor and alert on cost thresholds ($50/month alarm)
- **Keep-alive Lambda:** Free tier covers periodic health checks

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
- Individual tools (search, SQL, RAG) - Main functionality
- Cache logic - Core caching behavior
- Utility functions - Reusable helpers

**Testing Tools:**
- Python: pytest with pytest-cov (aim for 70%+ coverage on critical paths)
- TypeScript: Jest for frontend components
- Mock external services (Bedrock, Tavily, Pinecone) for unit tests

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

8. **docs/troubleshooting.md:**
   - Common issues and solutions
   - Debugging guide
   - Performance issues
   - Cost issues
   - Integration problems

9. **docs/adr/** (Architecture Decision Records):
   - 001-use-langgraph.md
   - 002-use-docker-compose.md
   - 003-use-pinecone.md
   - 004-use-bedrock-nova.md
   - 005-use-rrf-for-rag.md
   - 006-public-subnets-for-demo.md (cost optimization)
   - 007-sqlalchemy-pooling-vs-rds-proxy.md (cost optimization)
   - 008-nextjs-static-export.md (architecture clarification)

10. **docs/runbooks/** (Operational Runbooks):
    - database-connection-issues.md
    - bedrock-rate-limits.md
    - docker-startup-slow.md
    - rag-quality-poor.md
    - cost-optimization.md

11. **docs/examples/** (Code Examples):
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
   - **Fallback mechanisms** for each tool (search, SQL, RAG)
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

## Next Steps

**All Configuration Decisions Confirmed:**
- ✅ AWS Region: us-east-2 (Ohio)
- ✅ Domain: CloudFront URL (frontend) + App Runner URL (backend API)
- ✅ Testing: Balanced approach
- ✅ Sample Data: Financial dataset
- ✅ Documentation: Comprehensive + basic
- ✅ Docker: Optimized Compose (5-10s startup)
- ✅ LangGraph: Checkpointing (MemorySaver dev, PostgresSaver prod) + native streaming
- ✅ RAG: Query expansion + RRF + contextual compression
- ✅ Security: SQL injection prevention + rate limiting + input validation
- ✅ Observability: Structured logging + comprehensive metrics
- ✅ Error Handling: Fallbacks + circuit breakers + graceful degradation
- ✅ **Cost Optimization:** Public subnets (skip VPC endpoints), SQLAlchemy pooling (skip RDS Proxy)
- ✅ **Frontend:** Next.js static export (no server), native SSE client
- ✅ **Model Fallback:** Nova Pro → Claude 3.5 Sonnet
- ✅ **Cold Start UX:** Loading indicator with warmup endpoint
- ✅ **API Versioning:** /api/v1/ for future compatibility
- ✅ **Database Migrations:** Alembic for schema management

**Ready to Begin Phase 0:**

**Pre-Phase 0 Checklist (Do These First):**
- [ ] Docker Desktop installed and running
- [ ] Python 3.11+ installed
- [ ] AWS CLI v2 installed and configured (`aws configure`)
- [ ] Bedrock model access approved (check in console)
- [ ] Pinecone account created, index created, API key copied
- [ ] Tavily account created, API key copied
- [ ] Git installed

1. **Set up local development environment:**
   - Clone/initialize repository
   - Copy `.env.example` to `.env`
   - Fill in API keys (Tavily, Pinecone, AWS)
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
aws s3 mb s3://your-project-terraform-state --region us-east-2

# Create DynamoDB table for state locking
aws dynamodb create-table \
  --table-name terraform-state-lock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-2

# Update terraform/environments/dev/backend.tf with bucket name
```

**GitHub Actions Secrets (Required for Phase 1b CI/CD):**
- `AWS_ACCESS_KEY_ID` - IAM user access key
- `AWS_SECRET_ACCESS_KEY` - IAM user secret key
- `AWS_REGION` - us-east-2
- `TAVILY_API_KEY` - For web search tool (Phase 2)
- `PINECONE_API_KEY` - For vector store (Phase 2)
- `PINECONE_INDEX_NAME` - demo-index (Phase 2)
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
   aws s3 mb s3://your-project-terraform-state --region us-east-2
   
   # Create DynamoDB table for locking
   aws dynamodb create-table \
     --table-name terraform-state-lock \
     --attribute-definitions AttributeName=LockID,AttributeType=S \
     --key-schema AttributeName=LockID,KeyType=HASH \
     --billing-mode PAY_PER_REQUEST \
     --region us-east-2
   
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
   aws ecr get-login-password --region us-east-2 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-2.amazonaws.com
   
   # Build image
   docker build -t backend:latest -f backend/Dockerfile .
   
   # Tag for ECR
   docker tag backend:latest <account-id>.dkr.ecr.us-east-2.amazonaws.com/backend:latest
   
   # Push to ECR
   docker push <account-id>.dkr.ecr.us-east-2.amazonaws.com/backend:latest
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

1. **Deploy Aurora:**
   ```bash
   terraform apply -target=module.aurora
   ```
   ✅ **Verify:**
   - Aurora cluster status = "available"
   - Test connection: `psql -h <endpoint> -U demo -d demo`
   - Run migrations: `alembic upgrade head`

2. **Deploy VPC Connector:**
   ```bash
   terraform apply -target=module.app_runner_vpc_connector
   ```
   ✅ **Verify:** Connector status = "active"

3. **Update App Runner** to use VPC connector:
   ```bash
   terraform apply -target=module.app_runner
   ```
   ✅ **Verify:** App Runner can reach Aurora (check logs)

4. **Deploy Warmup Lambda:**
   ```bash
   terraform apply -target=module.warmup_lambda
   ```
   ✅ **Verify:** Lambda executes successfully (check CloudWatch Logs)

5. **Set up GitHub Actions CI/CD:**
   - Add secrets to GitHub repository
   - Push code to trigger workflow
   - Verify deployment succeeds

---

## Configuration Decisions

**Confirmed Settings:**
1. **AWS Region:** us-east-2 (Ohio - Central US)
   - Good service availability
   - Central US location
   - Cost-effective

2. **Domain:** App Runner generated URL
   - Format: `https://xxxxx.us-east-2.awsapprunner.com`
   - No custom domain setup required
   - HTTPS included automatically

3. **Testing:** Balanced approach
   - Best practices with minimal overhead
   - Unit tests for core logic (70%+ coverage on critical paths)
   - Integration tests for key flows
   - Manual testing for UI/UX
   - Focus on critical paths, not exhaustive coverage

4. **Sample Data:** Financial dataset
   - Transactions table (id, account_id, amount, date, type, description)
   - Accounts table (id, customer_id, account_type, balance, opened_date)
   - Customers table (id, name, email, risk_profile, created_date)
   - Portfolios table (id, customer_id, name, total_value, last_updated)
   - Trades table (id, portfolio_id, symbol, quantity, price, date)
   - Realistic financial queries: balance inquiries, transaction history, portfolio analysis

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
3. ✅ **Cold Start UX:** Added loading indicator + warmup endpoint
4. ✅ **Bedrock Nova:** Added fallback to Claude 3.5 Sonnet
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

### Suggested Demo Walkthrough (5 minutes)

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
- Highlight: LangGraph, Bedrock, Pinecone, Aurora, App Runner
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

Ready to begin Phase 0 when you are!

