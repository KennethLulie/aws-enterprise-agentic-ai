# Repository State Tracker

**Purpose:** This file is the authoritative source for what files exist in the repository. Before referencing a file in documentation, check this file to verify it exists.

**Last Updated:** 2026-01-12 (Phase 1b: Rate limiting middleware added)

---

## Currently Existing Files

### Project Root - Documentation
| File | Purpose |
|------|---------|
| README.md | Project overview and quick start |
| PROJECT_PLAN.md | Complete project plan with all phases |
| DEVELOPMENT_REFERENCE.md | Phase-specific implementation details |
| PHASE_1A_HOW_TO_GUIDE.md | Step-by-step Phase 1a guide (AWS deployment) |
| PHASE_1B_HOW_TO_GUIDE.md | Step-by-step Phase 1b guide (Production hardening) |
| REPO_STATE.md | This file - tracks repository state |

### Project Root - Configuration
| File | Purpose |
|------|---------|
| .gitignore | Git ignore patterns (Python, Node.js, env files, IDE, OS) |
| .gitattributes | Git attributes (line endings, binaries, platform defaults) |
| .env.example | Environment variable template (copy to .env) |
| .pre-commit-config.yaml | Pre-commit hooks configuration (black, ruff, mypy, pytest) |
| .gitleaks.toml | Gitleaks secret scanning rules |
| .secrets.baseline | detect-secrets baseline |
| docker-compose.yml | Docker Compose configuration (backend + frontend services) |

### Cursor Rules Directory (.cursor/rules/)
| File | Purpose |
|------|---------|
| .cursor/rules/_project.mdc | Project context, sources of truth, phase-specific patterns (alwaysApply: true) |
| .cursor/rules/_security.mdc | Secrets, SQL safety, validation, authentication (alwaysApply: true) |
| .cursor/rules/_workflow.mdc | Docker-first development, research-first, verification (alwaysApply: true) |
| .cursor/rules/agent.mdc | LangGraph agent patterns, tool calling, orchestration (globs: backend/src/agent/**) |
| .cursor/rules/aws.mdc | AWS configuration, region, credentials, Secrets Manager (alwaysApply: true) |
| .cursor/rules/backend.mdc | Python development rules (globs: backend/**) |
| .cursor/rules/docs.mdc | Documentation rules (globs: docs/**, *.md) |
| .cursor/rules/frontend.mdc | TypeScript/React rules (globs: frontend/**) |
| .cursor/rules/howtoguide.mdc | How-to guide generation patterns, structure, prompts (globs: *HOW_TO_GUIDE*.md) |
| .cursor/rules/infrastructure.mdc | Terraform and AWS infrastructure patterns (globs: terraform/**) |

### Backend Directory
| File | Purpose |
|------|---------|
| backend/Dockerfile | Production Docker image (multi-stage, non-root user) |
| backend/Dockerfile.dev | Development Docker image |
| backend/requirements.txt | Python dependencies |
| backend/pytest.ini | Pytest configuration |
| backend/src/__init__.py | Backend package marker |
| backend/src/config/__init__.py | Configuration package |
| backend/src/config/settings.py | Pydantic settings with AWS Secrets Manager integration, ALLOWED_ORIGINS |
| backend/src/api/__init__.py | API package marker |
| backend/src/api/main.py | FastAPI application factory with CORS, rate limiting, v1 API routes |
| backend/src/api/middleware/__init__.py | API middleware package |
| backend/src/api/middleware/logging.py | CloudWatch-compatible structlog configuration |
| backend/src/api/middleware/rate_limit.py | IP-based rate limiting using slowapi (10 req/min default) |
| backend/src/api/routes/__init__.py | API routes package |
| backend/src/api/routes/auth.py | Demo password login route |
| backend/src/api/routes/chat.py | Chat API endpoints with streaming, rate limiting (10 req/min) |
| backend/src/api/routes/health.py | Health check endpoint |
| backend/src/api/routes/v1/__init__.py | V1 router aggregation, includes chat router |
| backend/src/api/routes/v1/chat.py | Versioned chat endpoints (/api/v1/chat) with rate limiting |
| backend/src/agent/__init__.py | Agent package with get_agent(), checkpointer exports, tool utilities |
| backend/src/agent/graph.py | LangGraph graph definition, build_graph(), get_checkpointer() |
| backend/src/agent/state.py | Agent state schema (TypedDict) |
| backend/src/agent/nodes/__init__.py | Agent nodes package |
| backend/src/agent/nodes/chat.py | Chat node with LLM invocation |
| backend/src/agent/nodes/tools.py | Tool execution node |
| backend/src/agent/nodes/error_recovery.py | Error recovery node |
| backend/src/agent/tools/__init__.py | Tools package exports |
| backend/src/agent/tools/market_data.py | FMP market data tool (mock-friendly) |
| backend/src/agent/tools/rag.py | RAG retrieval tool stub |
| backend/src/agent/tools/search.py | Tavily search tool |
| backend/src/agent/tools/sql.py | SQL query tool stub |
| backend/src/cache/__init__.py | Cache package (Phase 4+ placeholders) |
| backend/src/db/__init__.py | Database package exports (SQLAlchemy session management) |
| backend/src/db/session.py | SQLAlchemy engine, session, connection pooling |
| backend/src/ingestion/__init__.py | Data ingestion package (Phase 2+ placeholders) |
| backend/src/utils/__init__.py | Utility helpers package |
| backend/tests/__init__.py | Tests package |
| backend/tests/test_agent.py | Agent and graph tests |
| backend/tests/test_api.py | API endpoint tests |
| backend/tests/test_tools.py | Tool tests (mock/live scenarios) |
| backend/scripts/verify_code_quality.py | Code quality verification report generator |
| backend/alembic.ini | Alembic migration configuration |
| backend/alembic/README | Alembic directory readme |
| backend/alembic/env.py | Alembic migration environment (dynamic DATABASE_URL) |
| backend/alembic/script.py.mako | Alembic migration script template |

### Frontend Directory
| File | Purpose |
|------|---------|
| frontend/Dockerfile.dev | Development Docker image |
| frontend/package.json | Node.js dependencies |
| frontend/package-lock.json | NPM lock file |
| frontend/next.config.ts | Next.js configuration (static export) |
| frontend/tsconfig.json | TypeScript configuration |
| frontend/components.json | shadcn/ui configuration |
| frontend/eslint.config.mjs | ESLint configuration |
| frontend/postcss.config.mjs | PostCSS configuration |
| frontend/src/app/layout.tsx | Root layout |
| frontend/src/app/page.tsx | Chat page with streaming (fixed TypeScript types) |
| frontend/src/app/login/page.tsx | Login page |
| frontend/src/app/globals.css | Global styles and Tailwind imports |
| frontend/src/components/ui/button.tsx | shadcn/ui Button component |
| frontend/src/components/ui/card.tsx | shadcn/ui Card components |
| frontend/src/components/ui/dialog.tsx | shadcn/ui Dialog component |
| frontend/src/components/ui/input.tsx | shadcn/ui Input component |
| frontend/src/components/ui/sonner.tsx | shadcn/ui Sonner toast component |
| frontend/src/lib/api.ts | API client with SSE support (fixed TypeScript type validation) |
| frontend/src/lib/utils.ts | Utility functions (cn for classnames) |

### Documentation Directory
| File | Purpose |
|------|---------|
| docs/README.md | Documentation directory overview |
| docs/SECURITY.md | Security and secrets management guide |
| docs/integration-test-checklist.md | Phase 0 end-to-end test checklist |
| docs/completed-phases/PHASE_0_HOW_TO_GUIDE.md | Completed Phase 0 guide (archived) |
| docs/completed-phases/PHASE_1A_HOW_TO_GUIDE.md | Completed Phase 1a guide (archived) |

### Scripts Directory
| File | Purpose |
|------|---------|
| scripts/README.md | Scripts directory overview |
| scripts/setup.sh | One-time setup script |
| scripts/dev.sh | Dev helper script (start/stop/logs/test/shell/clean) |
| scripts/validate_setup.py | Prerequisites validation script |

### Terraform Directory
| File | Purpose |
|------|---------|
| terraform/environments/dev/backend.tf | Terraform S3 backend configuration |
| terraform/environments/dev/.terraform.lock.hcl | Provider version lock file (commit to VCS) |
| terraform/environments/dev/main.tf | Dev environment module calls |
| terraform/environments/dev/variables.tf | Dev environment variables (placeholder) |
| terraform/environments/dev/outputs.tf | Dev environment output values |
| terraform/modules/networking/main.tf | VPC, subnets, IGW, route tables, security group |
| terraform/modules/networking/variables.tf | Networking module variables |
| terraform/modules/networking/outputs.tf | Networking module outputs |
| terraform/modules/ecr/main.tf | ECR repository and lifecycle policy |
| terraform/modules/ecr/variables.tf | ECR module variables |
| terraform/modules/ecr/outputs.tf | ECR module outputs |
| terraform/modules/secrets/main.tf | Secrets Manager data sources and IAM policy |
| terraform/modules/secrets/variables.tf | Secrets module variables |
| terraform/modules/secrets/outputs.tf | Secrets module outputs |
| terraform/modules/app-runner/main.tf | App Runner service and IAM roles |
| terraform/modules/app-runner/variables.tf | App Runner module variables |
| terraform/modules/app-runner/outputs.tf | App Runner module outputs |
| terraform/modules/s3-cloudfront/main.tf | S3 bucket, CloudFront distribution, OAC |
| terraform/modules/s3-cloudfront/variables.tf | S3/CloudFront module variables |
| terraform/modules/s3-cloudfront/outputs.tf | S3/CloudFront module outputs |

---

## Planned Files (Do Not Exist Yet)

### Phase 1b - Production Hardening
| File | Purpose |
|------|---------|
| .github/workflows/ci.yml | CI pipeline (lint, test, validate) |
| .github/workflows/deploy.yml | CD pipeline (build, deploy, test) |
| Note: Using Neon PostgreSQL (external) - no Aurora module needed |
| Note: LangGraph checkpoint tables are created by PostgresSaver.setup(), not Alembic |

### Phase 2+ - Advanced Features
| File | Purpose |
|------|---------|
| backend/src/ingestion/semantic_chunking.py | Grammar-aware text chunking (spaCy) |
| backend/src/ingestion/contextual_chunking.py | Context-preserving chunking |
| backend/src/knowledge_graph/__init__.py | Knowledge graph package (Neo4j) |
| backend/src/knowledge_graph/efficient_extractor.py | NLP entity extraction (spaCy) |
| backend/src/knowledge_graph/store.py | Neo4j graph store adapter |
| backend/src/knowledge_graph/queries.py | Graph traversal queries |
| backend/src/knowledge_graph/ontology.py | Financial domain ontology |
| backend/src/utils/reranker.py | Cross-encoder reranking (Phase 2 RAG) |
| lambda/document-ingestion/handler.py | S3-triggered document processing |
| terraform/modules/lambda/main.tf | Lambda infrastructure |

### Phase 2+ - To Be Created

**Knowledge Graph & 2025 SOTA RAG:**
| File | Purpose |
|------|---------|
| backend/src/ingestion/semantic_chunking.py | Grammar-aware chunking (spaCy) |
| backend/src/ingestion/contextual_chunking.py | Context prepending for chunks |
| backend/src/knowledge_graph/__init__.py | KG package (Neo4j) |
| backend/src/knowledge_graph/efficient_extractor.py | NLP entity extraction (spaCy) |
| backend/src/knowledge_graph/store.py | Neo4j graph store adapter |
| backend/src/knowledge_graph/queries.py | Graph traversal queries |
| backend/src/knowledge_graph/ontology.py | Financial domain ontology |
| backend/src/utils/reranker.py | Cross-encoder reranking |

**Lambda & Infrastructure:**
| File | Purpose |
|------|---------|
| lambda/document-ingestion/handler.py | Doc processing |
| terraform/modules/lambda/main.tf | Lambda infrastructure |

---

## Update Instructions

**When creating a new file:**
1. Add it to "Currently Existing Files" section
2. Remove from "Planned Files" if it was listed there
3. Update any documentation that referenced it as planned

**When deleting a file:**
1. Remove from "Currently Existing Files"
2. Search docs for references: `grep -r "filename" *.md`
3. Update or remove all references

**When renaming/moving a file:**
1. Update the path in "Currently Existing Files"
2. Search and update all references in documentation

---

## Validation Command

Run this to check for broken documentation links:
```bash
# Find markdown links to files and verify they exist
grep -roh '\[.*\](\./[^)]*' *.md docs/*.md | while read link; do
  file=$(echo "$link" | sed 's/.*(\.\///' | sed 's/)$//' | sed 's/#.*//')
  [ -f "$file" ] || echo "MISSING: $file (from link: $link)"
done
```
