# Repository State Tracker

**Purpose:** This file is the authoritative source for what files exist in the repository. Before referencing a file in documentation, check this file to verify it exists.

**Last Updated:** 2025-12-09 (Added 2025 SOTA RAG with Knowledge Graph plan)

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
| .gitignore | Git ignore patterns |
| .gitattributes | Git attributes (line endings, binaries, platform defaults) |
| .env.example | Environment variable template (copy to .env) |
| .pre-commit-config.yaml | Pre-commit hooks configuration |
| .gitleaks.toml | Gitleaks secret scanning rules |
| .secrets.baseline | detect-secrets baseline |
| docker-compose.yml | Docker Compose configuration |

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

### Frontend Directory
| File | Purpose |
|------|---------|
| frontend/Dockerfile.dev | Development Docker image |

### Documentation Directory
| File | Purpose |
|------|---------|
| docs/SECURITY.md | Security and secrets management guide |

### Scripts Directory
| File | Purpose |
|------|---------|
| scripts/README.md | Scripts directory placeholder |

---

## Planned Files (Do Not Exist Yet)

### Phase 0 - To Be Created During Implementation

**Backend Source (Section 3-5):**
| File | Target Section | Purpose |
|------|---------------|---------|
| backend/src/__init__.py | 2.1a | Package marker |
| backend/src/config/__init__.py | 3.2 | Config package |
| backend/src/config/settings.py | 3.2 | Pydantic settings |
| backend/src/api/__init__.py | 3.3 | API package |
| backend/src/api/main.py | 3.3 | FastAPI application |
| backend/src/api/routes/__init__.py | 3.4 | Routes package |
| backend/src/api/routes/health.py | 3.4 | Health check endpoint |
| backend/src/agent/__init__.py | 4.1 | Agent package |
| backend/src/agent/state.py | 4.1 | Agent state schema |
| backend/src/agent/graph.py | 4.5 | LangGraph definition |
| backend/src/agent/nodes/__init__.py | 4.2 | Nodes package |
| backend/src/agent/nodes/chat.py | 4.2 | Chat node |
| backend/src/agent/nodes/tools.py | 4.3 | Tool execution node |
| backend/src/agent/nodes/error_recovery.py | 4.4 | Error recovery |
| backend/src/agent/tools/__init__.py | 5.1 | Tools package |
| backend/src/agent/tools/search.py | 5.2 | Search tool stub |
| backend/src/agent/tools/sql.py | 5.3 | SQL tool stub |
| backend/src/agent/tools/rag.py | 5.4 | RAG tool stub |
| backend/src/agent/tools/weather.py | 5.5 | Weather tool stub |

**Backend Tests (Section 9):**
| File | Target Section | Purpose |
|------|---------------|---------|
| backend/tests/__init__.py | 9.2 | Tests package |
| backend/tests/test_agent.py | 9.3 | Agent tests |
| backend/tests/test_tools.py | 9.4 | Tool tests |
| backend/tests/test_api.py | 9.5 | API tests |
| backend/pytest.ini | 9.1 | Pytest configuration |

**Frontend Source (Section 6):**
| File | Target Section | Purpose |
|------|---------------|---------|
| frontend/package.json | 6.1 | Node.js dependencies |
| frontend/next.config.js | 6.2 | Next.js configuration |
| frontend/tsconfig.json | 6.1 | TypeScript config |
| frontend/src/app/layout.tsx | 6.7 | Root layout |
| frontend/src/app/page.tsx | 6.6 | Chat page |
| frontend/src/app/login/page.tsx | 6.4 | Login page |
| frontend/src/lib/api.ts | 6.5 | API client |

**Scripts (Section 8):**
| File | Target Section | Purpose |
|------|---------------|---------|
| scripts/setup.sh | 8.1 | One-time setup |
| scripts/validate_setup.py | 8.2 | Validation script |
| scripts/dev.sh | 8.3 | Dev helper script |

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

