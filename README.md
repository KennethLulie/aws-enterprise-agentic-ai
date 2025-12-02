# Enterprise Agentic AI Demo

An enterprise-grade agentic AI system on AWS demonstrating multi-tool orchestration, RAG, real-time streaming, and cost-optimized architecture.

## 🎯 Project Overview

This project showcases a production-ready AI agent system with:
- **Multi-tool orchestration** (Web Search, SQL Query, RAG Retrieval)
- **Input/Output verification** with SLMs
- **Streaming thought process** visualization
- **Inference caching** for cost optimization
- **Full observability** with Arize Phoenix
- **RAG evaluation** with RAGAS
- **Automated document ingestion** from S3
- **Password-protected** web interface
- **Infrastructure as Code** with Terraform
- **CI/CD** with GitHub Actions

**Target Cost:** $20-50/month for low-use portfolio demo  
**AWS Region:** us-east-2 (Ohio)  
**Architecture:** Scalable, enterprise-ready, cost-optimized

## 📋 Project Status

**Current Phase:** Planning Complete - Ready for Phase 0 (Local Development)

This repository contains the complete project plan and architecture documentation. Implementation will begin with Phase 0.

## 📚 Documentation

- **[PROJECT_PLAN.md](./PROJECT_PLAN.md)** - Complete project plan with all phases, architecture, and implementation details
- **[PLAN_SUMMARY.md](./PLAN_SUMMARY.md)** - Quick reference summary of key decisions
- **[DOCUMENTATION_STATUS.md](./DOCUMENTATION_STATUS.md)** - Documentation status tracking

### Review Documents (Historical)
- `FINAL_REVIEW.md` - Initial comprehensive review
- `FINAL_COMPREHENSIVE_REVIEW.md` - Phase 1 scope review
- `EXPERT_REVIEW.md` - Expert architecture review
- `ARCHITECTURE_REVIEW.md` - Architecture-specific review
- `PLAN_REVIEW.md` - Plan review

## 🏗️ Architecture

```
Frontend (Next.js Static) → CloudFront → S3
                              ↓
                    Password Protection
                              ↓
Backend (AWS App Runner) → LangGraph Agent
                              ↓
        ┌──────────┬──────────┴──────────┬──────────┐
        ↓          ↓                      ↓          ↓
    Bedrock    Tavily Search          Aurora SQL   Pinecone RAG
    (Nova)     (Web Search)           (PostgreSQL) (Vector Store)
```

## 🚀 Quick Start (Coming Soon)

This project is currently in planning phase. Implementation will follow this structure:

- **Phase 0:** Local development environment
- **Phase 1a:** Minimal MVP (basic chat interface)
- **Phase 1b:** Production hardening (persistent state, CI/CD)
- **Phase 2:** Core agent tools (Search, SQL, RAG)
- **Phase 3+:** Advanced features (verification, caching, observability, evaluation)

See [PROJECT_PLAN.md](./PROJECT_PLAN.md) for complete details.

## 🛠️ Technology Stack

- **LLM:** AWS Bedrock (Amazon Nova Pro/Lite)
- **Agent Framework:** LangGraph
- **Vector Store:** Pinecone Serverless
- **SQL Database:** Aurora Serverless v2 PostgreSQL
- **Compute:** AWS App Runner
- **Frontend:** Next.js + shadcn/ui
- **Infrastructure:** Terraform
- **CI/CD:** GitHub Actions

## 📝 License

This project is for portfolio/demonstration purposes.

## 👤 Author

Built as a portfolio project demonstrating enterprise-grade AI system architecture.

