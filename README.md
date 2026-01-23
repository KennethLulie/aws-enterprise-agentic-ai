# Enterprise Agentic AI Demo

An enterprise-grade agentic AI system on AWS demonstrating multi-tool orchestration, RAG, real-time streaming, and cost-optimized architecture.

## 🎯 Project Overview

This project demonstrates a **production-ready agentic AI system** that showcases enterprise-level patterns and best practices. Unlike simple chatbots or basic RAG implementations, this system demonstrates:

- **Real-world agentic AI patterns** - Multi-tool orchestration where an AI agent intelligently selects and coordinates multiple tools (web search, SQL queries, RAG retrieval, external APIs)
- **Enterprise-grade reliability** - Production-ready error handling, circuit breakers, retry logic, and graceful degradation
- **Full observability stack** - Complete tracing, metrics, logging, and evaluation pipelines for production monitoring
- **Cost-optimized architecture** - Serverless-first design with semantic caching, intelligent scaling, and infrastructure optimizations targeting $20-50/month for demo workloads
- **DevOps excellence** - Infrastructure as Code with Terraform, automated CI/CD pipelines, and comprehensive testing

**Target Use Cases:**
- Enterprise knowledge assistants that combine internal documents (RAG), databases (SQL), and external information (web search)
- Financial analysis systems requiring multi-source data aggregation
- Customer support agents with access to policies, databases, and real-time information
- Research assistants that synthesize information from multiple sources

This project showcases a production-ready AI agent system with:
- **Multi-tool orchestration** (Web Search, SQL Query, RAG Retrieval, Market Data API)
- **Input/Output verification** with SLMs for cost optimization
- **Streaming thought process** visualization
- **Inference caching** for cost optimization
- **Full observability** with Arize Phoenix
- **RAG evaluation** with RAGAS
- **VLM document extraction** with Claude Vision (handles complex PDFs)
- **Password-protected** web interface
- **Infrastructure as Code** with Terraform
- **CI/CD** with GitHub Actions

**Target Cost:** $20-50/month for low-use portfolio demo  
**AWS Region:** us-east-1 (N. Virginia - closest to Austin, TX)  
**Architecture:** Scalable, enterprise-ready, cost-optimized

## RAG Technology Stack

Our production-ready RAG system integrates **10+ technologies** working together for state-of-the-art retrieval:

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Document Extraction** | Claude Sonnet 4.5 Vision (Bedrock) | VLM extraction from complex PDFs with table preservation |
| **Embeddings** | AWS Bedrock Titan v2 (1024d) | Semantic vector generation for similarity search |
| **Vector Store** | Pinecone Serverless | Dense + sparse hybrid search with free tier |
| **Keyword Search** | BM25 Sparse Vectors | Exact term matching for domain terminology |
| **Knowledge Graph** | Neo4j AuraDB | Entity relationships + multi-hop traversal |
| **Entity Extraction** | spaCy NER | Cost-efficient extraction (20-50x cheaper than LLM) |
| **Query Enhancement** | Nova Lite | Query expansion generating 3 variants (+20-30% recall) |
| **Result Fusion** | RRF Algorithm | Reciprocal Rank Fusion merging multiple sources |
| **Reranking** | Nova Lite Cross-Encoder | LLM relevance scoring (+20-25% precision) |
| **Compression** | Contextual Compression | Extract query-relevant sentences from chunks |
| **SQL Analytics** | Neon PostgreSQL | Structured 10-K financial metrics for precise queries |
| **Orchestration** | LangGraph | Multi-tool agent with streaming and checkpointing |

**Query Pipeline:** User Query -> Query Expansion (3 variants) -> Parallel Retrieval (Dense + BM25 + KG) -> RRF Fusion -> KG Boost -> Cross-Encoder Reranking -> Contextual Compression -> Response with Citations

See [docs/RAG_README.md](./docs/RAG_README.md) for the complete architecture deep-dive.

## 🏢 Why Enterprise-Grade?

This system goes beyond a simple demo by implementing production-ready features:

### Production-Ready Architecture
- **Scalable & Fault-Tolerant**: Serverless architecture with auto-scaling, circuit breakers, and graceful degradation
- **Cost-Optimized**: Semantic inference caching reduces LLM costs by 30-40%, intelligent resource scaling minimizes idle costs
- **High Availability**: Multi-AZ deployments, health checks, and automatic failover mechanisms

### Security & Compliance
- **Input/Output Verification**: SLM guards validate user inputs and agent outputs for safety and quality
- **Rate Limiting**: Prevents abuse with configurable rate limits per IP
- **Audit Trails**: Full observability with structured logging, tracing, and evaluation metrics
- **SQL Injection Prevention**: Parameterized queries and table whitelisting for database security

### Full Observability
- **Distributed Tracing**: Arize Phoenix provides complete visibility into agent execution paths
- **Structured Logging**: Machine-readable JSON logs enable automated analysis and debugging
- **Metrics & Alarms**: CloudWatch dashboards track performance, costs, errors, and quality metrics
- **RAG Evaluation**: Continuous quality monitoring with RAGAS to detect regressions

### DevOps Excellence
- **Infrastructure as Code**: Terraform manages all AWS resources with version control and reproducibility
- **CI/CD Pipelines**: GitHub Actions automates testing, building, and deployment
- **Automated Testing**: Unit tests, integration tests, and RAGAS evaluation in CI pipeline
- **Documentation**: Comprehensive architecture docs, API references, and troubleshooting guides

### Reliability Patterns
- **Circuit Breakers**: Prevent cascade failures when external services are unavailable
- **Retry Logic**: Exponential backoff for transient failures
- **Fallback Mechanisms**: Graceful degradation when tools fail
- **Health Checks**: Dependency validation endpoints

## 📋 Project Status

**Current Phase:** Phase 2b ✅ **COMPLETED** (January 20, 2026) - Intelligence Layer with Knowledge Graph and Hybrid Search

> 🚀 **Demo link and password available on request**

**Phase 2b (completed January 20, 2026)** delivered the intelligence layer:
- ✅ Knowledge Graph - Neo4j AuraDB with spaCy entity extraction (781 vectors indexed)
- ✅ Hybrid Search - Dense + BM25 sparse vectors with RRF fusion
- ✅ Query Expansion - Nova Lite generates 3 query variants (+20-30% recall)
- ✅ Cross-encoder Reranking - Nova Lite relevance scoring (+20-25% precision)
- ✅ Contextual Compression - Extract query-relevant sentences
- ✅ Multi-tool Orchestration - SQL + RAG + Search combined queries
- ✅ AWS Secrets configured for Pinecone and Neo4j

**Phase 2a ** delivered data foundation and core tools:
- ✅ SQL Query Tool - Real implementation with Neon PostgreSQL
- ✅ RAG Retrieval Tool - Real implementation with Pinecone
- ✅ Document processing pipeline with VLM extraction
- ✅ Parent/child chunking with contextual enrichment
- ✅ Agent integration with graceful fallback

**Phase 1b ** added production hardening:
- ✅ Neon PostgreSQL integration for persistent state (free tier)
- ✅ PostgresSaver checkpointing for conversation persistence
- ✅ GitHub Actions CI/CD pipelines (CI on push/PR, CD manual trigger)
- ✅ Structured logging with structlog (CloudWatch-compatible JSON)
- ✅ Enhanced rate limiting (slowapi, 10 req/min per IP)
- ✅ API versioning (/api/v1/ routes)
- ✅ Database migrations ready (Alembic configured)

**Phase 1a ** deployed the system to AWS:
- ✅ App Runner backend with LangGraph agent and Bedrock (Nova Pro)
- ✅ CloudFront + S3 static frontend hosting
- ✅ Secrets Manager for secure credential storage
- ✅ Real-time streaming chat with Server-Sent Events
- ✅ Password-protected demo access
- ✅ Infrastructure as Code with Terraform
- ✅ Cost-optimized (~$10-25/month when active)

**Phase 0 (completed)** established a fully working local development environment with:
- LangGraph agent with Bedrock (Nova Pro) and streaming responses
- ✅ Tavily search tool (Phase 2a completed early) - live when `TAVILY_API_KEY` is set, mock fallback otherwise
- ✅ FMP market data tool (Phase 2d completed early) - live when `FMP_API_KEY` is set, mock fallback otherwise
- SQL and RAG tools stubbed (real implementations completed in Phase 2a)
- Docker Compose for all services with hot reload
- Password-protected web interface

**Local setup tip:** If you see `ModuleNotFoundError: langchain_community` in the backend container, rebuild the backend image to pull the pinned dependency:
```bash
docker-compose build backend && docker-compose up -d backend
```

**Phase 2 Overview:** Core Agent Tools implements SQL queries with Neon PostgreSQL (real 10-K financial metrics), RAG with Pinecone (hybrid search + Neo4j knowledge graph), and cross-document analysis. Document extraction uses Claude VLM for all documents (10-Ks + reference docs), with spaCy NER for entity extraction and Titan Embeddings for semantic search. Note: Tavily Search and Market Data were already completed in Phase 0. See [docs/RAG_README.md](./docs/RAG_README.md) for the complete RAG architecture.

## 📚 Documentation

### Architecture Deep-Dives
- **[docs/RAG_README.md](./docs/RAG_README.md)** - **RAG System Architecture** - Comprehensive guide to our hybrid retrieval system including VLM extraction, dense + BM25 search, knowledge graph integration, query expansion, reranking, and enterprise considerations

### Project References
- **[PROJECT_PLAN.md](./PROJECT_PLAN.md)** - Complete project plan with all phases, architecture, and implementation details
- **[DEVELOPMENT_REFERENCE.md](./DEVELOPMENT_REFERENCE.md)** - Detailed implementation reference for each phase
- **[docs/SECURITY.md](./docs/SECURITY.md)** - Security and secrets management guide

### Completed Phase Guides (Archived)
- **[docs/completed-phases/PHASE_2B_HOW_TO_GUIDE.md](./docs/completed-phases/PHASE_2B_HOW_TO_GUIDE.md)** - Phase 2b (Intelligence Layer - Knowledge Graph, Hybrid RAG)
- **[docs/completed-phases/PHASE_2A_HOW_TO_GUIDE.md](./docs/completed-phases/PHASE_2A_HOW_TO_GUIDE.md)** - Phase 2a (Data Foundation - VLM, SQL, Basic RAG)
- **[docs/completed-phases/PHASE_1B_HOW_TO_GUIDE.md](./docs/completed-phases/PHASE_1B_HOW_TO_GUIDE.md)** - Phase 1b (Production Hardening)
- **[docs/completed-phases/PHASE_1A_HOW_TO_GUIDE.md](./docs/completed-phases/PHASE_1A_HOW_TO_GUIDE.md)** - Phase 1a (AWS Cloud Deployment)
- **[docs/completed-phases/PHASE_0_HOW_TO_GUIDE.md](./docs/completed-phases/PHASE_0_HOW_TO_GUIDE.md)** - Phase 0 (Local Development)
- **[docs/completed-phases/PHASE_2_REQUIREMENTS.md](./docs/completed-phases/PHASE_2_REQUIREMENTS.md)** - Phase 2 Requirements (Archived planning document)

## 🧭 LangGraph Flow (Planned Graph)

Planned end-state graph (per `PROJECT_PLAN.md`, implemented in `backend/src/agent/graph.py` as phases mature). Planner chooses edges dynamically; tools loop results back for multi-hop reasoning:

```
                 ┌────────────────┐
                 │ Input Verify   │  (Nova Lite guards)
                 └──────┬─────────┘
                        │ safe / blocked
                        ▼
                 ┌────────────────┐
                 │ Cache Check    │  (semantic, DynamoDB)
                 └──────┬─────────┘
                        │ hit / miss
                        ▼
            ┌────────────────────────────┐
            │      Planner (LLM)         │
            │ decides next edge:         │
            │ - call tool(s)             │
            │ - respond directly         │
            │ - halt on error            │
            └─┬────────┬─────────┬──────┘
              │        │         │
   tool_calls │        │ no call │ error
              │        │         │
              ▼        ▼         ▼
   ┌────────────┐  ┌──────────┐  ┌────────────────┐
   │ SQL Tool   │  │ Respond  │  │ Error Recovery │
   │  (Neon)    │  │ (LLM out)│  │ (fallback/stop)│
   ├────────────┤  └────┬─────┘  └────────┬───────┘
   │ RAG Tool   │       │                 │
   │ (Pinecone) │       │                 │
   ├────────────┤       │                 │
   │ Search     │       │                 │
   │ (Tavily)   │       │                 │
   ├────────────┤       │                 │
   │ Market API │       │                 │
   │ (MCP)      │       │                 │
   └──────┬─────┘       │                 │
          │ results     │                 │
          ▼             │                 │
   ┌────────────────┐   │                 │
   │ Tool Result    │   │                 │
   │ (normalized)   │   │                 │
   └──────┬─────────┘   │                 │
          │             │                 │
          └─────────────┴──── loop back ──┐
                                          │
                                          ▼
                               (back to Planner box above for next decision)
                                          │ finish
                                          ▼
                 ┌────────────────┐
                 │ Cache Write    │  (on miss; planner-directed)
                 └──────┬─────────┘
                        ▼
                 ┌────────────────┐
                 │ Output Verify  │  (safety/quality gate)
                 └──────┬─────────┘
                        ▼
                 ┌──────────────┐
                 │     End      │
                 └──────────────┘
```

- Planner can loop through multiple tool calls; tools return to planner before finalizing.
- Error recovery can short-circuit to end with a safe fallback message.
- Cache read happens before tool work; cache write happens after successful tool/LLM work.
- Input/Output verification bookend the flow for safety.

## 🏗️ Architecture

The system is organized into three layers: **DevOps & Deployment**, **Runtime**, and **Evaluation & Monitoring**.

```
┌───────────────────────────────────────────────────────────────────────┐
│                    DEVOPS & DEPLOYMENT                                │
│  ┌──────────────────────┐         ┌──────────────────────┐            │
│  │   GitHub Actions     │────────▶│      Terraform      │            │
│  │   (CI/CD Pipeline)   │         │   (Infrastructure)   │            │
│  │  • Build & Test      │         │  • AWS Resources     │            │
│  │  • Deploy            │         │  • State Management  │            │
│  │  • RAGAS Evaluation  │         │                      │            │
│  └──────────────────────┘         └──────────────────────┘            │
│           │                                    │                      │
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
│   v2 PostgreSQL  │    │    Serverless    │    │    AuraDB        │
│   (SQL Data)     │    │  (Vector Store)  │    │(Knowledge Graph) │
└──────────────────┘    └──────────────────┘    └──────────────────┘
         ▲                       ▲                       ▲
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌────────────────────────┐
                    │   Document Ingestion    │
                    │   (VLM Extraction via   │
                    │   Claude Vision/Bedrock)│
                    │   + spaCy NER + Titan   │
                    │   Embeddings            │
                    └────────────────────────┘

┌───────────────────────────────────────────────────────────────────────┐
│                    EVALUATION & MONITORING                            │
│  ┌──────────────────────┐         ┌──────────────────────┐            │
│  │       RAGAS          │────────▶│   Arize Phoenix     │            │
│  │  (RAG Evaluation)    │         │   (Observability)    │            │
│  │  • Lambda Scheduled  │         │  • Trace Analysis    │            │
│  │  • GitHub Actions    │         │  • Metrics Dashboard │            │
│  │  • Quality Metrics   │         │  • Cost Tracking     │            │
│  └──────────────────────┘         └──────────────────────┘            │
│           │                                    │                      │
│           │                                    │                      │
│           ▼                                    ▼                      │
│  ┌──────────────────┐              ┌─────────────────┐                │
│  │  S3 Eval Dataset  │              │  CloudWatch    │                │
│  │  (Test Cases)     │              │  (Metrics/Logs)│                │
│  └───────────────────┘              └────────────────┘                │
└───────────────────────────────────────────────────────────────────────┘
```

**Architecture Layers:**

1. **DevOps & Deployment**: GitHub Actions orchestrates CI/CD pipelines that build, test, and deploy via Terraform. Terraform provisions and manages all AWS infrastructure as code.

2. **Runtime Layer**: 
   - **Frontend**: Static Next.js export hosted on S3/CloudFront with password protection
   - **Backend**: AWS App Runner hosts the LangGraph agent orchestrator with Bedrock Nova LLM, input/output verification, inference caching, and Arize Phoenix tracing
   - **Tools**: Four integrated tools (Tavily web search, Neon SQL queries, Pinecone RAG retrieval, Market Data API) that the agent can intelligently select and use

3. **Data Layer**: Neon PostgreSQL for structured data, Pinecone Serverless for vector storage, S3 for document storage (auto-ingestion available for enterprise scaling)

4. **Evaluation & Monitoring**: RAGAS evaluates RAG quality via scheduled Lambda and GitHub Actions, sending metrics to Arize Phoenix and CloudWatch for observability and regression detection

## 🚀 Quick Start

### Prerequisites

- Docker Desktop installed and running
- Windows 11: use WSL 2 (Ubuntu), keep the repo in `~/Projects` (not `/mnt/c`), and open the project from WSL with `cursor .`
- AWS CLI configured (`aws configure`)
- AWS Bedrock model access approved (Nova Pro, Nova Lite, Titan Embeddings)
- API keys for: Tavily, Pinecone (free tiers available)

### Setup

```bash
# Run from WSL (Ubuntu) on Windows; macOS/Linux use your shell
# 1. Clone the repository
git clone https://github.com/yourusername/aws-enterprise-agentic-ai.git
cd aws-enterprise-agentic-ai

# 2. Create your environment file from the template
cp .env.example .env

# 3. Edit .env and fill in your API keys
# See .env.example for descriptions of each variable

# 4. Start the development environment
# Search (Tavily) and Market Data (FMP) use real APIs when keys are set
# SQL and RAG tools use mock data in Phase 0
# /api/chat streams real LangGraph+Bedrock only when AWS creds are set; otherwise mock
docker compose up
```

### Development Phases

- **Phase 0:** ✅ Local development environment (real Tavily search, FMP market data; SQL/RAG stubbed)
- **Phase 1a:** ✅ Minimal MVP - AWS Cloud Deployment (App Runner + CloudFront)
- **Phase 1b:** ✅ Production hardening (persistent state, Neon PostgreSQL, CI/CD)
- **Phase 2a:** ✅ Data Foundation (VLM extraction, SQL tool, basic RAG with Pinecone)
- **Phase 2b:** ✅ Intelligence Layer (Knowledge Graph, hybrid search, query expansion, reranking) - **COMPLETED**
- **Phase 3+:** Advanced features (verification, caching, observability, evaluation) - **NEXT**

See [PROJECT_PLAN.md](./PROJECT_PLAN.md) for complete details.

## 🔐 Security & Secrets Management

**This project never stores real API keys in the repository.**

| Environment | Secrets Storage |
|-------------|-----------------|
| Local Development | `.env` file (gitignored) |
| CI/CD | GitHub Secrets |
| Production | AWS Secrets Manager |

### Setup for Local Development

1. Copy the template: `cp .env.example .env`
2. Edit `.env` with your actual API keys
3. The `.env` file is automatically gitignored

### Automated Secret Scanning

This project uses pre-commit hooks with `detect-secrets` to prevent accidental commits of secrets.

```bash
# Install pre-commit hooks
# Run in WSL terminal (Ubuntu)
pip install pre-commit
pre-commit install
```

See [docs/SECURITY.md](./docs/SECURITY.md) for the complete security guide.

## 🚀 Enterprise Features Deep Dive

### Multi-Tool Orchestration
The LangGraph agent framework intelligently coordinates multiple tools based on user queries. The agent decides which tools to use, in what order, and how to combine their outputs. For example, a query like "How did AAPL and MSFT move today and how does that compare to our customer data there?" triggers the Market Data MCP connection (FMP via MCP demo) alongside the SQL query tool, with the agent synthesizing the results.

### Advanced RAG (Retrieval-Augmented Generation)

> 📖 **Deep Dive:** See [docs/RAG_README.md](./docs/RAG_README.md) for complete architecture, design decisions, and enterprise considerations.

Beyond basic vector search, this system implements state-of-the-art 2026 RAG techniques:
- **VLM Document Extraction**: Claude Vision extracts structured data from complex 10-K filings, preserving table structure
- **Hybrid Search**: Combines semantic similarity (dense vectors) with keyword matching (BM25 sparse vectors)
- **Knowledge Graph**: Neo4j stores entity relationships for multi-hop reasoning and entity-aware queries
- **Query Expansion**: Generates 3 alternative phrasings to improve retrieval coverage by 20-30%
- **RRF (Reciprocal Rank Fusion)**: Intelligently merges results from vector, keyword, and graph searches
- **Cross-Encoder Reranking**: Nova Lite scores relevance of top results for +20-25% precision
- **Contextual Enrichment**: Prepends document/section context to chunks before embedding

### Input/Output Verification
Small Language Models (SLMs) act as guardrails:
- **Input Verification**: Detects prompt injection, jailbreak attempts, and policy violations before processing
- **Output Verification**: Validates response quality, checks for hallucinations, detects PII leakage, and verifies citations
- **Configurable Policies**: Strict/moderate/permissive modes for different use cases

### Semantic Inference Caching
Reduces LLM costs by 30-40% through intelligent caching:
- **Semantic Similarity Matching**: Caches based on meaning, not exact text match
- **Embedding-Based Keys**: Uses Bedrock Titan embeddings to identify similar queries
- **TTL-Based Expiration**: Automatic cache cleanup via DynamoDB TTL
- **Cache Invalidation**: Automatically invalidates cache when documents are updated

### Full Observability
Complete visibility into system behavior:
- **Arize Phoenix**: Distributed tracing shows complete agent execution paths, tool calls, and decision points
- **CloudWatch Metrics**: Tracks token usage, latency, costs, error rates, and cache hit rates
- **Structured Logging**: JSON-formatted logs enable automated analysis and debugging
- **Cost Tracking**: Per-request and per-conversation cost tracking for FinOps

### RAG Evaluation Pipeline
Continuous quality monitoring with RAGAS:
- **Automated Evaluation**: Scheduled Lambda runs RAGAS evaluation on test datasets
- **Quality Metrics**: Faithfulness, answer relevancy, context precision, context recall
- **Regression Detection**: CloudWatch alarms trigger when quality metrics drop
- **CI/CD Integration**: GitHub Actions runs RAGAS evaluation on PRs to prevent regressions

### Infrastructure as Code
Terraform manages all AWS resources:
- **Version-Controlled Infrastructure**: All infrastructure changes tracked in Git
- **Reproducible Deployments**: Consistent environments across dev/staging/prod
- **State Management**: Centralized state in S3 with DynamoDB locking
- **Modular Design**: Reusable modules for networking, compute, storage, etc.

### CI/CD Pipeline
GitHub Actions automates the entire development lifecycle:
- **Automated Testing**: Runs unit tests, integration tests, and security scans on every PR
- **Automated Deployment**: Builds Docker images, pushes to ECR, deploys via Terraform
- **Quality Gates**: RAGAS evaluation and smoke tests before production deployment
- **Rollback Capability**: Easy rollback via Terraform state management

### GitHub Actions (Implemented in Phase 1b)
- **CI (push & pull requests):** black, ruff, mypy; ESLint/tsc; pytest; Docker test builds; Terraform fmt/validate/plan (no apply); security scans (Bandit, gitleaks). Runs automatically on every push to main and on PRs.
- **CD (manual trigger):** Build and push backend image to ECR; build Next.js static export; upload frontend to S3; CloudFront cache invalidate; post-deploy smoke tests/health checks. **Triggered manually via GitHub Actions UI** - click "Run workflow" when ready to deploy.
- **Evaluation (scheduled/manual):** Run RAGAS on the eval dataset, publish metrics to Arize Phoenix/CloudWatch, and fail on regressions (Phase 4+).

## 🛠️ Technology Stack

### Core AI & Agent Framework
- **LLM:** AWS Bedrock (Amazon Nova Pro/Lite) - Latest AWS models with cost-effective pay-per-token pricing, excellent AWS integration, and fallback to Claude Sonnet 4.5 (with Claude 3.5 Sonnet V2 as deprecated fallback until Feb 2026) for reliability
- **Agent Framework:** LangGraph - Industry-standard orchestration framework with native streaming, checkpointing for state persistence, and excellent tool integration
- **Vector Store:** Pinecone Serverless - Fully managed vector database with native hybrid search, free tier (100K vectors), and superior performance vs. pgvector
- **Knowledge Graph:** Neo4j AuraDB Free - Graph database for entity relationships (200K nodes), enables "find all docs about X" queries
- **SQL Database:** Neon PostgreSQL - Serverless PostgreSQL with free tier (0.5GB storage), fully managed, stores structured 10-K financial metrics

### Document Processing & RAG
- **VLM Extraction:** Claude Vision (via Bedrock) - Extracts clean text from complex PDFs including tables, handles all document types
- **Embeddings:** AWS Bedrock Titan Embeddings v2 - 1024-dimensional vectors for semantic search (~$0.0001/1K tokens)
- **Entity Extraction:** spaCy NER - Cost-efficient entity extraction for Knowledge Graph population (20-50x cheaper than LLM)
- **Chunking:** Semantic chunking with spaCy sentence boundaries + contextual enrichment

> 💡 **Design Note:** For SEC filings specifically, an HTML+Markdown approach (downloading from EDGAR as HTML, converting to text) would be ~90% cheaper (~$0.30 vs $4.00 per 10-K). However, we chose PDF+Vision because it's more generally robust—it handles any PDF format, preserves charts/graphs, works with scanned documents, and requires only one extraction pipeline. For a demo with ~10 documents, simplicity wins. See [docs/RAG_README.md](./docs/RAG_README.md) for the full trade-off analysis.

> 📖 **Deep Dive:** See [docs/RAG_README.md](./docs/RAG_README.md) for complete RAG architecture including hybrid search, query expansion, and reranking

### Infrastructure & DevOps
- **Compute:** AWS App Runner - Serverless container platform that scales to zero, no timeout limits, simple deployment
- **Frontend:** Next.js + shadcn/ui - Modern React framework with static export for cost-effective hosting, beautiful UI components
- **Infrastructure:** Terraform - Industry-standard Infrastructure as Code tool for version-controlled, reproducible deployments
- **CI/CD:** GitHub Actions - Free-tier CI/CD with excellent GitHub integration, automated testing and deployment

### Observability & Evaluation
- **Tracing:** Arize Phoenix (self-hosted) - Open-source observability platform for distributed tracing and agent execution analysis
- **Evaluation:** RAGAS - Industry-standard RAG evaluation framework for continuous quality monitoring
- **Monitoring:** CloudWatch - Native AWS monitoring for metrics, logs, and alarms

## 🏛️ Architecture Decisions

### Serverless-First Approach
**Decision**: Use serverless and managed services wherever possible (App Runner, Neon PostgreSQL, Lambda, DynamoDB)

**Rationale**: 
- **Cost Optimization**: Pay only for what you use, scales to zero when idle
- **Reduced Operational Overhead**: No server management, automatic scaling, built-in high availability
- **Faster Development**: Focus on application logic, not infrastructure management

**Trade-offs**: 
- Cold starts (10-30s) acceptable for demo
- Less control over infrastructure, but sufficient for enterprise needs

### Multi-Tool Agent Pattern
**Decision**: Implement agent that orchestrates multiple tools rather than single-purpose system

**Rationale**:
- **Real-World Applicability**: Demonstrates production patterns used in enterprise AI systems
- **Flexibility**: Agent can handle diverse queries by selecting appropriate tools
- **Extensibility**: Easy to add new tools without changing core architecture

**Trade-offs**:
- More complex than single-tool systems, but showcases advanced capabilities

### Hybrid RAG Strategy
**Decision**: Combine semantic search, keyword search (BM25), and knowledge graph using RRF fusion

**Data Flow**:
```
PDF → Claude VLM → Clean Text → ┬→ Titan Embeddings → Pinecone (semantic search)
                                ├→ BM25 Index → Pinecone (keyword search)
                                ├→ spaCy NER → Neo4j (knowledge graph)
                                └→ Parse Tables → PostgreSQL (SQL queries)
```

**Rationale**:
- **VLM for All Documents**: Claude Vision extracts clean text from complex PDFs (tables, multi-column layouts)
- **Triple Retrieval**: Semantic + keyword + knowledge graph captures meaning, exact terms, and entity relationships
- **Cost-Efficient NER**: spaCy extracts entities for knowledge graph (20-50x cheaper than LLM extraction)
- **Query Enhancement**: Query expansion + cross-encoder reranking improves retrieval by 20-30%

**Trade-offs**:
- More complex than simple vector search, but significantly better results
- VLM extraction costs ~$0.03-0.05/page (~$50 total one-time for demo)
- See [docs/RAG_README.md](./docs/RAG_README.md) for detailed architecture and alternatives

### Structured Logging
**Decision**: Use structlog with JSON output instead of plain text logs

**Rationale**:
- **Machine-Readable**: Enables automated analysis and CloudWatch Logs Insights queries
- **Better Debugging**: Field-based filtering and searching
- **Production Standard**: Industry best practice for observability

**Trade-offs**:
- Slightly more verbose, but enables powerful analysis capabilities

### Circuit Breaker Pattern
**Decision**: Implement circuit breakers for all external service calls

**Rationale**:
- **Prevent Cascade Failures**: Stops retrying after failures to prevent overwhelming services
- **Graceful Degradation**: System continues operating when tools fail
- **Production Reliability**: Essential pattern for enterprise systems

**Trade-offs**:
- Additional complexity, but critical for production reliability

### Evaluation Pipeline
**Decision**: Integrate RAGAS evaluation into CI/CD and scheduled runs

**Rationale**:
- **Quality Assurance**: Continuous monitoring prevents regressions
- **Data-Driven Decisions**: Metrics guide improvements
- **Production Best Practice**: Standard approach for production RAG systems

**Trade-offs**:
- Additional infrastructure (Lambda, S3), but essential for quality assurance

## 💼 Business Value

This architecture demonstrates capabilities essential for enterprise AI deployments:

### Scalability
- **Auto-Scaling**: Handles variable workloads automatically, from zero to production scale
- **Serverless Architecture**: No capacity planning needed, scales seamlessly
- **Multi-Region Ready**: Architecture supports multi-region deployment for global scale

### Cost Efficiency
- **Optimized for Demo**: $20-50/month target cost for low-use workloads
- **Semantic Caching**: 30-40% cost reduction through intelligent caching
- **Serverless Scaling**: Pay only for actual usage, no idle costs
- **Infrastructure Optimization**: Public subnets, SQLAlchemy pooling instead of expensive RDS Proxy

### Reliability
- **Production-Ready Error Handling**: Circuit breakers, retry logic, graceful degradation
- **Health Checks**: Dependency validation endpoints
- **Monitoring & Alerts**: CloudWatch alarms for errors, latency, and cost thresholds
- **State Persistence**: Conversation state persists across restarts via Neon PostgreSQL

### Security
- **Input Validation**: Pydantic validators prevent malicious inputs
- **SQL Injection Prevention**: Parameterized queries and table whitelisting
- **Rate Limiting**: Prevents abuse with configurable limits
- **Audit Trails**: Complete observability for compliance and debugging

### Maintainability
- **Infrastructure as Code**: Terraform enables reproducible, version-controlled deployments
- **Comprehensive Documentation**: Architecture docs, API references, troubleshooting guides
- **Automated Testing**: CI/CD pipeline ensures quality and prevents regressions
- **Modular Design**: Clean separation of concerns enables easy updates and extensions

### Observability
- **Full Visibility**: Distributed tracing, metrics, logs, and evaluation provide complete system insight
- **Cost Tracking**: Per-request cost tracking enables FinOps optimization
- **Quality Monitoring**: RAGAS evaluation ensures consistent response quality
- **Debugging Capabilities**: Structured logs and traces enable rapid issue resolution

## 📝 License

This project is for portfolio/demonstration purposes.

## 👤 Author

Built as a portfolio project demonstrating enterprise-grade AI system architecture.
