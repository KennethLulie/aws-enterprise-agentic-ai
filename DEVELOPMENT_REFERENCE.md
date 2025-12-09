# Development Reference Guide

**Purpose:** This document serves as the authoritative reference for implementation details, technology specifications, and development order throughout all phases. Consult this document before implementing any feature to ensure consistency, completeness, and proper integration.  Make sure this document is updated as needed as the project proceeds.

**Last Updated:** Based on PROJECT_PLAN.md v1.0

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

**Required Variables:** See [`.env.example`](.env.example) for the complete list of environment variables with descriptions and where to obtain each key.

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
- **Agent Framework:** LangGraph
- **LLM:** AWS Bedrock (Nova Pro/Lite, Titan Embeddings, Claude fallback)
- **Checkpointing:** MemorySaver (in-memory, no DB)
- **Database:** Stub-only in Phase 0 (SQL tool returns mock data); real DB introduced in cloud phase
- **Vector Store:** Stub-only in Phase 0 (no local Chroma/Pinecone); real retrieval deferred to cloud phases
- **Logging:** Basic Python logging (upgrade to structlog in Phase 1b)

#### Frontend Stack
- **Framework:** Next.js 14+ (App Router)
- **Language:** TypeScript
- **UI Library:** shadcn/ui
- **SSE Client:** Native EventSource API (no Vercel AI SDK)
- **Build:** Static export (`output: 'export'` in next.config.js)
- **Styling:** Tailwind CSS

#### Docker Compose
- **Services (Phase 0 stub-only):**
  - `backend`: FastAPI on port 8000
  - `frontend`: Next.js dev server on port 3000
- **No local database/vector/KG services in Phase 0** (SQL and RAG tools return mock data)
- **Volume Mounts:** `./backend:/app`, `./frontend:/app` (hot reload)
- **Startup Time Target:** 5-10 seconds

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

#### Step 4: Basic Tools (Stubs)
1. **Tool Base** (`backend/src/agent/tools/__init__.py`)
   - Tool interface/base class
   - Common error handling
   - Circuit breaker base

2. **Tool Stubs** (for Phase 0, implement basic versions)
   - `search.py` - Return mock data
   - `sql.py` - Return mock data
   - `rag.py` - Return mock data
   - `weather.py` - Return mock data

#### Step 5: Frontend Foundation
1. **Next.js Setup** (`frontend/`)
   - Initialize Next.js with TypeScript
   - Configure for static export
   - Install shadcn/ui
   - Setup Tailwind CSS

2. **Login Page** (`frontend/src/app/login/page.tsx`)
   - Password input form
   - Store password in sessionStorage
   - Redirect to chat on success

3. **Chat Page** (`frontend/src/app/page.tsx`)
   - Chat interface layout
   - Message display area
   - Input field
   - SSE connection setup (EventSource)

4. **API Client** (`frontend/src/lib/api.ts`)
   - SSE connection function
   - Message sending function
   - Error handling

#### Step 6: Docker Compose
1. **docker-compose.yml**
   - Backend service (FastAPI)
   - Frontend service (Next.js)
   - PostgreSQL service
   - Chroma service (optional)
   - Volume mounts for hot reload
   - Environment variables

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
- **Checkpointing:** MemorySaver (no Aurora yet)
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
- **Aurora Serverless v2:**
  - Engine: PostgreSQL 15
  - Min capacity: 0.5 ACU
  - Max capacity: 2 ACU
  - Publicly accessible: true
  - In public subnets (from Phase 1a)
- **App Runner VPC Connector:**
  - Connects to public subnets
  - Security group allows App Runner → Aurora
- **Lambda (Warmup):**
  - Runtime: Python 3.11
  - Schedule: Every 5 minutes (EventBridge)
  - Calls `/health/warmup` endpoint
- **GitHub Actions:**
  - CI: On PR (test, lint, validate)
  - CD: On merge to main (build, deploy)

#### Backend Changes
- **Checkpointing:** PostgresSaver (migrate from MemorySaver)
- **Database:** Alembic migrations
- **Logging:** structlog with JSON output
- **API:** Version to `/api/v1/chat`
- **Health:** Enhanced with dependency checks
- **Rate Limiting:** slowapi middleware
- **Error Handling:** Comprehensive with retry logic

### Implementation Order

#### Step 1: Aurora Infrastructure
1. **Aurora Module** (`terraform/modules/aurora/`)
   - Aurora Serverless v2 cluster
   - Database instance
   - Security groups
   - Subnet group (public subnets)

2. **VPC Connector** (`terraform/modules/app-runner/vpc-connector.tf`)
   - App Runner VPC connector
   - Security group for connector
   - Update App Runner to use connector

#### Step 2: Database Setup
1. **Alembic Setup** (`backend/alembic/`)
   - Initialize Alembic
   - Create initial migration
   - LangGraph checkpoint tables schema

2. **Database Connection** (`backend/src/config/database.py`)
   - SQLAlchemy engine
   - Connection pooling (5 connections, max overflow 10)
   - Session management

3. **PostgresSaver Migration** (`backend/src/agent/graph.py`)
   - Replace MemorySaver with PostgresSaver
   - Use SQLAlchemy connection
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
   - Check Aurora connection
   - Check Bedrock access
   - Return dependency status

3. **Warmup Endpoint** (`backend/src/api/routes/warmup.py`)
   - `/health/warmup` endpoint
   - Initialize services
   - Return warmup status

4. **Rate Limiting** (`backend/src/api/middleware/rate_limit.py`)
   - slowapi middleware
   - 10 requests/minute per IP
   - Configurable limits

5. **Error Handling** (`backend/src/api/middleware/error_handler.py`)
   - Global error handler
   - User-friendly messages
   - Error logging

#### Step 5: Lambda Warmup
1. **Lambda Function** (`lambda/warm_app_runner/handler.py`)
   - HTTP request to `/health/warmup`
   - Authorization header
   - Error handling

2. **Lambda Terraform** (`terraform/modules/lambda/warmup.tf`)
   - Lambda function
   - EventBridge schedule
   - IAM role
   - Environment variables

#### Step 6: GitHub Actions CI/CD
1. **CI Pipeline** (`.github/workflows/ci.yml`)
   - Lint (black, ruff)
   - Type check (mypy)
   - Test (pytest)
   - Terraform validate
   - Security scan

2. **CD Pipeline** (`.github/workflows/deploy.yml`)
   - Build Docker image
   - Push to ECR
   - Build frontend
   - Upload to S3
   - Terraform apply
   - CloudFront invalidation
   - Health check

3. **GitHub Secrets Setup**
   - AWS_ACCESS_KEY_ID
   - AWS_SECRET_ACCESS_KEY
   - AWS_REGION
   - TAVILY_API_KEY
   - PINECONE_API_KEY
   - OPENWEATHER_API_KEY

### Phase 1b Deliverables Checklist
- [ ] Conversation state persists across restarts
- [ ] Automated deployment pipeline
- [ ] Enhanced monitoring and logging
- [ ] Production-ready security
- [ ] Aurora database provisioned
- [ ] VPC connector configured
- [ ] Warmup Lambda running
- [ ] GitHub Actions workflows working

### Consistency Checks
- [ ] PostgresSaver uses same connection pool as SQLAlchemy
- [ ] All logs use structlog with JSON format
- [ ] API versioning consistent across all endpoints
- [ ] Rate limiting applied to all API routes
- [ ] Error messages are user-friendly
- [ ] Health check validates all dependencies

---

## Phase 2: Core Agent Tools

### Goal
Agent can search the web, query SQL databases, and retrieve from documents.

### Technology Specifications

#### Tool 2a: Tavily Search
- **API:** Tavily Search API
- **Rate Limit:** 1,000 searches/month (free tier)
- **Error Handling:** Retry with exponential backoff
- **Circuit Breaker:** 5 failures → open, recover after 60s
- **Logging:** Structured logging of queries and results

#### Tool 2b: SQL Query
- **Database:** Aurora Serverless v2 (from Phase 1b)
- **ORM:** SQLAlchemy
- **Connection Pooling:** Built-in (5 connections, max overflow 10)
- **Security:** Parameterized queries, table whitelisting
- **Safety:** Read-only, max rows limit, query validation

#### Tool 2c: RAG Retrieval (2025 SOTA)
- **Vector Store:** Pinecone Serverless
- **Embeddings:** Bedrock Titan Embeddings (1536 dimensions)
- **Hybrid Search:** Dense + sparse vectors with RRF
- **Semantic Chunking:** spaCy sentence boundary detection (replaces fixed-size)
- **Contextual Retrieval:** Prepend doc title/type/section to chunks before embedding
- **Parent Document Retriever:** Small chunks for search, large context for response
- **Query Expansion:** Generate 3 alternative phrasings (+20-30% recall)
- **Cross-Encoder Reranking:** LLM scores relevance after RRF (+20-25% precision)
- **Compression:** LLMChainExtractor for contextual compression

#### Tool 2c-KG: Knowledge Graph Integration
- **Primary Store:** Neo4j AuraDB Free (200K nodes, $0/month)
- **Fallback:** PostgreSQL with recursive CTEs
- **Entity Extraction:** spaCy NER + dependency parsing (no LLM needed)
- **Ontology:** Financial domain (Policy, Customer, Account, Regulation, Concept, Person)
- **Traversal:** 1-2 hop relationship queries
- **Cost:** ~$0.001/doc ingestion, $0/query (free tier)

#### Tool 2d: Weather API
- **API:** OpenWeatherMap (free tier: 60 calls/minute)
- **Error Handling:** Retry with exponential backoff
- **Circuit Breaker:** 5 failures → open, recover after 60s
- **Input Validation:** City name, coordinates, or ZIP code
- **Output:** Temperature, conditions, humidity, wind speed

#### Infrastructure Additions
- **S3 Bucket:** Document storage (separate from frontend bucket)
- **Lambda:** Document ingestion trigger
- **IAM Policies:** Tool access permissions
- **Neo4j AuraDB Free:** Knowledge graph storage (200K nodes, $0/month)
- **Neo4j Docker:** Local development graph database
- **spaCy Model:** en_core_web_sm for NLP entity extraction

### Implementation Order

#### Step 1: Tavily Search Tool
1. **Tool Implementation** (`backend/src/agent/tools/search.py`)
   - Tavily API client
   - Tool definition for LangGraph
   - Result formatting with citations
   - Error handling with retry
   - Circuit breaker implementation
   - Structured logging

2. **Circuit Breaker** (`backend/src/utils/circuit_breaker.py`)
   - Generic circuit breaker class
   - Failure tracking
   - Recovery logic
   - Reusable for all tools

#### Step 2: SQL Query Tool
1. **Database Schema** (`backend/alembic/versions/002_sample_data.py`)
   - Customers table
   - Accounts table
   - Transactions table
   - Portfolios table
   - Trades table
   - Sample data seeding

2. **Tool Implementation** (`backend/src/agent/tools/sql.py`)
   - SQLAlchemy connection
   - Natural language to SQL (via LLM)
   - Query execution with safety checks
   - Parameterized queries only
   - Table whitelisting
   - Result formatting
   - Error handling

3. **SQL Safety** (`backend/src/agent/tools/sql_safety.py`)
   - ALLOWED_TABLES constant
   - Query validation function
   - SQL injection prevention

#### Step 3: RAG Retrieval Tool (2025 SOTA)

**3a. Ingestion Pipeline:**

1. **Semantic Chunking** (`backend/src/ingestion/semantic_chunking.py`)
   - spaCy sentence boundary detection
   - Grammar-aware splitting
   - Configurable max chunk size
   - Preserves complete thoughts

2. **Contextual Chunking** (`backend/src/ingestion/contextual_chunking.py`)
   - Prepend document title to each chunk
   - Add section header context
   - Include document type metadata
   - Impact: +15-20% precision

3. **Document Processing** (`backend/src/ingestion/document_processor.py`)
   - PDF/text parsing
   - Metadata extraction
   - Integration with semantic + contextual chunking

4. **Parent Document Retriever** (`backend/src/ingestion/chunking.py`)
   - Small chunks for retrieval
   - Large context for response
   - Metadata preservation

**3b. Knowledge Graph Pipeline:**

5. **Efficient Entity Extraction** (`backend/src/knowledge_graph/efficient_extractor.py`)
   - spaCy NER (PERSON, ORG, DATE, MONEY, etc.)
   - Custom financial domain patterns
   - Dependency parsing for relationships
   - Cost: ~$0.001/doc (vs $0.02-0.05 with LLM)

6. **Knowledge Graph Store** (`backend/src/knowledge_graph/store.py`)
   - Neo4j adapter for production
   - PostgreSQL fallback with recursive CTEs
   - Connection pooling
   - Entity/relationship CRUD

7. **Graph Ontology** (`backend/src/knowledge_graph/ontology.py`)
   - Entity types: Document, Policy, Customer, Account, Concept, Regulation, Person
   - Relationship types: MENTIONS, RELATES_TO, GOVERNED_BY, APPLIES_TO, SIMILAR_TO

8. **Graph Queries** (`backend/src/knowledge_graph/queries.py`)
   - 1-hop entity lookup
   - 2-hop relationship traversal
   - Entity-to-document linking

**3c. Query Pipeline:**

9. **Query Expansion** (`backend/src/ingestion/query_expansion.py`)
   - Generate 3 alternative phrasings
   - Multi-query retrieval
   - Parallel searches
   - Impact: +20-30% recall

10. **Embeddings** (`backend/src/utils/embeddings.py`)
    - Bedrock Titan integration
    - Batch embedding generation
    - Caching

11. **RRF Implementation** (`backend/src/utils/rrf.py`)
    - Reciprocal Rank Fusion algorithm
    - Merge vector + sparse + KG results
    - Score normalization

12. **Cross-Encoder Reranking** (`backend/src/utils/reranker.py`)
    - LLM-based relevance scoring
    - Score top 15 results
    - Return top 5
    - Impact: +20-25% precision
    - Cost: ~$0.015/query

13. **Tool Implementation** (`backend/src/agent/tools/rag.py`)
    - Pinecone client for vector search
    - BM25 for sparse search
    - KG lookup integration
    - RRF fusion of all results
    - Cross-encoder reranking
    - Contextual compression
    - Source citation
    - Error handling with fallbacks

#### Step 4: Weather API Tool
1. **Tool Implementation** (`backend/src/agent/tools/weather.py`)
   - OpenWeatherMap API client
   - Tool definition for LangGraph
   - Input validation (city/coordinates/ZIP)
   - Result formatting
   - Unit conversion
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

#### Step 6: Document Ingestion Infrastructure
1. **S3 Bucket** (`terraform/modules/s3/documents.tf`)
   - S3 bucket for documents
   - Intelligent-Tiering enabled
   - Lambda trigger configuration

2. **Lambda Function** (`lambda/document-ingestion/handler.py`)
   - S3 event handler
   - Document processing
   - Pinecone indexing
   - Error handling

3. **Lambda Terraform** (`terraform/modules/lambda/document-ingestion.tf`)
   - Lambda function
   - S3 trigger
   - IAM permissions
   - Environment variables

### Phase 2 Deliverables Checklist
- [ ] Agent can search the web and cite sources
- [ ] Agent can query SQL database with natural language
- [ ] Agent can retrieve relevant documents from vector store
- [ ] Agent can retrieve current weather information
- [ ] Documents uploaded to S3 are automatically indexed
- [ ] Tool selection is intelligent and contextual
- [ ] All tools have circuit breakers
- [ ] All tools have structured logging
- [ ] Sample database populated

### Consistency Checks
- [ ] All tools follow same error handling pattern
- [ ] All tools use circuit breaker
- [ ] All tools have structured logging
- [ ] SQL tool uses parameterized queries
- [ ] RAG tool uses hybrid search with RRF
- [ ] Tool results are properly formatted
- [ ] Tool citations are included in responses

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
langchain-aws~=0.2.0

# AWS SDK
boto3~=1.35.0
botocore~=1.35.0

# Database
sqlalchemy~=2.0.35
alembic~=1.13.0
psycopg2-binary~=2.9.9

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

**Version Philosophy:** Use `^` (caret) for semver-compatible updates. Next.js 14.2.x is stable LTS.

```json
{
  "dependencies": {
    "next": "^14.2.0",
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "@radix-ui/react-*": "latest",
    "tailwindcss": "^3.4.0",
    "typescript": "^5.6.0"
  },
  "devDependencies": {
    "@types/node": "^22.0.0",
    "@types/react": "^18.3.0",
    "eslint": "^9.0.0",
    "prettier": "^3.3.0"
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

### OpenWeatherMap
- **API Endpoint:** https://api.openweathermap.org/data/2.5/weather
- **Free Tier:** 60 calls/minute, 1M calls/month
- **Rate Limit:** 60 calls/minute

### AWS Bedrock
- **Region:** us-east-1
- **Models:**
  - Nova Pro: `amazon.nova-pro-v1:0`
  - Nova Lite: `amazon.nova-lite-v1:0`
  - Titan Embeddings: `amazon.titan-embed-text-v1`
  - Claude Fallback: `anthropic.claude-3-5-sonnet-20241022-v2:0`

### Neo4j AuraDB (Knowledge Graph)
- **Tier:** Free (200K nodes, 400K relationships)
- **Region:** us-east-1 (if available) or closest
- **Connection:** Bolt protocol (neo4j+s://)
- **Local Dev:** Docker image `neo4j:5-community`
- **Fallback:** PostgreSQL with recursive CTEs

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
- [ ] Warmup Lambda (Phase 1b+)
- [ ] CloudFront caching

---

## Cost Optimization Checklist

### Infrastructure
- [ ] App Runner scales to 0
- [ ] Aurora scales to 0.5 ACU minimum
- [ ] DynamoDB on-demand pricing
- [ ] S3 Intelligent-Tiering
- [ ] No RDS Proxy (use SQLAlchemy pooling)

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

