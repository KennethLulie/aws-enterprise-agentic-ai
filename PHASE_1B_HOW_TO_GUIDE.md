# Phase 1b: Production Hardening - Complete How-To Guide

> 🚧 **PHASE 1b IN PROGRESS**
>
> | Component | URL |
> |-----------|-----|
> | **Frontend (CloudFront)** | `https://d2bhnqevtvjc7f.cloudfront.net` |
> | **Backend (App Runner)** | `https://yhvmf3inyx.us-east-1.awsapprunner.com` |
>
> Building on Phase 1a deployment with production-grade features.

**Purpose:** This guide adds production-grade features to the Phase 1a deployment: persistent database state with Neon PostgreSQL (free tier), automated CI/CD with GitHub Actions, rate limiting, enhanced observability, and security hardening.

**Estimated Time:** 6-10 hours depending on Terraform/AWS/CI experience

**Prerequisites:** Phase 1a must be complete and verified before starting Phase 1b.

**💰 Cost Optimization:** This phase uses Neon PostgreSQL (external service, free tier) instead of Aurora Serverless v2. Total Phase 1 cost remains ~$5-15/month.

**🖥️ Development Environment:** Continue using Windows with WSL 2 as in Phase 0/1a. All terminal commands run in your WSL terminal (Ubuntu).

---

## Table of Contents

- [Quick Start Workflow Summary](#quick-start-workflow-summary)
- [1. Prerequisites Verification](#1-prerequisites-verification)
- [2. Neon PostgreSQL Setup](#2-neon-postgresql-setup)
- [3. Database Package Setup](#3-database-package-setup)
- [4. Alembic Migrations](#4-alembic-migrations)
- [5. PostgresSaver Migration](#5-postgressaver-migration)
- [6. Rate Limiting](#6-rate-limiting)
- [7. API Versioning](#7-api-versioning)
- [8. Enhanced Health Checks](#8-enhanced-health-checks)
- [9. GitHub Actions CI/CD](#9-github-actions-cicd)
- [10. End-to-End Verification](#10-end-to-end-verification)
- [Phase 1b Completion Checklist](#phase-1b-completion-checklist)
- [Common Issues and Solutions](#common-issues-and-solutions)
- [Files Created/Modified in Phase 1b](#files-createdmodified-in-phase-1b)
- [Branch Management and Next Steps](#branch-management-and-next-steps)

---

## Quick Start Workflow Summary

**📋 This guide is designed to be followed linearly.** Complete each section in order (1→2→3→...→10). There is no jumping back and forth.

**Overall Phase 1b Workflow:**
1. **Prerequisites** (Section 1): Verify Phase 1a complete, App Runner healthy
2. **Neon Setup** (Section 2): Create Neon account, database, and connection secret
3. **Database Package** (Section 3): SQLAlchemy session management
4. **Alembic Migrations** (Section 4): Schema versioning setup (checkpoint tables via PostgresSaver)
5. **PostgresSaver** (Section 5): Replace MemorySaver for persistent state
6. **Rate Limiting** (Section 6): slowapi middleware (10 req/min)
7. **API Versioning** (Section 7): Move to /api/v1/chat
8. **Enhanced Health** (Section 8): Dependency checks (Neon, Bedrock)
9. **CI/CD** (Section 9): GitHub Actions workflows
10. **Verification** (Section 10): End-to-end testing

**Key Principle:** Production hardening with persistent state. Conversation history survives App Runner restarts.

**Architecture Overview:**
```
┌─────────────────────────────────────────────────────────────────────────┐
│                              Internet                                    │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐
│     CloudFront      │ │     App Runner      │ │  Neon PostgreSQL    │
│  (Static Frontend)  │ │  (FastAPI Backend)  │ │    (External)       │
│                     │ │                     │ │                     │
│  S3 Bucket ─────────┼▶│  - LangGraph        │◀┼─  - Checkpoints     │
│  - HTML/JS/CSS      │ │  - Bedrock          │ │  - Free Tier        │
│                     │ │  - PostgresSaver    │ │  - 0.5GB Storage    │
└─────────────────────┘ └──────────┬──────────┘ └─────────────────────┘
                                   │
                                   ▼
                        ┌─────────────────────┐
                        │  Secrets Manager    │
                        │  - DEMO_PASSWORD    │
                        │  - DATABASE_URL     │
                        │  - API Keys         │
                        └─────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                         GitHub Actions CI/CD                             │
│  ┌─────────────────────┐              ┌─────────────────────┐           │
│  │   CI (on PR)        │              │   CD (on main)      │           │
│  │  - Lint/Test        │              │  - Build/Push ECR   │           │
│  │  - Type Check       │              │  - Terraform Apply  │           │
│  │  - Security Scan    │              │  - Deploy/Test      │           │
│  └─────────────────────┘              └─────────────────────┘           │
└─────────────────────────────────────────────────────────────────────────┘
```

**Estimated Time:** 6-10 hours

---

## 1. Prerequisites Verification

### What We're Doing
Verifying Phase 1a is complete and all deployed services are healthy before adding production features.

### Why This Matters
- **Foundation:** Phase 1b builds on Phase 1a infrastructure
- **Dependencies:** Uses existing VPC (for Phase 3 Phoenix), Secrets Manager
- **Continuity:** Existing secrets and IAM roles are reused

### 1.1 Verify Phase 1a Deployment

**Command (run in WSL terminal):**
```bash
cd ~/Projects/aws-enterprise-agentic-ai

# Test App Runner health endpoint
curl https://yhvmf3inyx.us-east-1.awsapprunner.com/health
```

**Expected Output:**
```json
{"status":"ok","environment":"aws","version":"0.1.0","api_version":"v1"}
```

**If health check fails:** Complete Phase 1a first. See `docs/completed-phases/PHASE_1A_HOW_TO_GUIDE.md`.

### 1.2 Verify CloudFront Access

**Command:**
```bash
# Test frontend loads
curl -I https://d2bhnqevtvjc7f.cloudfront.net
```

**Expected Output:** HTTP 200 status with CloudFront headers.

### 1.3 Verify Terraform State

**Command:**
```bash
cd ~/Projects/aws-enterprise-agentic-ai/terraform/environments/dev

# List current Terraform-managed resources
terraform state list | wc -l
```

**Expected Output:** 20-40 resources from Phase 1a.

### 1.4 Verify AWS Credentials

**Command:**
```bash
# Verify AWS CLI configured
aws sts get-caller-identity

# Verify region
aws configure get region
```

**Expected Output:** Your AWS account ID and `us-east-1` region.

### 1.5 Note Existing Infrastructure

Record these values from Phase 1a (you'll need them):

**Command:**
```bash
cd ~/Projects/aws-enterprise-agentic-ai/terraform/environments/dev

# Get key outputs
terraform output
```

**Save these values:**

| Item | Value |
|------|-------|
| App Runner URL | `https://yhvmf3inyx.us-east-1.awsapprunner.com` |
| CloudFront URL | `https://d2bhnqevtvjc7f.cloudfront.net` |
| VPC ID | (from terraform output) |
| Subnet IDs | (from terraform output) |
| ECR Repository URL | (from terraform output) |

### 1.6 Prerequisites Checklist

- [ ] App Runner health endpoint returns 200
- [ ] CloudFront frontend loads
- [ ] Terraform state accessible (20-40 resources)
- [ ] AWS CLI configured for us-east-1
- [ ] VPC ID and subnet IDs noted
- [ ] ECR repository URL noted

---

## 2. Neon PostgreSQL Setup

### What We're Doing
Creating a Neon PostgreSQL database for persistent conversation state. This replaces the in-memory MemorySaver with a durable database. Neon is an external serverless PostgreSQL service with a generous free tier.

### Why This Matters
- **Persistence:** Conversations survive App Runner restarts
- **Cost Optimization:** Free tier (0.5GB storage, 190 compute hours/month)
- **Simplicity:** No VPC connector needed (external service)
- **PostgreSQL Compatible:** Works with PostgresSaver and SQLAlchemy

### Why Neon Instead of Aurora?
| Aspect | Aurora Serverless v2 | Neon |
|--------|---------------------|------|
| **Cost** | ~$43/month minimum | **$0** (free tier) |
| **Setup** | VPC connector required | Just a connection string |
| **Complexity** | Terraform modules, security groups | External account, 5-minute setup |
| **PostgreSQL** | Yes | Yes (same compatibility) |

### Common Issues

| Symptom | Root Cause | Fix |
|---------|------------|-----|
| Connection timeout | IP not allowlisted | Neon free tier allows all IPs by default |
| "password authentication failed" | Wrong credentials | Copy connection string from Neon dashboard |
| SSL required error | Missing sslmode | Add `?sslmode=require` to connection string |

### 2.1 Create Neon Account and Project

**Step 1: Create Account**

1. Open your browser and go to https://neon.tech
2. Click the **"Sign Up"** or **"Start Free"** button (top right)
3. Choose your sign-up method:
   - **GitHub** (recommended - fastest)
   - **Google**
   - **Email** (requires email verification)
4. Complete the sign-up process

**No credit card required** - Neon's free tier includes:
- 0.5 GB storage
- 190 compute hours/month
- 1 project

**Step 2: Create Your First Project**

After signing up, you'll be prompted to create a project:

1. **Project Name:** Enter `enterprise-agentic-ai`
2. **Region:** Select **`AWS US East (N. Virginia)`**
   - **CRITICAL:** This MUST match our AWS region (us-east-1) for lowest latency
3. **PostgreSQL Version:** Select **16** (or latest available)
4. Click **"Create Project"**

**What Happens Next:**
- Neon automatically creates a database called `neondb`
- Neon creates a default branch called `main`
- Neon generates database credentials for you
- You'll see the "Connection Details" panel

**Expected Result:** You should see your project dashboard with a connection string displayed.

### 2.2 Get Connection String

**Locate the Connection String:**

1. In your Neon project dashboard, look for the **"Connection Details"** panel
   - It's usually displayed right after project creation
   - Or click **"Connection Details"** in the left sidebar
2. You'll see a connection string that looks like:
   ```
   postgresql://neondb_owner:YOUR_NEON_PASSWORD_HERE@ep-cool-darkness-123456.us-east-1.aws.neon.tech/neondb?sslmode=require
   ```

**Understanding the Connection String Parts:**
```
postgresql://USERNAME:PASSWORD@ENDPOINT/DATABASE?sslmode=require
             └──────┘ └───────┘ └──────┘ └──────┘
                │         │         │        │
                │         │         │        └── Database name (neondb)
                │         │         └─────────── Neon endpoint (unique to your project)
                │         └───────────────────── Auto-generated password
                └─────────────────────────────── Auto-generated username
```

**Copy the Connection String:**

1. Click the **"Copy"** button (or clipboard icon) next to the connection string
2. The string will be copied to your clipboard
3. **IMPORTANT:** Paste it somewhere safe temporarily (e.g., a local text file)
   - You'll need this for the AWS secret in the next step
   - Do NOT commit this to git

**Verify Your Connection String Has:**
- [ ] Starts with `postgresql://`
- [ ] Contains `@ep-` (Neon endpoint prefix)
- [ ] Contains `.us-east-1.aws.neon.tech` (correct region)
- [ ] Ends with `?sslmode=require` (required for security)

**Troubleshooting:**
- If you don't see a password, click "Show password" or regenerate credentials
- If the region is wrong, delete the project and create a new one in us-east-1

### 2.3 Create DATABASE_URL Secret in AWS

**What We're Doing:** Storing your Neon connection string securely in AWS Secrets Manager so App Runner can access it without hardcoding credentials.

**Step 1: Prepare Your Command**

Open your WSL terminal and prepare the following command. **Replace the placeholder** with your actual Neon connection string:

```bash
# TEMPLATE - Replace YOUR_CONNECTION_STRING with the value from Neon dashboard
aws secretsmanager create-secret \
  --name enterprise-agentic-ai/database-url \
  --description "Neon PostgreSQL connection string for LangGraph checkpoints" \
  --secret-string '{"url":"YOUR_CONNECTION_STRING"}'
```

**Example with a real connection string:**
```bash
aws secretsmanager create-secret \
  --name enterprise-agentic-ai/database-url \
  --description "Neon PostgreSQL connection string for LangGraph checkpoints" \
  --secret-string '{"url":"postgresql://neondb_owner:YOUR_NEON_PASSWORD_HERE@ep-cool-darkness-123456.us-east-1.aws.neon.tech/neondb?sslmode=require"}'
```

**IMPORTANT Notes:**
- The secret value is a **JSON object** with a key called `url`
- Use **single quotes** around the JSON to prevent shell interpretation
- The connection string goes **inside double quotes** within the JSON
- Do NOT add extra spaces inside the JSON

**Step 2: Run the Command**

```bash
cd ~/Projects/aws-enterprise-agentic-ai
aws secretsmanager create-secret \
  --name enterprise-agentic-ai/database-url \
  --description "Neon PostgreSQL connection string for LangGraph checkpoints" \
  --secret-string '{"url":"YOUR_ACTUAL_CONNECTION_STRING_HERE"}'
```

**Step 3: Verify the Secret Was Created**

```bash
aws secretsmanager describe-secret --secret-id enterprise-agentic-ai/database-url
```

**Expected Output:**
```json
{
    "ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:enterprise-agentic-ai/database-url-AbCdEf",
    "Name": "enterprise-agentic-ai/database-url",
    "Description": "Neon PostgreSQL connection string for LangGraph checkpoints",
    ...
}
```

**Step 4: Verify the Secret Value (Optional)**

```bash
aws secretsmanager get-secret-value --secret-id enterprise-agentic-ai/database-url --query 'SecretString' --output text | jq
```

**Expected Output:**
```json
{
  "url": "postgresql://neondb_owner:...@ep-...us-east-1.aws.neon.tech/neondb?sslmode=require"
}
```

**Common Errors:**

| Error | Cause | Fix |
|-------|-------|-----|
| `ResourceExistsException` | Secret already exists | Delete with `aws secretsmanager delete-secret --secret-id enterprise-agentic-ai/database-url --force-delete-without-recovery` then recreate |
| `Invalid JSON` | Missing quotes or wrong format | Check JSON structure: `{"url":"..."}` |
| `Access Denied` | Wrong AWS credentials | Run `aws sts get-caller-identity` to verify |

### 2.4 Update Terraform Secrets Module

**Agent Prompt:**
```
Update `terraform/modules/secrets/main.tf` to reference the database-url secret

Add:
1. New data source:
   data "aws_secretsmanager_secret" "database_url" {
     name = "enterprise-agentic-ai/database-url"
   }

2. Add to the IAM policy document resources list:
   data.aws_secretsmanager_secret.database_url.arn

Reference:
- Existing secrets module patterns
- [infrastructure.mdc] for Terraform patterns

Verify: terraform validate
```

### 2.5 Update Terraform Secrets Outputs

**Agent Prompt:**
```
Update `terraform/modules/secrets/outputs.tf` to include database_url

Add to the secret_arns output map:
  database_url = data.aws_secretsmanager_secret.database_url.arn

Reference:
- Existing outputs.tf pattern

Verify: terraform validate
```

### 2.6 Update App Runner to Use DATABASE_URL

**Agent Prompt:**
```
Update `terraform/modules/app-runner/main.tf` to add DATABASE_URL environment secret

In the runtime_environment_secrets block, add:
  DATABASE_URL = "${var.secret_arns["database_url"]}:url::"

Note: The secret format is ARN:jsonKey:: where "url" is the key in our JSON secret.

Reference:
- Existing runtime_environment_secrets pattern
- [infrastructure.mdc] for App Runner patterns

Verify: terraform validate
```

### 2.7 Apply Terraform Changes

**Commands:**
```bash
cd ~/Projects/aws-enterprise-agentic-ai/terraform/environments/dev

# Preview changes
terraform plan

# Review the plan - should show:
# - Secrets module update (reading new secret)
# - App Runner update (adding DATABASE_URL env var)

# Apply changes
terraform apply
```

**When prompted, verify the plan shows:**
- Changes to App Runner service (adding environment variable)
- No resources being destroyed

Type `yes` to apply.

**Verify App Runner Updated:**
```bash
# Wait 2-3 minutes for deployment
curl https://yhvmf3inyx.us-east-1.awsapprunner.com/health
```

### 2.8 Test Database Connection

**Option A: Test with psql (if installed in WSL)**

```bash
# Replace with your actual Neon connection string
psql "postgresql://neondb_owner:YOUR_NEON_PASSWORD_HERE@ep-cool-darkness-123456.us-east-1.aws.neon.tech/neondb?sslmode=require" -c "SELECT version();"
```

**Expected Output:**
```
                          version                                                      
-----------------------------------------------------------------------------------
 PostgreSQL 16.x on x86_64-pc-linux-gnu, compiled by gcc...
(1 row)
```

**Option B: Test with Python in Docker**

```bash
cd ~/Projects/aws-enterprise-agentic-ai

# Pass DATABASE_URL directly to the container for testing
docker-compose exec -e DATABASE_URL="postgresql://neondb_owner:YOUR_NEON_PASSWORD_HERE@ep-cool-darkness-123456.us-east-1.aws.neon.tech/neondb?sslmode=require" backend python -c "
from sqlalchemy import create_engine, text
import os
url = os.environ.get('DATABASE_URL')
print(f'Connecting to: {url[:50]}...')
engine = create_engine(url)
with engine.connect() as conn:
    result = conn.execute(text('SELECT version()'))
    print(f'SUCCESS: {result.fetchone()[0][:60]}...')
"
```

**Expected Output:**
```
Connecting to: postgresql://neondb_owner:...
SUCCESS: PostgreSQL 16.x on x86_64-pc-linux-gnu...
```

**Option C: Test connectivity with curl (basic check)**

```bash
# This just verifies the endpoint is reachable (not a full database test)
# Neon endpoints don't respond to HTTP, but you can check DNS resolution
nslookup ep-cool-darkness-123456.us-east-1.aws.neon.tech
```

**Troubleshooting Connection Issues:**

| Symptom | Cause | Solution |
|---------|-------|----------|
| `connection refused` | Firewall or endpoint typo | Verify endpoint URL in Neon dashboard |
| `password authentication failed` | Wrong password | Copy fresh connection string from Neon |
| `SSL required` | Missing `?sslmode=require` | Add `?sslmode=require` to connection string |
| `timeout` | Network issue | Check internet connection, try again |
| `could not translate host name` | DNS issue or typo | Verify endpoint spelling |

### 2.9 Neon Setup Checklist

**Account & Project:**
- [ ] Neon account created at neon.tech (free tier, no credit card required)
- [ ] Project named `enterprise-agentic-ai` created
- [ ] Region is `AWS US East (N. Virginia)` / us-east-1 (verify this!)
- [ ] Connection string copied and saved temporarily

**AWS Secrets Manager:**
- [ ] Secret `enterprise-agentic-ai/database-url` created
- [ ] Secret contains JSON with `url` key: `{"url":"postgresql://..."}`
- [ ] Verified with `aws secretsmanager describe-secret`

**Terraform Updates:**
- [ ] `terraform/modules/secrets/main.tf` - Added `data.aws_secretsmanager_secret.database_url`
- [ ] `terraform/modules/secrets/outputs.tf` - Added `database_url` to `secret_arns` map
- [ ] `terraform/modules/app-runner/main.tf` - Added `DATABASE_URL` to `runtime_environment_secrets`
- [ ] `terraform validate` passes
- [ ] `terraform plan` shows expected changes (App Runner update)
- [ ] `terraform apply` completed successfully

**Verification:**
- [ ] App Runner service redeployed (check AWS Console or wait 2-3 min)
- [ ] Health endpoint responds: `curl https://YOUR_APP_RUNNER_URL/health`
- [ ] Database connection tested (psql or Python test passed)

---

## 3. Database Package Setup

### What We're Doing
Creating a database package with SQLAlchemy session management and connection pooling for the FastAPI backend.

### Why This Matters
- **Connection Pooling:** Efficient database connections (5 base, 10 max)
- **Session Management:** Proper transaction handling
- **Reusability:** Centralized database configuration

### 3.1 Create Database Package

**Agent Prompt:**
```
Create `backend/src/db/__init__.py`

Contents:
1. Export get_engine, get_session, SessionLocal from session module
2. Docstring explaining the database package purpose

Reference:
- [backend.mdc] for Python patterns
- Standard SQLAlchemy patterns

Verify: Check for linter errors
```

### 3.2 Create Session Management Module

**Agent Prompt:**
```
Create `backend/src/db/session.py`

Requirements:
1. Import from sqlalchemy: create_engine, Engine
2. Import from sqlalchemy.orm: sessionmaker, Session
3. Import from src.config.settings import get_settings

Structure:
- _engine: Engine | None = None (module-level singleton)

- get_engine() -> Engine function:
  - Returns existing _engine if set
  - Creates new engine from settings.database_url
  - Connection pool settings:
    - pool_size = 5
    - max_overflow = 10
    - pool_pre_ping = True (connection health check)
    - pool_recycle = 300 (5 minutes)
  - For local dev (no DATABASE_URL), return None or raise helpful error
  - Cache engine in _engine global

- SessionLocal = sessionmaker(autocommit=False, autoflush=False)

- get_session() -> Generator[Session, None, None]:
  - Dependency injection function for FastAPI
  - Gets engine, binds to SessionLocal if not bound
  - Yields session
  - Closes session in finally block

- init_db() -> None:
  - Called at startup to verify database connection
  - Logs success or raises clear error

Key Features:
- Lazy engine initialization (only when needed)
- Connection pooling for performance
- pool_pre_ping prevents stale connections
- Works with or without DATABASE_URL (graceful fallback for local dev)

Error Handling:
- Clear error message if DATABASE_URL not set in AWS
- Log warning for local dev without database

Reference:
- SQLAlchemy 2.0 docs: https://docs.sqlalchemy.org/en/20/
- [backend.mdc] for Python patterns
- FastAPI dependency injection patterns

Verify: docker-compose exec backend python -c "from src.db.session import get_engine; print('OK')"
```

### 3.3 Verify Settings for Database URL

**Note:** The `database_url` field already exists in settings.py (see lines 266-277). Verify it's configured correctly.

**Agent Prompt:**
```
Verify `backend/src/config/settings.py` has database connection pool settings

The file should already have:
1. database_url field (already exists at line 266)
2. postgres_* fields for local dev (already exist)
3. populate_database_url model_validator (already exists)

Optional additions (if not present):
- db_pool_size: int = Field(default=5, description="SQLAlchemy pool size")
- db_max_overflow: int = Field(default=10, description="SQLAlchemy max overflow")
- db_pool_recycle: int = Field(default=300, description="Connection recycle time in seconds")

These are optional because session.py will use its own pool settings.

Reference:
- Existing settings.py patterns (already has comprehensive database config)

Verify: docker-compose exec backend python -c "from src.config.settings import get_settings; print(get_settings().database_url)"
```

### 3.4 Database Package Checklist

- [ ] backend/src/db/__init__.py created
- [ ] backend/src/db/session.py created with connection pooling
- [ ] settings.py updated with database_url field
- [ ] Local import test passes

---

## 4. Alembic Migrations

### What We're Doing
Setting up Alembic for database schema versioning (checkpoint tables are handled by PostgresSaver.setup()).

### Why This Matters
- **Schema Versioning:** Track database changes over time
- **Reproducibility:** Apply same migrations in all environments
- **Rollback:** Ability to undo schema changes if needed

### 4.1 Initialize Alembic

**Commands:**
```bash
cd ~/Projects/aws-enterprise-agentic-ai

# Start backend container
docker-compose up -d backend

# Initialize Alembic in backend directory
docker-compose exec backend bash -c "cd /app && alembic init alembic"
```

**Expected Output:** Creates `backend/alembic/` directory with configuration files.

### 4.2 Configure Alembic

**Agent Prompt:**
```
Update `backend/alembic.ini` for project configuration

Changes:
1. Update sqlalchemy.url line:
   - Comment out the default:
   # sqlalchemy.url = driver://user:pass@localhost/dbname
   - Add comment: # URL is set programmatically in env.py from settings

2. Update script_location:
   script_location = alembic

3. Keep other defaults

Reference:
- Alembic documentation: https://alembic.sqlalchemy.org/en/latest/
- Database URL comes from settings, not hardcoded

Verify: File exists and is valid INI format
```

### 4.3 Update Alembic env.py

**Agent Prompt:**
```
Update `backend/alembic/env.py` for dynamic database URL

Changes:
1. Add imports at top:
   import sys
   from pathlib import Path
   
   # Add backend/src to path for imports
   sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
   
   from config.settings import get_settings

2. In run_migrations_offline() function:
   - Get URL from settings: url = get_settings().database_url
   - If url is None, raise RuntimeError("DATABASE_URL not configured")
   - Use url instead of config.get_main_option("sqlalchemy.url")

3. In run_migrations_online() function:
   - Get URL from settings: url = get_settings().database_url
   - If url is None, raise RuntimeError("DATABASE_URL not configured")
   - Create engine with url instead of using engine_from_config

4. Keep target_metadata = None:
   - Leave as is (required by Alembic, will be updated when adding SQLAlchemy models)

Configuration:
- Settings loads DATABASE_URL from environment or Secrets Manager
- Works in both local and AWS environments

Reference:
- Alembic env.py documentation
- Existing settings.py patterns

Verify: docker-compose exec backend alembic --help
```

### 4.4 ~~Create Initial Migration for LangGraph Checkpoints~~ (REMOVED)

> **Note:** This section was removed. The `langgraph-checkpoint-postgres` library manages its own schema via `PostgresSaver.setup()`, which:
> - Creates tables: `checkpoints`, `checkpoint_writes`, `checkpoint_blobs`
> - Tracks migrations in `checkpoint_migrations` table
> - Handles schema evolution automatically
>
> **Do NOT create Alembic migrations for checkpoint tables.** The library's internal schema may differ from documentation and is subject to change between versions.

### 4.5 Verify Alembic Setup

Alembic is now configured for future application migrations (user tables, etc.). Checkpoint tables are handled by `PostgresSaver.setup()` in Section 5.

```bash
# Verify Alembic is configured correctly
docker-compose exec backend alembic --help
```

### 4.6 Alembic Checklist

- [ ] Alembic initialized in backend directory
- [ ] alembic.ini configured (URL from settings)
- [ ] env.py updated for dynamic URL loading
- [ ] (Checkpoint tables: handled by PostgresSaver.setup() - see Section 5)

---

## 5. PostgresSaver Migration

### What We're Doing
Replacing the in-memory MemorySaver with PostgresSaver for persistent conversation state that survives App Runner restarts.

### Security Note

**Good news:** The `langgraph-checkpoint-postgres` package handles all database operations for checkpoint tables internally. You don't write any SQL queries for checkpoint operations - the library manages:
- Table creation/migration (via its `setup()` method or our Alembic migration)
- Parameterized queries for all checkpoint operations
- Proper connection handling

**What this means for Phase 1b:**
- ✅ No custom SQL code needed for checkpoints
- ✅ The library handles SQL injection prevention internally
- ✅ You only need to provide a valid DATABASE_URL

**For Phase 2 (SQL Query Tool):**
When implementing the SQL query tool that allows natural language database queries, you'll need to implement the full SQL security measures documented in `[_security.mdc]`:
- Parameterized queries only
- Table/column whitelisting (ALLOWED_TABLES)
- Query restrictions and timeouts
- Input validation with Pydantic

**Reference:** See `[_security.mdc]` for complete SQL security patterns when needed.

### Why This Matters
- **Persistence:** Conversations survive restarts
- **Multi-Instance:** Multiple App Runner instances share state
- **Production-Ready:** Enterprise-grade state management

### 5.1 Update Requirements

**Agent Prompt:**
```
Update `backend/requirements.txt` to add PostgresSaver dependencies

Add these packages to the Database section:
- langgraph-checkpoint-postgres~=2.0.0

Note:
- langgraph-checkpoint-postgres uses psycopg3 (v3) internally for async operations
- The existing psycopg2-binary is used by SQLAlchemy for sync operations and can coexist
- psycopg3 will be installed automatically as a dependency of langgraph-checkpoint-postgres
- Both versions are compatible and serve different purposes (sync vs async)

Add under "# Database (Phase 1b+, but include now for consistency)":
langgraph-checkpoint-postgres~=2.0.0

Reference:
- DEVELOPMENT_REFERENCE.md for version patterns
- langgraph-checkpoint-postgres requires psycopg>=3.1 (installed automatically)

Verify: docker-compose exec backend pip install -r requirements.txt
```

### 5.2 Update Agent Graph for PostgresSaver

**Agent Prompt:**
```
Update `backend/src/agent/graph.py` for PostgresSaver

IMPORTANT: This file currently has a module-level checkpointer. We need to make it 
configurable to support both MemorySaver (local) and PostgresSaver (AWS).

Changes:
1. The MemorySaver import already exists. Add conditional import for PostgresSaver:
   
   # Conditional import for PostgresSaver (requires langgraph-checkpoint-postgres)
   try:
       from langgraph.checkpoint.postgres import PostgresSaver
       POSTGRES_AVAILABLE = True
   except ImportError:
       POSTGRES_AVAILABLE = False

2. Add get_checkpointer() function BEFORE graph construction:
   
   def get_checkpointer(database_url: str | None = None):
       """Get appropriate checkpointer based on environment.
       
       Args:
           database_url: PostgreSQL connection string. If provided and valid,
                        uses PostgresSaver. Otherwise falls back to MemorySaver.
       
       Returns:
           A LangGraph checkpointer instance.
       """
       if database_url and POSTGRES_AVAILABLE:
           try:
               saver = PostgresSaver.from_conn_string(database_url)
               saver.setup()  # Creates tables if they don't exist
               return saver
           except Exception as e:
               import logging
               logging.warning(f"PostgresSaver failed, using MemorySaver: {e}")
       
       return MemorySaver()

3. REPLACE the existing module-level checkpointer with a function:
   
   OLD (remove this):
   checkpointer = MemorySaver()
   graph = _graph_builder.compile(checkpointer=checkpointer)
   
   NEW (add this):
   # Default checkpointer for local development
   _default_checkpointer = MemorySaver()
   
   def build_graph(checkpointer=None):
       """Build the agent graph with the specified checkpointer."""
       if checkpointer is None:
           checkpointer = _default_checkpointer
       return _graph_builder.compile(checkpointer=checkpointer)
   
   # For backward compatibility, create default graph
   graph = build_graph()

4. Update __all__ export:
   __all__ = ["graph", "build_graph", "get_registered_tools", "get_checkpointer"]

Key Features:
- Backward compatible: existing code using `graph` still works
- Configurable: build_graph(checkpointer) allows custom checkpointer
- Auto-setup: PostgresSaver.setup() creates checkpoint tables

Reference:
- langgraph-checkpoint-postgres documentation
- Existing graph.py structure (lines 1-126)
- [agent.mdc] for LangGraph patterns

Verify: docker-compose exec backend python -c "from src.agent.graph import get_checkpointer, build_graph; print('OK')"
```

### 5.3 Update Agent Initialization

**Agent Prompt:**
```
Update `backend/src/agent/__init__.py` to initialize checkpointer

Changes:
1. Import get_checkpointer from graph module

2. In agent initialization or get_agent() function:
   - Get checkpointer using get_checkpointer(settings)
   - Log checkpointer type: logger.info("Using checkpointer", type=type(checkpointer).__name__)
   - Pass checkpointer when building graph

3. Add setup step for PostgresSaver:
   - If checkpointer is PostgresSaver, call checkpointer.setup()
   - This creates checkpoint tables if they don't exist
   - Log success: logger.info("PostgresSaver tables initialized")

Reference:
- Existing __init__.py patterns
- graph.py get_checkpointer function
- [agent.mdc] for initialization patterns

Verify: docker-compose exec backend python -c "from src.agent import get_agent; print('OK')"
```

### 5.4 Test PostgresSaver Locally (Optional)

If you have a local PostgreSQL for testing:

```bash
# Set DATABASE_URL for local testing
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/test"

# Test checkpointer initialization
docker-compose exec backend python -c "
from src.config.settings import get_settings
from src.agent.graph import get_checkpointer
settings = get_settings()
cp = get_checkpointer(settings)
print(f'Checkpointer: {type(cp).__name__}')
"
```

### 5.5 PostgresSaver Checklist

- [ ] requirements.txt updated with langgraph-checkpoint-postgres (psycopg3 installs as dependency)
- [ ] graph.py updated with get_checkpointer function
- [ ] **main.py lifespan initializes checkpointer and stores graph in app.state** ⚠️ Critical!
- [ ] **Chat routes use request.app.state.graph instead of module-level import** ⚠️ Critical!
- [ ] PostgresSaver setup() called for table creation
- [ ] Fallback to MemorySaver works for local dev
- [ ] App Runner logs show "checkpointer_type=PostgresSaver" on startup

### 5.6 Critical: Initialize PostgresSaver in Application Lifespan

> **⚠️ IMPORTANT:** The previous steps add PostgresSaver *capability* to `graph.py`, but the application won't actually USE it unless `main.py` is updated to initialize the checkpointer at startup and chat routes are updated to use the graph from `app.state`.
>
> **The Problem:** Without this step, the chat routes import the module-level `graph` from `graph.py`, which is created with `MemorySaver()` at import time. Even though `get_checkpointer()` and `build_graph()` exist, they're never called!
>
> **The Solution:** Update `main.py` lifespan to initialize PostgresSaver and store the graph in `app.state`, then update chat routes to use `request.app.state.graph`.

**Agent Prompt:**
```
Update `backend/src/api/main.py` to initialize PostgresSaver in the lifespan

The issue: While graph.py has get_checkpointer() and build_graph() functions for 
PostgresSaver support, main.py never calls them. The chat routes import the 
module-level `graph` which always uses MemorySaver.

Changes to main.py:

1. Add import at the top:
   from src.agent.graph import build_graph, get_checkpointer

2. Update the lifespan function to initialize the checkpointer:
   
   After configuration validation, add:
   
   # Initialize checkpointer and graph
   # get_checkpointer() returns PostgresSaver if database_url is set,
   # otherwise falls back to MemorySaver for local development
   database_url = settings.database_url
   logger.info(
       "initializing_checkpointer",
       has_database_url=bool(database_url),
       environment=settings.environment,
   )

   with get_checkpointer(database_url) as checkpointer:
       # Store checkpointer and graph in app.state for access by routes
       app.state.checkpointer = checkpointer
       app.state.graph = build_graph(checkpointer)

       logger.info(
           "checkpointer_initialized",
           checkpointer_type=type(checkpointer).__name__,
       )

       logger.info(
           "application_started",
           version=__version__,
           api_version=__api_version__,
       )

       yield  # Application runs here - keeps checkpointer connection open

   # PostgresSaver connection automatically closes when exiting context
   logger.info("application_shutting_down")

IMPORTANT: The `yield` must be INSIDE the `with get_checkpointer()` block so the 
database connection stays open for the lifetime of the application.

Reference:
- graph.py get_checkpointer() docstring shows the pattern
- PostgresSaver.from_conn_string() is a context manager

Verify: Check App Runner logs for "checkpointer_initialized" with "checkpointer_type=PostgresSaver"
```

**Agent Prompt:**
```
Update chat routes to use graph from app.state instead of module-level import

The issue: Chat routes import `from src.agent.graph import graph` which is the 
module-level graph created with MemorySaver. They need to use the graph from 
app.state which is initialized with PostgresSaver.

Changes to `backend/src/api/routes/chat.py`:

1. Remove the module-level graph import:
   REMOVE: from src.agent.graph import graph

2. Update _stream_langgraph_events function signature to accept graph:
   async def _stream_langgraph_events(
       conversation_id: str, user_message: str, settings: Settings, graph: Any
   ) -> None:

3. Update the post_chat endpoint to get graph from app.state and pass it:
   if use_real_agent:
       # Get the graph from app.state (initialized with PostgresSaver in lifespan)
       graph = request.app.state.graph
       asyncio.create_task(
           _stream_langgraph_events(conversation_id, message_text, settings, graph)
       )

Apply the same changes to `backend/src/api/routes/v1/chat.py`.

Reference:
- main.py stores graph in app.state.graph
- FastAPI request object has app.state accessible

Verify: 
- docker-compose restart backend
- Check logs for "checkpointer_initialized" 
- Test conversation memory persists across messages
```

### 5.7 Verify PostgresSaver is Active

After deployment, check App Runner logs for these entries:

**Expected startup logs:**
```
initializing_checkpointer  has_database_url=True  environment=aws
postgres_checkpointer_created  message="Using PostgresSaver for persistent checkpointing"
checkpointer_initialized  checkpointer_type=PostgresSaver
```

**If you see this instead (problem!):**
```
checkpointer_initialized  checkpointer_type=InMemorySaver
```

**Troubleshooting:**

| Log Entry | Meaning | Solution |
|-----------|---------|----------|
| `has_database_url=False` | DATABASE_URL not set | Check App Runner env vars for DATABASE_URL |
| `postgres_checkpointer_failed` | Connection to Neon failed | Verify Neon connection string format |
| `checkpointer_type=InMemorySaver` | Fallback triggered | Check DATABASE_URL secret in Secrets Manager |

### 5.8 Frontend: Persist Conversation ID Across Page Refresh

> **⚠️ IMPORTANT:** The backend now correctly persists conversation memory in PostgreSQL, but the frontend must also persist the `conversationId` across page refreshes. Without this, every page refresh generates a NEW conversation_id, starting a fresh conversation with no memory!

**The Problem:** By default, `conversationId` is stored only in React state:
```typescript
const [conversationId, setConversationId] = useState<string | null>(null);
```
This state is **lost on page refresh**, so each refresh starts a new conversation.

**The Solution:** Persist `conversationId` in `sessionStorage` and add a "New Chat" button.

**Agent Prompt:**
```
Update `frontend/src/app/page.tsx` to persist conversationId in sessionStorage

The issue: conversationId is stored only in React state and lost on page refresh.
Each refresh generates a new conversation, losing memory even though the backend
correctly persists it in PostgreSQL.

Changes needed:

1. Initialize conversationId from sessionStorage:
   
   const [conversationId, setConversationId] = useState<string | null>(() => {
     if (typeof window !== "undefined") {
       return sessionStorage.getItem("conversationId");
     }
     return null;
   });

2. Add useEffect to save conversationId when it changes:
   
   useEffect(() => {
     if (conversationId) {
       sessionStorage.setItem("conversationId", conversationId);
     }
   }, [conversationId]);

3. Add a "New Chat" button handler to start fresh conversations:
   
   const handleNewConversation = useCallback(() => {
     sessionStorage.removeItem("conversationId");
     setConversationId(null);
     setMessages([]);
     if (eventSourceRef.current) {
       eventSourceRef.current.close();
       eventSourceRef.current = null;
     }
   }, []);

4. Add a "New Chat" button to the chat header (in chatHeader useMemo):
   
   <button
     onClick={handleNewConversation}
     className="text-xs text-muted-foreground hover:text-foreground transition-colors px-2 py-1 rounded hover:bg-muted"
     title="Start a new conversation"
   >
     New Chat
   </button>

5. Update chatHeader useMemo dependencies to include handleNewConversation:
   
   }, [handleNewConversation]);

Verify:
1. Send: "My favorite food is pizza"
2. Refresh the page (F5)
3. Ask: "What's my favorite food?"
4. AI should remember "pizza"
5. Click "New Chat" to verify it starts fresh
```

### 5.9 Memory Persistence Checklist

- [ ] Backend: AsyncPostgresSaver initialized (check startup logs)
- [ ] Backend: Chat routes use `request.app.state.graph`
- [ ] Frontend: conversationId initialized from sessionStorage
- [ ] Frontend: conversationId saved to sessionStorage on change
- [ ] Frontend: "New Chat" button clears sessionStorage and starts fresh
- [ ] Test: Memory persists across page refresh (same conversation_id in logs)
- [ ] Test: "New Chat" creates new conversation_id

---

## 6. Rate Limiting

### What We're Doing
Adding slowapi rate limiting middleware to prevent abuse and ensure fair usage of the API.

### Why This Matters
- **Security:** Prevents denial-of-service attacks
- **Cost Control:** Limits Bedrock API usage
- **Fair Usage:** Ensures all users get reasonable access

### 6.1 Create Rate Limiting Middleware

**Agent Prompt:**
```
Create `backend/src/api/middleware/rate_limit.py`

Requirements:
1. Import from slowapi: Limiter, _rate_limit_exceeded_handler
2. Import from slowapi.util: get_remote_address
3. Import from slowapi.errors: RateLimitExceeded
4. Import from starlette.requests: Request
5. Import from starlette.responses: JSONResponse

Structure:
- limiter = Limiter(key_func=get_remote_address)

- rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
  - Return JSONResponse with status 429
  - Body: {"detail": "Rate limit exceeded. Please wait before making more requests.", "retry_after": exc.detail}
  - Headers: {"Retry-After": str(exc.detail)}

- get_limiter() -> Limiter:
  - Returns the limiter instance

- DEFAULT_RATE_LIMIT = "10/minute"

Key Features:
- 10 requests per minute per IP address
- User-friendly error message (not technical)
- Retry-After header for client handling

Configuration:
- Rate limit configurable via settings (future enhancement)
- Uses IP address as rate limit key

Reference:
- slowapi documentation: https://slowapi.readthedocs.io/
- [backend.mdc] for middleware patterns
- [_security.mdc] for rate limiting requirements

Verify: docker-compose exec backend python -c "from src.api.middleware.rate_limit import limiter; print('OK')"
```

### 6.2 Update FastAPI App with Rate Limiting

**Agent Prompt:**
```
Update `backend/src/api/main.py` to add rate limiting

Changes:
1. Import rate limiting components (use OUR custom handler, not slowapi's):
   from src.api.middleware.rate_limit import limiter, rate_limit_exceeded_handler
   from slowapi.errors import RateLimitExceeded

2. After creating FastAPI app, add:
   app.state.limiter = limiter
   app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

3. The limiter will be used via decorators on individual routes

Note: We use our custom rate_limit_exceeded_handler (from rate_limit.py) for 
user-friendly error messages, NOT slowapi's default _rate_limit_exceeded_handler.

Reference:
- Existing main.py structure
- slowapi FastAPI integration
- Rate limit middleware module (Section 7.1)

Verify: docker-compose exec backend python -c "from src.api.main import app; print('limiter' in dir(app.state))"
```

### 6.3 Apply Rate Limits to Chat Endpoints

**Agent Prompt:**
```
Update `backend/src/api/routes/chat.py` to apply rate limits

Changes:
1. Import limiter and default rate:
   from src.api.middleware.rate_limit import limiter, DEFAULT_RATE_LIMIT

2. Apply rate limit decorator to chat endpoints:
   
   @router.post("/api/chat")
   @limiter.limit(DEFAULT_RATE_LIMIT)
   async def chat(request: Request, ...):
       ...
   
   @router.get("/api/chat")
   @limiter.limit(DEFAULT_RATE_LIMIT)
   async def chat_stream(request: Request, ...):
       ...

3. Ensure Request is passed as first parameter (required by slowapi)

Configuration:
- 10 requests per minute per IP
- Applied to both POST and GET chat endpoints
- Health endpoints are NOT rate limited

Reference:
- Existing chat.py structure
- slowapi decorator usage
- [_security.mdc] for rate limiting

Verify: Check for linter errors
```

### 6.4 Rate Limiting Checklist

- [ ] rate_limit.py middleware created
- [ ] main.py updated with limiter and exception handler
- [ ] Chat endpoints decorated with rate limit
- [ ] Rate limit set to 10/minute
- [ ] Health endpoints NOT rate limited

---

## 7. API Versioning

### What We're Doing
Moving chat endpoints to versioned routes (/api/v1/chat) to allow future API evolution without breaking existing clients.

### Why This Matters
- **Backward Compatibility:** Old clients continue working
- **Future-Proofing:** Can add /api/v2 later
- **Best Practice:** Enterprise APIs use versioning

### 7.1 Update V1 Router

**Note:** The file `backend/src/api/routes/v1/__init__.py` already exists as a placeholder. 
We need to add the actual router content.

**Agent Prompt:**
```
Update `backend/src/api/routes/v1/__init__.py`

The file currently contains only a docstring. Replace it with:

1. Import APIRouter from fastapi
2. Import chat router from v1.chat (to be created in 8.2)
3. Create router with prefix="" (prefix is applied in main.py) and tags=["v1"]
4. Include chat router

Structure:
"""Versioned API routes (v1)."""
from fastapi import APIRouter

from src.api.routes.v1 import chat

router = APIRouter(tags=["v1"])
router.include_router(chat.router)

__all__ = ["router"]

Note: The /api/v1 prefix will be applied when including this router in main.py

Reference:
- FastAPI router patterns
- Existing routes/__init__.py for patterns

Verify: Import test passes after creating chat.py in 8.2
```

### 7.2 Create V1 Chat Routes

**Agent Prompt:**
```
Create `backend/src/api/routes/v1/chat.py`

Requirements:
1. Copy functionality from existing chat.py
2. Update route paths:
   - POST /chat (relative to /api/v1 prefix)
   - GET /chat (for SSE streaming)
3. Apply rate limiting with decorator
4. Keep all existing functionality

Key Features:
- Same functionality as existing chat routes
- Rate limiting applied
- Proper streaming support

Reference:
- Existing backend/src/api/routes/chat.py
- Rate limiting middleware
- [backend.mdc] for route patterns

Verify: Import test passes
```

### 7.3 Update Main App for V1 Router

**Agent Prompt:**
```
Update `backend/src/api/main.py` to include V1 router

Changes:
1. Import v1 router:
   from src.api.routes.v1 import router as v1_router

2. Include v1 router WITH prefix:
   app.include_router(v1_router, prefix="/api/v1")
   
   CRITICAL: The prefix="/api/v1" ensures routes are mounted at /api/v1/chat

3. Keep existing /api/chat routes for backward compatibility
4. Add deprecation warning to old routes (optional):
   - Log warning when old routes are used
   - Add response header: X-Deprecated: true

Reference:
- Existing main.py structure
- V1 router module

Verify: docker-compose exec backend python -c "from src.api.main import app; print([r.path for r in app.routes])"

Expected output should include: '/api/v1/chat'
```

### 7.4 Update Frontend for V1 API

**Agent Prompt:**
```
Update `frontend/src/lib/api.ts` to use V1 API routes

Changes:
1. Update connectSSE function:
   - Change: buildUrl("/api/chat") → buildUrl("/api/v1/chat")
   - This updates the SSE streaming endpoint

2. Update sendMessage function:
   - Change: fetch(buildUrl("/api/chat"), ...) → fetch(buildUrl("/api/v1/chat"), ...)
   - This updates the POST endpoint for sending messages

3. Keep other endpoints unchanged:
   - /health remains /health (not versioned)
   - /api/me, /api/login, /api/logout remain unchanged (auth endpoints)

Current code uses "/api/chat" in these locations:
- Line ~112: connectSSE function (SSE streaming)
- Line ~166: sendMessage function (POST request)

Reference:
- Existing api.ts structure
- [frontend.mdc] for TypeScript patterns

Verify: 
- npm run lint
- npm run build (ensure no TypeScript errors)
```

### 7.5 API Versioning Checklist

- [ ] V1 router created at routes/v1/__init__.py
- [ ] V1 chat routes created at routes/v1/chat.py
- [ ] main.py includes V1 router
- [ ] Old routes kept for backward compatibility
- [ ] Frontend updated to use /api/v1/chat
- [ ] Rate limiting applied to V1 routes

---

## 8. Enhanced Health Checks

### What We're Doing
Upgrading the health endpoint to check dependencies (Neon database, Bedrock) for better monitoring and debugging.

### Why This Matters
- **Reliability:** Know when dependencies are down
- **Debugging:** Faster issue identification
- **Operations:** Load balancer health checks

### 8.1 Update Health Endpoint

**Agent Prompt:**
```
Update `backend/src/api/routes/health.py` for dependency checks

Changes:
1. Add check_database() function:
   - Attempt database connection using get_engine()
   - Execute simple query: SELECT 1
   - Return {"status": "ok", "latency_ms": X} or {"status": "error", "error": "message"}
   - Timeout after 5 seconds

2. Add check_bedrock() function:
   - Attempt to list available models or simple API call
   - Return {"status": "ok"} or {"status": "error", "error": "message"}
   - Timeout after 5 seconds

3. Update health endpoint response:
   {
     "status": "ok" | "degraded" | "error",
     "environment": "aws" | "local",
     "version": "0.1.0",
     "api_version": "v1",
     "checks": {
       "database": {"status": "ok", "latency_ms": 50},
       "bedrock": {"status": "ok"}
     }
   }

4. Status logic:
   - "ok": All checks pass
   - "degraded": Some checks fail but service can function
   - "error": Critical checks fail

5. Make dependency checks optional (don't fail health if database unavailable during startup)

Key Features:
- Non-blocking checks (use asyncio.wait_for with timeout)
- Graceful degradation
- Latency tracking for database

Reference:
- Existing health.py structure
- [backend.mdc] for health check patterns

Verify: curl http://localhost:8000/health
```

### 8.2 Enhanced Health Checklist

- [ ] Health endpoint checks Neon database connection
- [ ] Health endpoint checks Bedrock access
- [ ] Health returns status: ok/degraded/error

---

## 9. GitHub Actions CI/CD

### What We're Doing
Creating GitHub Actions workflows for continuous integration (on every push) and deployment (manual trigger via GitHub UI).

### Why This Matters
- **Quality:** Every push is tested automatically
- **Control:** You decide when to deploy (manual trigger)
- **Speed:** Faster feedback on issues
- **Reliability:** Consistent deployment process
- **Simplicity:** No surprise deployments - push freely, deploy when ready

### 9.1 Create CI Workflow

**Agent Prompt:**
```
Create `.github/workflows/ci.yml`

Requirements:
1. Name: CI
2. Triggers: push to main branch AND pull_request to main branch

Jobs:

job: lint-backend
- runs-on: ubuntu-latest
- steps:
  - uses: actions/checkout@v4
  - uses: actions/setup-python@v5
    with:
      python-version: '3.11'
      cache: 'pip'
      cache-dependency-path: backend/requirements.txt
  - Install dependencies: pip install -r backend/requirements.txt
  - Run black: black --check backend/src/
  - Run ruff: ruff check backend/src/
  - Run mypy: mypy backend/src/ --ignore-missing-imports

job: lint-frontend
- runs-on: ubuntu-latest
- defaults: run: working-directory: frontend
- steps:
  - uses: actions/checkout@v4
  - uses: actions/setup-node@v4
    with:
      node-version: '20'
      cache: 'npm'
      cache-dependency-path: frontend/package-lock.json
  - Install: npm ci
  - Run lint: npm run lint
  - Run type check: npx tsc --noEmit
  Note: package.json doesn't have type-check script, use tsc directly

job: test-backend
- runs-on: ubuntu-latest
- steps:
  - uses: actions/checkout@v4
  - uses: actions/setup-python@v5
    with:
      python-version: '3.11'
      cache: 'pip'
      cache-dependency-path: backend/requirements.txt
  - Install dependencies: pip install -r backend/requirements.txt
  - Run pytest: pytest backend/tests/ -v --cov=backend/src --cov-report=xml

job: terraform-validate
- runs-on: ubuntu-latest
- steps:
  - uses: actions/checkout@v4
  - uses: hashicorp/setup-terraform@v3
  - terraform fmt -check -recursive terraform/
  - terraform init -backend=false (in terraform/environments/dev)
  - terraform validate

job: security-scan
- runs-on: ubuntu-latest
- steps:
  - uses: actions/checkout@v4
  - Run bandit: pip install bandit && bandit -r backend/src/
  - Run gitleaks: uses: gitleaks/gitleaks-action@v2

Configuration:
- All jobs run in parallel
- Fail fast if any job fails
- Cache pip and npm dependencies for speed

Reference:
- GitHub Actions documentation
- DEVELOPMENT_REFERENCE.md for CI patterns
- [backend.mdc] for test patterns

Post-creation:
- Update REPO_STATE.md to add workflow file
```

### 9.2 Create CD Workflow

> **⚠️ CRITICAL: Service Name Mismatch**
>
> The ECR repository and App Runner service have **different naming patterns**:
> - **ECR repository**: `enterprise-agentic-ai-backend` (no environment suffix)
> - **App Runner service**: `enterprise-agentic-ai-dev-backend` (includes `-dev-` environment suffix)
>
> This is because Terraform creates the App Runner service with pattern: `${project_name}-${environment}-backend`
>
> **The CD workflow MUST use the correct App Runner service name or the deployment trigger will silently fail!**

**Agent Prompt:**
```
Create `.github/workflows/deploy.yml`

Requirements:
1. Name: Deploy
2. Triggers: workflow_dispatch (manual trigger via GitHub Actions UI)
   - Add input: environment (choice: production, default: production)
   - This allows you to deploy only when you click "Run workflow" in GitHub

Environment secrets needed (configure in GitHub repo settings):
- AWS_ACCESS_KEY_ID
- AWS_SECRET_ACCESS_KEY
- AWS_REGION (us-east-1)
- AWS_ACCOUNT_ID

Jobs:

job: build-and-deploy-backend
- runs-on: ubuntu-latest
- steps:
  - uses: actions/checkout@v4
  - Configure AWS credentials:
    uses: aws-actions/configure-aws-credentials@v4
    with:
      aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
      aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
      aws-region: ${{ secrets.AWS_REGION }}
  - Login to ECR:
    uses: aws-actions/amazon-ecr-login@v2
  - Build and push Docker image:
    - docker build -t backend -f backend/Dockerfile backend/
    - docker tag backend:latest ${{ secrets.AWS_ACCOUNT_ID }}.dkr.ecr.us-east-1.amazonaws.com/enterprise-agentic-ai-backend:latest
    - docker tag backend:latest ${{ secrets.AWS_ACCOUNT_ID }}.dkr.ecr.us-east-1.amazonaws.com/enterprise-agentic-ai-backend:${{ github.sha }}
    - docker push (both tags)
  - Trigger App Runner deployment:
    CRITICAL: Use the correct service name pattern from Terraform!
    - ECR repo name: enterprise-agentic-ai-backend (NO env suffix)
    - App Runner service name: enterprise-agentic-ai-dev-backend (WITH env suffix)
    
    SERVICE_ARN=$(aws apprunner list-services \
      --query "ServiceSummaryList[?ServiceName=='enterprise-agentic-ai-dev-backend'].ServiceArn" \
      --output text)
    
    if [ -z "$SERVICE_ARN" ] || [ "$SERVICE_ARN" == "None" ]; then
      echo "❌ App Runner service not found! Check service name."
      aws apprunner list-services --query 'ServiceSummaryList[*].ServiceName'
      exit 1
    fi
    
    aws apprunner start-deployment --service-arn "$SERVICE_ARN"

job: build-and-deploy-frontend
- runs-on: ubuntu-latest
- steps:
  - uses: actions/checkout@v4
  - uses: actions/setup-node@v4
  - npm ci (in frontend directory)
  - Get App Runner URL from AWS (or use known URL)
  - Build: NEXT_PUBLIC_API_URL=https://yhvmf3inyx.us-east-1.awsapprunner.com npm run build
  - Configure AWS credentials
  - Sync to S3: aws s3 sync frontend/out/ s3://BUCKET_NAME/ --delete
  - Invalidate CloudFront: aws cloudfront create-invalidation

job: smoke-test
- needs: [build-and-deploy-backend, build-and-deploy-frontend]
- runs-on: ubuntu-latest
- steps:
  - Wait for deployment (sleep 60)
  - Test health endpoint: curl https://yhvmf3inyx.us-east-1.awsapprunner.com/health
  - Test frontend: curl -I https://d2bhnqevtvjc7f.cloudfront.net

Configuration:
- Jobs run sequentially (deploy then test)
- Fail if smoke test fails
- Uses GitHub secrets for credentials

Reference:
- GitHub Actions documentation
- AWS Actions marketplace
- DEVELOPMENT_REFERENCE.md for CD patterns

Post-creation:
- Update REPO_STATE.md to add workflow file
```

### 9.3 Create GitHub Secrets

**Navigate in GitHub:**
1. Go to your repository on GitHub
2. Settings → Secrets and variables → Actions
3. Click "New repository secret" for each:
**#**No enviormental secrets necessary**
**Required Secrets:**
| Secret Name | Value | Source |
|-------------|-------|--------|
| AWS_ACCESS_KEY_ID | Your IAM access key | AWS Console → IAM |
| AWS_SECRET_ACCESS_KEY | Your IAM secret key | AWS Console → IAM |
| APP_RUNNER_URL | Your App Runner URL | `https://xxx.us-east-1.awsapprunner.com` from Terraform output |
| FRONTEND_S3_BUCKET | S3 bucket name | Terraform output (e.g., `enterprise-agentic-ai-frontend-xxx`) |

**Optional Secrets (for full smoke testing):**
| Secret Name | Value | Source |
|-------------|-------|--------|
| CLOUDFRONT_DISTRIBUTION_ID | Distribution ID | Terraform output (e.g., `E1234ABCD5678`) |
| CLOUDFRONT_URL | CloudFront URL | `https://xxx.cloudfront.net` from Terraform output |

**Note:** `AWS_REGION` and `AWS_ACCOUNT_ID` are NOT needed - the region is hardcoded (`us-east-1`) and the ECR login action provides the account ID automatically.

**Security Note (Public Repositories):**
- GitHub secrets are encrypted and never exposed in logs (shown as `***`)
- Forks do NOT have access to your secrets - only your repository does
- PRs from forks run with restricted permissions and cannot access secrets
- Only users with write access can trigger the manual deploy workflow
- Your AWS resources are safe - forks can only affect their own environments

### 9.4 Create Workflow Directories

**Command:**
```bash
cd ~/Projects/aws-enterprise-agentic-ai
mkdir -p .github/workflows
```

### 9.5 Test CI Workflow

**Commands:**
```bash
cd ~/Projects/aws-enterprise-agentic-ai

# Commit and push workflows
git add .github/workflows/
git commit -m "Add GitHub Actions CI/CD workflows"
git push origin main

# Create a test PR to trigger CI
git checkout -b test-ci
echo "# Test" >> README.md
git add README.md
git commit -m "Test CI workflow"
git push origin test-ci

# Create PR in GitHub UI and observe CI checks
```

### 9.6 GitHub Actions Checklist

- [ ] CI workflow created at .github/workflows/ci.yml
- [ ] CD workflow created at .github/workflows/deploy.yml
- [ ] GitHub secrets configured (AWS credentials)
- [ ] CI triggers on push to main AND pull_request
- [ ] CD triggers on workflow_dispatch (manual "Run workflow" button)
- [ ] **App Runner service name in deploy.yml matches Terraform output** (includes `-dev-` suffix!)
- [ ] Smoke test verifies deployment
- [ ] Verified: `aws apprunner list-services` shows expected service name

### 9.7 How to Deploy (Manual Process)

After CI passes and you're ready to deploy:

1. Go to your repository on GitHub
2. Click **Actions** tab
3. Select **Deploy** workflow from the left sidebar
4. Click **Run workflow** dropdown button (right side)
5. Select branch: `main`
6. Click **Run workflow** (green button)
7. Monitor the deployment progress

This gives you full control over when changes go live to AWS.

---

## 10. End-to-End Verification

### What We're Doing
Testing all Phase 1b features together to ensure the production hardening is complete and working.

### Why This Matters
- **Integration:** Verify all components work together
- **Persistence:** Confirm conversations survive restarts
- **Security:** Test rate limiting works
- **Automation:** Confirm CI/CD pipeline functions

### 10.1 Database Persistence Test

**Test conversation persistence across restarts:**

1. **Start a conversation:**
```bash
# Login and get session
curl -X POST https://yhvmf3inyx.us-east-1.awsapprunner.com/api/login \
  -H "Content-Type: application/json" \
  -d '{"password": "YOUR_PASSWORD"}' \
  -c cookies.txt

# Send a message (note the conversation_id in response)
curl -X POST https://yhvmf3inyx.us-east-1.awsapprunner.com/api/chat \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{"message": "My name is TestUser. Remember this."}'
```

2. **Force App Runner restart** (in AWS Console):
   - App Runner → Your service → Actions → Pause/Resume
   - Or: Push a new Docker image

3. **Continue conversation after restart:**
```bash
# Same conversation should remember the name
curl -X POST https://yhvmf3inyx.us-east-1.awsapprunner.com/api/chat \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{"message": "What is my name?", "conversation_id": "PREVIOUS_CONVERSATION_ID"}'
```

**Expected:** Agent remembers the name from before restart.

### 10.2 Rate Limiting Test

**Test that rate limiting works:**

```bash
# Send 15 requests rapidly (should hit 10/minute limit)
for i in {1..15}; do
  echo "Request $i:"
  curl -s -o /dev/null -w "%{http_code}\n" \
    -X POST https://yhvmf3inyx.us-east-1.awsapprunner.com/api/chat \
    -H "Content-Type: application/json" \
    -b cookies.txt \
    -d '{"message": "Test"}'
  sleep 1
done
```

**Expected:** First 10 requests return 200, subsequent requests return 429.

### 10.3 Health Check Verification

**Test enhanced health endpoint:**

```bash
curl https://yhvmf3inyx.us-east-1.awsapprunner.com/health | jq
```

**Expected Output:**
```json
{
  "status": "ok",
  "environment": "aws",
  "version": "0.1.0",
  "api_version": "v1",
  "checks": {
    "database": {"status": "ok", "latency_ms": 50},
    "bedrock": {"status": "ok"}
  }
}
```

### 10.4 CI/CD Pipeline Verification

**Test the full pipeline:**

1. Create a small change (e.g., update version in settings.py)
2. Create a PR → CI should run
3. Merge PR → CD should deploy
4. Verify changes are live

### 10.5 Neon Connection Verification

**Step 1: Check Health Endpoint Shows Database Status**

```bash
curl https://yhvmf3inyx.us-east-1.awsapprunner.com/health | jq '.checks.database'
```

**Expected Output:**
```json
{
  "status": "ok",
  "latency_ms": 45
}
```

**Step 2: Check App Runner Logs for Database Connections**

```bash
# Check App Runner logs for database connections
aws logs tail /aws/apprunner/enterprise-agentic-ai-backend \
  --since 1h \
  --filter-pattern "postgresql" \
  --format short
```

**Step 3: Verify Tables Exist in Neon**

From WSL (using your Neon connection string):
```bash
psql "YOUR_NEON_CONNECTION_STRING" -c "\dt"
```

**Expected:** Tables `checkpoints`, `checkpoint_writes`, `checkpoint_blobs` exist.

**Troubleshooting Connection Issues:**

| Symptom | Possible Cause | Solution |
|---------|----------------|----------|
| `database.status: "error"` | DATABASE_URL not set | Check App Runner env vars in AWS Console |
| `timeout` | Network issue | Verify Neon endpoint is correct region (us-east-1) |
| No tables | Migrations not run | Run `alembic upgrade head` or restart App Runner to trigger setup() |

### 10.6 Final End-to-End Test

**Complete user flow:**

1. Open https://d2bhnqevtvjc7f.cloudfront.net
2. Login with password
3. Send message: "Hello, my name is DemoUser"
4. Receive streaming response
5. Refresh page
6. Continue conversation (should remember name)
7. Send 15 rapid messages (should see rate limit)

### 10.7 End-to-End Checklist

- [ ] Conversations persist after App Runner restart
- [ ] Rate limiting kicks in after 10 requests/minute
- [ ] Health endpoint shows database and Bedrock status
- [ ] CI runs on PR creation
- [ ] CD deploys on merge to main
- [ ] Full user flow works in browser

---

## Phase 1b Completion Checklist

### Infrastructure
- [ ] Neon PostgreSQL project created
- [ ] Database connection verified
- [ ] DATABASE_URL secret created in Secrets Manager
- [ ] DATABASE_URL secret created
- [ ] App Runner updated with DATABASE_URL environment variable

### Backend Code
- [ ] Database package created (src/db/)
- [ ] SQLAlchemy session management with connection pooling
- [ ] Alembic initialized and configured
- [ ] PostgresSaver replaces MemorySaver in AWS (creates checkpoint tables via setup())
- [ ] SQL injection prevention implemented (parameterized queries, table whitelisting)
- [ ] Rate limiting middleware added (10 req/min)
- [ ] API versioned to /api/v1/chat
- [ ] Enhanced health checks (Neon database, Bedrock)

### CI/CD
- [ ] CI workflow runs on PRs
- [ ] CD workflow deploys on main push
- [ ] GitHub secrets configured
- [ ] Smoke tests pass after deployment

### Verification
- [ ] Conversations persist across restarts
- [ ] Rate limiting works (429 after 10 requests)
- [ ] Health endpoint shows dependency status
- [ ] SQL injection prevention working (parameterized queries validated)
- [ ] Full user flow works end-to-end

### Cost Verification
- [ ] Neon free tier (~$0/month)
- [ ] No unexpected resources (NAT Gateway, etc.)
- [ ] Total Phase 1 cost ~$5-15/month

---

## Common Issues and Solutions

### Issue: App Runner cannot connect to Neon database

**Symptoms:**
- Health check shows database status "error"
- Logs show "could not connect to server"
- Timeout errors on database operations

**Solutions:**
1. **Check security group:**
   ```bash
   aws ec2 describe-security-groups \
     --query 'SecurityGroups[].{ID:GroupId,Name:GroupName}'
   ```
   Verify ingress rule allows port 5432 from App Runner security group.

2. **Check DATABASE_URL secret:**
   ```bash
   aws secretsmanager get-secret-value --secret-id enterprise-agentic-ai/database-url
   ```
   Verify connector status is ACTIVE.

3. **Check database connection:**
   ```bash
   aws rds describe-db-clusters \
     --query 'DBClusters[?contains(DBClusterIdentifier, `enterprise-agentic-ai`)].Status'
   ```
   Should be "available".

### Issue: Alembic migration fails

**Symptoms:**
- "alembic upgrade head" fails
- "relation does not exist" errors

**Solutions:**
1. **Verify DATABASE_URL:**
   ```bash
   docker-compose exec backend python -c "from src.config.settings import get_settings; print(get_settings().database_url[:50])"
   ```

2. **Run migration manually:**
   ```bash
   docker-compose exec backend alembic upgrade head
   ```

3. **Check Alembic history:**
   ```bash
   docker-compose exec backend alembic history
   ```

### Issue: Rate limiting not working

**Symptoms:**
- No 429 responses even after many requests
- Rate limit header missing

**Solutions:**
1. **Check limiter is attached:**
   ```python
   from src.api.main import app
   print(hasattr(app.state, 'limiter'))
   ```

2. **Check decorator applied:**
   Verify @limiter.limit() decorator on chat routes.

3. **Check exception handler:**
   Verify RateLimitExceeded handler in main.py.

### Issue: GitHub Actions deployment fails

**Symptoms:**
- CD workflow fails
- ECR push errors
- S3 sync errors

**Solutions:**
1. **Check secrets configured:**
   - AWS_ACCESS_KEY_ID
   - AWS_SECRET_ACCESS_KEY
   - AWS_REGION
   - AWS_ACCOUNT_ID

2. **Check IAM permissions:**
   The GitHub Actions IAM user needs:
   - ECR push
   - S3 write
   - CloudFront invalidation
   - App Runner start-deployment

### Issue: Frontend updates but backend doesn't deploy

**Symptoms:**
- Frontend shows new version after GitHub Actions deploy
- Backend still running old code (check logs for old version)
- GitHub Actions shows "App Runner service not found. Skipping deployment trigger."
- No App Runner deployment triggered

**Root Cause:**
The ECR repository and App Runner service have **different naming patterns**:
- ECR repository: `enterprise-agentic-ai-backend` (no environment suffix)
- App Runner service: `enterprise-agentic-ai-dev-backend` (WITH `-dev-` environment suffix)

If deploy.yml looks for the wrong service name, it silently skips the deployment!

**Solutions:**
1. **Verify actual App Runner service name:**
   ```bash
   aws apprunner list-services --query 'ServiceSummaryList[*].ServiceName' --output text
   ```

2. **Fix deploy.yml to use correct service name:**
   The service name in deploy.yml must match exactly. Update the lookup:
   ```bash
   SERVICE_ARN=$(aws apprunner list-services \
     --query "ServiceSummaryList[?ServiceName=='enterprise-agentic-ai-dev-backend'].ServiceArn" \
     --output text)
   ```
   Note: Includes `-dev-` (from Terraform pattern: `${project_name}-${environment}-backend`)

3. **Trigger deployment manually while fixing workflow:**
   ```bash
   aws apprunner start-deployment --service-arn $(aws apprunner list-services \
     --query 'ServiceSummaryList[?ServiceName==`enterprise-agentic-ai-dev-backend`].ServiceArn' \
     --output text)
   ```

4. **Verify deployment worked - check logs for new version:**
   ```bash
   aws logs tail "/aws/apprunner/enterprise-agentic-ai-dev-backend/.../application" \
     --since 5m --format short | grep -i "version\|application_start"
   ```

5. **Check workflow logs:**
   GitHub → Actions → Failed workflow → View logs

### Issue: LangGraph stream fails with NotImplementedError

**Symptoms:**
- Chat POST returns 200 but no response streams
- Logs show: `"error_type": "NotImplementedError"`, `"event": "LangGraph agent stream failed"`
- Error happens immediately after "Starting LangGraph agent stream"

**Root Cause:**
Using the **synchronous** `PostgresSaver` with **async** `astream()`. The sync version doesn't implement async methods required by `astream()`.

**Solution:**
Use `AsyncPostgresSaver` instead of `PostgresSaver`:

```python
# WRONG - sync version, fails with astream()
from langgraph.checkpoint.postgres import PostgresSaver

# CORRECT - async version, works with astream()
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
```

**Required changes:**

1. **Update requirements.txt:**
   ```
   psycopg[binary,pool]~=3.2.0  # Need pool extra for AsyncConnectionPool
   ```

2. **Update graph.py:**
   ```python
   from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
   from psycopg.rows import dict_row  # Required for type compatibility
   from psycopg_pool import AsyncConnectionPool
   
   @asynccontextmanager
   async def get_checkpointer(database_url: str | None = None):
       if database_url and POSTGRES_AVAILABLE:
           # IMPORTANT: row_factory=dict_row is required!
           # AsyncPostgresSaver expects dict rows, not tuples
           async with AsyncConnectionPool(
               conninfo=database_url,
               max_size=20,
               kwargs={"autocommit": True, "row_factory": dict_row},
           ) as pool:
               checkpointer = AsyncPostgresSaver(pool)
               await checkpointer.setup()
               yield checkpointer
               return
       yield MemorySaver()
   ```

3. **Update main.py lifespan:**
   ```python
   # Change 'with' to 'async with'
   async with get_checkpointer(database_url) as checkpointer:
       app.state.graph = build_graph(checkpointer)
       yield
   ```

**Verification:**
```bash
aws logs tail "/aws/apprunner/..." --since 5m | grep -i "checkpointer"
# Should show: "AsyncPostgresSaver" (not "PostgresSaver")
```

### Issue: Memory works in conversation but forgets after page refresh

**Symptoms:**
- AI correctly remembers earlier messages within the same session
- After page refresh, AI doesn't remember anything
- Each refresh shows a different `conversation_id` in logs
- Logs show `total_messages_from_checkpoint: 1` (only current message)

**Root Cause:**
The frontend stores `conversationId` only in React state, which is **lost on page refresh**. Each refresh generates a new conversation_id, starting a fresh conversation with no memory.

**Diagnosis:**
Check logs for different conversation_ids:
```bash
aws logs tail "/aws/apprunner/..." --since 30m | grep "conversation_id"
# If you see different UUIDs for what you thought was the same conversation,
# the frontend isn't persisting the conversation_id
```

**Solution:**
Persist `conversationId` in `sessionStorage`:

```typescript
// Initialize from sessionStorage
const [conversationId, setConversationId] = useState<string | null>(() => {
  if (typeof window !== "undefined") {
    return sessionStorage.getItem("conversationId");
  }
  return null;
});

// Save to sessionStorage when it changes
useEffect(() => {
  if (conversationId) {
    sessionStorage.setItem("conversationId", conversationId);
  }
}, [conversationId]);

// Add "New Chat" button to clear
const handleNewConversation = useCallback(() => {
  sessionStorage.removeItem("conversationId");
  setConversationId(null);
  setMessages([]);
}, []);
```

**Verification:**
1. Send a message: "My favorite food is pizza"
2. Refresh the page
3. Ask: "What's my favorite food?"
4. AI should remember "pizza"
5. Check logs: same `conversation_id` across both messages

---

## Files Created/Modified in Phase 1b

### New Files Created

| File | Purpose |
|------|---------|
| `terraform/modules/secrets/main.tf` | Updated with database-url secret reference |
| `terraform/modules/secrets/outputs.tf` | Updated with database_url in secret_arns |
| `terraform/modules/app-runner/main.tf` | Updated with DATABASE_URL environment secret |
| `backend/src/db/__init__.py` | Database package exports |
| `backend/src/db/session.py` | SQLAlchemy session management |
| `backend/alembic.ini` | Alembic configuration |
| `backend/alembic/env.py` | Alembic migration environment |
| `backend/src/api/middleware/rate_limit.py` | slowapi rate limiting |
| `backend/src/api/routes/v1/__init__.py` | V1 API router |
| `backend/src/api/routes/v1/chat.py` | Versioned chat endpoints |
| `.github/workflows/ci.yml` | CI pipeline (lint, test, validate) |
| `.github/workflows/deploy.yml` | CD pipeline (build, deploy, test) |

### Files Modified

| File | Changes |
|------|---------|
| `terraform/modules/app-runner/main.tf` | Add DATABASE_URL environment secret |
| `terraform/modules/secrets/main.tf` | Add database password secret |
| `backend/requirements.txt` | Add langgraph-checkpoint-postgres |
| `backend/src/config/settings.py` | Add database_url, rate limit settings |
| `backend/src/agent/graph.py` | PostgresSaver integration |
| `backend/src/agent/__init__.py` | Checkpointer initialization |
| `backend/src/api/main.py` | Rate limiting, V1 router |
| `backend/src/api/routes/health.py` | Enhanced dependency checks |
| `backend/src/api/routes/chat.py` | Rate limit decorator, use app.state.graph |
| `frontend/src/lib/api.ts` | Use /api/v1/chat endpoints |
| `frontend/src/app/page.tsx` | Persist conversationId in sessionStorage, add "New Chat" button |
| `REPO_STATE.md` | Update file inventory |

### AWS Resources Created

| Resource Type | Count | Details |
|---------------|-------|---------|
| Neon Database | 1 | External PostgreSQL (free tier) |
| Secrets Manager Secret | 1 | DATABASE_URL for Neon connection |

---

## Branch Management and Next Steps

### Save Phase 1b Work

**Commands:**
```bash
cd ~/Projects/aws-enterprise-agentic-ai

# Commit all changes
git add .
git commit -m "Complete Phase 1b: Production hardening with Neon, CI/CD, rate limiting"

# Tag Phase 1b completion
git tag -a v0.3.0-phase1b -m "Phase 1b complete - Production hardening"

# Push to remote
git push origin main
git push origin v0.3.0-phase1b
```

### Prepare for Phase 2

Phase 2 adds:
- Real Tavily search tool implementation
- Real SQL query tool with Neon PostgreSQL
- Real RAG retrieval with Pinecone
- Real market data tool with FMP
- Document ingestion Lambda

**Create Phase 2 branch:**
```bash
git checkout -b phase-2-core-tools
```

### Document Your Deployment

Update your deployment values:

| Item | Value |
|------|-------|
| CloudFront URL | `https://d2bhnqevtvjc7f.cloudfront.net` |
| App Runner URL | `https://yhvmf3inyx.us-east-1.awsapprunner.com` |
| Neon Endpoint | (from Neon dashboard) |
| Database Name | neondb |

---

## Summary

Phase 1b establishes production hardening with:
- ✅ Neon PostgreSQL for persistent conversation state (free tier)
- ✅ Neon PostgreSQL for persistent database (no VPC connector needed)
- ✅ PostgresSaver replacing MemorySaver
- ✅ Rate limiting (10 requests/minute per IP)
- ✅ API versioning (/api/v1/chat)
- ✅ Enhanced health checks with dependency validation
- ✅ GitHub Actions CI/CD automation

**Key Achievements:**
- Conversations survive App Runner restarts
- Automated deployment pipeline
- Production-grade security with rate limiting
- Enhanced observability with dependency health checks
- Cost-optimized (~$5-15/month total for Phase 1)

**Next Phase (2):** Add core agent tools:
- Real Tavily web search
- Real SQL queries against Neon PostgreSQL
- Real RAG retrieval with Pinecone
- Real market data from FMP

**Estimated Time for Phase 1b:** 6-10 hours

**Success Criteria:** ✅ Conversations persist across App Runner restarts, rate limiting prevents abuse, CI/CD automates deployment, and the system is production-ready.
