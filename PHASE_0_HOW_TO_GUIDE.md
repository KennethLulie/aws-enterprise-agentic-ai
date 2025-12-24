# Phase 0: Local Development Environment - Complete How-To Guide

## ✅ PHASE 0 COMPLETE - Ready for Phase 1a MVP

**Status:** All Phase 0 deliverables successfully implemented and verified ✅

**Completion Date:** December 23, 2025

**Verified:** Full end-to-end testing completed with streaming chat working

---

**Purpose:** This guide provides step-by-step instructions for implementing Phase 0, including all commands, agent prompts, verification steps, and file specifications.

**Estimated Time:** 4-6 hours for complete implementation

**Prerequisites:** Complete all prerequisites in Section 1 before starting implementation.

**⚠️ Important:** This guide follows a Docker-first approach. Dependencies are installed via Docker builds, not locally. Some verification commands in early sections require Docker to be set up first (Section 7). See "Important Notes About Execution Order" section for details.

**🖥️ Development Environment:** This guide is written for **Windows with WSL 2** (Windows Subsystem for Linux). All terminal commands should be run in your WSL terminal (Ubuntu), not PowerShell or Command Prompt. Docker Desktop should be configured to use the WSL 2 backend.

---

## Table of Contents

- [Quick Start Workflow Summary](#quick-start-workflow-summary)
- [Windows/WSL Development Setup](#windowswsl-development-setup)
- [Prerequisites and Setup](#1-prerequisites-and-setup)
- [Initial Project Structure](#2-initial-project-structure)
- [Backend Foundation](#3-backend-foundation)
- [LangGraph Agent Core](#4-langgraph-agent-core)
- [Basic Tools (Stubs)](#5-basic-tools-stubs)
- [Frontend Foundation](#6-frontend-foundation)
- [Docker Compose Setup](#7-docker-compose-setup)
- [Development Scripts](#8-development-scripts)
- [Testing Foundation](#9-testing-foundation)
- [Pre-commit Hooks](#10-pre-commit-hooks)
- [Real Tool Integration](#11-real-tool-integration)
- [Verification and Testing](#12-verification-and-testing)
- [Important Notes About Execution Order](#important-notes-about-execution-order)
- [Phase 0 Completion Checklist](#phase-0-completion-checklist)
- [Common Issues and Solutions](#common-issues-and-solutions)
- [File Inventory](#13-file-inventory)
- [Branch Management and Next Steps](#branch-management-and-next-steps)

---

## Quick Start Workflow Summary

**Overall Phase 0 Workflow:**
1. **Prerequisites** (Section 1): Install Docker, Python, Node.js, AWS CLI, get API keys
2. **Project Structure** (Section 2): Create directories, Git init, .env setup
3. **Backend Foundation** (Section 3): Create config, FastAPI app, health endpoint
4. **Agent Core** (Section 4): LangGraph agent, state, nodes, graph
5. **Tools** (Section 5): Create tool stubs (search, SQL, RAG, market data)
6. **Frontend** (Section 6): Next.js setup, login page, chat interface
7. **Docker Setup** (Section 7): Dockerfiles, docker-compose.yml, **test startup**
8. **Scripts** (Section 8): Development helper scripts
9. **Testing** (Section 9): Pytest setup, test files
10. **Pre-commit** (Section 10): Code quality hooks
11. **Real Tools** (Section 11): Enable real Tavily search and FMP market data APIs
12. **Verification** (Section 12): End-to-end testing

**Phase 0 default:** Tavily search and FMP market data run in mock mode unless you provide API keys. Keep them mocked while stabilizing MVP login + chat; add keys only after tests pass.

**Key Principle:** Docker-first development - all code runs in containers, dependencies installed via Docker, no local venv or npm install needed.

**Execution Context Clarification:**
- **On Host (WSL):** Initial project setup (Git init, directory creation, .env setup), install host tools (Node 20+ via nvm, Python 3.11+ for pre-commit, AWS CLI v2), run `npx create-next-app` and `npx shadcn-ui`
- **In Docker:** All Python/Node runtime, development, testing, running services after scaffolding
- **Paths:** Work from WSL paths (e.g., `~/Projects/aws-enterprise-agentic-ai`), not `/mnt/c/...`, for fast volumes and reliable file watching
- **Quick start for location:** After opening your WSL terminal, run `cd ~/Projects/aws-enterprise-agentic-ai` before any commands.

**Estimated Time:** 4-6 hours for complete implementation

---

## Windows/WSL Development Setup

This project is developed on **Windows with WSL 2** (Windows Subsystem for Linux). Follow these guidelines for the best experience.

### WSL 2 Requirements

1. **Windows 10 version 2004+** or **Windows 11**
2. **WSL 2** with Ubuntu 24.04 (or 22.04)
3. **Docker Desktop** with WSL 2 backend enabled

### Initial WSL Setup

**If WSL is not installed:**
```powershell
# Run in PowerShell as Administrator
wsl --install -d Ubuntu-24.04
```

**Verify WSL 2 is being used:**
```powershell
# Run in PowerShell
wsl -l -v
# Should show Ubuntu with VERSION 2
```

### Docker Desktop Configuration

1. Open Docker Desktop → Settings → General
2. ✅ Enable "Use the WSL 2 based engine"
3. Go to Settings → Resources → WSL Integration
4. ✅ Enable integration with your Ubuntu distro
5. Click "Apply & Restart"
6. Back in WSL, confirm: `docker --version` and `docker compose version`

### Where to Run Commands

| Command Type | Where to Run |
|-------------|--------------|
| All development commands | WSL terminal (Ubuntu) |
| Docker commands | WSL terminal (Ubuntu) |
| Git commands | WSL terminal (Ubuntu) |
| `chmod +x` scripts | WSL terminal (Ubuntu) |
| Opening Cursor/VS Code | Windows (with WSL extension) |

**Open the project from WSL:** In your WSL terminal, `cd ~/Projects/aws-enterprise-agentic-ai` then run `cursor .` (or `code .`). Avoid opening from Windows Explorer paths.

### Opening Project in Cursor/VS Code

**From WSL terminal:**
```bash
# Navigate to project directory in WSL
cd ~/Projects/aws-enterprise-agentic-ai

# Open in Cursor (or VS Code)
cursor .
# or: code .
```

**Important:** Always open the project from WSL to ensure file watchers and Docker volume mounts work correctly.

### File System Performance

For best performance, keep your project files in the WSL filesystem (e.g., `~/Projects/`), NOT in `/mnt/c/` (Windows filesystem). Docker volume mounts are significantly faster with native WSL paths.

### Path Format Reference

| Context | Path Format | Example |
|---------|-------------|---------|
| WSL terminal | Linux paths | `~/Projects/aws-enterprise-agentic-ai` |
| Docker volumes | Linux paths | `./backend:/app` |
| Windows Explorer | `\\wsl$\Ubuntu\...` | `\\wsl$\Ubuntu\home\user\Projects` |

---

## 1. Prerequisites and Setup

### What We're Doing
Before writing any code, we need to ensure all required tools, services, and accounts are set up. This prevents "works on my machine" issues and ensures smooth development.

### Why This Matters
- **External Services:** Pinecone, Tavily, and AWS Bedrock require account setup and API keys
- **Local Tools:** Docker, Python, Node.js must be installed and configured
- **AWS Access:** Bedrock model access must be approved before testing
- **Time Savings:** Setting up prerequisites first prevents mid-development blockers

### Common Issues
- **Bedrock Access Denied:** Most common issue - model access not approved (takes 1-24 hours)
- **Docker Permissions:** User not in docker group on Linux
- **API Keys Missing:** Forgetting to add keys to `.env` causes 401 errors
- **Python/Node Version Mismatch:** Using wrong versions causes compatibility issues

### Step-by-Step Prerequisites

**Host vs Container Responsibilities (Phase 0)**
- Host (WSL): Install toolchain only (Node 20+ via nvm, Python 3.11+ for pre-commit, AWS CLI v2, Git); run scaffolding commands (`npx create-next-app`, `npx shadcn`), pre-commit, and AWS auth. Work from WSL paths (e.g., `~/Projects/aws-enterprise-agentic-ai`), not `/mnt/c/...`.
- Containers: All runtime dependencies and services run in Docker (backend, frontend, tests, installs). Do not create a host venv or run `npm install` beyond the initial scaffolding commands.
- Before running commands: `cd ~/Projects/aws-enterprise-agentic-ai` in your WSL terminal (avoid `/mnt/c/...`).

#### 1.1 Verify Local Tools

**Command (run in WSL terminal):**
# "bash" command changes the terminal from powershell to bash
```bash
# Verify you're in WSL (should show "Linux")
uname -a

# Check Docker (requires Docker Desktop running with WSL integration)
docker --version
docker compose version  # Note: 'docker compose' (no hyphen) is the modern syntax

# Check Python
python3 --version  # Should be 3.11+

# Check Node.js (optional, for local npm commands)
node --version  # Should be 20+

# Check AWS CLI
aws --version  # Should be v2

# Check Git
git --version
```

**Note:** If Docker commands fail, ensure Docker Desktop is running and WSL integration is enabled (Settings → Resources → WSL Integration).
- Quick Docker Desktop verification (WSL): after enabling WSL integration, run `docker --version` and `docker compose version` in WSL to confirm connectivity.

**Expected Output:**
- Docker: 24.0+ or 20.10+
- Python: 3.11.0 or higher
- Node.js: 20.0.0 or higher (if installed)
- AWS CLI: aws-cli/2.x.x
- Git: 2.x.x

**Location:** Run these checks and installs from WSL paths (e.g., `~/Projects/aws-enterprise-agentic-ai`), not `/mnt/c/...`, for fast Docker volumes and reliable file watching.

**If Missing (install in WSL, not Windows):**
- **Docker:** Install Docker Desktop from https://www.docker.com/products/docker-desktop and enable WSL 2 integration
- **Python (WSL):** Install Python 3.11+ in WSL (host Python is mainly for pre-commit; runtime is in Docker). If only Python 3.12 is present, also install 3.11 or adjust pre-commit `language_version`.
- **Node.js (WSL):** Install Node 20+ in WSL (not Windows). Recommended: nvm  
```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
source ~/.bashrc
nvm install 20 && nvm use 20
node --version
```
- If `nvm` is not found, open a new terminal or `source ~/.bashrc`.
- Alternative (fallback): NodeSource for Ubuntu 22/24 (if nvm fails) — install in WSL only.
- **AWS CLI (WSL):** Install AWS CLI v2 inside WSL (not Windows). Use the official installer and keep CLI usage inside WSL for Docker-first workflows.  
  ```bash
  cd /tmp
  curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
  unzip -q awscliv2.zip
  sudo ./aws/install           # use --update to upgrade an existing install
  aws --version && which aws   # verify v2 and path (should be /usr/local/bin/aws)
  aws --help | head -n 3       # quick sanity
  rm -rf aws awscliv2.zip      # cleanup installer artifacts
  ```
  - Verification (after configuration): `aws sts get-caller-identity`
  - If you prefer SSO: `aws configure sso` in WSL and use that profile
- **Git:** Install from https://git-scm.com/downloads (or `sudo apt install git` in WSL)

**Region and paths:** Use `us-east-1` consistently (AWS/Pinecone). Keep all work and installs in WSL paths (e.g., `~/Projects/aws-enterprise-agentic-ai`), not `/mnt/c/...`.

#### 1.2 Configure AWS CLI 

**Create a project-specific IAM user (personal account):**
- Sign in to the AWS console (personal account, not root for daily use).
- IAM → Users → Create user → Name: e.g., `agentic-demo-cli`.
- Access type: Attach a policy -> Programmatic access (CLI), scroll down to the bottom then click next.
  - For fastest start: `AdministratorAccess` (tighten later to least privilege).
- Finish creation, then open the user → Security credentials → Create access key.
- Choose “Command Line Interface (CLI)”, create the key, and download the `.csv`.
- Save Access Key ID and Secret Access Key in a password manager; do not commit to git or .env.

**Command:**
```bash
aws configure
```

**Input Required:**
- AWS Access Key ID: `<your-access-key>`
- AWS Secret Access Key: `<your-secret-key>`
- Default region name: `us-east-1` (project default)
- Default output format: `json`
- If using SSO: run `aws configure sso` in WSL, select profile, and set that profile in `.env` if the app expects it.

**Verify identity (after configure/SSO):**
```bash
aws sts get-caller-identity
```
**Expected Output:** Should show your AWS account ID and user ARN

#### 1.3 Request Bedrock Model Access

**Action:** Go to AWS Console → Bedrock → Model access

**Models to Request:**
1. Amazon Nova Pro (`amazon.nova-pro-v1:0`)
2. Amazon Nova Lite (`amazon.nova-lite-v1:0`)
3. Amazon Titan Embeddings (`amazon.titan-embed-text-v1`)
4. Anthropic Claude 3.5 Sonnet (`anthropic.claude-3-5-sonnet-20240620-v1:0`)

**Verification:**
```bash
aws bedrock list-foundation-models --region us-east-1 --query 'modelSummaries[?modelId==`amazon.nova-pro-v1:0`]'
```

**Expected Output:** Should show model details, not "AccessDeniedException"

**Common Issue:** If you get "AccessDeniedException", wait for approval (usually instant, can take up to 24 hours)

**Reminder:** Add AWS credentials and region (`us-east-1`) to `.env` in WSL. Keep `.env` gitignored (`git check-ignore .env` should output `.env`). For SSO, run `aws configure sso` in WSL and ensure the profile used by the project is set in `.env` if applicable.
- If access is denied initially, re-run the verification command after access is approved.
- Some organizations require accepting Bedrock terms in the AWS Console before access is granted; check the Bedrock console if approval seems delayed.

#### 1.4 Create Pinecone Account and Index

**Action:** 
1. Go to https://pinecone.io
2. Create free account (Starter tier is free)
3. Create a **Serverless** index with these settings:
   - For phase 0, may need to go back and make a new one for later.
   - Pick MANUAL 
   - Pick Dense
   - **Name:** `demo-index`
   - **Dimensions:** `1536` (Bedrock Titan embedding size)
   - **Metric:** `cosine`
   - **Cloud:** AWS
   - **Region:** `us-east-1` (must match AWS region; use the serverless region, e.g., `PINECONE_ENVIRONMENT=us-east-1`)

**Get API Key:**
- Go to API Keys in Pinecone dashboard
- Copy your API key
- Save for `.env` file (Step 2.5) in WSL

**Note:** Pinecone Serverless uses "environment" terminology (e.g., `us-east-1`). The `.env.example` uses `PINECONE_ENVIRONMENT` for this value.

#### 1.5 Create Tavily Account

**Action:**
1. Go to https://tavily.com
2. Create free account
3. Get API key from dashboard
4. Free tier: 1,000 searches/month (no extra setup needed)

**Get API Key:**
- Copy API key from Tavily dashboard
- Save for `.env` file (Step 2.3) in WSL

#### 1.6 Create Financial Modeling Prep (FMP) Account (for Market Data MCP)

**Action:**
1. Go to https://financialmodelingprep.com
2. Create free account (no credit card)
3. Get API key from dashboard
4. Free tier: ~250 calls/day; batch tickers supported

**Note:** If you skip this for Phase 0, the market data tool will use mock data.

#### 1.7 (Optional) Local Python Tooling for IDE Support

**Purpose:** While this project follows a Docker-first approach (all runtime dependencies in containers), installing Python tooling locally provides significantly better IDE support in Cursor/VS Code:

| Benefit | Impact |
|---------|--------|
| **Better autocomplete** | Cursor/Pylance can suggest methods, attributes, and parameters |
| **Real-time type checking** | Catch type errors as you code, not just at runtime |
| **Import resolution** | No more "Module not found" warnings in the editor |
| **mypy/Pyright integration** | Pre-commit hooks and linting work properly |
| **Faster feedback loop** | Catch issues before running Docker |

**Important:** This does NOT change the Docker-first workflow. You still run the application in Docker - this is purely for IDE tooling support.

**Step 1: Install python3-venv (if not already installed)**
```bash
# In WSL terminal - requires sudo password
sudo apt install python3.12-venv -y
# Or for Python 3.11: sudo apt install python3.11-venv -y
```

**Step 2: Create virtual environment**
```bash
cd ~/Projects/aws-enterprise-agentic-ai
python3 -m venv .venv
```

**Step 3: Activate and install dependencies**
```bash
source .venv/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt
```

**Step 4: Configure Cursor/VS Code to use the venv**
1. Open Command Palette: `Ctrl+Shift+P` (or `Cmd+Shift+P` on Mac)
2. Search for: `Python: Select Interpreter`
3. Select the interpreter at: `.venv/bin/python`

**Verification:**
```bash
# With venv activated
source .venv/bin/activate
PYTHONPATH=backend python -c "from src.config.settings import Settings; s = Settings(); print(f'Environment: {s.environment}')"
```

**Expected Output:** `Environment: local`

**Note:** The `.venv/` directory is already in `.gitignore`, so it won't be committed.

**Deactivate when done (optional):**
```bash
deactivate
```

---

## 2. Initial Project Structure

### What We're Doing
Creating the complete directory structure and initial configuration files. This establishes the foundation for all code.

### Why This Matters
- **Organization:** Clear structure makes code easy to find and maintain
- **Standards:** Following the structure ensures consistency
- **Scalability:** Structure supports all future phases
- **Team Collaboration:** Standard structure helps other developers navigate

### Common Issues
- **Missing Directories:** Forgetting to create subdirectories causes import errors
- **Wrong Permissions:** Files not executable (scripts)
- **Git Ignore Missing:** Accidentally committing `.env` or `__pycache__`

### Step-by-Step Setup

#### 2.1 Create Directory Structure

**Command (run in WSL terminal):**
```bash
# Create main directories
mkdir -p backend/src/{agent/{nodes,tools},api/{routes/v1,middleware},config,cache,ingestion,utils}
mkdir -p backend/tests
mkdir -p backend/alembic/versions
mkdir -p frontend/src/{app/login,components/{chat,cold-start,thought-process,ui},lib,styles}
mkdir -p scripts
mkdir -p docs
mkdir -p lambda/document-ingestion
mkdir -p .github/workflows
mkdir -p terraform/{environments/{dev,prod},modules/{networking,app-runner,aurora,s3-cloudfront,lambda,observability}}
```

**Note:** The `frontend/src/app/` directory is for Next.js App Router pages only. Component directories go under `frontend/src/components/`.

**Verification:**
```bash
# Verify structure was created
tree -L 3 -d
```

**Expected Output:** Should show all directories listed above

#### 2.1a Create All __init__.py Files

**Command:**
```bash
# Create all required __init__.py files for Python packages
# Backend source packages
touch backend/src/__init__.py
touch backend/src/config/__init__.py
touch backend/src/api/__init__.py
touch backend/src/api/routes/__init__.py
touch backend/src/api/routes/v1/__init__.py
touch backend/src/api/middleware/__init__.py
touch backend/src/agent/__init__.py
touch backend/src/agent/nodes/__init__.py
touch backend/src/agent/tools/__init__.py
touch backend/src/cache/__init__.py
touch backend/src/ingestion/__init__.py
touch backend/src/utils/__init__.py

# Test packages
touch backend/tests/__init__.py
```

**Verification:**
```bash
# Verify all __init__.py files exist
find backend/src backend/tests -name "__init__.py" | wc -l
# Should show 13+ files
```

**Why This Matters:** Python requires `__init__.py` files to recognize directories as packages. Missing these files will cause `ModuleNotFoundError` when importing modules.

#### 2.2 Initialize Git Repository

**Command (run in WSL terminal):**
```bash
# Configure Git for WSL (important for Windows/Linux compatibility)
git config --global core.autocrlf input  # Prevents Windows line ending issues
git config --global init.defaultBranch main

# Initialize git (if not already done)
git init

# Create initial commit with project plan and cursor rules
git add README.md PROJECT_PLAN.md DEVELOPMENT_REFERENCE.md .cursor/
git commit -m "Initial commit: Project plan, documentation, and cursor rules"
```

**Note:** The `.cursor/rules/` directory contains AI-assisted development guidelines in `.mdc` files. It should be committed to help maintain consistency.

**WSL Git Tip:** Always run Git commands from WSL terminal, not from Windows. This ensures consistent line endings and file permissions.

#### 2.3 Create .gitignore

**Agent Prompt:**
```
Create `.gitignore`

Include patterns for:
- Python: __pycache__, *.pyc, .venv, venv, *.egg-info, .pytest_cache, .mypy_cache
- Node.js: node_modules, .next, out, .turbo, *.log
- Environment: .env, .env.local, .env.*.local
- IDE: .vscode, .idea, *.swp, *.swo
- OS: .DS_Store, Thumbs.db
- AWS: .aws-sam, samconfig.toml
- Terraform: .terraform, *.tfstate, *.tfstate.*, .terraform.lock.hcl
- Docker: *.log (container logs)
- Testing: .coverage, htmlcov, .pytest_cache
- Build artifacts: dist, build, *.egg

Verify: Check for linter errors and consistency with project structure.
```

**Verification:**
```bash
# Check .gitignore exists and has content
cat .gitignore | wc -l  # Should be 30+ lines
```

#### 2.4 Review .env.example

The [`.env.example`](.env.example) file is already provided in the repository with all required environment variables and detailed comments explaining each one.

**SECURITY NOTE:** 
- The `.env.example` file contains placeholder values (safe to commit)
- Your actual `.env` file with real keys is gitignored (never committed)
- For production, use AWS Secrets Manager (see [`docs/SECURITY.md`](docs/SECURITY.md))

**Verification:**
```bash
# Check .env.example exists and has the required variables
cat .env.example | grep -c "="  # Should be 15+ variables
```

#### 2.5 Create .env from .env.example

**Command:**
```bash
# Copy example to actual .env
cp .env.example .env  # run in WSL from project root

# Safety: ensure .env is gitignored
git check-ignore .env  # Should output: .env

# Edit .env and fill in your actual values
# Use your preferred editor (nano, vim, VS Code, etc.)
```

**What to do:**
1. Open `.env` in your editor
2. Replace all placeholder values with your actual API keys
3. See the comments in `.env.example` for where to obtain each key
4. Save the file


---

## 3. Backend Foundation

### What We're Doing
Setting up the core FastAPI application, configuration management, and dependency management. This is the foundation that all other backend code builds upon.

### Why This Matters
- **Configuration:** Centralized settings prevent hardcoded values
- **FastAPI:** Provides API framework, automatic OpenAPI docs, async support
- **Dependencies:** Pinned versions ensure reproducible builds
- **Environment Detection:** Allows same code to work locally and in AWS

### Common Issues
- **Import Errors:** Python path not set correctly
- **Missing Dependencies:** Forgetting to install packages
- **Environment Variables:** Not loading from .env correctly
- **Type Errors:** Missing type hints cause mypy failures

### Step-by-Step Implementation

#### 3.1 Create Backend requirements.txt

**Agent Prompt:**
```
Create `backend/requirements.txt`

Requirements:
- Core Framework: fastapi~=0.115.0, uvicorn[standard]~=0.32.0, pydantic~=2.9.0, pydantic-settings~=2.6.0
- Agent Framework: langgraph~=0.2.50, langchain~=0.3.0, langchain-community~=0.3.0, langchain-aws~=0.2.0
- AWS SDK: boto3~=1.35.0, botocore~=1.35.0
- Database: sqlalchemy~=2.0.35, alembic~=1.13.0, psycopg2-binary~=2.9.9
- Vector Store: pinecone-client~=5.0.0, chromadb~=0.5.15
- Logging: structlog~=24.4.0
- HTTP Clients: httpx~=0.27.0, requests~=2.32.0
- Utilities: python-dotenv~=1.0.0, tenacity~=9.0.0
- Rate Limiting: slowapi~=0.1.9
- Testing: pytest~=8.3.0, pytest-asyncio~=0.24.0, pytest-cov~=5.0.0, pytest-mock~=3.14.0
- Code Quality: black~=24.10.0, ruff~=0.7.0, mypy~=1.13.0
- Type Stubs: types-requests~=2.32.0

Constraints:
- Use ~= for compatible release pinning (allows patch updates)
- Add comments grouping packages by functionality
- Versions must match DEVELOPMENT_REFERENCE.md "Technology Version Reference"

Verify: All versions match DEVELOPMENT_REFERENCE.md.
```

**Verification:**
```bash
# Check requirements.txt exists and has pinned versions
# Note: Uses ~= (compatible release) not == (exact version)
grep -c "~=" backend/requirements.txt  # Should be 20+ packages
# Or count all lines with version specifiers:
grep -E "(~=|==|>=|<=)" backend/requirements.txt | wc -l
```

**Version Reference:** All versions in `backend/requirements.txt` must match the "Technology Version Reference" section in `DEVELOPMENT_REFERENCE.md`. That document is the single source of truth for all dependency versions.

#### 3.2 Create Backend Configuration Module

**Agent Prompt:**
```
Create `backend/src/config/__init__.py`

Requirements:
- Package initialization file that exposes the Settings class
- Re-export key functions: get_settings, validate_config, get_environment
- Add module docstring explaining package purpose

Reference: Follow patterns in existing package __init__.py files.
Verify: Check for linter errors.
```

**Agent Prompt:**
```
Create `backend/src/config/settings.py`

Requirements:
1. Use Pydantic Settings (BaseSettings from pydantic_settings)
2. Load from .env file using SettingsConfigDict
3. Auto-detect environment (local vs aws) based on ENVIRONMENT variable
   - Important: Use `ENVIRONMENT` variable name, not `ENV`
4. Include all environment variables from .env.example with proper types
5. Add validation for required variables with clear error messages
6. Provide sensible defaults where possible
7. Use type hints throughout
8. Add docstrings explaining each setting

Structure:
- Settings class inheriting from BaseSettings
- SettingsConfigDict with env_file=".env"
- Fields for: AWS, Bedrock models, External APIs, Database, Application
- validate_config() function that checks all required settings
- get_settings() cached singleton function
- detect_environment() function for local vs AWS detection

Reference: .env.example for all required variables.
Verify: Check for linter errors and type safety.
```

**Verification:** See consolidated Docker verification checklist in Section 7.6 once services are running.

#### 3.3 Create Backend API Main Module

**Agent Prompt:**
```
Create `backend/src/api/__init__.py`

Requirements:
- Package initialization for FastAPI API module
- Export app instance and create_app factory function
- Add version tracking (__version__, __api_version__)
- Add module docstring documenting package structure

Reference: Follow patterns in src/config/__init__.py.
Verify: Check for linter errors.
```

**Agent Prompt:**
```
Create `backend/src/api/main.py`

Requirements:
1. Create FastAPI app instance with title, description, version
2. Configure CORS middleware to allow localhost:3000 (frontend)
3. Add basic error handling middleware with user-friendly messages
4. Include health check endpoint at /health
5. Load settings from config.settings
6. Add lifespan context manager to validate configuration on startup
7. Use proper type hints and docstrings
8. Structure for future route additions (use include_router pattern)

Health endpoint spec:
- Returns: {"status": "ok", "environment": "local", "version": "0.1.0"}
- Method: GET
- No authentication required (Phase 0)

Reference: FastAPI 0.115+ lifespan pattern (not deprecated on_event).
Verify: Check for linter errors and test endpoint accessibility.
```

**Verification:** See consolidated Docker verification checklist in Section 7.6 once services are running.

#### 3.4 Create Backend Health Route

**Agent Prompt:**
```
Create `backend/src/api/routes/__init__.py`

Requirements:
- Package initialization for API routes
- Export routers for easy importing (health_router, etc.)
- Add module docstring documenting route structure and versioning plan

Reference: Follow patterns in other package __init__.py files.
Verify: Check for linter errors.
```

**Agent Prompt:**
```
Create `backend/src/api/routes/health.py`

Requirements:
1. Create FastAPI APIRouter with tags=["Health"]
2. Define GET /health endpoint
3. Return {"status": "ok", "environment": <from settings>, "version": "..."}
4. Use Pydantic response model (HealthResponse)
5. Use proper type hints and docstrings
6. Keep simple for Phase 0 (no dependency checks - that's Phase 1b)

Reference: FastAPI router patterns.
Verify: Check for linter errors.
```

**Update main.py:**
```
Update `backend/src/api/main.py`

Changes:
1. Import health_router from src.api.routes
2. Include router via app.include_router(health_router)
3. Remove duplicate inline health endpoint (now in routes/health.py)

Verify: Check for linter errors and test /health endpoint.
```

**Verification Command (After Docker Setup):**
```bash
# Test health endpoint (requires Docker from Section 7)
# This will be verified in Section 7.5 after Docker Compose is set up
# For now, just verify the file exists:
ls backend/src/api/routes/health.py
```

**Note:** Full endpoint testing will happen after Docker Compose setup (Section 7.5)

#### 3.5 Create Auth Routes

**Agent Prompt:**
```
Create `backend/src/api/routes/auth.py`

Requirements:
1. POST /api/login endpoint for password authentication
2. GET /api/me endpoint for session validation
3. POST /api/logout endpoint for session cleanup
4. Use HttpOnly cookies for secure session management
5. Integrate with settings.demo_password validation
6. Return appropriate HTTP status codes (200, 401, 204)
7. Include authentication middleware/dependencies

Key Features:
- Password validation against settings.demo_password
- Session token generation and validation
- Secure cookie configuration (HttpOnly, SameSite)
- Proper error messages without exposing sensitive info

Reference: FastAPI router patterns, cookie-based authentication.
Verify: Test login/logout flow and session persistence.
```

**Verification:**
```bash
# Check auth routes exist
ls backend/src/api/routes/auth.py

# Full testing after Docker setup (Section 7.5)
```

#### 3.6 Create Chat API Streaming Endpoint

**Agent Prompt:**
```
Create `backend/src/api/routes/chat.py`

Requirements:
1. POST /api/chat endpoint with Server-Sent Events streaming
2. GET /api/chat endpoint for SSE connection establishment
3. Integrate LangGraph astream() for real-time streaming
4. Parse Nova Pro thinking content (<thinking>...</thinking>)
5. Handle tool call events separately from messages
6. Implement conversation queue management with asyncio.Queue
7. Support authentication via session validation
8. Handle reconnection and error scenarios gracefully

Key Features:
- Async processing with LangGraph.astream() integration
- Thinking content extraction and separate event streaming
- Tool execution event handling (tool_call, tool_used, tool_result)
- Conversation persistence across reconnections
- Keepalive mechanism for SSE connections
- Proper error handling with user-friendly messages

LangChain Integration:
- Use graph.astream() with stream_mode="values"
- Extract messages, errors, and metadata from each state update
- Handle AIMessage with tool_calls for tool execution
- Support conversation_id for multi-turn conversations

Reference: FastAPI streaming responses, LangGraph astream(), Server-Sent Events spec.
Verify: Test streaming conversation flow with thinking display and tool calls.
```

**Verification:**
```bash
# Check chat API exists
ls backend/src/api/routes/chat.py

# Full testing after Docker setup (Section 7.5)
```

#### 3.8 Update API Route Registration

**Agent Prompt:**
```
Update `backend/src/api/routes/__init__.py` and `backend/src/api/main.py`

Requirements:
1. Add auth_router, chat_router exports to routes/__init__.py
2. Register all routers in main.py with proper prefixes and tags
3. Apply authentication middleware to protected routes
4. Configure CORS for frontend origin (localhost:3000)
5. Add session validation dependencies where needed
6. Structure for future API versioning (/api/v1/*)

Router Configuration:
- auth_router: prefix="/api", tags=["Auth"]
- chat_router: prefix="/api", tags=["Chat"]
- health_router: prefix="", tags=["Health"]

Authentication:
- Apply require_session dependency to chat routes
- Auth routes handle their own authentication logic
- Health endpoint remains public

Reference: FastAPI router registration, CORS middleware, dependency injection.
Verify: All endpoints accessible and properly authenticated.
```

**Verification:**
```bash
# Check route registrations
grep -n "include_router" backend/src/api/main.py

# Full testing after Docker setup (Section 7.5)
```

#### 3.9 Note: Dependencies Will Be Installed via Docker

**Important:** Following the Docker-first approach, Python dependencies will be installed automatically when Docker containers are built (Section 7). 

**No local installation needed:** Do NOT create a local venv or install packages directly on your host machine. All development happens inside Docker containers.
**Note, but still best practice to enable for cursor development
**Verification:** Dependencies will be verified after Docker Compose setup (Section 7.5).

---

## 4. LangGraph Agent Core

### What We're Doing
Implementing the core LangGraph agent with state management, graph definition, and basic nodes. This is the heart of the AI agent system.

### Why This Matters
- **Agent Framework:** LangGraph provides orchestration, checkpointing, and streaming
- **State Management:** Proper state schema enables conversation persistence
- **Node Architecture:** Modular nodes make the agent extensible
- **Streaming:** Real-time responses improve user experience

### Common Issues
- **Bedrock Compatibility:** Nova Pro tool calling may need specific configuration
- **State Schema:** Incorrect state structure causes runtime errors
- **Checkpointing:** MemorySaver must be configured correctly
- **Streaming:** SSE events must be formatted correctly

### Step-by-Step Implementation

#### 4.1 Create Agent State Schema

**Agent Prompt:**
```
Create `backend/src/agent/__init__.py`

Requirements:
- Package initialization for LangGraph agent module
- Export: AgentState, create_initial_state, get_registered_tools
- Export state utilities: validate_state, add_tool_used, set_error, clear_error
- Re-export tools for convenience (market_data_tool)
- Add validation utility: validate_agent_config()
- Add module docstring with architecture overview and usage examples

Reference: Follow patterns in src/config/__init__.py, agentic-ai.mdc rules.
Verify: Check for linter errors and circular import issues.
```

**Agent Prompt:**
```
Create `backend/src/agent/state.py`

Requirements:
1. Define TypedDict for agent state (LangGraph requires TypedDict, not Pydantic)
2. Include fields:
   - messages: Annotated[list[BaseMessage], add_messages] (with reducer)
   - conversation_id: str | None
   - tools_used: list[str]
   - last_error: str | None
   - metadata: dict[str, Any]
3. Use `total=False` for incremental state updates
4. Add factory function: create_initial_state()
5. Add validation function: validate_state()
6. Add state helpers: add_tool_used(), set_error(), clear_error()
7. Use proper type hints and comprehensive docstrings

Reference: agentic-ai.mdc rules, LangGraph add_messages reducer pattern.
Verify: Check for linter errors and type safety.
```

**Verification**
```bash
# For now, just verify the file exists:
ls backend/src/agent/state.py
```

**Note:** Full import testing will happen after Docker Compose setup (Section 7.5):


#### 4.2 Create Chat Node

**Agent Prompt:**
```
Create `backend/src/agent/nodes/__init__.py`

Requirements:
- Package initialization for LangGraph node functions
- Export node functions: chat_node, tools_node, error_recovery_node
- Add module docstring explaining node architecture

Reference: agentic-ai.mdc node function patterns.
Verify: Check for linter errors.
```

**Agent Prompt:**
```
Create `backend/src/agent/nodes/chat.py`

Requirements:
1. Import ChatBedrockConverse from langchain_aws (Converse API)
2. Create async chat node function:
   - Signature: async def chat_node(state: AgentState, tools: Sequence[BaseTool]) -> AgentState
   - Get messages from state
   - Invoke Bedrock model with tool binding
   - Return updated state with new message
3. Include fallback logic: if Nova fails, try Claude 3.5 Sonnet
4. Use proper error handling with try/except
5. Log errors with structlog
6. Use type hints throughout and add docstrings

LangChain 0.3.x Compatibility Notes:
- Use ChatBedrockConverse (not ChatBedrock) for Nova Pro
- AIMessageChunk does NOT have to_message() method in 0.3.x
- Combine chunks with + operator, extract content directly
- Nova Pro returns content as [{'type': 'text', 'text': '...'}] list
- Tool calling works differently with Converse API

Configuration (from settings):
- Primary: amazon.nova-pro-v1:0
- Fallback: anthropic.claude-3-5-sonnet-20240620-v1:0
- Temperature: 0.7
- Max tokens: 4096
- Region: us-east-1

Streaming Implementation:
- Use model.astream() for UI streaming support
- Handle AIMessageChunk accumulation and content extraction
- Support tool calls in streaming responses

Reference: agentic-ai.mdc node patterns, LangChain 0.3.x ChatBedrockConverse docs.
Verify: Check for linter errors and proper async streaming handling.
```

**Verification**
```bash
# For now, just verify the file exists docker will set up later in 7.5 and we will test it then:
ls backend/src/agent/nodes/chat.py
```

**Note:** Full import testing will happen after Docker Compose setup:


#### 4.3 Create Tool Execution Node

**Agent Prompt:**
```
Create `backend/src/agent/nodes/tools.py`

Requirements:
1. Create async tool_execution_node function
   - Signature: async def tool_execution_node(state: AgentState) -> AgentState
2. Check if last message has tool calls (AIMessage with tool_calls)
3. Execute tools via get_registered_tools()
4. Format tool results as ToolMessage objects
5. Return updated state with tool results appended to messages
6. Track tools used via add_tool_used() helper
7. Handle errors gracefully, set last_error on failure
8. Use type hints and docstrings

Phase 0 notes:
- Tools return mock data via stubs
- Focus on execution flow, not real implementations
- Log which tools are being called

Reference: agentic-ai.mdc tool execution patterns.
Verify: Check for linter errors.
```

**Verification:** See consolidated Docker verification checklist in Section 7.6 once services are running.

#### 4.4 Create Error Recovery Node

**Agent Prompt:**
```
Create `backend/src/agent/nodes/error_recovery.py`

Requirements:
1. Create async error_recovery_node function
   - Signature: async def error_recovery_node(state: AgentState) -> AgentState
2. Check state["last_error"] for error message
3. Generate user-friendly error response (AIMessage)
4. Add error response to state messages
5. Clear last_error via clear_error() helper
6. Log full technical details with structlog

Error message guidelines:
- User-friendly (no stack traces)
- Actionable (suggest what user can do)
- Internal: Log full technical details

Reference: agentic-ai.mdc error recovery patterns.
Verify: Check for linter errors.
```

**Verification:** See consolidated Docker verification checklist in Section 7.6 once services are running.

#### 4.5 Create LangGraph Graph

**Agent Prompt:**
```
Create `backend/src/agent/graph.py`

Requirements:
1. Import all nodes (chat_node, tool_execution_node, error_recovery_node)
2. Import AgentState from state module
3. Create LangGraph StateGraph with AgentState
4. Add nodes: "chat", "tools", "error_recovery"
5. Add edges with conditional routing:
   - START -> chat
   - chat -> tools (if tool_calls present)
   - chat -> END (if no tool_calls)
   - tools -> chat (loop back)
   - Add error handling edge to error_recovery
6. Configure MemorySaver for Phase 0 checkpointing
7. Compile graph with checkpointer
8. Export: compiled graph, get_registered_tools()
9. Use proper type hints and docstrings

Graph flow:
START -> chat -> [tools -> chat]* -> END
         ↓
    error_recovery -> END

Checkpointing:
- MemorySaver() for Phase 0 (in-memory, no DB)
- Phase 1b+ will use PostgresSaver

Reference: agentic-ai.mdc graph patterns, LangGraph StateGraph docs.
Verify: Check for linter errors and proper edge configuration.
```

**Verification:** See consolidated Docker verification checklist in Section 7.6 once services are running.

---

## 5. Basic Tools (Stubs)

### What We're Doing
Creating stub implementations of all four tools (search, SQL, RAG, market data) that return mock data. The market data stub uses an MCP connection to demonstrate MCP compatibility; live Financial Modeling Prep (FMP) calls remain optional and can be enabled later with an API key. This allows testing the agent flow before implementing real tool logic.

### Why This Matters
- **Early Testing:** Can test agent orchestration without external APIs
- **Development Speed:** Faster iteration without API rate limits
- **Pattern Establishment:** Sets up tool interface pattern for Phase 2
- **Error Handling:** Tests error handling paths

### Common Issues
- **Tool Interface:** Tools must follow LangGraph tool format
- **Mock Data:** Mock data should be realistic
- **Error Cases:** Should test both success and failure paths
- **Local Infra:** Do not run real database/vector/KG services in Phase 0; SQL and RAG stay stub-only. Real DB/vector/KG are added in later cloud phases.

### Step-by-Step Implementation

#### 5.1 Create Tool Base Class

**Agent Prompt:**
```
Create `backend/src/agent/tools/__init__.py`

Requirements:
1. Package initialization for agent tools
2. Export all tool instances: market_data_tool (and stubs when created)
3. Add module docstring explaining tool architecture

Note: Tools use LangChain @tool decorator pattern, not base class.

Reference: agentic-ai.mdc tool definition patterns.
Verify: Check for linter errors.
```

#### 5.2 Create Search Tool Stub

**Agent Prompt:**
```
Create `backend/src/agent/tools/search.py`

Requirements:
1. Use @tool decorator from langchain.tools
2. Create Pydantic input schema (SearchInput)
3. For Phase 0: Return mock search results
4. Mock data: titles, snippets, URLs
5. Tool name: "tavily_search"
6. Tool description: "Search the web for current information using Tavily API"
7. Use type hints and docstrings

Mock result format:
{
    "results": [
        {"title": "...", "snippet": "...", "url": "https://..."}
    ],
    "query": "<user_query>",
    "source": "mock"
}

Reference: agentic-ai.mdc tool definition pattern.
Verify: Check for linter errors.
```

**Verification:** See consolidated Docker verification checklist in Section 7.6 once services are running.

#### 5.3 Create SQL Tool Stub

**Agent Prompt:**
```
Create `backend/src/agent/tools/sql.py`

Requirements:
1. Use @tool decorator from langchain.tools
2. Create Pydantic input schema (SQLQueryInput)
3. For Phase 0: Return mock SQL query results
4. Mock data: table-like structure with multiple rows
5. Include TODO comments for Phase 2 SQL injection prevention
6. Tool name: "sql_query"
7. Tool description: "Query the PostgreSQL database using natural language"
8. Use type hints and docstrings

Mock result format:
{
    "query": "SELECT * FROM customers LIMIT 5",
    "results": [{"id": 1, "name": "...", "email": "..."}],
    "row_count": 2,
    "source": "mock"
}

Reference: agentic-ai.mdc tool definition pattern.
Verify: Check for linter errors.
```

**Verification:** See consolidated Docker verification checklist in Section 7.6 once services are running.

#### 5.4 Create RAG Tool Stub

**Agent Prompt:**
```
Create `backend/src/agent/tools/rag.py`

Requirements:
1. Use @tool decorator from langchain.tools
2. Create Pydantic input schema (RAGQueryInput)
3. For Phase 0: Return mock document retrieval results
4. Mock data: documents with content, source citations, relevance scores
5. Tool name: "rag_retrieval"
6. Tool description: "Retrieve relevant documents from vector store using semantic search"
7. Use type hints and docstrings

Mock result format:
{
    "query": "<user_query>",
    "documents": [
        {"content": "...", "source": "doc.pdf", "page": 1, "score": 0.95}
    ],
    "count": 1,
    "source": "mock"
}

Reference: agentic-ai.mdc tool definition pattern.
Verify: Check for linter errors.
```

**Verification:** See consolidated Docker verification checklist in Section 7.6 once services are running.

#### 5.5 Create Market Data Tool Stub (FMP via MCP)

**Agent Prompt:**
```
Create `backend/src/agent/tools/market_data.py`

Requirements:
1. Use @tool decorator from langchain.tools
2. Create Pydantic input schema (MarketDataInput) with tickers list
3. Return mock data when FMP_API_KEY not set, live data when available
4. Support multiple tickers in one call
5. Fields: ticker, price, change, change_percent, open, previous_close,
   day_high, day_low, volume, currency, exchange, timestamp, source
6. Tool name: "market_data"
7. Tool description: "Get market data for one or more tickers via Financial Modeling Prep"
8. Use httpx for async HTTP calls to FMP API
9. Use type hints and docstrings
10. Add get_market_data_mode() function for testing graceful degradation

Mock result format:
{
    "data": [{"ticker": "AAPL", "price": 123.45, ...}],
    "mode": "mock" | "live",
    "source": "financialmodelingprep"
}

Additional Functions:
- get_market_data_mode(): Return "live" if FMP_API_KEY set, else "mock"
- Export both market_data_tool and get_market_data_mode in __all__

Reference: DEVELOPMENT_REFERENCE.md FMP configuration.
Verify: Check for linter errors and test get_market_data_mode() function.
```

**Verification:** See consolidated Docker verification checklist in Section 7.6 once services are running.

#### 5.6 Register Tools in Graph

**Agent Prompt:**
```
Update backend/src/agent/graph.py to:
1. Import all four tools (search, sql, rag, market data)
2. Create list of tools: [search_tool, sql_tool, rag_tool, market_data_tool]
3. Bind tools to the LLM in chat_node
4. Ensure tools are available for tool calling
5. Update chat node to use tools list

The tools should be bound to the Bedrock model so it can call them.
Reference LangGraph documentation for tool binding with Bedrock.
```

**Verification:** See consolidated Docker verification checklist in Section 7.6 once services are running.

---

## 6. Frontend Foundation

### What We're Doing
Setting up the Next.js frontend with TypeScript, shadcn/ui, and basic chat interface. This provides the user interface for interacting with the agent.

### Why This Matters
- **User Interface:** Frontend is how users interact with the agent
- **SSE Streaming:** Real-time responses require proper SSE implementation
- **Static Export:** Phase 1a will use static export, so we configure it now
- **UI Components:** shadcn/ui provides professional, accessible components

### Common Issues
- **SSE Connection:** EventSource may have CORS issues
- **TypeScript Errors:** Missing type definitions
- **Build Errors:** Next.js config issues
- **Hot Reload:** Volume mounts may not work correctly

### Step-by-Step Implementation

#### 6.1 Initialize Next.js Project

**Note:** This initial setup step runs in your WSL terminal (not in Docker) because it creates the initial project structure. Uses Next.js 16 and React 19 (see DEVELOPMENT_REFERENCE.md "Technology Version Reference" for exact versions). All subsequent development will happen in Docker containers.

**Pre-check (avoid conflicts):**
- Run `ls -A frontend`. If you see existing files (e.g., `Dockerfile.dev`, `src/`, `package.json`), the Next.js scaffold already exists—skip this step and proceed to the configuration steps below.
- If you intentionally need to recreate the app, scaffold into a new empty directory (e.g., `frontend-new`) or move/remove the existing files first; `npx create-next-app` will fail in a non-empty folder.

**Command (run in WSL terminal):**
```bash
cd frontend
npx create-next-app@latest . --typescript --tailwind --eslint --app --src-dir --import-alias "@/*" --yes
```

**The `--yes` flag accepts defaults. If you prefer interactive prompts, omit it:**
```bash
npx create-next-app@latest .
```

**When Prompted (if running interactively):**
- Would you like to use TypeScript? → **Yes**
- Would you like to use ESLint? → **Yes**
- Would you like to use Tailwind CSS? → **Yes**
- Would you like your code inside a `src/` directory? → **Yes**
- Would you like to use App Router? → **Yes**
- Would you like to use Turbopack for `next dev`? → **No** (optional, can say Yes)
- Would you like to customize the import alias? → **Yes** (@/*)

**Verification:**
```bash
# Check Next.js was initialized
#go back to rootfile if still in front end
cd ..
ls -la frontend/package.json

# Verify package.json exists and has Next.js dependencies
grep -q "next" frontend/package.json && echo "✓ Next.js initialized" || echo "✗ Next.js initialization failed"
```

#### 6.2 Configure Next.js for Static Export

**Note:** Next.js 16+ creates `next.config.mjs` (ES modules) or `next.config.ts` by default. Either format works.

**Agent Prompt:**
```
Update `frontend/next.config.mjs` (or .ts if TypeScript config)

Requirements:
1. Set output: 'export' for static export
2. Disable image optimization (images.unoptimized: true)
3. Enable trailingSlash: true
4. Add comments explaining each setting

Configuration:
const nextConfig = {
  output: 'export',
  images: { unoptimized: true },
  trailingSlash: true,
}

Reference: Next.js 16 static export docs.
Verify: Check for valid config syntax.
```

**Verification:**
```bash
# Check next.config exists and has output: 'export'
# Note: File may be .mjs, .ts, or .js depending on Next.js version
grep "output" frontend/next.config.* 2>/dev/null || echo "Check next.config file manually"
```

#### 6.3 Install shadcn/ui

**Note:** This setup step runs in your WSL terminal (not in Docker) because it configures the project. All subsequent development will happen in Docker containers.

**Command (run in WSL terminal):**
```bash
cd frontend
npx shadcn@latest init
```

**When Prompted:**
- Which style would you like to use? → **Default**
- Which color would you like to use as base color? → **Slate**
- Would you like to use CSS variables for colors? → **Yes**

**Install Required Components:**
```bash
npx shadcn@latest add button
npx shadcn@latest add card
npx shadcn@latest add input
npx shadcn@latest add sonner  # replaces deprecated toast; provides toaster + provider
npx shadcn@latest add dialog
```

**Note:** The `toast` component path was removed from the registry. Use `sonner` instead (official replacement for toasts/notifications).

**Note:** The CLI was renamed from `shadcn-ui` to `shadcn` in late 2024. Use `shadcn@latest` for all commands.

**Verification:**
```bash
# Check components were installed
ls frontend/src/components/ui/

# Verify components directory exists
[ -d "frontend/src/components/ui" ] && echo "✓ shadcn/ui components installed" || echo "✗ Components installation failed"
```

#### 6.4 Create Login Page

**Agent Prompt:**
```
Create `frontend/src/app/login/page.tsx`

Requirements:
1. Use shadcn/ui components (Card, Input, Button)
2. Password input with form submission
3. Call backend POST `/api/login` (cookie-based auth, no local password storage)
4. Redirect to / on successful login
5. Show error message if password validation fails
6. Use TypeScript with proper types
7. Style with Tailwind CSS (responsive, mobile-friendly)
8. On mount, call `/api/me` to redirect if already authenticated

Implementation:
- 'use client' directive
- useRouter from next/navigation
- useState for form state and error
- Use `login()` and `getSession()` from `frontend/src/lib/api.ts`

Reference: Next.js 16 App Router patterns, shadcn/ui docs.
Verify: Check for TypeScript errors.
```

**Verification:**
```bash
# Check login page exists
ls frontend/src/app/login/page.tsx
```

#### 6.5 Create API Client

**Agent Prompt:**
```
Create `frontend/src/lib/api.ts`

Requirements:
1. TypeScript types for API requests/responses and event handling
2. SSE connection using native EventSource API
3. Message sending using fetch with proper error handling
4. Advanced SSE event processing for LangGraph integration
5. Base URL from NEXT_PUBLIC_API_URL (default: http://localhost:8000)

Functions:
- connectSSE(conversationId, onMessage, onError): EventSource (with credentials)
- sendMessage(message, conversationId): Promise<SendMessageResponse> (credentials included)
- getHealth(): Promise<HealthResponse> (credentials included)
- login(password): Promise<void> (sets HttpOnly session cookie)
- getSession(): Promise<SessionResponse> (validates session)
- logout(): Promise<void> (clears session cookie)

SSE Event Types (for LangGraph integration):
- 'open': Connection established
- 'thinking': Chain-of-thought content from model (display separately)
- 'message': Regular chat message content
- 'tool_call': Tool execution started (show indicator)
- 'tool_used': Tool execution completed (update status)
- 'tool_result': Raw tool results (deprecated - not displayed)
- 'complete': Stream finished successfully
- 'error': Stream failed with error details

Advanced SSE Features:
- Parse complex event payloads with conversationId, content, tool info
- Handle thinking content extraction and collapsible display
- Implement exponential backoff reconnection logic
- Support conversation persistence across page refreshes
- Proper error differentiation (recoverable vs fatal)

Reference: Native EventSource API (no Vercel AI SDK per project rules), Server-Sent Events spec.
Verify: Check for TypeScript errors and test SSE event handling.
```

**Verification:**
```bash
# Check API client exists
ls frontend/src/lib/api.ts
```

#### 6.6 Create Chat Page

**Agent Prompt:**
```
Create `frontend/src/app/page.tsx`

Requirements:
1. Check sessionStorage for authentication, redirect to /login if missing
2. Chat interface with message list, input field, send button
3. SSE connection for streaming responses via api.ts
4. Real-time message display as chunks arrive
5. Use shadcn/ui components
6. TypeScript with proper types
7. Tailwind CSS styling (responsive)

Chat UI:
- Message bubbles (user: right, assistant: left)
- Input field at bottom
- Auto-scroll to latest message
- Loading indicator while waiting
- Error toast on failures

Implementation:
- 'use client' directive
- useState for messages[], input, isLoading
- useEffect for auth check and SSE setup
- useRouter for navigation

Reference: frontend.mdc rules, shadcn/ui docs.
Verify: Check for TypeScript errors.
```

**Verification:**
```bash
# Check chat page exists
ls frontend/src/app/page.tsx
```

#### 6.7 Create Layout

**Agent Prompt:**
```
Update `frontend/src/app/layout.tsx`

Requirements:
1. Include metadata (title, description)
2. Include global styles (globals.css)
3. Set up font (Inter or system font stack)
4. Include Toaster component for toast notifications
5. Use TypeScript

Metadata:
- title: "Enterprise Agentic AI Demo"
- description: "Enterprise-grade agentic AI system"

Reference: Next.js 16 App Router metadata docs.
Verify: Check for TypeScript errors.
```

**Verification:**
```bash
# Check layout exists
cat frontend/src/app/layout.tsx | head -20
```

#### 6.8 Frontend Dependencies

**Note:** Frontend dependencies are installed automatically via Docker (same Docker-first approach as backend dependencies in Section 3.9). Do NOT run `npm install` locally - all development happens in containers.

**Verification:** Dependencies will be verified after Docker Compose setup (Section 7.5).

---

## 7. Docker Compose Setup

### What We're Doing
Creating Docker Compose configuration to run all services locally with hot reload. This ensures consistent development environment.

### Why This Matters
- **Consistency:** Same environment for all developers
- **Hot Reload:** Code changes reflect immediately
- **Isolation:** No conflicts with system packages
- **Reproducibility:** Easy to start/stop entire stack

### Common Issues
- **Port Conflicts:** Ports 3000, 8000, 5432 already in use
- **Volume Mounts:** Permissions issues on Linux
- **Startup Time:** Slow if images not pre-pulled
- **Hot Reload:** Not working if volume mounts incorrect

### Step-by-Step Implementation

#### 7.1 Review/Update Backend Dockerfile.dev

The `backend/Dockerfile.dev` file is already provided in the repository. Review it and update if needed.

**What's Configured:**
**Agent Command, review dockerfile and ensure it is properly set up, create if it doesn't exist.**
The Dockerfile should:
1. Use Python 3.11-slim base image
2. Set working directory to /app
3. Install system dependencies (if needed)
4. Copy requirements.txt
5. Install Python dependencies
6. Copy source code (or use volume mount)
7. Expose port 8000
8. Run uvicorn with --reload flag for hot reload
9. Use volume mount for code (./backend:/app)
10. Set environment variables

Structure:
- FROM python:3.11-slim
- WORKDIR /app
- COPY requirements.txt .
- RUN pip install -r requirements.txt
- CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

For development:
- Code will be mounted as volume, so COPY . /app is optional
- --reload enables hot reload on file changes
```

**Verification:**
```bash
# Check Dockerfile exists
ls backend/Dockerfile.dev
```

#### 7.2 Review/Update Frontend Dockerfile.dev

**Agent Command**

 The `frontend/Dockerfile.dev` file should already be provided in the repository. Review it and update if needed.  Create if it does not exist
**What's Configured:**

The Dockerfile should:
1. Use Node.js 20 base image
2. Set working directory to /app
3. Copy package files
4. Install dependencies
5. Expose port 3000
6. Run npm run dev for hot reload
7. Use volume mount for code

Structure:
- FROM node:20-alpine
- WORKDIR /app
- COPY package*.json ./
- RUN npm install
- EXPOSE 3000
- CMD ["npm", "run", "dev"]

For development:
- Code will be mounted as volume
- npm run dev enables hot reload
```

**Verification:**
```bash
# Check Dockerfile exists
ls frontend/Dockerfile.dev
```

#### 7.3 Review/Update docker-compose.yml


**Agent Command**

 The `docker-compose.yml`  file should already be provided in the repository. Review it and update if needed.  Create if it does not exist
**What's Configured (Phase 0):**

- Do **NOT** include a `version` key (deprecated in Docker Compose V2+).
- Services (Phase 0):  
  - `backend`: FastAPI app on 8000  
  - `frontend`: Next.js app on 3000  
  - **No Postgres/Chroma in Phase 0** — SQL and RAG tools use mock data. Database/vector services are added in later phases.
  - **External APIs** — Tavily (search) and FMP (market data) make real API calls when keys are configured.
  - **Chat route** — `/api/chat` streams mock responses by default; it switches to real LangGraph + Bedrock automatically when AWS credentials are set.
- Volumes for hot reload:
  - `./backend:/app`
  - `./frontend:/app`
- Environment:
  - Load from `.env` for API keys/region
  - `ENVIRONMENT=${ENVIRONMENT:-local}` (use ENVIRONMENT, not ENV)
  - `DEBUG=${DEBUG:-true}`
  - `NEXT_PUBLIC_API_URL=http://localhost:8000` (frontend)
- Ports:
  - Backend: `8000:8000`
  - Frontend: `3000:3000`
- Health checks for backend and frontend
- Build contexts: `./backend` and `./frontend`

Backend service (Phase 0):
- Build context: `./backend`
- Dockerfile: `Dockerfile.dev`
- Volume: `./backend:/app`
- `env_file: .env`
- Health check: `curl http://localhost:8000/health` (with start_period: 30s)

Frontend service (Phase 0):
- Build context: `./frontend`
- Dockerfile: `Dockerfile.dev`
- Volumes: `./frontend:/app`, `/app/node_modules` (anonymous volume to preserve deps)
- Environment: `NEXT_PUBLIC_API_URL=http://localhost:8000`
- Depends_on: backend
- Health check: uses `wget` (alpine base)

**Note:** Database/vector services (Postgres, Chroma) are intentionally omitted in Phase 0. Add them when moving to Phase 1a+; remove any unused DB/vector env vars from the Phase 0 compose to avoid startup noise.
```
fo
**Verification Command:**
```bash
# Validate docker-compose.yml syntax
docker-compose config
```

**Expected Output:** Should show validated configuration without errors

**Command syntax note:** We use `docker compose` (V2). `docker-compose` (hyphen) also works if installed; commands are interchangeable.

#### 7.4 Create .dockerignore Files

**Agent Prompt:**
```
Create `backend/.dockerignore`

Exclude:
- venv/, .venv/
- __pycache__/, *.pyc
- .pytest_cache/, .mypy_cache
- .git/
- *.log
- .env

Verify: File exists and has correct patterns.
```

**Agent Prompt:**
```
Create `frontend/.dockerignore`

Exclude:
- node_modules/
- .next/
- out/
- .git/
- *.log
- .env.local

Verify: File exists and has correct patterns.
```

**Verification:**
```bash
# Check .dockerignore files exist
ls backend/.dockerignore frontend/.dockerignore
```

#### 7.5 Test Docker Compose Startup

**Command (run in WSL terminal):**
```bash
# Start all services in detached mode
# Note: 'docker compose' (no hyphen) is the modern Docker Compose V2 syntax
docker compose up -d

# Wait for services to be ready (10-15 seconds)
sleep 15

# Check all services are running
docker compose ps
```

**Note:** Both `docker-compose` (hyphenated) and `docker compose` (space) work. The space version is the newer Docker Compose V2 integrated into Docker CLI.

**Expected Output:** All services should show "Up" status:
- backend: Up
- frontend: Up

**Note** run this to fix some formatting errors before validation.
docker-compose exec backend black src/

#### 7.6 Docker Verification Checklist (run after services are Up)

Use these commands once `docker compose up -d` is running to validate everything quickly:

```bash
# Health + frontend reachability
curl http://localhost:8000/health
curl -I http://localhost:3000

# Settings load and .env visibility
docker-compose exec backend python -c "from src.config.settings import Settings; s=Settings(); print(f'Environment: {s.environment}')"
# Environment variables are injected via env_file; the .env file itself is not mounted.
# Verify by reading a variable (example: AWS_REGION) or by loading Settings.
docker-compose exec backend printenv AWS_REGION
docker-compose exec backend python -c "from src.config.settings import Settings; s=Settings(); print(s.model_dump())"

# FastAPI imports and graph/tool wiring
docker-compose exec backend python -c "from src.api.main import app; print('FastAPI app created successfully')"
#Can ignore UserWarning: Field "model_arn" in BedrockRerank
docker-compose exec backend python -c "from src.agent.nodes.tools import tool_execution_node; print('Tool execution node imported')"
docker-compose exec backend python -c "from src.agent.nodes.error_recovery import error_recovery_node; print('Error recovery node imported')"
docker-compose exec backend python -c "from src.agent.graph import graph; print('Graph created successfully'); print(f'Graph nodes: {list(graph.nodes.keys())}')"
docker-compose exec backend python -c "from src.agent.tools.search import tavily_search; print('Search tool created')"
docker-compose exec backend python -c "from src.agent.tools.sql import sql_query; print('SQL tool created')"
docker-compose exec backend python -c "from src.agent.tools.rag import rag_retrieval; print('RAG tool created')"
docker-compose exec backend python -c "from src.agent.tools.market_data import market_data_tool; print('Market data tool created')"
docker-compose exec backend python -c "from src.agent.graph import graph; print('Tools registered in graph')"

# Test suites and quality checks
docker-compose exec backend pytest --collect-only
docker-compose exec backend pytest tests/test_tools.py -v  # current Phase 0 tests
# Run agent/API tests after those files are added in later steps.
docker-compose exec backend black --check src/
docker-compose exec backend ruff check src/
docker-compose exec backend mypy src/
```

**Expected Results:**
- Health endpoint returns: `{"status":"ok","environment":"local"}`
- Frontend returns HTTP 200 or 302 (redirect)
- Import/graph/tool commands print success lines
- Tests and linters complete without errors

**If Services Fail to Start:**
1. Check logs: `docker-compose logs`
2. Verify ports aren't in use: `lsof -i :8000 -i :3000 -i :5432`
3. Confirm Docker is running
4. Verify `.env` has required variables
5. Rerun `docker-compose up -d` after fixes

**Stop Services:**
```bash
docker-compose down
```

**Note:** Keep services running for subsequent sections, or restart with `docker-compose up -d` when needed.

---

## 8. Development Scripts

### What We're Doing
Creating helper scripts to simplify common development tasks like starting services, viewing logs, running tests, etc.

### Why This Matters
- **Convenience:** One command instead of multiple
- **Consistency:** Same commands for all developers
- **Documentation:** Scripts serve as usage examples
- **Automation:** Reduces manual errors

### Common Issues
- **Permissions:** Scripts not executable
- **Path Issues:** Scripts not in PATH
- **Shell Compatibility:** Scripts may not work in all shells

### Step-by-Step Implementation

#### 8.1 Create Setup Script


**Agent Prompt:**
```
Create `scripts/setup.sh`

Requirements:
1. Validate Docker is installed and running
2. Validate Python 3.11+ is installed
3. Validate AWS CLI is configured
4. Create .env from .env.example if missing
5. Pre-pull Docker images (python:3.11-slim, node:20-alpine)
6. Clear error messages on failure
7. Use bash with set -e for error handling
8. Be idempotent (safe to run multiple times)

Verify: Script is executable and runs without errors.
```

**Command (run in WSL terminal):**
```bash
chmod +x scripts/setup.sh
```

**Note:** The `chmod` command must be run in WSL, not PowerShell. If you see "command not found", you're in the wrong terminal.

**Verification:**
```bash
# Test setup script (will fail if prerequisites missing)
./scripts/setup.sh
```

#### 8.2 Create Validation Script

**Agent Prompt:**
```
Create `scripts/validate_setup.py`

Requirements:
1. Check all prerequisites programmatically
2. Validate .env file has required variables
3. Test AWS credentials (boto3 sts get-caller-identity)
4. Test Bedrock access (list-foundation-models)
5. Test Pinecone API key (if provided)
6. Test Tavily API key (if provided)
7. Clear error messages
8. Exit code 0 on success, 1 on failure
9. Python 3.11+, load .env via python-dotenv
10. Colored output (green=pass, red=fail)

Verify: Script runs and validates environment correctly.
```


**Verification Command:**
```bash
# Test validation script
python3 scripts/validate_setup.py
```

**Expected Output:** Should show all checks passing (green) or specific failures (red)

#### 8.3 Create Dev Script

**Agent Prompt:**
```
Create `scripts/dev.sh`

Commands:
- start: docker compose up -d
- stop: docker compose down
- logs: docker compose logs -f
- test: docker compose exec backend pytest
- shell: docker compose exec backend bash
- restart: down + up
- clean: down -v (remove volumes)

Requirements:
- Bash script
- Accept command as first argument
- Show usage if no command
- Handle errors gracefully

Verify: Script is executable and commands work.
```

**Command:**
```bash
chmod +x scripts/dev.sh
```

**Verification:**
```bash
# Smoke test dev script
./scripts/dev.sh start   # Starts all services via Docker Compose
./scripts/dev.sh stop    # Stops all services
```
#palceholder - script validation START BEGIN HERE
---

## 9. Testing Foundation

### What We're Doing
Setting up testing infrastructure with pytest, test structure, and initial tests for the agent.

### Why This Matters
- **Quality Assurance:** Tests catch bugs early
- **Regression Prevention:** Tests prevent breaking changes
- **Documentation:** Tests serve as usage examples
- **CI/CD Ready:** Tests needed for GitHub Actions (Phase 1b)

### Common Issues
- **Import Errors:** Test imports not finding modules
- **Mock Setup:** Incorrect mocking causes test failures
- **Async Tests:** Forgetting pytest-asyncio for async tests
- **Coverage:** Not testing all code paths

### Step-by-Step Implementation

#### 9.1 Create pytest Configuration

**Agent Prompt:**
```
Create `backend/pytest.ini`

Configuration:
- testpaths = tests
- pythonpath = src
- asyncio_mode = auto
- asyncio_default_fixture_loop_scope = function (pytest-asyncio 0.24+)
- addopts = -v --cov=src --cov-report=term-missing
- filterwarnings: ignore DeprecationWarning

Reference: pytest-asyncio 0.24+ requires asyncio_default_fixture_loop_scope.
Verify: pytest runs without configuration errors.
```




**Verification:** See consolidated Docker verification checklist in Section 7.6 once services are running.

#### 9.2 Create Test Structure

#note the agent will make the files as needed

#### 9.3 Create Agent Tests

**Agent Prompt:**
```
Create `backend/tests/test_agent.py`

Test cases:
- test_state_creation: Verify create_initial_state() works
- test_state_validation: Verify validate_state() catches errors
- test_state_helpers: Test add_tool_used, set_error, clear_error
- test_get_registered_tools: Verify tools are registered

Requirements:
- Pytest fixtures for common setup
- Use @pytest.mark.asyncio for async tests
- Proper assertions with clear messages
- Docstrings on test functions

Reference: agentic-ai.mdc testing patterns.
Verify: Tests pass with pytest.
```

**Verification:** See consolidated Docker verification checklist in Section 7.6 once services are running.

#### 9.4 Create Tool Tests

**Agent Prompt:**
```
Create `backend/tests/test_tools.py`

Test cases:
- test_market_data_tool_mock: Test returns mock data when no API key
- test_market_data_input_validation: Test Pydantic input schema
- test_tool_error_handling: Test graceful error handling

Requirements:
- Use @pytest.mark.asyncio for async tool tests
- Pytest fixtures for common setup
- Mock external API calls
- Test both success and error paths

Reference: Existing market_data.py implementation.
Verify: Tests pass with pytest.
```

**Verification:** See consolidated Docker verification checklist in Section 7.6 once services are running.

#### 9.5 Create API Tests

**Agent Prompt:**
```
Create `backend/tests/test_api.py`

Test cases:
- test_health_endpoint: GET /health returns 200 with correct JSON
- test_root_endpoint: GET / returns API info
- test_cors_headers: CORS headers set correctly
- test_404_response: Unknown endpoint returns 404

Requirements:
- Use TestClient from fastapi.testclient
- Pytest fixtures for app client
- Test response status codes and JSON structure

Reference: FastAPI testing docs.
Verify: Tests pass with pytest.
```

**Verification:** See consolidated Docker verification checklist in Section 7.6 once services are running.


**NOTE**
Run the below to verify tests are working




docker-compose up -d
docker-compose exec backend pytest
docker-compose down

---

## 10. Pre-commit Hooks

### What We're Doing
Setting up pre-commit hooks to automatically check code quality before commits.

### Why This Matters
- **Code Quality:** Catches issues before commit
- **Consistency:** Enforces coding standards
- **Time Savings:** Prevents bad code from being committed
- **Team Standards:** Ensures all developers follow same standards

### Common Issues
- **Hook Installation:** Forgetting to install hooks
- **Slow Hooks:** Some hooks can be slow
- **False Positives:** Hooks may fail on valid code

### Step-by-Step Implementation

#### 10.1 Install pre-commit

**Note:** Pre-commit is a Git hook tool that runs in your WSL environment (not in Docker). It hooks into Git commits to run code quality checks.

**Command (run in WSL terminal):**
```bash
# Install pre-commit in WSL (not in Docker)
pip install pre-commit

# Or if you prefer using pipx (recommended for CLI tools):
pipx install pre-commit

# If pip/pipx not found, install Python packages first:
sudo apt update && sudo apt install -y python3-pip pipx
```

**Verification:**
```bash
# Verify pre-commit is installed
pre-commit --version
```

**Expected Output:** Should show pre-commit version (e.g., `pre-commit 3.x.x`)

#### 10.2 Create Pre-commit Configuration

**Agent Prompt:**
```
Create `.pre-commit-config.yaml`

Hooks:
- black: Python formatting
- ruff: Python linting  
- mypy: Type checking
- detect-secrets: Secret scanning
- pre-commit-hooks: Trailing whitespace, YAML validation

Configuration:
- files: ^backend/ for Python hooks
- stages: [commit]
- Exclude migrations, generated files

Important: Versions MUST match DEVELOPMENT_REFERENCE.md "Technology Version Reference".

Note: pytest NOT included (too slow for every commit - use CI/CD).

Reference: DEVELOPMENT_REFERENCE.md for versions.
Verify: pre-commit validate-config passes.
```

**Verification:**


#run these commands from 7.6 to double check everything for back end.
# we are starting up the backend docker container in detached mode, running the tests, then stopping it.
docker-compose up -d backend
docker-compose exec backend black --check src/
docker-compose exec backend ruff check src/
docker-compose exec backend mypy src/
docker-compose stop backend


```bash
# Validate pre-commit config
pre-commit validate-config
```

**Note this is a good time to commit for safety sake as pre-commit hooks may impact the functionality of committing until resolved**
**only for a demo project, otherwise we would actually want to move this to the top of the development process for enterprise workflows**

#### 10.3 Install Pre-commit Hooks

**Command:**
```bash
pre-commit install
```

**Verification:**
```bash
# Test pre-commit hooks
pre-commit run --all-files
```

**Expected Output:** Should run all hooks and show results
**re run it twice if you get black formatting errors, it should fix automatically on first go**

---

## 11. Real Tool Integration

### What We're Doing
Enable real LangGraph agent flow with real external API tools (Tavily web search, FMP market data) now that Docker services and UI are running. Test each tool incrementally in Docker.

### Why This Matters
- **Easier Troubleshooting:** Website is running, making debugging easier with visible UI feedback
- **No Infrastructure Duplication:** Tavily and FMP are pure API calls to external managed services (no local infrastructure to set up)
- **Validate Orchestration:** Testing real tools now validates the agent orchestration pattern before cloud deployment
- **Incremental Testing:** Test each tool one-by-one to isolate issues
- **Gradual Enablement:** `/api/chat` streams **mock** responses by default; it automatically switches to real LangGraph + Bedrock when AWS credentials are set (so you can verify the UI first, then turn on the real pipeline).

**Note:** SQL and RAG tools remain stubbed in Phase 0. They require database/vector store setup that would duplicate effort needed in later phases. Real SQL (Aurora) and RAG (Pinecone) are enabled in Phase 2.

### Step-by-Step Implementation

#### 11.1 Verify API Keys Are Configured

**Prerequisites:** Ensure your `.env` file has the required API keys from Section 1:

```bash
# Check .env has these keys (should not be empty)
grep -E "^TAVILY_API_KEY=" .env
grep -E "^FMP_API_KEY=" .env
grep -E "^AWS_ACCESS_KEY_ID=" .env
grep -E "^AWS_SECRET_ACCESS_KEY=" .env
```

**If any keys are missing:**
- `TAVILY_API_KEY` - Get from https://tavily.com (free: 1,000 searches/month)
- `FMP_API_KEY` - Get from https://financialmodelingprep.com (free: ~250 calls/day)
- AWS credentials - From `aws configure` or IAM console

**Recommended order (test one at a time):**
1) Set AWS credentials first (enables real LangGraph + Bedrock on `/api/chat`)
2) Add `TAVILY_API_KEY` to turn on real web search (search tool)
3) Add `FMP_API_KEY` to turn on real market data (market data tool)

**Restart containers after adding keys:**
```bash
docker-compose down && docker-compose up -d
sleep 10  # Wait for services to start
docker-compose ps  # Verify all services are "Up"
```

> Quick fix for `ModuleNotFoundError: langchain_community`: rebuild the backend image so the pinned dependency is installed:
> ```bash
> docker-compose build backend && docker-compose up -d backend
> ```

#### 11.2 Enable Real LangGraph with Bedrock

**Agent Prompt:**
```
Update `backend/src/agent/nodes/chat.py`

Changes:
1. Ensure ChatBedrock is initialized with settings.bedrock_model_id (Nova Pro)
2. Add fallback to Claude 3.5 Sonnet if Nova Pro fails
3. Bind tools to LLM using LangChain tool binding pattern
4. Use proper async invocation with astream for streaming
5. Log model used and any fallback events

Model IDs (from DEVELOPMENT_REFERENCE.md):
- Nova Pro: amazon.nova-pro-v1:0 (primary)
- Nova Lite: amazon.nova-lite-v1:0 (verification/cheaper tasks)
- Claude: anthropic.claude-3-5-sonnet-20240620-v1:0 (fallback)

Reference: agentic-ai.mdc "Tool Binding" and "Cost Optimization" sections
Verify: docker-compose exec backend pytest tests/test_agent.py -v
```

**Verification:**
```bash
# Verify Bedrock configuration
docker-compose exec backend python -c "
from src.config.settings import Settings
s = Settings()
print(f'Primary Model: {s.bedrock_model_id}')
print(f'Fallback Model: {s.bedrock_fallback_model_id}')
print(f'AWS Region: {s.aws_region}')
"

# Test Bedrock connectivity
docker-compose exec backend python -c "
import boto3
client = boto3.client('bedrock-runtime', region_name='us-east-1')
print('Bedrock client created successfully')
"
```

**Expected Output:** Should show model IDs and confirm Bedrock client creation.

#### 11.3 Enable Real Tavily Search Tool

**Agent Prompt:**
```
Update `backend/src/agent/tools/search.py`

Changes:
1. Replace mock data with real Tavily API call when TAVILY_API_KEY is set
2. Keep mock fallback when API key is missing (graceful degradation)
3. Add rate limit handling (free tier: 1,000 searches/month)
4. Return structured results: title, snippet, url
5. Add proper error handling with user-friendly messages
6. Log whether using real API or mock mode

Tool Configuration:
- Use TavilySearchResults from langchain_community.tools
- Max results: 5 (configurable)
- Search depth: "basic" for free tier
- Note: Requires langchain-community~=0.3.0 (rebuild backend if ModuleNotFoundError)

Reference:
- agentic-ai.mdc "Tool Definition Pattern"
- security.mdc "Input Validation"
- Cost: Free tier 1,000 searches/month

Verify: docker-compose exec backend pytest tests/test_tools.py -k search -v
```

**Verification Commands:**
```bash
# Test search tool directly
docker-compose exec backend python -c "
from src.agent.tools.search import search_tool
from src.config.settings import Settings
s = Settings()
print(f'Tavily API Key set: {bool(s.tavily_api_key)}')

# Test search (uses real API if key is set)
import asyncio
result = asyncio.run(search_tool.ainvoke({'query': 'latest AI news'}))
print(f'Search result type: {type(result)}')
print(f'Result preview: {str(result)[:200]}...')
"

# Run search tool tests
docker-compose exec backend pytest tests/test_tools.py -k search -v
```

**Manual Test via UI:**
1. Open  
2. Login with DEMO_PASSWORD
3. Ask: "What are the latest AI news headlines?"
4. Verify response includes real web search results (not obviously mock data)
5. Check backend logs for Tavily API call:
   ```bash
   docker-compose logs backend | grep -i tavily
   ```

**Expected Output:** Real search results with actual titles, snippets, and URLs from current web content.

#### 11.4 Enable Real FMP Market Data Tool

**Agent Prompt:**
```
Update `backend/src/agent/tools/market_data.py`

Changes:
1. Replace mock data with real FMP API call when FMP_API_KEY is set
2. Keep mock fallback when API key is missing (graceful degradation)
3. Use batch quote endpoint for multiple tickers (rate limit friendly)
4. Add rate limit handling (free tier: ~250 calls/day)
5. Return structured data: ticker, price, change, change_percent, volume
6. Log whether using real API or mock mode

API Configuration:
- Base URL: https://financialmodelingprep.com/stable
- Endpoint: /quote?symbol={symbol}
- Batch: /quote?symbol={symbol1},{symbol2},... for multiple tickers
- Response includes: symbol, name, price, change, changePercentage, volume, etc.

Reference:
- DEVELOPMENT_REFERENCE.md "Financial Modeling Prep" section
- agentic-ai.mdc "Tool Definition Pattern"

Verify: docker-compose exec backend pytest tests/test_tools.py -k market -v
```

**Verification Commands:**
```bash
# Test market data tool directly
docker-compose exec backend python -c "
from src.agent.tools.market_data import market_data_tool
from src.config.settings import Settings
s = Settings()
print(f'FMP API Key set: {bool(s.fmp_api_key)}')

# Test market data (uses real API if key is set)
import asyncio
result = asyncio.run(market_data_tool.ainvoke({'symbol': 'AAPL'}))
print(f'Market data result: {result}')
"

# Run market data tool tests
docker-compose exec backend pytest tests/test_tools.py -k market -v
```

**Manual Test via UI:**
1. Open http://localhost:3000
2. Ask: "What is the current stock price of AAPL?"
3. Verify response includes real market data (current price, not static mock)
4. Check backend logs for FMP API call:
   ```bash
   docker-compose logs backend | grep -i fmp
   ```

**Expected Output:** Real stock price data that matches current market values.

#### 11.5 Test Multi-Tool Agent Flow

Now test that the agent correctly orchestrates multiple tools in a single query.

**Manual Test via UI:**
1. Open http://localhost:3000
2. Ask: "What's the latest news about Apple and what is AAPL trading at?"
3. Verify agent uses both tools:
   - Tavily search for Apple news
   - FMP for AAPL stock price
   - Ensure AWS credentials are set; otherwise `/api/chat` will remain in mock mode
4. Check backend logs show both tool calls:
   ```bash
   docker-compose logs backend | grep -iE "(tavily|fmp|tool)"
   ```

**Verification Commands:**
```bash
# Run all tool tests
docker-compose exec backend pytest tests/test_tools.py -v

# Check tool registration in graph
docker-compose exec backend python -c "
from src.agent.graph import create_agent_graph
graph = create_agent_graph()
print('Graph nodes:', list(graph.nodes.keys()))
"

# Verify tools are bound to LLM
docker-compose exec backend python -c "
from src.agent.tools import get_all_tools
tools = get_all_tools()
print(f'Registered tools: {[t.name for t in tools]}')
"
```

**Expected Output:** Agent synthesizes information from both tools into a coherent response.

#### 11.6 Verify Graceful Degradation

Test that the agent works correctly when API keys are missing (falls back to mock data).

**Test Mock Fallback:**
```bash
# Test search fallback (temporarily unset key)
docker-compose exec backend python -c "
import os
# Simulate missing API key
original_key = os.environ.pop('TAVILY_API_KEY', None)
try:
    from src.agent.tools.search import get_search_mode
    mode = get_search_mode()
    print(f'Search mode without key: {mode}')
finally:
    if original_key:
        os.environ['TAVILY_API_KEY'] = original_key
"

# Test market data fallback
docker-compose exec backend python -c "
import os
original_key = os.environ.pop('FMP_API_KEY', None)
try:
    from src.agent.tools.market_data import get_market_data_mode
    mode = get_market_data_mode()
    print(f'Market data mode without key: {mode}')
finally:
    if original_key:
        os.environ['FMP_API_KEY'] = original_key
"
```

**Expected Output:** Tools should report "mock" mode when API keys are not set, and still return valid (mock) data.

#### 11.7 Real Tools Integration Checklist

Before proceeding to Section 12, verify:

- [x] Bedrock connection working (Nova Pro accessible)
- [x] Tavily search returns real results (when API key set)
- [x] FMP market data returns real prices (when API key set)
- [x] Multi-tool queries work correctly
- [x] Graceful fallback to mock data when API keys missing
- [x] Backend logs show tool execution details
- [x] No errors in browser console during tool use

**Troubleshooting:**

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| `AccessDeniedException` from Bedrock | Model access not approved | Request access in AWS Console → Bedrock → Model access |
| Tavily returns 401 | Invalid or missing API key | Verify `TAVILY_API_KEY` in `.env`, restart containers |
| FMP returns 401 | Invalid or missing API key | Verify `FMP_API_KEY` in `.env`, restart containers |
| Tavily rate limit error | Exceeded 1,000/month free tier | Wait until next month or upgrade plan |
| FMP rate limit error | Exceeded ~250/day free tier | Wait 24 hours or upgrade plan |
| Tools return mock data | API key not loaded | Run `docker-compose down && docker-compose up -d` |
| Agent doesn't call tools | Tools not bound to LLM | Check `graph.py` tool binding, verify tool registration |

---

## 12. Verification and Testing

### What We're Doing
Comprehensive verification that Phase 0 is complete and working correctly.

### Why This Matters
- **Completeness:** Ensures all deliverables are met
- **Functionality:** Verifies everything works together
- **Quality:** Catches issues before moving to Phase 1a
- **Documentation:** Creates baseline for future phases

### Step-by-Step Verification

#### 12.1 Code Quality Verification

**Agent Prompt:**
```
Review the entire codebase and verify:
1. All Python files have type hints
2. All functions have docstrings
3. All imports are used
4. No hardcoded values (use config/settings)
5. Error handling is consistent
6. Logging is used appropriately
7. Code follows PEP 8 style (black formatted)
8. No linting errors (ruff passes)
9. Type checking passes (mypy passes)

Create a verification report listing:
- Files checked
- Issues found (if any)
- Recommendations
```

**Commands:** Use the Docker verification checklist in Section 7.6 for black/ruff/mypy. Review outputs and fix any reported issues.

After creating the script, run the automated verification and capture the report:

```bash
# Run inside backend container
docker-compose up -d backend
docker-compose exec backend python scripts/verify_code_quality.py \
  --output reports/code_quality_report.md
docker-compose stop backend
```

#### 12.2 Functional Testing

**Prerequisites:** Docker Compose must be set up and tested (Section 7.5) before running these tests.

**Commands:** Functional test commands are consolidated in Section 7.6 (health, frontend reachability, pytest suites, and log checks). Use that checklist to validate; if anything fails, inspect container logs and rerun after fixes.

#### 12.3 Integration Testing

**Agent Prompt:**
```
Test the complete flow:
1. Start all services (docker-compose up)
2. Open browser to http://localhost:3000
3. Login with password from .env
4. Send a test message: "Hello, how are you?"
5. Verify streaming response appears
6. Verify agent responds (even if using mock tools)
7. Check browser console for errors
8. Check backend logs for errors
9. Verify conversation_id is generated
10. Send follow-up message and verify context is maintained

Create a test checklist and verify each item.
```

**Prerequisites:** Docker Compose must be running (Section 7.5).

**Manual Testing Steps:**
1. **Start services** (if not already running):
   ```bash
   docker-compose up -d
   sleep 15  # Wait for services to be ready
   docker-compose ps  # Verify all services are "Up"
   ```

2. **Open browser** to http://localhost:3000
   - Should redirect to /login
   - If connection refused, check frontend is running: `docker-compose logs frontend`

3. **Login:**
   - Enter password from `.env` file (DEMO_PASSWORD variable)
   - Should redirect to chat page
   - If login fails, check backend logs: `docker-compose logs backend | grep -i error`

4. **Send test message:**
   - Type message: "Hello, how are you?"
   - Click send
   - Should see streaming response appear in real-time

5. **Verify SSE connection:**
   - Open browser DevTools → Network tab
   - Filter by "EventSource" or "SSE"
   - Should see connection to http://localhost:8000/api/chat (or similar)
   - Status should be 200 or streaming

6. **Check for errors:**
   - Browser DevTools → Console tab
   - Should see no red errors
   - Check backend logs: `docker-compose logs backend --tail=50`
   - Check frontend logs: `docker-compose logs frontend --tail=50`

7. **Verify conversation context:**
   - Send follow-up message: "What did I just ask?"
   - Agent should remember previous message (conversation_id working)

**If Something Fails:**
- See troubleshooting section below
- Check all services are running: `docker-compose ps`
- Review logs: `docker-compose logs --tail=100`
- Verify .env has correct DEMO_PASSWORD

#### 11.4 Performance Verification

**Commands:**
```bash
# Stop any running containers
docker-compose down

# Test startup time
time docker-compose up -d

# Wait for services to be ready
sleep 15

# Verify services started
docker-compose ps

# Test hot reload (make a small change, check reload time)
# 1. Edit backend/src/api/routes/health.py, add a comment at the top
# 2. Save the file
# 3. Check logs immediately:
docker-compose logs backend --tail=20 | grep -i reload

# Should see reload message within 2-3 seconds
# Example: "Reloading: /app/src/api/routes/health.py"
```

**Expected Results:**
- Startup time: 5-10 seconds (from `docker-compose up -d` to all services "Up")
- Hot reload: 2-3 seconds (from file save to reload message in logs)

**If Hot Reload Not Working:**
1. Verify volume mounts: `docker-compose config | grep volumes`
2. Check uvicorn has `--reload`: `docker-compose exec backend ps aux | grep uvicorn`
3. Verify file permissions: `ls -la backend/src/api/routes/health.py`
4. Check Docker Desktop file sharing settings (Windows/Mac)
5. See troubleshooting section for hot reload issues

---

## 13. File Inventory

### Files at Start of Phase 0 (Actually Exist Now)

**Project Root - Documentation:**
- README.md ✓
- PROJECT_PLAN.md ✓
- DEVELOPMENT_REFERENCE.md ✓
- PHASE_0_HOW_TO_GUIDE.md ✓

**Project Root - Configuration (exist now):**
- .gitignore ✓
- .env.example ✓ (copy to .env and fill in your values)
- .pre-commit-config.yaml ✓
- .gitleaks.toml ✓
- .secrets.baseline ✓
- .cursor/rules/*.mdc ✓ (AI-assisted development guidelines)
- docker-compose.yml ✓

**Project Root - User Files (create yourself, gitignored):**
- .env (create from .env.example, gitignored)

**Backend (exist now):**
- backend/Dockerfile.dev ✓
- backend/requirements.txt ✓

**Frontend (exist now):**
- frontend/Dockerfile.dev ✓

**Documentation (exist now):**
- docs/SECURITY.md ✓

**Directories/Files Created DURING Phase 0 (do NOT exist yet):**
- scripts/ directory and scripts (Section 8)
- backend/src/ directory and all Python code (Sections 3-5)
- frontend/src/ directory and all TypeScript code (Section 6)
- backend/tests/ directory and test files (Section 9)

**Directories Created in Later Phases:**
- terraform/ (Phase 1a)
- lambda/ (Phase 2)
- .github/workflows/ (Phase 1b)

### Files at End of Phase 0

#### Project Root Files
- `.gitignore` - Git ignore patterns (comprehensive security patterns)
- `.env.example` - Environment variable template with descriptions
- `.env` - Actual environment variables (gitignored, created from .env.example)
- `.pre-commit-config.yaml` - Pre-commit hooks including secret scanning
- `.gitleaks.toml` - Gitleaks secret scanning configuration
- `.secrets.baseline` - detect-secrets baseline file
- `.cursor/rules/*.mdc` - AI-assisted development guidelines (modern Cursor format)
- `docker-compose.yml` - Docker Compose configuration
- `PHASE_0_HOW_TO_GUIDE.md` - This guide

#### Documentation Files (`docs/`)
- `docs/SECURITY.md` - Security and secrets management guide

#### Backend Files (`backend/`)
- `requirements.txt` - Python dependencies with pinned versions
- `Dockerfile.dev` - Development Docker image
- `.dockerignore` - Docker ignore patterns
- `pytest.ini` - Pytest configuration
- `src/__init__.py` - Python package marker
- `src/config/__init__.py` - Config package
- `src/config/settings.py` - Pydantic settings with environment detection
- `src/api/__init__.py` - API package
- `src/api/main.py` - FastAPI application
- `src/api/routes/__init__.py` - Routes package
- `src/api/routes/health.py` - Health check endpoint
- `src/agent/__init__.py` - Agent package
- `src/agent/state.py` - Agent state schema (TypedDict)
- `src/agent/graph.py` - LangGraph graph definition
- `src/agent/nodes/__init__.py` - Nodes package
- `src/agent/nodes/chat.py` - Chat node with Bedrock integration
- `src/agent/nodes/tools.py` - Tool execution node
- `src/agent/nodes/error_recovery.py` - Error recovery node
- `src/agent/tools/__init__.py` - Tools package with base class
- `src/agent/tools/search.py` - Tavily search tool (stub with mock data)
- `src/agent/tools/sql.py` - SQL query tool (stub with mock data)
- `src/agent/tools/rag.py` - RAG retrieval tool (stub with mock data)
- `src/agent/tools/market_data.py` - Market data tool (FMP via MCP, stub with mock data)
- `tests/__init__.py` - Tests package
- `tests/test_agent.py` - Agent tests with mocks
- `tests/test_tools.py` - Tool tests
- `tests/test_api.py` - API endpoint tests

#### Frontend Files (`frontend/`)
- `package.json` - Node.js dependencies
- `package-lock.json` - Locked dependency versions
- `next.config.js` - Next.js configuration (static export)
- `tsconfig.json` - TypeScript configuration
- `tailwind.config.js` - Tailwind CSS configuration
- `postcss.config.js` - PostCSS configuration
- `.dockerignore` - Docker ignore patterns
- `Dockerfile.dev` - Development Docker image
- `src/app/layout.tsx` - Root layout with metadata
- `src/app/page.tsx` - Main chat page
- `src/app/login/page.tsx` - Login page
- `src/lib/api.ts` - API client with SSE support
- `src/lib/utils.ts` - Utility functions (shadcn/ui)
- `src/styles/globals.css` - Global styles
- `src/components/ui/` - shadcn/ui components (button, card, input, etc.)

#### Scripts (`scripts/`)
- `setup.sh` - One-time setup script (executable)
- `validate_setup.py` - Prerequisites validation script
- `dev.sh` - Development helper script (executable)

### File Contents Summary

#### Key Files and Their Purpose

**backend/src/config/settings.py:**
- Pydantic Settings class
- Environment variable loading
- Local vs AWS detection
- Configuration validation
- **Changes in Phase 1b:** Add Secrets Manager integration

**backend/src/api/main.py:**
- FastAPI app instance
- CORS middleware
- Route registration
- **Changes in Phase 1b:** Add structured logging, rate limiting, API versioning

**backend/src/agent/graph.py:**
- LangGraph StateGraph definition
- Node registration
- Edge configuration
- MemorySaver checkpointing
- **Changes in Phase 1b:** Migrate to PostgresSaver

**backend/src/agent/tools/*.py:**
- Search tool: Real Tavily API (when key set) or mock fallback
- Market data tool: Real FMP API (when key set) or mock fallback
- SQL tool: Stub returning mock data (real in Phase 2)
- RAG tool: Stub returning mock data (real in Phase 2)
- **Changes in Phase 2:** Implement real SQL (Aurora) and RAG (Pinecone) integrations

**frontend/src/app/page.tsx:**
- Chat interface
- SSE connection
- Message display
- **Changes in Phase 7:** Add thought process display

**docker-compose.yml:**
- All services configuration
- Volume mounts for hot reload
- **Changes in Phase 1a:** Add production build configs

---

## Important Notes About Execution Order

**Critical:** Some verification commands in Sections 3-6 require Docker Compose to be set up (Section 7) before they can run. This is intentional - we create the code structure first, then set up Docker, then verify everything works together.

**Two Approaches:**
1. **Create all code first, then test** (recommended): Follow sections 1-6 to create all files, then set up Docker (Section 7), then run all verifications together.
2. **Test as you go**: Set up Docker early (after Section 2), then use Docker-based verification commands throughout.

**For Early Verification:** If you want to verify imports before Docker setup, you can temporarily install dependencies locally, but remember to remove the venv before proceeding (Docker handles dependencies).

---

## Phase 0 Completion Checklist

### Prerequisites
- [x] Docker Desktop installed and running
- [x] Python 3.11+ installed
- [x] Node.js 20+ installed (optional)
- [x] AWS CLI configured
- [x] Bedrock model access approved
- [x] Pinecone account created, index created
- [x] Tavily account created
- [x] FMP account created, API key copied (optional; mock mode without key)

### Project Structure
- [x] All directories created
- [x] All __init__.py files created (Section 2.1a)
- [x] Git repository initialized
- [x] .gitignore created (exists in repo)
- [x] .env.example created (exists in repo)
- [x] .env created from .env.example with actual values
- [x] .env validated (check: `git check-ignore .env` should output `.env`)

### Backend
- [x] requirements.txt with pinned versions (exists in repo)
- [x] Configuration module (settings.py)
- [x] FastAPI app (main.py)
- [x] Health endpoint working
- [x] Agent state schema defined
- [x] LangGraph graph created
- [x] Chat node implemented
- [x] Tool execution node implemented
- [x] Error recovery node implemented
- [x] All four tool stubs created
- [x] Tools registered in graph

### Real Tool Integration
- [x] Bedrock connection working (Nova Pro accessible)
- [x] Tavily search returns real results (when API key set)
- [x] FMP market data returns real prices (when API key set)
- [x] Multi-tool queries work correctly
- [x] Graceful fallback to mock data when API keys missing

### Frontend
- [x] Next.js initialized
- [x] Static export configured
- [x] shadcn/ui installed
- [x] Login page created
- [x] Chat page created
- [x] API client with SSE created
- [x] Layout configured

### Docker
- [x] docker-compose.yml created (already in repo)
- [x] Backend Dockerfile.dev created (already in repo)
- [x] Frontend Dockerfile.dev created (already in repo)
- [x] .dockerignore files created
- [x] docker-compose.yml syntax validated
- [x] Services start successfully (Section 7.5)
- [x] All services show "Up" status
- [x] Health endpoint accessible
- [x] Frontend accessible
- [x] Database connection works
- [x] Hot reload working

### Scripts
- [x] setup.sh created and executable
- [x] validate_setup.py created
- [x] dev.sh created and executable
- [x] All scripts tested

### Testing
- [x] pytest.ini configured
- [x] Test structure created
- [x] Agent tests written
- [x] Tool tests written
- [x] API tests written
- [x] All tests passing

### Code Quality
- [x] Pre-commit hooks configured
- [x] Hooks installed
- [x] Black formatting passes (run in Docker)
- [x] Ruff linting passes (run in Docker)
- [x] Mypy type checking passes (run in Docker)
- [x] All tests pass (run in Docker)

### Functionality
- [x] Health endpoint responds
- [x] Frontend loads
- [x] Login works
- [x] Chat interface displays
- [x] SSE connection works
- [x] Agent responds (with mock tools)
- [x] Streaming works
- [x] Error handling works

### Documentation
- [x] Code has docstrings
- [x] README updated (if needed)
- [x] Troubleshooting guide created
- [x] .cursor/rules/ directory referenced/committed

### ⚠️ CRITICAL: Branch Management (DO THIS BEFORE STARTING PHASE 1)
- [x] All Phase 0 work committed to git
- [x] Created `phase-0-local-dev` branch
- [x] Tagged Phase 0 as `v0.1.0-phase0`
- [x] Pushed branch and tag to remote (if using remote repo)
- [x] Verified you can switch back to Phase 0 branch: `git checkout phase-0-local-dev`
- [ ] Created `phase-1a-mvp` branch from Phase 0 for AWS deployment work

**See "Next Steps After Phase 0" section below for detailed commands.**

---

## 🎉 Phase 0 Implementation Complete!

**Status:** ✅ **PHASE 0 SUCCESSFULLY COMPLETED**

**Date:** December 23, 2025

**Verification:** All core functionality tested and working:
- ✅ Backend API with FastAPI
- ✅ LangGraph agent with Nova Pro LLM
- ✅ Tool stubs (search, SQL, RAG, market data)
- ✅ Frontend with Next.js and SSE streaming
- ✅ Docker containerized development
- ✅ Complete end-to-end chat flow
- ✅ Code quality checks (Black, Ruff, MyPy)
- ✅ All tests passing

**Next Steps:** Ready to proceed to Phase 1a MVP (AWS deployment)

**Note:** Conversation context persistence is limited to in-memory (MemorySaver) as expected for Phase 0. Full persistence will be added in Phase 1b with PostgresSaver.

---

## Common Issues and Solutions

### Issue: Commands Not Working (Wrong Terminal)

**Symptoms:**
- `chmod: command not found`
- `docker: command not found` in PowerShell
- Path format errors

**Solutions:**
1. **Always use WSL terminal for development commands**, not PowerShell or Command Prompt
2. Open WSL: Press `Win + R`, type `wsl`, press Enter
3. Or open Windows Terminal and select your Ubuntu profile
4. Verify you're in WSL: `uname -a` should show "Linux"

### Issue: Docker Not Connecting to WSL

**Symptoms:**
- `Cannot connect to the Docker daemon`
- Docker commands hang or fail

**Solutions:**
1. Open Docker Desktop → Settings → Resources → WSL Integration
2. Ensure your Ubuntu distro is enabled
3. Restart Docker Desktop
4. In WSL, run: `docker ps` to verify connection
5. If still failing, restart WSL: `wsl --shutdown` (in PowerShell), then reopen WSL

### Issue: Slow File Operations in Docker

**Symptoms:**
- Hot reload is very slow
- npm install takes forever
- File watchers don't trigger

**Solutions:**
1. **Move project to WSL filesystem:** `~/Projects/` not `/mnt/c/Users/...`
2. Clone the repo directly in WSL: `cd ~ && git clone <repo>`
3. Never edit files through `/mnt/c/` path - use VS Code/Cursor with WSL extension

### Issue: Docker Compose Fails to Start

**Symptoms:**
- `docker-compose up` fails with error
- Port already in use
- Permission denied

**Solutions:**
1. Check if ports are in use: `lsof -i :8000` or `ss -tlnp | grep 8000`
2. Stop conflicting services or change ports in docker-compose.yml
3. In WSL, Docker group is usually automatic with Docker Desktop
4. Ensure Docker Desktop is running (check system tray)

### Issue: Import Errors in Python

**Symptoms:**
- `ModuleNotFoundError` when running Python
- Import errors in tests

**Solutions:**
1. Ensure PYTHONPATH includes `backend/src`: `export PYTHONPATH="${PYTHONPATH}:$(pwd)/backend/src"`
2. Run from backend directory: `cd backend && python -m pytest`
3. Check `__init__.py` files exist in all packages
4. Verify Python path in pytest.ini

### Issue: Bedrock Access Denied

**Symptoms:**
- `AccessDeniedException` when calling Bedrock
- Model not found errors

**Solutions:**
1. Verify model access in AWS Console → Bedrock → Model access
2. Request access to: Nova Pro, Nova Lite, Titan Embeddings, Claude
3. Wait for approval (can take up to 24 hours)
4. Verify region is us-east-1
5. Test with: `aws bedrock list-foundation-models --region us-east-1`

### Issue: Frontend Can't Connect to Backend

**Symptoms:**
- CORS errors in browser console
- Connection refused errors
- SSE connection fails

**Solutions:**
1. Verify backend is running: `curl http://localhost:8000/health`
2. Check CORS configuration in `backend/src/api/main.py` allows `http://localhost:3000`
3. Verify NEXT_PUBLIC_API_URL in frontend environment
4. Check browser console for specific error messages
5. Verify both services are in same Docker network

### Issue: Hot Reload Not Working

**Symptoms:**
- Code changes don't reflect immediately
- Need to restart containers

**Solutions:**
1. Verify volume mounts in docker-compose.yml: `./backend:/app`
2. Check uvicorn has `--reload` flag in Dockerfile.dev CMD
3. Check Next.js has `npm run dev` (not `npm run build`)
4. Verify file permissions allow Docker to read files
5. Check Docker Desktop file sharing settings

### Issue: Tests Fail

**Symptoms:**
- pytest fails with import errors
- Tests can't find modules
- Mock errors

**Solutions:**
1. **Run tests in Docker** (recommended): `docker-compose exec backend pytest`
2. **Or run from backend directory:** `cd backend && docker-compose exec backend pytest`
3. Check pytest.ini has correct pythonpath
4. Verify all mocks are set up correctly
5. Check test imports match source structure (use absolute imports from `backend/src/`)
6. Verify all `__init__.py` files exist (see Section 2.1a)
7. Ensure Docker containers are running: `docker-compose ps`

### Issue: Import Errors in Docker

**Symptoms:**
- `ModuleNotFoundError` when running commands in Docker
- Import errors in tests running in Docker

**Solutions:**
1. Verify all `__init__.py` files exist (see Section 2.1a)
2. Check imports use absolute paths from `backend/src/` (not relative imports)
3. Verify Python path in Docker: `docker-compose exec backend python -c "import sys; print(sys.path)"`
4. Check that source files are mounted correctly: `docker-compose exec backend ls -la /app/src/`
5. Restart containers: `docker-compose restart backend`

### Issue: Docker Volume Mounts Not Working

**Symptoms:**
- Code changes don't reflect in container
- Files not visible in container
- Permission errors

**Solutions:**
1. Verify volume mounts in docker-compose.yml: `docker-compose config | grep volumes`
2. Check file permissions: `ls -la backend/src/`
3. On Linux: Ensure Docker has read access to project directory
4. On Windows/Mac: Check Docker Desktop file sharing settings
5. Restart Docker Desktop if on Windows/Mac
6. Verify files exist on host: `ls backend/src/api/main.py`

### Issue: Port Conflicts

**Symptoms:**
- `docker-compose up` fails with "port already in use"
- Services can't bind to ports 3000, 8000, 5432

**Solutions:**
1. Check what's using the port: `lsof -i :8000` (Linux/Mac) or `netstat -ano | findstr :8000` (Windows)
2. Stop conflicting services or change ports in docker-compose.yml
3. Common conflicts:
   - Port 8000: Another FastAPI/uvicorn service
   - Port 3000: Another Next.js/React app
   - Port 5432: Another PostgreSQL instance
4. Change ports in docker-compose.yml if needed (update frontend API URL accordingly)

### Issue: Docker Compose Services Won't Start

**Symptoms:**
- Services exit immediately after starting
- Containers show "Exited" status
- Health checks failing

**Solutions:**
1. Check logs: `docker-compose logs backend` (or frontend, postgres)
2. Verify .env file exists and has all required variables
3. Check Docker Desktop is running
4. Verify Docker has enough resources (memory, CPU)
5. Check for syntax errors in docker-compose.yml: `docker-compose config`
6. Try rebuilding: `docker-compose build --no-cache`
7. Check for missing files referenced in Dockerfiles

### Issue: Hot Reload Not Working

**Symptoms:**
- Code changes don't reflect automatically
- Need to restart containers manually
- No reload messages in logs

**Solutions:**
1. Verify volume mounts: `docker-compose config | grep volumes`
2. Check uvicorn has `--reload` flag: `docker-compose exec backend ps aux | grep uvicorn`
3. Check Next.js is using `npm run dev` (not `npm run build`)
4. Verify file permissions allow Docker to read files
5. Check Docker Desktop file sharing settings (Windows/Mac)
6. Look for reload messages in logs: `docker-compose logs backend | grep -i reload`
7. Restart containers: `docker-compose restart backend frontend`

---

## Branch Management and Next Steps

### Why Create a Phase 0 Branch?

**Yes, creating a Phase 0 branch is a best practice.** Here's why:

1. **Rollback Safety:** You can always return to a working local-only setup
2. **Comparison:** Easy to diff Phase 0 vs Phase 1 changes
3. **Debugging:** If AWS deployment breaks something, you have a known-good baseline
4. **Learning:** Review what changed between phases
5. **Cost Control:** Switch back to Phase 0 branch to stop incurring AWS costs

### Branch Strategy

```
main (production)
  └── phase-0-local-dev (tag: v0.1.0)
        └── phase-1a-mvp
              └── phase-1b-hardening
                    └── phase-2-tools
                          └── ... (future phases)
```

### Step-by-Step Branch Management

#### Before Starting Phase 1a (After Phase 0 Complete):

```bash
# Ensure you're on main and everything is committed
git status
git add .
git commit -m "Phase 0: Local development environment complete"

# Create and tag the Phase 0 branch for easy reference
git checkout -b phase-0-local-dev
git tag -a v0.1.0-phase0 -m "Phase 0 complete - local dev environment"
git push origin phase-0-local-dev
git push origin v0.1.0-phase0

# Now create Phase 1a branch from Phase 0
git checkout -b phase-1a-mvp
# ... work on Phase 1a ...
```

#### To Return to Phase 0 (Local-Only Development):

```bash
# Switch back to Phase 0 branch
git checkout phase-0-local-dev

# Start local development environment
docker-compose up -d

# Everything works locally without AWS!
```

#### After Completing Each Phase:

```bash
# Tag the phase completion
git tag -a v0.X.0-phaseY -m "Phase Y complete"
git push origin --tags

# Merge to main if ready for production
git checkout main
git merge phase-Xa-name
git push origin main
```

### Recommended Tags

| Tag | Description |
|-----|-------------|
| `v0.1.0-phase0` | Local dev environment complete |
| `v0.2.0-phase1a` | Minimal MVP deployed to AWS |
| `v0.3.0-phase1b` | Production hardening complete |
| `v0.4.0-phase2` | Core tools implemented |
| ... | ... |

## Next Steps After Phase 0

### ⚠️ CRITICAL: Save Phase 0 as a Separate Branch Before Starting Phase 1

**Before moving to Phase 1a, you MUST create a separate branch for Phase 0.** This allows you to:
- Return to a working local-only setup anytime
- Stop AWS costs by switching back to Phase 0
- Compare changes between phases
- Debug AWS deployment issues with a known-good baseline

### Step-by-Step: Create Phase 0 Branch

**Run these commands in your WSL terminal:**

```bash
# 1. Verify all Phase 0 work is complete and tested
docker compose up -d
# Test that everything works: http://localhost:3000, http://localhost:8000/health

# 2. Ensure you're on main branch and everything is committed
git status
git add .
git commit -m "Phase 0: Local development environment complete"

# 3. Create the Phase 0 branch (this preserves your local-only setup)
git checkout -b phase-0-local-dev

# 4. Tag this version for easy reference
git tag -a v0.1.0-phase0 -m "Phase 0 complete - local dev environment"

# 5. Push branch and tag to remote (if using remote repository)
git push origin phase-0-local-dev
git push origin v0.1.0-phase0

# 6. Now you're ready to start Phase 1a - create branch from Phase 0
git checkout -b phase-1a-mvp

# You're now on phase-1a-mvp branch, ready to start AWS deployment!
```

### Quick Reference: Switching Between Branches

**To return to Phase 0 (local-only, no AWS):**
```bash
git checkout phase-0-local-dev
docker compose up -d
# Everything works locally without AWS costs!
```

**To continue with Phase 1a (AWS deployment):**
```bash
git checkout phase-1a-mvp
# Continue AWS deployment work
```

### Additional Next Steps

1. **Review Deliverables:**
   - Verify all Phase 0 deliverables are met (check Phase 0 Completion Checklist)
   - Test complete flow end-to-end
   - Document any issues encountered

2. **Prepare for Phase 1a:**
   - Review Phase 1a requirements in DEVELOPMENT_REFERENCE.md
   - Set up Terraform state (S3 + DynamoDB)
   - Prepare AWS IAM permissions
   - Review AWS costs and billing alerts

3. **Update Documentation:**
   - Update README with Phase 0 completion
   - Document any deviations from plan
   - Update troubleshooting guide with Phase 0 issues

---

## Summary

Phase 0 establishes the complete local development environment with:
- ✅ Working LangGraph agent with streaming
- ✅ FastAPI backend with health endpoint
- ✅ Next.js frontend with chat interface
- ✅ Docker Compose for consistent environment
- ✅ Development scripts for convenience
- ✅ Testing infrastructure
- ✅ Code quality tools (pre-commit hooks)

**Key Achievements:**
- Agent can process messages and respond (using mock tools)
- Frontend can connect to backend via SSE
- Hot reload works for fast development
- All code follows consistent patterns
- Docker-first development environment established
- All dependencies managed via Docker (no local venv/npm install)
- Ready for Phase 1a AWS deployment

**Important Reminders:**
- ✅ Always use Docker Compose for development (never run services directly on host)
- ✅ All Python/Node dependencies installed via Docker builds
- ✅ All verification/testing happens in Docker containers
- ✅ Hot reload enabled via volume mounts
- ✅ Consistent environment matches production setup

**Time Estimate:** 4-6 hours for complete implementation

**Success Criteria:** ✅ **ALL ITEMS IN PHASE 0 COMPLETION CHECKLIST ARE CHECKED** ✅

**Actual Completion:** Phase 0 fully implemented and verified on December 23, 2025
