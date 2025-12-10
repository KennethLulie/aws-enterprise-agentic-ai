# Phase 0: Local Development Environment - Complete How-To Guide

**Purpose:** This guide provides step-by-step instructions for implementing Phase 0, including all commands, agent prompts, verification steps, and file specifications.

**Estimated Time:** 4-6 hours for complete implementation

**Prerequisites:** Complete all prerequisites in Section 1 before starting implementation.

**⚠️ Important:** This guide follows a Docker-first approach. Dependencies are installed via Docker builds, not locally. Some verification commands in early sections require Docker to be set up first (Section 7). See "Important Notes About Execution Order" section for details.

**🖥️ Development Environment:** This guide is written for **Windows with WSL 2** (Windows Subsystem for Linux). All terminal commands should be run in your WSL terminal (Ubuntu), not PowerShell or Command Prompt. Docker Desktop should be configured to use the WSL 2 backend.

---

## Table of Contents

1. [Quick Start Workflow Summary](#quick-start-workflow-summary)
2. [Windows/WSL Development Setup](#windowswsl-development-setup)
3. [Prerequisites and Setup](#1-prerequisites-and-setup)
4. [Initial Project Structure](#2-initial-project-structure)
5. [Backend Foundation](#3-backend-foundation)
6. [LangGraph Agent Core](#4-langgraph-agent-core)
7. [Basic Tools (Stubs)](#5-basic-tools-stubs)
8. [Frontend Foundation](#6-frontend-foundation)
9. [Docker Compose Setup](#7-docker-compose-setup)
10. [Development Scripts](#8-development-scripts)
11. [Testing Foundation](#9-testing-foundation)
12. [Pre-commit Hooks](#10-pre-commit-hooks)
13. [Verification and Testing](#11-verification-and-testing)
14. [Important Notes About Execution Order](#important-notes-about-execution-order)
15. [Phase 0 Completion Checklist](#phase-0-completion-checklist)
16. [Common Issues and Solutions](#common-issues-and-solutions)
17. [File Inventory](#12-file-inventory)
18. [Branch Management and Next Steps](#branch-management-and-next-steps)

---

## Quick Start Workflow Summary

**Overall Phase 0 Workflow:**
1. **Prerequisites** (Section 1): Install Docker, Python, Node.js, AWS CLI, get API keys
2. **Project Structure** (Section 2): Create directories, Git init, .env setup
3. **Backend Foundation** (Section 3): Create config, FastAPI app, health endpoint
4. **Agent Core** (Section 4): LangGraph agent, state, nodes, graph
5. **Tools** (Section 5): Create tool stubs (search, SQL, RAG, weather)
6. **Frontend** (Section 6): Next.js setup, login page, chat interface
7. **Docker Setup** (Section 7): Dockerfiles, docker-compose.yml, **test startup**
8. **Scripts** (Section 8): Development helper scripts
9. **Testing** (Section 9): Pytest setup, test files
10. **Pre-commit** (Section 10): Code quality hooks
11. **Verification** (Section 11): End-to-end testing

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
4. Anthropic Claude 3.5 Sonnet (`anthropic.claude-3-5-sonnet-20241022-v2:0`)

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

#### 1.6 Create OpenWeatherMap Account (Optional for Phase 0)

**Action:**
1. Go to https://openweathermap.org/api
2. Create free account
3. Choose the Free plan and get API key from dashboard
4. Free tier: 60 calls/minute, 1M calls/month

**Note:** This is optional for Phase 0 but recommended to set up now. Can use mock data if not set up.

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
Create file .gitignore in accordance with project plan and how to guide using best coding practices and latest best practices/sota way of doing it that is stable, do as much research as is necessary. Include patterns for:
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

Review the new file for errors, inconsistencies, version issues, latest documentation.
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

**Verification:**
```bash
# Verify .env is not tracked by git (CRITICAL for security)
git check-ignore .env  # Should output: .env

# If this doesn't output ".env", your secrets could be committed!
# Check that .env is listed in .gitignore
```

**Expected Output:** `.env` (confirms the file is gitignored)

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
Create file backend/requirements.txt in accordance with project plan and how to guide using best coding practices and latest best practices/sota way of doing it that is stable, do as much research as is necessary. Include pinned versions for Phase 0:
- Core Framework: fastapi~=0.115.0, uvicorn[standard]~=0.32.0, pydantic~=2.9.0, pydantic-settings~=2.6.0
- Agent Framework: langgraph~=0.2.50, langchain~=0.3.0, langchain-aws~=0.2.0
- AWS SDK: boto3~=1.35.0, botocore~=1.35.0
- Database: sqlalchemy~=2.0.35, alembic~=1.13.0, psycopg2-binary~=2.9.9 (for Phase 1b, but include now)
- Vector Store: pinecone-client~=5.0.0, chromadb~=0.5.15
- Logging: structlog~=24.4.0 (used in Phase 1b+, include now for consistency)
- HTTP Clients: httpx~=0.27.0, requests~=2.32.0
- Utilities: python-dotenv~=1.0.0, tenacity~=9.0.0
- Rate Limiting: slowapi~=0.1.9 (used in Phase 1b+, include now for consistency)
- Testing: pytest~=8.3.0, pytest-asyncio~=0.24.0, pytest-cov~=5.0.0, pytest-mock~=3.14.0
- Code Quality: black~=24.10.0, ruff~=0.7.0, mypy~=1.13.0
- Type Stubs: types-requests~=2.32.0
- Add comments grouping by phase/functionality
- Use ~= for compatible release pinning (allows patch updates)

Review the new file for errors, inconsistencies, version issues, latest documentation.
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
Create file backend/src/config/__init__.py in accordance with project plan and how to guide using best coding practices and latest best practices/sota way of doing it that is stable, do as much research as is necessary. The file should be empty or expose the Settings class.

Review the new file for errors, inconsistencies, version issues, latest documentation.
```

**Agent Prompt:**
```
Create file backend/src/config/settings.py in accordance with project plan and how to guide using best coding practices and latest best practices/sota way of doing it that is stable, do as much research as is necessary. The file should:
1. Use Pydantic Settings (BaseSettings from pydantic_settings)
2. Load from .env file using python-dotenv
3. Auto-detect environment (local vs aws) based on ENVIRONMENT variable (not ENV) or AWS availability
   - **Important:** Use `ENVIRONMENT` variable name, not `ENV`, to avoid conflicts with other tools
4. Include all environment variables from .env.example with proper types
5. Add validation for required variables
6. Provide sensible defaults where possible
7. Include a function to validate configuration on startup
8. Add clear error messages if validation fails
9. Use type hints throughout
10. Add docstrings explaining each setting

Structure:
- Settings class inheriting from BaseSettings
- Model Config with env_file=".env"
- Fields for: AWS, Bedrock models, External APIs, Database, Application settings
- validate_config() function that checks all required settings
- get_environment() function that detects local vs AWS

Review the new file for errors, inconsistencies, version issues, latest documentation.
```

**Verification Command (After Docker Setup):**
```bash
# Test configuration loads correctly (requires Docker from Section 7)
# This will be verified in Section 7.5 after Docker Compose is set up
# For now, just verify the file exists:
ls backend/src/config/settings.py
```

**Note:** Full configuration testing will happen after Docker Compose setup (Section 7.5) using:
```bash
docker-compose exec backend python -c "from src.config.settings import Settings; s = Settings(); print(f'Environment: {s.environment}')"
```

**Expected Output (after Docker setup):** `Environment: local`

**If Error:** 
- Check that `.env` file exists and has correct values
- Verify all required environment variables are set (see Section 2.5 validation)
- Check Docker container can access .env file: `docker-compose exec backend ls -la /app/.env`
- Review error message for specific missing variable

#### 3.3 Create Backend API Main Module

**Agent Prompt:**
```
Create file backend/src/api/__init__.py in accordance with project plan and how to guide using best coding practices and latest best practices/sota way of doing it that is stable, do as much research as is necessary.

Review the new file for errors, inconsistencies, version issues, latest documentation.
```

**Agent Prompt:**
```
Create file backend/src/api/main.py in accordance with project plan and how to guide using best coding practices and latest best practices/sota way of doing it that is stable, do as much research as is necessary. The file should:
1. Create FastAPI app instance with title, description, version
2. Configure CORS middleware to allow localhost:3000 (frontend)
3. Add basic error handling middleware
4. Include health check endpoint at /health that returns {"status": "ok"}
5. Load settings from config.settings
6. Add startup event to validate configuration
7. Use proper type hints
8. Add docstrings
9. Structure for future route additions

The health endpoint should:
- Return simple JSON: {"status": "ok", "environment": "local"}
- Be accessible without authentication (for Phase 0)
- Use GET method

Review the new file for errors, inconsistencies, version issues, latest documentation.
```

**Verification Command (After Docker Setup):**
```bash
# Test FastAPI app can be imported (requires Docker from Section 7)
# This will be verified in Section 7.5 after Docker Compose is set up
# For now, just verify the file exists:
ls backend/src/api/main.py
```

**Note:** Full import testing will happen after Docker Compose setup (Section 7.5) using:
```bash
docker-compose exec backend python -c "from src.api.main import app; print('FastAPI app created successfully')"
```

**Expected Output (after Docker setup):** `FastAPI app created successfully`

#### 3.4 Create Backend Health Route

**Agent Prompt:**
```
Create file backend/src/api/routes/__init__.py in accordance with project plan and how to guide using best coding practices and latest best practices/sota way of doing it that is stable, do as much research as is necessary.

Review the new file for errors, inconsistencies, version issues, latest documentation.
```

**Agent Prompt:**
```
Create file backend/src/api/routes/health.py in accordance with project plan and how to guide using best coding practices and latest best practices/sota way of doing it that is stable, do as much research as is necessary. The file should:
1. Create a FastAPI router
2. Define GET /health endpoint
3. Return {"status": "ok", "environment": <from settings>}
4. Use proper type hints
5. Add docstring
6. Keep it simple for Phase 0 (no dependency checks yet - that's Phase 1b)

Review the new file for errors, inconsistencies, version issues, latest documentation.
```

**Update main.py:**
```
Update file backend/src/api/main.py in accordance with project plan and how to guide using best coding practices and latest best practices/sota way of doing it that is stable, do as much research as is necessary.
1. Import the health router
2. Include the router with prefix "/" (so /health works)
3. Add the import at the top

Review the new file for errors, inconsistencies, version issues, latest documentation.
```

**Verification Command (After Docker Setup):**
```bash
# Test health endpoint (requires Docker from Section 7)
# This will be verified in Section 7.5 after Docker Compose is set up
# For now, just verify the file exists:
ls backend/src/api/routes/health.py
```

**Note:** Full endpoint testing will happen after Docker Compose setup (Section 7.5) using:
```bash
docker-compose up -d
sleep 5
curl http://localhost:8000/health
docker-compose down
```

**Expected Output (after Docker setup):** `{"status":"ok","environment":"local"}`

#### 3.5 Note: Dependencies Will Be Installed via Docker

**Important:** Following the Docker-first approach, Python dependencies will be installed automatically when Docker containers are built (Section 7). 

**No local installation needed:** Do NOT create a local venv or install packages directly on your host machine. All development happens inside Docker containers.

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
Create file backend/src/agent/__init__.py in accordance with project plan and how to guide using best coding practices and latest best practices/sota way of doing it that is stable, do as much research as is necessary.

Review the new file for errors, inconsistencies, version issues, latest documentation.
```

**Agent Prompt:**
```
Create file backend/src/agent/state.py in accordance with project plan and how to guide using best coding practices and latest best practices/sota way of doing it that is stable, do as much research as is necessary. The file should:
1. Define TypedDict for agent state (or use Pydantic BaseModel)
2. Include fields:
   - messages: List[BaseMessage] (from langchain)
   - conversation_id: Optional[str]
   - tools_used: List[str] (track which tools were called)
   - last_error: Optional[str] (for error recovery)
   - metadata: Dict[str, Any] (for extensibility)
3. Use proper type hints
4. Add docstring explaining state structure
5. Import necessary types from langchain_core.messages

Reference: LangGraph state should be a TypedDict that matches LangChain message format.

Review the new file for errors, inconsistencies, version issues, latest documentation.
```

**Verification (After Docker Setup):**
```bash
# Test state schema can be imported (requires Docker from Section 7)
# This will be verified in Section 7.5 after Docker Compose is set up
# For now, just verify the file exists:
ls backend/src/agent/state.py
```

**Note:** Full import testing will happen after Docker Compose setup (Section 7.5) using:
```bash
docker-compose exec backend python -c "from src.agent.state import AgentState; print('State schema imported successfully')"
```

#### 4.2 Create Chat Node

**Agent Prompt:**
```
Create file backend/src/agent/nodes/__init__.py in accordance with project plan and how to guide using best coding practices and latest best practices/sota way of doing it that is stable, do as much research as is necessary.

Review the new file for errors, inconsistencies, version issues, latest documentation.
```

**Agent Prompt:**
```
Create file backend/src/agent/nodes/chat.py in accordance with project plan and how to guide using best coding practices and latest best practices/sota way of doing it that is stable, do as much research as is necessary. The file should:
1. Import Bedrock client from langchain_aws
2. Create chat node function that:
   - Takes state (AgentState) as input
   - Gets latest message from state.messages
   - Invokes Bedrock Nova Pro model
   - Handles tool calling (if model supports it)
   - Returns updated state with new message
3. Include fallback logic: if Nova fails, try Claude 3.5 Sonnet
4. Use proper error handling with try/except
5. Log errors with clear messages
6. Use type hints throughout
7. Add docstrings

Configuration:
- Model ID: amazon.nova-pro-v1:0 (from settings)
- Fallback: anthropic.claude-3-5-sonnet-20241022-v2:0
- Temperature: 0.7
- Max tokens: 4096
- Region: us-east-1 (from settings)

The function signature should be:
def chat_node(state: AgentState) -> AgentState:

Review the new file for errors, inconsistencies, version issues, latest documentation.
```

**Verification Command (After Docker Setup):**
```bash
# Test chat node can be imported (requires Docker from Section 7)
# This will be verified in Section 7.5 after Docker Compose is set up
# For now, just verify the file exists:
ls backend/src/agent/nodes/chat.py
```

**Note:** Full import testing will happen after Docker Compose setup (Section 7.5) using:
```bash
docker-compose exec backend python -c "from src.agent.nodes.chat import chat_node; print('Chat node imported successfully')"
```

#### 4.3 Create Tool Execution Node

**Agent Prompt:**
```
Create file backend/src/agent/nodes/tools.py in accordance with project plan and how to guide using best coding practices and latest best practices/sota way of doing it that is stable, do as much research as is necessary. The file should:
1. Create tool_execution_node function
2. Take state as input
3. Check if last message has tool calls
4. Execute tools (for Phase 0, return mock results)
5. Format tool results as messages
6. Return updated state
7. Handle errors gracefully
8. Use type hints and docstrings

For Phase 0:
- Tools will be stubs returning mock data
- Focus on the execution flow, not actual tool implementation
- Log which tools are being called

Review the new file for errors, inconsistencies, version issues, latest documentation.
```

**Verification (After Docker Setup):**
```bash
# Test tool execution node can be imported (requires Docker from Section 7)
# This will be verified in Section 7.5 after Docker Compose is set up
# For now, just verify the file exists:
ls backend/src/agent/nodes/tools.py
```

**Note:** Full import testing will happen after Docker Compose setup (Section 7.5) using:
```bash
docker-compose exec backend python -c "from src.agent.nodes.tools import tool_execution_node; print('Tool execution node imported')"
```

#### 4.4 Create Error Recovery Node

**Agent Prompt:**
```
Create file backend/src/agent/nodes/error_recovery.py in accordance with project plan and how to guide using best coding practices and latest best practices/sota way of doing it that is stable, do as much research as is necessary. The file should:
1. Create error_recovery_node function
2. Check state.last_error for errors
3. Generate user-friendly error message
4. Add error message to state.messages
5. Clear last_error from state
6. Log errors appropriately
7. Use type hints and docstrings

Error messages should be:
- User-friendly (not technical)
- Actionable (suggest what user can do)
- Logged with full technical details

Review the new file for errors, inconsistencies, version issues, latest documentation.
```

**Verification (After Docker Setup):**
```bash
# Test error recovery node can be imported (requires Docker from Section 7)
# This will be verified in Section 7.5 after Docker Compose is set up
# For now, just verify the file exists:
ls backend/src/agent/nodes/error_recovery.py
```

**Note:** Full import testing will happen after Docker Compose setup (Section 7.5) using:
```bash
docker-compose exec backend python -c "from src.agent.nodes.error_recovery import error_recovery_node; print('Error recovery node imported')"
```

#### 4.5 Create LangGraph Graph

**Agent Prompt:**
```
Create file backend/src/agent/graph.py in accordance with project plan and how to guide using best coding practices and latest best practices/sota way of doing it that is stable, do as much research as is necessary. The file should:
1. Import all nodes (chat, tools, error_recovery)
2. Import state schema
3. Create LangGraph graph using StateGraph
4. Add nodes: chat, tools, error_recovery
5. Add edges:
   - Start -> chat
   - chat -> tools (if tool calls needed)
   - tools -> chat (continue conversation)
   - chat -> error_recovery (if error)
   - error_recovery -> end
6. Configure MemorySaver for checkpointing
7. Compile the graph
8. Add streaming support
9. Export compiled graph
10. Use proper type hints and docstrings

Graph flow:
- Start -> chat -> (if tool calls) -> tools -> chat -> end
- If error -> error_recovery -> end

Checkpointing:
- Use MemorySaver() for Phase 0 (in-memory, no DB)
- Configure with proper state schema

Review the new file for errors, inconsistencies, version issues, latest documentation.
```

**Verification Command (After Docker Setup):**
```bash
# Test graph can be created (requires Docker from Section 7)
# This will be verified in Section 7.5 after Docker Compose is set up
# For now, just verify the file exists:
ls backend/src/agent/graph.py
```

**Note:** Full graph testing will happen after Docker Compose setup (Section 7.5) using:
```bash
docker-compose exec backend python -c "from src.agent.graph import graph; print('Graph created successfully'); print(f'Graph nodes: {list(graph.nodes.keys())}')"
```

**Expected Output (after Docker setup):** Should show graph nodes: ['chat', 'tools', 'error_recovery']

---

## 5. Basic Tools (Stubs)

### What We're Doing
Creating stub implementations of all four tools (search, SQL, RAG, weather) that return mock data. The weather stub specifically uses an MCP connection to demonstrate MCP compatibility; live OpenWeather calls remain optional and can be enabled later with an API key. This allows testing the agent flow before implementing real tool logic.

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
Create file backend/src/agent/tools/__init__.py in accordance with project plan and how to guide using best coding practices and latest best practices/sota way of doing it that is stable, do as much research as is necessary. The file should:
1. Export a base Tool class or interface
2. Define common tool interface
3. Include error handling base
4. Define tool result format

The base should include:
- execute() method signature
- error handling pattern
- result formatting
- logging pattern

Review the new file for errors, inconsistencies, version issues, latest documentation.
```

#### 5.2 Create Search Tool Stub

**Agent Prompt:**
```
Create file backend/src/agent/tools/search.py in accordance with project plan and how to guide using best coding practices and latest best practices/sota way of doing it that is stable, do as much research as is necessary. The file should:
1. Create a SearchTool class
2. Implement LangGraph tool format (using @tool decorator or Tool class)
3. For Phase 0: Return mock search results
4. Mock data should include:
   - Query parameter
   - Mock results with titles, snippets, URLs
   - Proper formatting
5. Include error handling (for Phase 0, just log)
6. Use type hints and docstrings
7. Tool name: "tavily_search"
8. Tool description: "Search the web for current information using Tavily API"

Mock result format:
{
    "results": [
        {
            "title": "Mock Result 1",
            "snippet": "This is a mock search result...",
            "url": "https://example.com/1"
        }
    ],
    "query": "<user_query>"
}

Review the new file for errors, inconsistencies, version issues, latest documentation.
```

**Verification (After Docker Setup):**
```bash
# Test search tool can be imported (requires Docker from Section 7)
# This will be verified in Section 7.5 after Docker Compose is set up
# For now, just verify the file exists:
ls backend/src/agent/tools/search.py
```

**Note:** Full tool testing will happen after Docker Compose setup (Section 7.5) using:
```bash
docker-compose exec backend python -c "from src.agent.tools.search import SearchTool; tool = SearchTool(); print('Search tool created')"
```

#### 5.3 Create SQL Tool Stub

**Agent Prompt:**
```
Create file backend/src/agent/tools/sql.py in accordance with project plan and how to guide using best coding practices and latest best practices/sota way of doing it that is stable, do as much research as is necessary. The file should:
1. Create SQLTool class
2. Implement LangGraph tool format
3. For Phase 0: Return mock SQL query results
4. Mock data should simulate database results:
   - Table-like structure
   - Multiple rows
   - Proper data types
5. Include SQL injection prevention comments (will implement in Phase 2)
6. Use type hints and docstrings
7. Tool name: "sql_query"
8. Tool description: "Query the PostgreSQL database using natural language"

Mock result format:
{
    "query": "SELECT * FROM customers LIMIT 5",
    "results": [
        {"id": 1, "name": "John Doe", "email": "john@example.com"},
        {"id": 2, "name": "Jane Smith", "email": "jane@example.com"}
    ],
    "row_count": 2
}

Review the new file for errors, inconsistencies, version issues, latest documentation.
```

**Verification (After Docker Setup):**
```bash
# Test SQL tool can be imported (requires Docker from Section 7)
# This will be verified in Section 7.5 after Docker Compose is set up
# For now, just verify the file exists:
ls backend/src/agent/tools/sql.py
```

**Note:** Full tool testing will happen after Docker Compose setup (Section 7.5) using:
```bash
docker-compose exec backend python -c "from src.agent.tools.sql import SQLTool; tool = SQLTool(); print('SQL tool created')"
```

#### 5.4 Create RAG Tool Stub

**Agent Prompt:**
```
Create file backend/src/agent/tools/rag.py in accordance with project plan and how to guide using best coding practices and latest best practices/sota way of doing it that is stable, do as much research as is necessary. The file should:
1. Create RAGTool class
2. Implement LangGraph tool format
3. For Phase 0: Return mock document retrieval results
4. Mock data should include:
   - Retrieved documents with content
   - Source citations
   - Relevance scores
5. Use type hints and docstrings
6. Tool name: "rag_retrieval"
7. Tool description: "Retrieve relevant documents from vector store using semantic search"

Mock result format:
{
    "query": "<user_query>",
    "documents": [
        {
            "content": "Mock document content...",
            "source": "document1.pdf",
            "page": 1,
            "score": 0.95
        }
    ],
    "count": 1
}

Review the new file for errors, inconsistencies, version issues, latest documentation.
```

**Verification (After Docker Setup):**
```bash
# Test RAG tool can be imported (requires Docker from Section 7)
# This will be verified in Section 7.5 after Docker Compose is set up
# For now, just verify the file exists:
ls backend/src/agent/tools/rag.py
```

**Note:** Full tool testing will happen after Docker Compose setup (Section 7.5) using:
```bash
docker-compose exec backend python -c "from src.agent.tools.rag import RAGTool; tool = RAGTool(); print('RAG tool created')"
```

#### 5.5 Create Weather Tool Stub

**Agent Prompt:**
```
Create file backend/src/agent/tools/weather.py in accordance with project plan and how to guide using best coding practices and latest best practices/sota way of doing it that is stable, do as much research as is necessary. The file should:
1. Create WeatherTool class
2. Implement LangGraph tool format
3. For Phase 0: Return mock weather data (exposed via an MCP connection to demonstrate MCP compatibility; API key only needed when enabling live OpenWeather calls later)
4. Mock data should include:
   - Location parameter
   - Temperature, conditions, humidity, wind speed
   - Proper units
5. Use type hints and docstrings
6. Tool name: "weather_api"
7. Tool description: "Get current weather information for a location"

Mock result format:
{
    "location": "Austin, TX",
    "temperature": 75,
    "unit": "Fahrenheit",
    "conditions": "Sunny",
    "humidity": 65,
    "wind_speed": 10,
    "wind_unit": "mph"
}

Review the new file for errors, inconsistencies, version issues, latest documentation.
```

**Verification (After Docker Setup):**
```bash
# Test weather tool can be imported (requires Docker from Section 7)
# This will be verified in Section 7.5 after Docker Compose is set up
# For now, just verify the file exists:
ls backend/src/agent/tools/weather.py
```

**Note:** Full tool testing will happen after Docker Compose setup (Section 7.5) using:
```bash
docker-compose exec backend python -c "from src.agent.tools.weather import WeatherTool; tool = WeatherTool(); print('Weather tool created')"
```

#### 5.6 Register Tools in Graph

**Agent Prompt:**
```
Update backend/src/agent/graph.py to:
1. Import all four tools (search, sql, rag, weather)
2. Create list of tools: [search_tool, sql_tool, rag_tool, weather_tool]
3. Bind tools to the LLM in chat_node
4. Ensure tools are available for tool calling
5. Update chat node to use tools list

The tools should be bound to the Bedrock model so it can call them.
Reference LangGraph documentation for tool binding with Bedrock.
```

**Verification Command (After Docker Setup):**
```bash
# Verify tools are registered (requires Docker from Section 7)
# This will be verified in Section 7.5 after Docker Compose is set up
# For now, verify all tool files exist:
ls backend/src/agent/tools/*.py
```

**Note:** Full graph testing will happen after Docker Compose setup (Section 7.5) using:
```bash
docker-compose exec backend python -c "from src.agent.graph import graph; print('Tools registered in graph')"
```

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

**Note:** This initial setup step runs in your WSL terminal (not in Docker) because it creates the initial project structure. All subsequent development will happen in Docker containers.

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
ls -la frontend/package.json

# Verify package.json exists and has Next.js dependencies
grep -q "next" frontend/package.json && echo "✓ Next.js initialized" || echo "✗ Next.js initialization failed"
```

#### 6.2 Configure Next.js for Static Export

**Note:** Next.js 14+ creates `next.config.mjs` (ES modules) or `next.config.ts` by default. Either format works.

**Agent Prompt:**
```
Update file frontend/next.config.mjs (or next.config.ts if TypeScript config was created) in accordance with project plan and how to guide using best coding practices and latest best practices/sota way of doing it that is stable, do as much research as is necessary. The file should:
1. Set output: 'export' for static export (needed for Phase 1a)
2. Disable image optimization (not needed for static export)
3. Configure base path if needed
4. Add comments explaining each setting

Configuration should be:
```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  images: {
    unoptimized: true
  },
  // Disable server-side features for static export
  trailingSlash: true,
}

export default nextConfig
```

Review the new file for errors, inconsistencies, version issues, latest documentation.
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
npx shadcn@latest add toast
npx shadcn@latest add dialog
```

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
Create file frontend/src/app/login/page.tsx in accordance with project plan and how to guide using best coding practices and latest best practices/sota way of doing it that is stable, do as much research as is necessary. The file should:
1. Use shadcn/ui components (Card, Input, Button)
2. Have a password input field
3. On submit, store password in sessionStorage
4. Redirect to home page (/) on successful login
5. Show error message if password is wrong
6. Use TypeScript with proper types
7. Style with Tailwind CSS
8. Be responsive (mobile-friendly)

Password validation:
- Check against DEMO_PASSWORD from environment (for Phase 0, hardcode or use env var)
- Show "Invalid password" error if wrong
- Store in sessionStorage as "auth_token" or "password"

Use Next.js App Router patterns:
- 'use client' directive (for interactivity)
- useRouter from next/navigation
- useState for form state

Review the new file for errors, inconsistencies, version issues, latest documentation.
```

**Verification:**
```bash
# Check login page exists
ls frontend/src/app/login/page.tsx
```

#### 6.5 Create API Client

**Agent Prompt:**
```
Create file frontend/src/lib/api.ts in accordance with project plan and how to guide using best coding practices and latest best practices/sota way of doing it that is stable, do as much research as is necessary. The file should:
1. Export functions for API communication
2. SSE connection function using native EventSource
3. Message sending function using fetch
4. Error handling for both SSE and fetch
5. TypeScript types for requests/responses
6. Handle CORS errors
7. Handle connection errors
8. Base URL from environment variable (NEXT_PUBLIC_API_URL)

Functions needed:
- connectSSE(conversationId, onMessage, onError): EventSource
- sendMessage(message, conversationId): Promise<Response>
- getHealth(): Promise<Response>

SSE connection:
- Use native EventSource API
- Handle 'message' events
- Handle 'error' events
- Handle connection close
- Parse JSON messages

For Phase 0:
- API URL: http://localhost:8000 (hardcoded for local dev)
- No authentication headers yet (Phase 1a will add)

Review the new file for errors, inconsistencies, version issues, latest documentation.
```

**Verification:**
```bash
# Check API client exists
ls frontend/src/lib/api.ts
```

#### 6.6 Create Chat Page

**Agent Prompt:**
```
Create file frontend/src/app/page.tsx in accordance with project plan and how to guide using best coding practices and latest best practices/sota way of doing it that is stable, do as much research as is necessary. The file should:
1. Check for authentication (password in sessionStorage)
2. Redirect to /login if not authenticated
3. Display chat interface:
   - Message list (user and assistant messages)
   - Input field for new messages
   - Send button
4. Connect to backend via SSE for streaming responses
5. Display messages in real-time as they stream
6. Handle errors gracefully
7. Use shadcn/ui components
8. Use TypeScript with proper types
9. Style with Tailwind CSS
10. Be responsive

Chat interface:
- Message bubbles (user messages on right, assistant on left)
- Input field at bottom
- Auto-scroll to latest message
- Loading indicator while waiting for response
- Error messages displayed

SSE Integration:
- Use api.ts connectSSE function
- Handle streaming chunks
- Update UI as messages arrive
- Handle connection errors
- Reconnect on disconnect

Use Next.js App Router:
- 'use client' directive
- useState for messages and input
- useEffect for SSE connection
- useRouter for navigation

Review the new file for errors, inconsistencies, version issues, latest documentation.
```

**Verification:**
```bash
# Check chat page exists
ls frontend/src/app/page.tsx
```

#### 6.7 Create Layout

**Agent Prompt:**
```
Update file frontend/src/app/layout.tsx in accordance with project plan and how to guide using best coding practices and latest best practices/sota way of doing it that is stable, do as much research as is necessary. The file should:
1. Include proper metadata (title, description)
2. Include global styles
3. Set up font (Inter or system font)
4. Include any global providers if needed
5. Use TypeScript

Metadata:
- Title: "Enterprise Agentic AI Demo"
- Description: "Enterprise-grade agentic AI system"

Review the new file for errors, inconsistencies, version issues, latest documentation.
```

**Verification:**
```bash
# Check layout exists
cat frontend/src/app/layout.tsx | head -20
```

#### 6.8 Note: Frontend Dependencies Will Be Installed via Docker

**Important:** Following the Docker-first approach, Node.js dependencies will be installed automatically when Docker containers are built (Section 7).

**No local installation needed:** Do NOT run `npm install` directly on your host machine. All development happens inside Docker containers.

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

The `frontend/Dockerfile.dev` file is already provided in the repository. Review it and update if needed.

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

The `docker-compose.yml` file is already provided in the repository. Review it and update if needed.

**What's Configured (Phase 0, stub-only):**

- Do **NOT** include a `version` key (deprecated in Docker Compose V2+).
- Services (Phase 0):  
  - `backend`: FastAPI app on 8000  
  - `frontend`: Next.js app on 3000  
  - **No Postgres/Chroma in Phase 0** — SQL and RAG tools are stubs that return mock data. Database/vector services are added in later phases (Phase 1a+).
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
Create file backend/.dockerignore in accordance with project plan and how to guide using best coding practices and latest best practices/sota way of doing it that is stable, do as much research as is necessary. The file should exclude:
- venv/, .venv/
- __pycache__/, *.pyc
- .pytest_cache/, .mypy_cache
- .git/
- *.log
- .env (will use environment variables)

Review the new file for errors, inconsistencies, version issues, latest documentation.
```

**Agent Prompt:**
```
Create file frontend/.dockerignore in accordance with project plan and how to guide using best coding practices and latest best practices/sota way of doing it that is stable, do as much research as is necessary. The file should exclude:
- node_modules/
- .next/
- out/
- .git/
- *.log
- .env.local

Review the new file for errors, inconsistencies, version issues, latest documentation.
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

**Test Service Communication:**
```bash
# Test backend health endpoint
curl http://localhost:8000/health

# Test frontend is accessible
curl -I http://localhost:3000

# No database/vector services in Phase 0; SQL/RAG tools use stub data
```

**Expected Results:**
- Health endpoint returns: `{"status":"ok","environment":"local"}`
- Frontend returns HTTP 200 or 302 (redirect)
- Configuration loads successfully

**If Services Fail to Start:**
1. Check logs: `docker-compose logs`
2. Verify ports aren't in use: `lsof -i :8000 -i :3000 -i :5432`
3. Check Docker Desktop is running
4. Verify .env file has all required variables
5. See troubleshooting section below

**Stop Services:**
```bash
# Stop all services
docker-compose down
```

**Note:** Keep services running for the next sections, or restart with `docker-compose up -d` when needed.

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
Create file scripts/setup.sh in accordance with project plan and how to guide using best coding practices and latest best practices/sota way of doing it that is stable, do as much research as is necessary. The script should:
1. Validate Docker is installed and running
2. Validate Python 3.11+ is installed
3. Validate AWS CLI is configured
4. Create .env from .env.example if it doesn't exist
5. Pre-pull Docker images (postgres:15-alpine, chromadb/chroma, python:3.11-slim, node:20-alpine)
6. Provide clear error messages if validation fails
7. Use bash with set -e for error handling
8. Be idempotent (safe to run multiple times)

Review the new file for errors, inconsistencies, version issues, latest documentation.
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
Create file scripts/validate_setup.py in accordance with project plan and how to guide using best coding practices and latest best practices/sota way of doing it that is stable, do as much research as is necessary. The script should:
1. Check all prerequisites programmatically
2. Validate .env file has all required variables
3. Test AWS credentials (aws sts get-caller-identity)
4. Test Bedrock model access (list-foundation-models)
5. Test Pinecone API key (if provided)
6. Test Tavily API key (if provided)
7. Provide clear error messages
8. Return exit code 0 if all checks pass, 1 if any fail
9. Use Python 3.11+
10. Load .env file
11. Use boto3 for AWS checks
12. Use requests for API checks
13. Print colored output (green for pass, red for fail)

Review the new file for errors, inconsistencies, version issues, latest documentation.
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
Create file scripts/dev.sh in accordance with project plan and how to guide using best coding practices and latest best practices/sota way of doing it that is stable, do as much research as is necessary. The script should provide convenient commands:
- start: Start all services (docker-compose up)
- stop: Stop all services (docker-compose down)
- logs: View logs (docker-compose logs -f)
- test: Run tests (pytest in backend)
- shell: Open backend shell (docker-compose exec backend bash)
- db: Open database shell (docker-compose exec postgres psql -U demo -d demo)
- restart: Restart all services
- clean: Stop and remove volumes

The script should:
- Use bash
- Accept command as first argument
- Provide usage message if no command
- Handle errors gracefully
- Use docker-compose commands

Review the new file for errors, inconsistencies, version issues, latest documentation.
```

**Command:**
```bash
chmod +x scripts/dev.sh
```

**Verification:**
```bash
# Test dev script
./scripts/dev.sh  # Should show usage
```

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
Create file backend/pytest.ini in accordance with project plan and how to guide using best coding practices and latest best practices/sota way of doing it that is stable, do as much research as is necessary. The file should:
1. Configure pytest for the project
2. Set test paths (tests/)
3. Configure coverage settings
4. Set Python path to include src/
5. Configure asyncio mode for pytest-asyncio 0.24+
6. Set test discovery patterns

Configuration:
- testpaths = tests
- pythonpath = src
- asyncio_mode = auto
- asyncio_default_fixture_loop_scope = function (required for pytest-asyncio 0.24+)
- addopts = --verbose --cov=src --cov-report=term-missing
- Coverage threshold: 70% (for critical paths)

Example pytest.ini:
```ini
[pytest]
testpaths = tests
pythonpath = src
asyncio_mode = auto
asyncio_default_fixture_loop_scope = function
addopts = -v --cov=src --cov-report=term-missing
filterwarnings =
    ignore::DeprecationWarning
```

Review the new file for errors, inconsistencies, version issues, latest documentation.
```

**Verification (After Docker Setup):**
```bash
# Test pytest configuration (requires Docker from Section 7)
# This will be verified in Section 7.5 after Docker Compose is set up
# For now, just verify the file exists:
ls backend/pytest.ini
```

**Note:** Full pytest testing will happen after Docker Compose setup (Section 7.5) using:
```bash
docker-compose exec backend pytest --collect-only
```

#### 9.2 Create Test Structure

**Command:**
```bash
# Create test files
touch backend/tests/__init__.py
touch backend/tests/test_agent.py
touch backend/tests/test_tools.py
touch backend/tests/test_api.py
```

#### 9.3 Create Agent Tests

**Agent Prompt:**
```
Create file backend/tests/test_agent.py in accordance with project plan and how to guide using best coding practices and latest best practices/sota way of doing it that is stable, do as much research as is necessary. The file should include:
1. Tests for agent graph creation
2. Tests for state schema
3. Tests for node execution (with mocks)
4. Mock Bedrock calls using unittest.mock
5. Test error handling
6. Test tool calling flow
7. Pytest fixtures for common setup
8. Proper assertions
9. Docstrings to test functions

Test cases:
- test_graph_creation: Verify graph can be created
- test_state_schema: Verify state structure
- test_chat_node_mock: Test chat node with mocked Bedrock
- test_tool_execution: Test tool execution flow
- test_error_recovery: Test error recovery node

Mocking:
- Use @patch decorator for Bedrock calls
- Mock boto3 BedrockRuntime client
- Return realistic mock responses

Review the new file for errors, inconsistencies, version issues, latest documentation.
```

**Verification Command (After Docker Setup):**
```bash
# Run agent tests (requires Docker from Section 7)
# This will be verified in Section 7.5 after Docker Compose is set up
# For now, just verify the file exists:
ls backend/tests/test_agent.py
```

**Note:** Full test execution will happen after Docker Compose setup (Section 7.5) using:
```bash
docker-compose exec backend pytest tests/test_agent.py -v
```

#### 9.4 Create Tool Tests

**Agent Prompt:**
```
Create file backend/tests/test_tools.py in accordance with project plan and how to guide using best coding practices and latest best practices/sota way of doing it that is stable, do as much research as is necessary. The file should include:
1. Tests for each tool (search, sql, rag, weather)
2. Test tool execution with mock data
3. Test error handling
4. Test tool result formatting
5. Pytest fixtures
6. Mock external APIs

Test cases:
- test_search_tool: Test search tool returns mock data
- test_sql_tool: Test SQL tool returns mock data
- test_rag_tool: Test RAG tool returns mock data
- test_weather_tool: Test weather tool returns mock data
- test_tool_errors: Test error handling in tools

Review the new file for errors, inconsistencies, version issues, latest documentation.
```

**Verification (After Docker Setup):**
```bash
# Run tool tests (requires Docker from Section 7)
# This will be verified in Section 7.5 after Docker Compose is set up
# For now, just verify the file exists:
ls backend/tests/test_tools.py
```

**Note:** Full test execution will happen after Docker Compose setup (Section 7.5) using:
```bash
docker-compose exec backend pytest tests/test_tools.py -v
```

#### 9.5 Create API Tests

**Agent Prompt:**
```
Create file backend/tests/test_api.py in accordance with project plan and how to guide using best coding practices and latest best practices/sota way of doing it that is stable, do as much research as is necessary. The file should include:
1. Tests for FastAPI app
2. Tests for health endpoint
3. Use TestClient from fastapi.testclient
4. Test CORS headers
5. Test error responses

Test cases:
- test_health_endpoint: GET /health returns 200
- test_cors_headers: CORS headers are set correctly
- test_app_startup: App starts without errors

Review the new file for errors, inconsistencies, version issues, latest documentation.
```

**Verification (After Docker Setup):**
```bash
# Run API tests (requires Docker from Section 7)
# This will be verified in Section 7.5 after Docker Compose is set up
# For now, just verify the file exists:
ls backend/tests/test_api.py
```

**Note:** Full test execution will happen after Docker Compose setup (Section 7.5) using:
```bash
docker-compose exec backend pytest tests/test_api.py -v
```

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
Create file .pre-commit-config.yaml in accordance with project plan and how to guide using best coding practices and latest best practices/sota way of doing it that is stable, do as much research as is necessary. The file should:
1. Configure black for Python formatting
2. Configure ruff for Python linting
3. Configure mypy for type checking
4. Configure detect-secrets for secret scanning (security)
5. Configure pre-commit-hooks for general quality (trailing whitespace, YAML/JSON validation)
6. Set up hooks to run on commit
7. Exclude certain files (migrations, generated files)

**IMPORTANT:** Version alignment - The versions specified here MUST match DEVELOPMENT_REFERENCE.md "Technology Version Reference" section. Update that file first, then update .pre-commit-config.yaml.

Configuration:
- repos for: black, ruff, mypy, detect-secrets, pre-commit-hooks
- files: ^backend/ for Python hooks
- pass_filenames: true for most hooks
- stages: [commit]

Hooks:
- black: Format Python code (version must match DEVELOPMENT_REFERENCE.md)
- ruff: Lint Python code (version must match DEVELOPMENT_REFERENCE.md)
- mypy: Type check Python code (version must match DEVELOPMENT_REFERENCE.md)
- detect-secrets: Scan for accidentally committed secrets

Note: pytest is intentionally NOT included as a pre-commit hook because running tests on every commit is slow. Run tests manually or via CI/CD.

Review the new file for errors, inconsistencies, version issues, latest documentation.
```

**Verification:**
```bash
# Validate pre-commit config
pre-commit validate-config
```

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

---

## 11. Verification and Testing

### What We're Doing
Comprehensive verification that Phase 0 is complete and working correctly.

### Why This Matters
- **Completeness:** Ensures all deliverables are met
- **Functionality:** Verifies everything works together
- **Quality:** Catches issues before moving to Phase 1a
- **Documentation:** Creates baseline for future phases

### Step-by-Step Verification

#### 11.1 Code Quality Verification

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

**Commands (After Docker Setup):**
```bash
# Run code quality checks (requires Docker from Section 7)
# Start services if not running
docker-compose up -d

# Run formatting check
docker-compose exec backend black --check src/

# Run linting
docker-compose exec backend ruff check src/

# Run type checking
docker-compose exec backend mypy src/
```

**Expected Results:**
- Black: No formatting issues (or list of files needing formatting)
- Ruff: No linting errors
- Mypy: No type errors (or list of type issues to fix)

**If Issues Found:**
- Format code: `docker-compose exec backend black src/`
- Fix linting: Review ruff output and fix issues
- Fix types: Add missing type hints based on mypy output

#### 11.2 Functional Testing

**Prerequisites:** Docker Compose must be set up and tested (Section 7.5) before running these tests.

**Commands:**
```bash
# Start services (if not already running)
docker-compose up -d

# Wait for services to be ready (10-15 seconds)
sleep 15

# Verify all services are running
docker-compose ps

# Test health endpoint
curl http://localhost:8000/health

# Test frontend loads
curl -I http://localhost:3000

# Run tests in Docker
docker-compose exec backend pytest

# Or use dev script (if created)
./scripts/dev.sh test

# Check logs for errors
docker-compose logs backend | grep -i error
docker-compose logs frontend | grep -i error
```

**Expected Results:**
- All services show "Up" status
- Health endpoint returns: `{"status":"ok","environment":"local"}`
- Frontend returns HTTP 200 or 302 (redirect to login)
- All tests pass
- No errors in logs

**If Tests Fail:**
1. Check Docker containers are running: `docker-compose ps`
2. Verify dependencies installed: `docker-compose exec backend pip list | grep pytest`
3. Check test files exist: `ls backend/tests/test_*.py`
4. Review test output for specific errors
5. See troubleshooting section for import errors

#### 11.3 Integration Testing

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

## 12. File Inventory

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
- `src/agent/tools/weather.py` - Weather API tool (stub with mock data)
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
- Tool stubs returning mock data
- **Changes in Phase 2:** Implement real API integrations

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
- [ ] Docker Desktop installed and running
- [ ] Python 3.11+ installed
- [ ] Node.js 20+ installed (optional)
- [ ] AWS CLI configured
- [ ] Bedrock model access approved
- [ ] Pinecone account created, index created
- [ ] Tavily account created
- [ ] OpenWeatherMap account created (optional)

### Project Structure
- [ ] All directories created
- [ ] All __init__.py files created (Section 2.1a)
- [x] Git repository initialized
- [x] .gitignore created (exists in repo)
- [x] .env.example created (exists in repo)
- [ ] .env created from .env.example with actual values
- [ ] .env validated (check: `git check-ignore .env` should output `.env`)

### Backend
- [x] requirements.txt with pinned versions (exists in repo)
- [ ] Configuration module (settings.py)
- [ ] FastAPI app (main.py)
- [ ] Health endpoint working
- [ ] Agent state schema defined
- [ ] LangGraph graph created
- [ ] Chat node implemented
- [ ] Tool execution node implemented
- [ ] Error recovery node implemented
- [ ] All four tool stubs created
- [ ] Tools registered in graph

### Frontend
- [ ] Next.js initialized
- [ ] Static export configured
- [ ] shadcn/ui installed
- [ ] Login page created
- [ ] Chat page created
- [ ] API client with SSE created
- [ ] Layout configured

### Docker
- [x] docker-compose.yml created (already in repo)
- [x] Backend Dockerfile.dev created (already in repo)
- [x] Frontend Dockerfile.dev created (already in repo)
- [ ] .dockerignore files created
- [ ] docker-compose.yml syntax validated
- [ ] Services start successfully (Section 7.5)
- [ ] All services show "Up" status
- [ ] Health endpoint accessible
- [ ] Frontend accessible
- [ ] Database connection works
- [ ] Hot reload working

### Scripts
- [ ] setup.sh created and executable
- [ ] validate_setup.py created
- [ ] dev.sh created and executable
- [ ] All scripts tested

### Testing
- [ ] pytest.ini configured
- [ ] Test structure created
- [ ] Agent tests written
- [ ] Tool tests written
- [ ] API tests written
- [ ] All tests passing

### Code Quality
- [ ] Pre-commit hooks configured
- [ ] Hooks installed
- [ ] Black formatting passes (run in Docker)
- [ ] Ruff linting passes (run in Docker)
- [ ] Mypy type checking passes (run in Docker)
- [ ] All tests pass (run in Docker)

### Functionality
- [ ] Health endpoint responds
- [ ] Frontend loads
- [ ] Login works
- [ ] Chat interface displays
- [ ] SSE connection works
- [ ] Agent responds (with mock tools)
- [ ] Streaming works
- [ ] Error handling works

### Documentation
- [ ] Code has docstrings
- [ ] README updated (if needed)
- [ ] Troubleshooting guide created
- [ ] .cursor/rules/ directory referenced/committed

### ⚠️ CRITICAL: Branch Management (DO THIS BEFORE STARTING PHASE 1)
- [ ] All Phase 0 work committed to git
- [ ] Created `phase-0-local-dev` branch
- [ ] Tagged Phase 0 as `v0.1.0-phase0`
- [ ] Pushed branch and tag to remote (if using remote repo)
- [ ] Verified you can switch back to Phase 0 branch: `git checkout phase-0-local-dev`
- [ ] Created `phase-1a-mvp` branch from Phase 0 for AWS deployment work

**See "Next Steps After Phase 0" section below for detailed commands.**

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

**Success Criteria:** All items in Phase 0 Completion Checklist are checked ✅

