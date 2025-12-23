# Repository State Tracker

**Purpose:** This file is the authoritative source for what files exist in the repository. Before referencing a file in documentation, check this file to verify it exists.

**Last Updated:** 2025-12-22 (Synchronized with current Phase 0 implementation - complete backend and frontend structure)

---

## Currently Existing Files

### Project Root - Documentation
| File | Purpose |
|------|---------|
| README.md | Project overview and quick start |
| PROJECT_PLAN.md | Complete project plan with all phases |
| DEVELOPMENT_REFERENCE.md | Phase-specific implementation details |
| PHASE_0_HOW_TO_GUIDE.md | Step-by-step Phase 0 guide |
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
| .cursor/rules/general.mdc | Core project rules, Docker-first, phase tracking |
| .cursor/rules/backend.mdc | Python development rules (globs: backend/**) |
| .cursor/rules/frontend.mdc | TypeScript/React rules (globs: frontend/**) |
| .cursor/rules/security.mdc | Secrets, SQL safety, validation rules |
| .cursor/rules/docs.mdc | Documentation rules (globs: docs/**, *.md) |
| .cursor/rules/agentic-ai.mdc | Agentic AI patterns - LangGraph, tool orchestration (globs: backend/src/agent/**) |

### Backend Directory
| File | Purpose |
|------|---------|
| backend/Dockerfile.dev | Development Docker image |
| backend/requirements.txt | Python dependencies |
| backend/pytest.ini | Pytest configuration |
| backend/src/__init__.py | Backend package marker |
| backend/src/config/__init__.py | Configuration package |
| backend/src/config/settings.py | Pydantic settings with environment and FMP config |
| backend/src/api/__init__.py | API package marker |
| backend/src/api/main.py | FastAPI application factory |
| backend/src/api/middleware/__init__.py | API middleware package |
| backend/src/api/routes/__init__.py | API routes package |
| backend/src/api/routes/auth.py | Demo password login route |
| backend/src/api/routes/chat.py | Chat API endpoints with streaming |
| backend/src/api/routes/health.py | Health check endpoint |
| backend/src/api/routes/v1/__init__.py | Versioned API routes (Phase 1b+) |
| backend/src/agent/__init__.py | Agent package marker |
| backend/src/agent/graph.py | LangGraph tool registration |
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
| backend/src/ingestion/__init__.py | Data ingestion package (Phase 2+ placeholders) |
| backend/src/utils/__init__.py | Utility helpers package |
| backend/tests/__init__.py | Tests package |
| backend/tests/test_agent.py | Agent and graph tests |
| backend/tests/test_api.py | API endpoint tests |
| backend/tests/test_tools.py | Tool tests (mock/live scenarios) |
| backend/scripts/verify_code_quality.py | Code quality verification report generator |

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
| frontend/src/app/page.tsx | Chat page with streaming |
| frontend/src/app/login/page.tsx | Login page |
| frontend/src/app/globals.css | Global styles and Tailwind imports |
| frontend/src/components/ui/button.tsx | shadcn/ui Button component |
| frontend/src/components/ui/card.tsx | shadcn/ui Card components |
| frontend/src/components/ui/dialog.tsx | shadcn/ui Dialog component |
| frontend/src/components/ui/input.tsx | shadcn/ui Input component |
| frontend/src/components/ui/sonner.tsx | shadcn/ui Sonner toast component |
| frontend/src/lib/api.ts | API client with SSE support |
| frontend/src/lib/utils.ts | Utility functions (cn for classnames) |

### Documentation Directory
| File | Purpose |
|------|---------|
| docs/SECURITY.md | Security and secrets management guide |
| docs/integration-test-checklist.md | Phase 0 end-to-end test checklist |

### Scripts Directory
| File | Purpose |
|------|---------|
| scripts/README.md | Scripts directory overview |
| scripts/setup.sh | One-time setup script |
| scripts/dev.sh | Dev helper script (start/stop/logs/test/shell/clean) |
| scripts/validate_setup.py | Prerequisites validation script |

---

## Planned Files (Do Not Exist Yet)

### Phase 1a - Infrastructure & Deployment
| File | Purpose |
|------|---------|
| terraform/environments/dev/main.tf | Dev environment infrastructure |
| terraform/environments/dev/backend.tf | Terraform state configuration |
| terraform/modules/networking/main.tf | VPC and subnet configuration |
| terraform/modules/app-runner/main.tf | App Runner service configuration |
| terraform/modules/s3-cloudfront/main.tf | Frontend hosting infrastructure |

### Phase 1b - Production Hardening
| File | Purpose |
|------|---------|
| .github/workflows/ci.yml | CI pipeline (lint, test, validate) |
| .github/workflows/deploy.yml | CD pipeline (build, deploy, test) |
| terraform/modules/aurora/main.tf | Aurora Serverless v2 database |
| lambda/warm_app_runner/handler.py | App Runner warmup Lambda function |

### Phase 2+ - Advanced Features
| File | Purpose |
|------|---------|
| backend/src/ingestion/semantic_chunking.py | Grammar-aware text chunking (spaCy) |
| backend/src/ingestion/contextual_chunking.py | Context-preserving chunking |
| backend/src/knowledge_graph/__init__.py | Knowledge graph package |
| backend/src/knowledge_graph/efficient_extractor.py | NLP entity extraction (spaCy) |
| backend/src/knowledge_graph/store.py | Neo4j/PostgreSQL graph store |
| backend/src/knowledge_graph/queries.py | Graph traversal queries |
| backend/src/knowledge_graph/ontology.py | Financial domain ontology |
| backend/src/utils/reranker.py | Cross-encoder reranking (Phase 2 RAG) |
| lambda/document-ingestion/handler.py | S3-triggered document processing |
| terraform/modules/lambda/main.tf | Lambda infrastructure |

**Scripts (Section 8):**
| File | Target Section | Purpose |
|------|---------------|---------|

### Phase 1a - To Be Created
| File | Purpose |
|------|---------|
| terraform/environments/dev/main.tf | Dev environment |
| terraform/environments/dev/backend.tf | Terraform state |
| terraform/modules/networking/main.tf | VPC and subnets |
| terraform/modules/app-runner/main.tf | App Runner service |
| terraform/modules/s3-cloudfront/main.tf | Frontend hosting |

### Phase 1b - To Be Created
| File | Purpose |
|------|---------|
| .github/workflows/ci.yml | CI pipeline |
| .github/workflows/deploy.yml | CD pipeline |
| terraform/modules/aurora/main.tf | Aurora database |
| lambda/warm_app_runner/handler.py | Warmup Lambda |

### Phase 2+ - To Be Created

**Knowledge Graph & 2025 SOTA RAG:**
| File | Purpose |
|------|---------|
| backend/src/ingestion/semantic_chunking.py | Grammar-aware chunking (spaCy) |
| backend/src/ingestion/contextual_chunking.py | Context prepending for chunks |
| backend/src/knowledge_graph/__init__.py | KG package |
| backend/src/knowledge_graph/efficient_extractor.py | NLP entity extraction (spaCy) |
| backend/src/knowledge_graph/store.py | Neo4j/PostgreSQL adapter |
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
