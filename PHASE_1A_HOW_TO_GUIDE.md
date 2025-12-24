# Phase 1a: Minimal MVP - AWS Cloud Deployment - Complete How-To Guide

**Purpose:** This guide provides step-by-step instructions for deploying the Phase 0 local development environment to AWS, creating a publicly accessible demo with password protection.

**Estimated Time:** 8-16 hours depending on AWS/Terraform experience

**Prerequisites:** Phase 0 must be complete and verified before starting Phase 1a.

**⚠️ Important:** This phase involves AWS costs. While optimized for cost (~$20-50/month when active), ensure you understand the billing implications. We'll set up billing alerts as part of this guide.

**🖥️ Development Environment:** Continue using Windows with WSL 2 as in Phase 0. All terminal commands run in your WSL terminal (Ubuntu).

---

## Table of Contents

- [Quick Start Workflow Summary](#quick-start-workflow-summary)
- [Prerequisites Verification](#1-prerequisites-verification)
- [AWS Account Setup and Billing Alerts](#2-aws-account-setup-and-billing-alerts)
- [Terraform State Backend Setup](#3-terraform-state-backend-setup)
- [Secrets Manager Setup](#4-secrets-manager-setup)
- [Terraform Infrastructure](#5-terraform-infrastructure)
- [Backend Updates for AWS](#6-backend-updates-for-aws)
- [Production Docker Build](#7-production-docker-build)
- [ECR Repository and Image Push](#8-ecr-repository-and-image-push)
- [App Runner Deployment](#9-app-runner-deployment)
- [Frontend Build and S3 Upload](#10-frontend-build-and-s3-upload)
- [CloudFront Distribution](#11-cloudfront-distribution)
- [End-to-End Verification](#12-end-to-end-verification)
- [Phase 1a Completion Checklist](#phase-1a-completion-checklist)
- [Common Issues and Solutions](#common-issues-and-solutions)
- [Cost Monitoring](#cost-monitoring)
- [Cleanup Instructions](#cleanup-instructions)
- [Branch Management and Next Steps](#branch-management-and-next-steps)

---

## Quick Start Workflow Summary

**Overall Phase 1a Workflow:**
1. **Prerequisites** (Section 1): Verify Phase 0 complete, AWS CLI configured
2. **AWS Setup** (Section 2): Billing alerts, IAM permissions verification
3. **Terraform State** (Section 3): Create S3 bucket and DynamoDB table for state
4. **Secrets Manager** (Section 4): Store all secrets (password, API keys)
5. **Terraform Infrastructure** (Section 5): Write and apply Terraform modules
6. **Backend Updates** (Section 6): CORS, environment detection, CloudWatch logging
7. **Docker Build** (Section 7): Create production Dockerfile
8. **ECR Push** (Section 8): Build and push Docker image to ECR
9. **App Runner** (Section 9): Deploy backend service
10. **Frontend** (Section 10): Build static export, upload to S3
11. **CloudFront** (Section 11): Configure distribution, test access
12. **Verification** (Section 12): End-to-end testing

**Key Principle:** Manual deployment in Phase 1a (terraform apply + aws s3 sync). CI/CD automation is added in Phase 1b.

**Architecture Overview:**
```
┌─────────────────────────────────────────────────────────────────┐
│                         Internet                                 │
└───────────────────────────┬─────────────────────────────────────┘
                            │
        ┌───────────────────┴───────────────────┐
        │                                       │
        ▼                                       ▼
┌───────────────────┐                 ┌───────────────────┐
│    CloudFront     │                 │    App Runner     │
│  (Static Frontend)│                 │  (FastAPI Backend)│
│                   │      CORS       │                   │
│  S3 Bucket ───────┼────────────────▶│  - LangGraph      │
│  - HTML/JS/CSS    │                 │  - Bedrock        │
│                   │                 │  - Tools          │
└───────────────────┘                 └─────────┬─────────┘
                                                │
                                                ▼
                                      ┌───────────────────┐
                                      │ Secrets Manager   │
                                      │ - DEMO_PASSWORD   │
                                      │ - API Keys        │
                                      └───────────────────┘
```

**Estimated Time:** 8-16 hours

---

## 1. Prerequisites Verification

### What We're Doing
Before deploying to AWS, we must verify that Phase 0 is complete and all required tools are properly configured.

### Why This Matters
- **Phase 0 Foundation:** All code we're deploying was built in Phase 0
- **AWS Access:** Terraform and deployments require proper AWS credentials
- **Tool Versions:** Terraform and AWS CLI versions affect functionality

### 1.1 Verify Phase 0 Completion

**Checkpoint:** Confirm Phase 0 is complete before proceeding.

**Command (run in WSL terminal):**
```bash
cd ~/Projects/aws-enterprise-agentic-ai

# Verify services start and work
docker-compose up -d
sleep 10

# Test health endpoint
curl http://localhost:8000/health

# Test frontend loads
curl -s http://localhost:3000 | head -20

# Stop services
docker-compose down
```

**Expected Output:**
- Health endpoint returns: `{"status":"ok","environment":"local","version":"0.1.0","api_version":"v1"}`
- Frontend returns HTML content

**If Phase 0 is NOT complete:** Stop here and complete Phase 0 first. See `docs/completed-phases/PHASE_0_HOW_TO_GUIDE.md`.

### 1.2 Verify AWS CLI Configuration

**Command:**
```bash
# Check AWS CLI version (should be v2)
aws --version

# Verify credentials are configured
aws sts get-caller-identity

# Verify region is set to us-east-1
aws configure get region
```

**Expected Output:**
```
aws-cli/2.x.x Python/3.x.x ...
{
    "UserId": "AIDAXXXXXXXXXXXXXXXXX",
    "Account": "123456789012",
    "Arn": "arn:aws:iam::123456789012:user/your-username"
}
us-east-1
```

**If region is not us-east-1:**
```bash
aws configure set region us-east-1
```

### 1.3 Verify Terraform Installation

**Command:**
```bash
# Check Terraform version (should be 1.5.0+)
terraform --version
```

**Expected Output:**
```
Terraform v1.5.x (or higher)
```

**If Terraform is not installed:**
```bash
# Install Terraform (Ubuntu/WSL)
sudo apt-get update && sudo apt-get install -y gnupg software-properties-common

wget -O- https://apt.releases.hashicorp.com/gpg | \
gpg --dearmor | \
sudo tee /usr/share/keyrings/hashicorp-archive-keyring.gpg > /dev/null

echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] \
https://apt.releases.hashicorp.com $(lsb_release -cs) main" | \
sudo tee /etc/apt/sources.list.d/hashicorp.list

sudo apt update && sudo apt-get install terraform
```

### 1.4 Verify AWS Bedrock Model Access

**Command:**
```bash
# List available foundation models (verify Bedrock access)
aws bedrock list-foundation-models --region us-east-1 --query 'modelSummaries[?contains(modelId, `nova`) || contains(modelId, `claude`)].modelId' --output table
```

**Expected Output:** Should list Nova Pro, Nova Lite, and Claude models.

**If access denied:** You need to request model access in AWS Console:
1. Go to AWS Console → Bedrock → Model access
2. Request access to: Amazon Nova Pro, Amazon Nova Lite, Claude 3.5 Sonnet
3. Wait for approval (can take up to 24 hours)

### 1.5 Verify IAM Permissions

Your IAM user/role needs permissions for:
- ECR (container registry)
- App Runner (compute)
- S3 (storage)
- CloudFront (CDN)
- Secrets Manager (secrets)
- IAM (role creation)
- VPC (networking)
- CloudWatch (logging)

**Command to test basic permissions:**
```bash
# Test S3 access
aws s3 ls

# Test ECR access
aws ecr describe-repositories --region us-east-1

# Test Secrets Manager access
aws secretsmanager list-secrets --region us-east-1
```

**If any fail with AccessDenied:** You need to add permissions to your IAM user. See Section 2 for required policies.

### 1.6 Prerequisites Checklist

Before proceeding, verify all items:

- [ ] Phase 0 services start and work locally
- [ ] AWS CLI v2 installed and configured
- [ ] AWS region set to us-east-1
- [ ] Terraform 1.5.0+ installed
- [ ] AWS Bedrock model access approved
- [ ] IAM permissions verified (S3, ECR, App Runner, etc.)

---

## 2. AWS Account Setup and Billing Alerts

### What We're Doing
Setting up billing alerts to monitor costs and ensuring your AWS account is properly configured for this project.

### Why This Matters
- **Cost Control:** Prevents surprise bills
- **Visibility:** Know when costs exceed expected range
- **Best Practice:** Production accounts always have billing alerts

### 2.1 Create Billing Alert

**Navigate in AWS Console:**
1. Sign in to AWS Console: https://console.aws.amazon.com
2. Click on your account name (top right) → **Billing and Cost Management**
3. In left sidebar, click **Budgets**
4. Click **Create budget**

**Budget Configuration:**
- Budget type: **Cost budget**
- Name: `enterprise-agentic-ai-demo`
- Period: **Monthly**
- Budget amount: **$50** (our target ceiling)
- Click **Next**

**Alert Configuration:**
- Threshold: **80%** of budgeted amount ($40)
- Notification: Your email address
- Click **Next** → **Create budget**

### 2.2 Verify Cost Explorer Access

**Navigate in AWS Console:**
1. Billing and Cost Management → **Cost Explorer**
2. If prompted, click **Enable Cost Explorer** (takes up to 24 hours to populate)

### 2.3 Review Required IAM Permissions

For Phase 1a deployment, your IAM user needs these AWS managed policies (or equivalent custom permissions):

| Policy | Purpose |
|--------|---------|
| `AmazonEC2FullAccess` | VPC, subnets, security groups |
| `AmazonS3FullAccess` | Frontend hosting, Terraform state |
| `CloudFrontFullAccess` | CDN distribution |
| `AWSAppRunnerFullAccess` | Backend deployment |
| `AmazonEC2ContainerRegistryFullAccess` | Docker image storage |
| `SecretsManagerReadWrite` | Password and API key storage |
| `IAMFullAccess` | Create roles for App Runner |
| `AmazonDynamoDBFullAccess` | Terraform state locking |
| `CloudWatchLogsFullAccess` | Application logging |
| `AmazonBedrockFullAccess` | LLM access |

**Note:** These are broad permissions for development. Production would use more restrictive custom policies.

**To add policies to your IAM user:**
1. AWS Console → IAM → Users → Select your user
2. **Permissions** tab → **Add permissions** → **Attach policies directly**
3. Search and select each policy above
4. Click **Next** → **Add permissions**

### 2.4 AWS Setup Checklist

- [ ] Billing alert created for $50/month
- [ ] Cost Explorer enabled
- [ ] IAM permissions verified/added
- [ ] Account ID noted (needed for ECR): `aws sts get-caller-identity --query Account --output text`

---

## 3. Terraform State Backend Setup

### What We're Doing
Creating an S3 bucket and DynamoDB table to store Terraform state remotely. This enables team collaboration and prevents state corruption.

### Why This Matters
- **State Persistence:** Local state files can be lost or corrupted
- **Locking:** DynamoDB prevents concurrent modifications
- **Team Collaboration:** Multiple developers can run Terraform
- **Best Practice:** Never use local state for real infrastructure

### 3.1 Choose Unique Names

Terraform state resources need globally unique names. Use your initials or a unique identifier.

**Define your naming convention (replace `YOUR_INITIALS` with your actual initials):**
```bash
# Example: if your name is John Doe, use "jd"
export TF_STATE_BUCKET="enterprise-agentic-ai-tfstate-YOUR_INITIALS"
export TF_LOCK_TABLE="enterprise-agentic-ai-tflock"
export AWS_REGION="us-east-1"

# Echo to verify
echo "Bucket: $TF_STATE_BUCKET"
echo "Table: $TF_LOCK_TABLE"
echo "Region: $AWS_REGION"
```

**Important:** Note these values - you'll need them throughout Phase 1a.

### 3.2 Create S3 Bucket for State

**Navigate in AWS Console:**
1. AWS Console → **S3**
2. Click **Create bucket**

**Bucket Configuration:**
- **Bucket name:** `enterprise-agentic-ai-tfstate-YOUR_INITIALS` (must be globally unique)
- **AWS Region:** US East (N. Virginia) us-east-1
- **Object Ownership:** ACLs disabled (recommended)
- **Block Public Access:** ✅ Block ALL public access (keep all checked)
- **Bucket Versioning:** ✅ Enable (critical for state recovery)
- **Default encryption:** 
  - Encryption type: Server-side encryption with Amazon S3 managed keys (SSE-S3)
  - Bucket Key: Enable

Click **Create bucket**

**Verification:**
```bash
aws s3 ls | grep tfstate
```

### 3.3 Create DynamoDB Table for Locking

**Navigate in AWS Console:**
1. AWS Console → **DynamoDB**
2. Click **Create table**

**Table Configuration:**
- **Table name:** `enterprise-agentic-ai-tflock`
- **Partition key:** `LockID` (String) - **MUST be exactly this name**
- **Table settings:** Default settings (on-demand capacity)

Click **Create table**

**Verification:**
```bash
aws dynamodb describe-table --table-name enterprise-agentic-ai-tflock --query 'Table.TableStatus'
```

Expected output: `"ACTIVE"`

### 3.4 Terraform State Setup Checklist

- [ ] S3 bucket created with versioning enabled
- [ ] S3 bucket has public access blocked
- [ ] DynamoDB table created with `LockID` partition key
- [ ] Both resources in us-east-1 region
- [ ] Bucket name noted: `________________`
- [ ] Table name noted: `enterprise-agentic-ai-tflock`

---

## 4. Secrets Manager Setup

### What We're Doing
Creating secrets in AWS Secrets Manager to store sensitive configuration. This keeps secrets out of code, Terraform state, and environment variables.

### Why This Matters
- **Security:** Secrets never appear in code or logs
- **Rotation:** Easy to update without redeploying
- **Audit Trail:** CloudTrail logs all secret access
- **Best Practice:** Always use a secrets manager in production

### 4.1 Required Secrets

We need to store these secrets:

| Secret Name | Purpose | Source |
|-------------|---------|--------|
| `enterprise-agentic-ai/demo-password` | Login password | You choose |
| `enterprise-agentic-ai/auth-token-secret` | Session signing key | Generate random |
| `enterprise-agentic-ai/tavily-api-key` | Web search API | From Tavily dashboard |
| `enterprise-agentic-ai/fmp-api-key` | Market data API | From FMP dashboard |

### 4.2 Generate Auth Token Secret

First, generate a secure random string for the auth token secret:

```bash
# Generate a 64-character random secret
openssl rand -base64 48
```

**Save this value** - you'll use it in the next step.

### 4.3 Create Secrets in AWS Console

**Navigate in AWS Console:**
1. AWS Console → **Secrets Manager**
2. Ensure region is **US East (N. Virginia)** (top right dropdown)

**Create Secret 1: Demo Password**
1. Click **Store a new secret**
2. Secret type: **Other type of secret**
3. Key/value pairs:
   - Key: `password`
   - Value: (choose a secure password for your demo, e.g., `MySecureDemo2025!`)
4. Click **Next**
5. Secret name: `enterprise-agentic-ai/demo-password`
6. Description: `Demo login password for enterprise agentic AI`
7. Click **Next** → **Next** → **Store**

**Create Secret 2: Auth Token Secret**
1. Click **Store a new secret**
2. Secret type: **Other type of secret**
3. Key/value pairs:
   - Key: `secret`
   - Value: (paste the random string you generated in 4.2)
4. Click **Next**
5. Secret name: `enterprise-agentic-ai/auth-token-secret`
6. Description: `HMAC secret for session token signing`
7. Click **Next** → **Next** → **Store**

**Create Secret 3: Tavily API Key**
1. Click **Store a new secret**
2. Secret type: **Other type of secret**
3. Key/value pairs:
   - Key: `api_key`
   - Value: (your Tavily API key from https://tavily.com)
4. Click **Next**
5. Secret name: `enterprise-agentic-ai/tavily-api-key`
6. Description: `Tavily search API key`
7. Click **Next** → **Next** → **Store**

**Create Secret 4: FMP API Key**
1. Click **Store a new secret**
2. Secret type: **Other type of secret**
3. Key/value pairs:
   - Key: `api_key`
   - Value: (your FMP API key from https://financialmodelingprep.com)
4. Click **Next**
5. Secret name: `enterprise-agentic-ai/fmp-api-key`
6. Description: `Financial Modeling Prep API key`
7. Click **Next** → **Next** → **Store**

### 4.4 Verify Secrets Created

**Command:**
```bash
aws secretsmanager list-secrets --region us-east-1 --query 'SecretList[?contains(Name, `enterprise-agentic-ai`)].Name' --output table
```

**Expected Output:**
```
----------------------------------------------------
|                   ListSecrets                    |
+--------------------------------------------------+
|  enterprise-agentic-ai/auth-token-secret         |
|  enterprise-agentic-ai/demo-password             |
|  enterprise-agentic-ai/fmp-api-key               |
|  enterprise-agentic-ai/tavily-api-key            |
+--------------------------------------------------+
```

### 4.5 Note Secret ARNs

You'll need the ARNs for Terraform. Get them now:

```bash
# Get all secret ARNs
aws secretsmanager list-secrets --region us-east-1 \
  --query 'SecretList[?contains(Name, `enterprise-agentic-ai`)].{Name:Name,ARN:ARN}' \
  --output table
```

**Save these ARNs** - you'll reference them in Terraform.

### 4.6 Secrets Manager Checklist

- [ ] Demo password secret created
- [ ] Auth token secret created (random 64-char string)
- [ ] Tavily API key secret created
- [ ] FMP API key secret created
- [ ] All secrets in us-east-1 region
- [ ] All secret ARNs noted for Terraform

---

## 5. Terraform Infrastructure

### What We're Doing
Writing and applying Terraform configurations to create the AWS infrastructure: VPC, ECR, App Runner, S3, CloudFront, and IAM roles.

### Why This Matters
- **Infrastructure as Code:** Reproducible, version-controlled infrastructure
- **Consistency:** Same infrastructure every time
- **Documentation:** Terraform files document what exists

### 5.1 Terraform Module Structure

We'll use the existing directory structure:

```
terraform/
├── environments/
│   └── dev/
│       ├── main.tf           # Module calls
│       ├── variables.tf      # Input variables
│       ├── outputs.tf        # Output values
│       ├── backend.tf        # State configuration
│       └── terraform.tfvars  # Variable values (gitignored)
└── modules/
    ├── networking/           # VPC, subnets, IGW
    ├── ecr/                  # Container registry
    ├── app-runner/           # Backend service
    ├── s3-cloudfront/        # Frontend hosting
    └── secrets/              # IAM for Secrets Manager
```

### 5.2 Create Backend Configuration

**Agent Prompt - Create Terraform Backend Configuration:**

> Create the Terraform backend configuration file at `terraform/environments/dev/backend.tf` that:
> 
> 1. Configures the S3 backend for state storage with these settings:
>    - Bucket: Use a variable or placeholder that I'll replace with my actual bucket name
>    - Key: `dev/terraform.tfstate`
>    - Region: `us-east-1`
>    - DynamoDB table for locking: `enterprise-agentic-ai-tflock`
>    - Encrypt: true
> 
> 2. Specifies required Terraform version >= 1.5.0
> 
> 3. Specifies required providers:
>    - AWS provider ~> 5.0
>    - Random provider ~> 3.0 (for generating unique names)
> 
> Follow Terraform best practices as of December 2025. Include comments explaining each section.

**After running the prompt:** Replace the placeholder bucket name with your actual bucket name from Section 3.

### 5.3 Create Networking Module

**Agent Prompt - Create Networking Module:**

> Create the Terraform networking module at `terraform/modules/networking/` with these files:
> 
> **main.tf:**
> - VPC with CIDR 10.0.0.0/16 and DNS hostnames enabled
> - Two public subnets in different AZs (us-east-1a, us-east-1b) with CIDRs 10.0.1.0/24 and 10.0.2.0/24
> - Internet Gateway attached to VPC
> - Route table for public subnets with route to Internet Gateway
> - Security group for App Runner VPC connector (if needed later for Aurora in Phase 1b)
> 
> **variables.tf:**
> - project_name (string)
> - environment (string, default "dev")
> - vpc_cidr (string, default "10.0.0.0/16")
> - tags (map of strings)
> 
> **outputs.tf:**
> - vpc_id
> - public_subnet_ids (list)
> - security_group_id
> 
> Follow AWS and Terraform best practices as of December 2025. Use proper tagging. Include comments.
> 
> Note: Phase 1a uses public subnets only (no NAT Gateway to save costs). App Runner doesn't need VPC connector yet - that's added in Phase 1b for Aurora access.

### 5.4 Create ECR Module

**Agent Prompt - Create ECR Module:**

> Create the Terraform ECR module at `terraform/modules/ecr/` with these files:
> 
> **main.tf:**
> - ECR repository for the backend application
> - Image scanning on push enabled
> - Image tag mutability: MUTABLE (allows reusing tags during development)
> - Lifecycle policy to keep only last 10 images (cost optimization)
> 
> **variables.tf:**
> - repository_name (string)
> - tags (map of strings)
> 
> **outputs.tf:**
> - repository_url
> - repository_arn
> - registry_id
> 
> Follow AWS and Terraform best practices as of December 2025. Include the lifecycle policy as a JSON document.

### 5.5 Create Secrets Module

**Agent Prompt - Create Secrets Module:**

> Create the Terraform secrets module at `terraform/modules/secrets/` with these files:
> 
> **main.tf:**
> - Data sources to reference existing Secrets Manager secrets (we created them manually):
>   - enterprise-agentic-ai/demo-password
>   - enterprise-agentic-ai/auth-token-secret
>   - enterprise-agentic-ai/tavily-api-key
>   - enterprise-agentic-ai/fmp-api-key
> - IAM policy document allowing secretsmanager:GetSecretValue for these secrets
> - IAM policy resource using the policy document
> 
> **variables.tf:**
> - project_name (string)
> - environment (string)
> - tags (map of strings)
> 
> **outputs.tf:**
> - secret_arns (map of secret name to ARN)
> - secrets_access_policy_arn (the IAM policy ARN)
> 
> Follow AWS and Terraform best practices as of December 2025. We're referencing existing secrets, not creating new ones.

### 5.6 Create App Runner Module

**Agent Prompt - Create App Runner Module:**

> Create the Terraform App Runner module at `terraform/modules/app-runner/` with these files:
> 
> **main.tf:**
> - IAM role for App Runner service with trust policy for apprunner.amazonaws.com
> - IAM role for App Runner ECR access with trust policy for build.apprunner.amazonaws.com
> - Policy attachments:
>   - ECR access role gets AmazonEC2ContainerRegistryReadOnly
>   - Service role gets the secrets access policy (passed as variable)
>   - Service role gets CloudWatch Logs write access
>   - Service role gets Bedrock invoke access
> - App Runner service configuration:
>   - Source: ECR image (passed as variable)
>   - Instance: 1 vCPU, 2 GB memory
>   - Auto scaling: min 0, max 10 (scale to zero when idle)
>   - Health check: path /health, interval 10s
>   - Environment variables from Secrets Manager references:
>     - DEMO_PASSWORD
>     - AUTH_TOKEN_SECRET
>     - TAVILY_API_KEY
>     - FMP_API_KEY
>   - Regular environment variables:
>     - ENVIRONMENT=aws
>     - AWS_REGION=us-east-1
>     - LOG_LEVEL=INFO
> 
> **variables.tf:**
> - service_name (string)
> - ecr_repository_url (string)
> - image_tag (string, default "latest")
> - secrets_policy_arn (string)
> - secret_arns (map of string to string)
> - cpu (string, default "1024")
> - memory (string, default "2048")
> - tags (map of strings)
> 
> **outputs.tf:**
> - service_url
> - service_arn
> - service_id
> 
> Follow AWS and Terraform best practices as of December 2025. Use the newer App Runner API features for secrets integration. Set connection_drain_timeout to 900 seconds for SSE streaming support.

### 5.7 Create S3-CloudFront Module

**Agent Prompt - Create S3-CloudFront Module:**

> Create the Terraform S3 and CloudFront module at `terraform/modules/s3-cloudfront/` with these files:
> 
> **main.tf:**
> - S3 bucket for frontend static files:
>   - Block all public access
>   - Bucket ownership controls (BucketOwnerEnforced)
>   - Versioning enabled
> - S3 bucket policy allowing CloudFront OAC access only
> - CloudFront Origin Access Control (OAC) - use OAC not OAI (OAI is legacy)
> - CloudFront distribution:
>   - Origin: S3 bucket with OAC
>   - Default root object: index.html
>   - Price class: PriceClass_100 (US, Canada, Europe only - cost optimization)
>   - Viewer protocol policy: redirect-to-https
>   - Default cache behavior: CachingOptimized managed policy
>   - Custom error responses: 403 and 404 return /index.html with 200 (for SPA routing)
>   - Enabled: true
>   - HTTP/2 and HTTP/3 enabled
> 
> **variables.tf:**
> - bucket_name (string)
> - project_name (string)
> - environment (string)
> - tags (map of strings)
> 
> **outputs.tf:**
> - bucket_name
> - bucket_arn
> - cloudfront_distribution_id
> - cloudfront_domain_name
> - cloudfront_url (formatted as https://...)
> 
> Follow AWS and Terraform best practices as of December 2025. Use CloudFront Origin Access Control (OAC), not the legacy Origin Access Identity (OAI).

### 5.8 Create Dev Environment Main Configuration

**Agent Prompt - Create Dev Environment Main Configuration:**

> Create the main Terraform configuration at `terraform/environments/dev/main.tf` that:
> 
> 1. Calls all modules in the correct order:
>    - networking (VPC, subnets)
>    - ecr (container registry)
>    - secrets (IAM policy for secrets access)
>    - app-runner (backend service)
>    - s3-cloudfront (frontend hosting)
> 
> 2. Passes outputs between modules appropriately:
>    - ECR URL to App Runner
>    - Secrets policy ARN and secret ARNs to App Runner
> 
> 3. Uses local values for:
>    - project_name = "enterprise-agentic-ai"
>    - environment = "dev"
>    - common_tags (project, environment, managed_by = "terraform")
> 
> 4. Sets up any data sources needed (e.g., aws_region, aws_caller_identity)
> 
> Also create `terraform/environments/dev/variables.tf` with any required input variables.
> 
> And create `terraform/environments/dev/outputs.tf` that outputs:
> - app_runner_url
> - cloudfront_url
> - ecr_repository_url
> - s3_bucket_name
> 
> Follow Terraform best practices as of December 2025.

### 5.9 Create terraform.tfvars (gitignored)

**Agent Prompt - Create tfvars and Update Gitignore:**

> Create the terraform.tfvars file at `terraform/environments/dev/terraform.tfvars` with placeholder values for any required variables. This file should be gitignored since it may contain sensitive values.
> 
> Also verify that `.gitignore` includes patterns to ignore:
> - `*.tfvars` (except examples)
> - `.terraform/`
> - `*.tfstate*`
> - `.terraform.lock.hcl` (optional, some teams commit this)
> 
> Add a `terraform.tfvars.example` file showing the expected variables with placeholder values.

### 5.10 Initialize and Validate Terraform

**Commands:**
```bash
cd ~/Projects/aws-enterprise-agentic-ai/terraform/environments/dev

# Initialize Terraform (downloads providers, configures backend)
terraform init

# Validate configuration syntax
terraform validate

# Preview what will be created
terraform plan
```

**Expected Output:**
- `terraform init`: "Terraform has been successfully initialized!"
- `terraform validate`: "Success! The configuration is valid."
- `terraform plan`: Shows resources to be created (VPC, subnets, ECR, S3, CloudFront, App Runner)

### 5.11 Apply Terraform (Partial - ECR First)

We'll apply in stages to catch issues early. First, just create ECR:

**Commands:**
```bash
# Apply only ECR module first
terraform apply -target=module.ecr

# Verify ECR was created
aws ecr describe-repositories --region us-east-1 --query 'repositories[].repositoryName'
```

**Expected Output:** ECR repository appears in the list.

**Checkpoint:** Stop here and proceed to Section 6 (Backend Updates) before applying remaining infrastructure. We need to push a Docker image to ECR before App Runner can start.

### 5.12 Terraform Infrastructure Checklist

- [ ] Backend configuration created with S3 state
- [ ] Networking module created
- [ ] ECR module created
- [ ] Secrets module created
- [ ] App Runner module created
- [ ] S3-CloudFront module created
- [ ] Dev environment main.tf created
- [ ] terraform.tfvars created (gitignored)
- [ ] `terraform init` successful
- [ ] `terraform validate` passes
- [ ] ECR repository created via `terraform apply -target=module.ecr`

---

## 6. Backend Updates for AWS

### What We're Doing
Updating the FastAPI backend to work in AWS: environment detection, CORS configuration for CloudFront, and CloudWatch logging.

### Why This Matters
- **Environment Detection:** App needs to know it's running in AWS to load secrets correctly
- **CORS:** Frontend on CloudFront needs to call App Runner API across origins
- **Logging:** CloudWatch integration for observability

### 6.1 Update Settings for AWS

**Agent Prompt - Update Settings for AWS Environment:**

> Review and update `backend/src/config/settings.py` to ensure it properly handles the AWS environment:
> 
> 1. Environment detection:
>    - When `ENVIRONMENT=aws`, load secrets from AWS Secrets Manager
>    - Use the secret names: `enterprise-agentic-ai/demo-password`, etc.
>    - Cache secrets in memory after loading (don't fetch on every request)
> 
> 2. Secrets Manager integration:
>    - Create a function to load secrets from Secrets Manager
>    - Handle the JSON structure (each secret has a key like "password" or "api_key")
>    - Fallback gracefully if secrets aren't available (for local dev)
> 
> 3. Ensure these settings work in both local (.env) and AWS (Secrets Manager) modes:
>    - DEMO_PASSWORD
>    - AUTH_TOKEN_SECRET
>    - TAVILY_API_KEY
>    - FMP_API_KEY
> 
> Check the existing settings.py implementation and only add what's missing. Follow the existing code patterns and style. Include proper error handling and logging.

### 6.2 Update CORS Configuration

**Agent Prompt - Update CORS for CloudFront:**

> Review and update `backend/src/api/main.py` CORS configuration to:
> 
> 1. Allow requests from CloudFront domains:
>    - Pattern: `https://*.cloudfront.net`
>    - Also keep localhost for development
> 
> 2. Read allowed origins from environment variable `ALLOWED_ORIGINS`:
>    - Format: comma-separated list
>    - Default: `http://localhost:3000`
>    - In AWS: set to CloudFront URL
> 
> 3. Ensure CORS allows:
>    - Methods: GET, POST, OPTIONS
>    - Headers: Content-Type, Authorization
>    - Credentials: true (for cookies)
> 
> 4. Handle preflight OPTIONS requests properly
> 
> Check the existing CORS setup and update as needed. Don't break existing local development functionality.

### 6.3 Add CloudWatch Logging Configuration

**Agent Prompt - Add CloudWatch Logging:**

> Review the logging configuration in the backend and ensure it works well with CloudWatch:
> 
> 1. Check that structlog is configured to output JSON format (CloudWatch-friendly)
> 
> 2. Ensure log levels are configurable via LOG_LEVEL environment variable
> 
> 3. Verify that:
>    - Logs include conversation_id for tracing
>    - Error logs include full context
>    - No sensitive data (passwords, keys) in logs
> 
> 4. Add a note in settings.py about the LOG_LEVEL variable (default: INFO in production, DEBUG in development)
> 
> Check existing logging setup in the backend and only add what's missing. The goal is CloudWatch compatibility without breaking local development.

### 6.4 Create Production Dockerfile

**Agent Prompt - Create Production Dockerfile:**

> Create `backend/Dockerfile` (production version, not Dockerfile.dev) that:
> 
> 1. Uses multi-stage build for smaller image:
>    - Builder stage: Install dependencies
>    - Production stage: Copy only what's needed
> 
> 2. Uses Python 3.11-slim as base image
> 
> 3. Sets appropriate environment variables:
>    - PYTHONUNBUFFERED=1
>    - PYTHONDONTWRITEBYTECODE=1
> 
> 4. Installs dependencies from requirements.txt without dev dependencies
> 
> 5. Copies only the src/ directory (not tests, dev files)
> 
> 6. Exposes port 8000
> 
> 7. Runs uvicorn WITHOUT --reload (production mode):
>    - Command: `uvicorn src.api.main:app --host 0.0.0.0 --port 8000`
>    - Workers: 1 (App Runner handles scaling via instances)
> 
> 8. Creates a non-root user for security
> 
> 9. Sets proper WORKDIR
> 
> 10. Includes health check instruction
> 
> Follow Docker best practices as of December 2025. Optimize for layer caching and small image size.

### 6.5 Test Production Docker Build Locally

**Commands:**
```bash
cd ~/Projects/aws-enterprise-agentic-ai

# Build production image
docker build -t enterprise-agentic-ai-backend:test -f backend/Dockerfile backend/

# Verify image was created
docker images | grep enterprise-agentic-ai

# Test image locally (with .env file for secrets)
docker run -d --name test-backend \
  --env-file .env \
  -e ENVIRONMENT=local \
  -p 8001:8000 \
  enterprise-agentic-ai-backend:test

# Wait for startup
sleep 5

# Test health endpoint
curl http://localhost:8001/health

# Check logs
docker logs test-backend

# Cleanup
docker stop test-backend && docker rm test-backend
```

**Expected Output:**
- Build completes successfully
- Health endpoint returns `{"status":"ok",...}`
- Logs show startup messages without errors

### 6.6 Backend Updates Checklist

- [ ] Settings.py updated for AWS Secrets Manager
- [ ] CORS configuration updated for CloudFront
- [ ] Logging compatible with CloudWatch
- [ ] Production Dockerfile created
- [ ] Production build tested locally
- [ ] Health endpoint works in production build

---

## 7. Production Docker Build

### What We're Doing
Building the production Docker image that will be deployed to AWS App Runner.

### Why This Matters
- **Optimization:** Production image is smaller and faster than dev
- **Security:** Non-root user, minimal dependencies
- **Reliability:** No hot-reload, stable production settings

### 7.1 Final Production Build

**Commands:**
```bash
cd ~/Projects/aws-enterprise-agentic-ai

# Build production image with proper tag
docker build -t enterprise-agentic-ai-backend:latest -f backend/Dockerfile backend/

# Also tag with a version
docker tag enterprise-agentic-ai-backend:latest enterprise-agentic-ai-backend:v1.0.0

# Verify images
docker images | grep enterprise-agentic-ai-backend
```

### 7.2 Production Build Checklist

- [ ] Production Docker image builds successfully
- [ ] Image tagged as `latest` and `v1.0.0`
- [ ] Image tested locally (Section 6.5)

---

## 8. ECR Repository and Image Push

### What We're Doing
Pushing the production Docker image to AWS ECR (Elastic Container Registry) so App Runner can access it.

### Why This Matters
- **AWS Integration:** App Runner pulls images from ECR
- **Security:** Private registry, IAM-controlled access
- **Versioning:** ECR stores multiple image versions

### 8.1 Get ECR Repository URL

**Commands:**
```bash
# Get your AWS account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "Account ID: $AWS_ACCOUNT_ID"

# Get ECR repository URL from Terraform output
cd ~/Projects/aws-enterprise-agentic-ai/terraform/environments/dev
ECR_URL=$(terraform output -raw ecr_repository_url)
echo "ECR URL: $ECR_URL"
```

### 8.2 Authenticate Docker to ECR

**Command:**
```bash
# Login to ECR (valid for 12 hours)
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com
```

**Expected Output:** `Login Succeeded`

### 8.3 Tag and Push Image to ECR

**Commands:**
```bash
# Tag image for ECR
docker tag enterprise-agentic-ai-backend:latest ${ECR_URL}:latest
docker tag enterprise-agentic-ai-backend:latest ${ECR_URL}:v1.0.0

# Push both tags
docker push ${ECR_URL}:latest
docker push ${ECR_URL}:v1.0.0

# Verify image in ECR
aws ecr describe-images --repository-name enterprise-agentic-ai-backend --region us-east-1
```

**Expected Output:** Shows image details with tags `latest` and `v1.0.0`

### 8.4 ECR Push Checklist

- [ ] Docker authenticated to ECR
- [ ] Image pushed with `latest` tag
- [ ] Image pushed with `v1.0.0` tag
- [ ] Image visible in ECR via AWS CLI

---

## 9. App Runner Deployment

### What We're Doing
Deploying the backend service to AWS App Runner, which will pull the image from ECR and run it.

### Why This Matters
- **Managed Compute:** App Runner handles scaling, load balancing, HTTPS
- **Cost Optimization:** Scales to zero when idle
- **Simplicity:** No Kubernetes or ECS complexity

### 9.1 Apply Remaining Terraform

**Commands:**
```bash
cd ~/Projects/aws-enterprise-agentic-ai/terraform/environments/dev

# Apply all remaining infrastructure
terraform apply
```

**Review the plan carefully** before typing `yes`. You should see:
- VPC and networking resources
- App Runner service
- S3 bucket
- CloudFront distribution
- IAM roles and policies

**Expected Duration:** 5-10 minutes (CloudFront takes the longest)

### 9.2 Get App Runner URL

**Command:**
```bash
# Get App Runner service URL
terraform output app_runner_url
```

**Save this URL** - you'll need it for frontend configuration.

### 9.3 Verify App Runner Deployment

**Commands:**
```bash
# Get App Runner URL
APP_RUNNER_URL=$(terraform output -raw app_runner_url)

# Test health endpoint (may take 1-2 minutes for first cold start)
curl ${APP_RUNNER_URL}/health

# If you get "Service Unavailable", wait 30 seconds and retry
sleep 30
curl ${APP_RUNNER_URL}/health
```

**Expected Output:** `{"status":"ok","environment":"aws","version":"0.1.0","api_version":"v1"}`

### 9.4 Check App Runner Logs

**Navigate in AWS Console:**
1. AWS Console → **App Runner**
2. Click on your service name
3. Click **Logs** tab
4. Review **Application logs** for any errors

**Command alternative:**
```bash
# Tail App Runner logs
aws logs tail /aws/apprunner/enterprise-agentic-ai-backend --follow --region us-east-1
```

### 9.5 App Runner Deployment Checklist

- [ ] `terraform apply` completed successfully
- [ ] App Runner service running (green status in Console)
- [ ] Health endpoint responds
- [ ] No errors in application logs

---

## 10. Frontend Build and S3 Upload

### What We're Doing
Building the Next.js static export and uploading it to S3 for CloudFront distribution.

### Why This Matters
- **Static Export:** No server needed, just HTML/JS/CSS files
- **Cost Optimization:** S3 hosting is very cheap
- **Performance:** CloudFront edge caching globally

### 10.1 Update Frontend API Configuration

**Agent Prompt - Update Frontend for Production API:**

> Update the frontend to use the App Runner URL in production:
> 
> 1. In `frontend/src/lib/api.ts`:
>    - Read API URL from `NEXT_PUBLIC_API_URL` environment variable
>    - Default to `http://localhost:8000` for local development
>    - Ensure all API calls use this base URL
> 
> 2. Verify the environment variable is already in `next.config.ts` or add it:
>    - `NEXT_PUBLIC_API_URL` should be passed through to the client bundle
> 
> 3. No changes to the SSE/streaming logic - it should already work
> 
> Check existing implementation and only modify what's needed.

### 10.2 Build Frontend for Production

**Commands:**
```bash
cd ~/Projects/aws-enterprise-agentic-ai

# Get App Runner URL from Terraform
APP_RUNNER_URL=$(cd terraform/environments/dev && terraform output -raw app_runner_url)
echo "API URL: $APP_RUNNER_URL"

# Build frontend with production API URL
cd frontend
NEXT_PUBLIC_API_URL=${APP_RUNNER_URL} npm run build

# Verify the build output
ls -la out/
```

**Expected Output:**
- `out/` directory created with static files
- Contains `index.html`, `_next/` directory, etc.

### 10.3 Get S3 Bucket Name

**Command:**
```bash
cd ~/Projects/aws-enterprise-agentic-ai/terraform/environments/dev
S3_BUCKET=$(terraform output -raw s3_bucket_name)
echo "S3 Bucket: $S3_BUCKET"
```

### 10.4 Upload to S3

**Commands:**
```bash
cd ~/Projects/aws-enterprise-agentic-ai/frontend

# Sync build output to S3
aws s3 sync out/ s3://${S3_BUCKET}/ --delete

# Verify files uploaded
aws s3 ls s3://${S3_BUCKET}/ --recursive | head -20
```

### 10.5 Frontend Build Checklist

- [ ] Frontend API URL configured for App Runner
- [ ] `npm run build` completed successfully
- [ ] `out/` directory contains static files
- [ ] Files uploaded to S3
- [ ] S3 bucket contains index.html

---

## 11. CloudFront Distribution

### What We're Doing
Verifying the CloudFront distribution is working and invalidating cache to serve the latest content.

### Why This Matters
- **HTTPS:** CloudFront provides SSL certificate
- **Performance:** Edge caching reduces latency globally
- **Single URL:** Users access one clean URL

### 11.1 Get CloudFront URL

**Command:**
```bash
cd ~/Projects/aws-enterprise-agentic-ai/terraform/environments/dev
CLOUDFRONT_URL=$(terraform output -raw cloudfront_url)
echo "CloudFront URL: $CLOUDFRONT_URL"
```

### 11.2 Invalidate CloudFront Cache

After uploading new files, invalidate the cache:

**Command:**
```bash
# Get distribution ID
DISTRIBUTION_ID=$(terraform output -raw cloudfront_distribution_id)

# Create invalidation for all files
aws cloudfront create-invalidation \
  --distribution-id ${DISTRIBUTION_ID} \
  --paths "/*"
```

**Expected Output:** Returns invalidation ID. Wait 1-2 minutes for propagation.

### 11.3 Test CloudFront Access

**Commands:**
```bash
# Test frontend loads
curl -I ${CLOUDFRONT_URL}

# Open in browser
echo "Open this URL in your browser: ${CLOUDFRONT_URL}"
```

### 11.4 CloudFront Checklist

- [ ] CloudFront URL accessible
- [ ] Cache invalidation created
- [ ] Frontend loads in browser
- [ ] Login page appears

---

## 12. End-to-End Verification

### What We're Doing
Testing the complete deployed system from CloudFront frontend to App Runner backend.

### Why This Matters
- **Integration Testing:** Verify all components work together
- **User Experience:** Test the actual user flow
- **Demo Readiness:** Ensure the demo is impressive

### 12.1 Full User Flow Test

**Manual Testing Steps:**

1. **Open CloudFront URL in browser:**
   ```
   Open: ${CLOUDFRONT_URL}
   ```

2. **Verify login page loads:**
   - Should see professional login interface
   - Password field visible
   - No console errors (F12 → Console)

3. **Login with demo password:**
   - Enter the password you stored in Secrets Manager
   - Click Login
   - Should redirect to chat interface

4. **Send a test message:**
   - Type: "Hello, how are you?"
   - Click Send
   - Observe streaming response
   - Should see real-time text appearing

5. **Test tool usage:**
   - Type: "Search for the latest AI news"
   - Should see search tool being called
   - Response includes search results

6. **Check for cold start behavior:**
   - If first request, may see 10-30 second delay
   - Subsequent requests should be fast (<2 seconds)

### 12.2 API Direct Test

**Commands:**
```bash
APP_RUNNER_URL=$(cd terraform/environments/dev && terraform output -raw app_runner_url)

# Test login (replace YOUR_PASSWORD_HERE with your demo password)
curl -X POST ${APP_RUNNER_URL}/api/login \
  -H "Content-Type: application/json" \
  -d '{"password": "YOUR_PASSWORD_HERE"}' \  # pragma: allowlist secret
  -c cookies.txt

# Test chat (with cookie)
curl -X POST ${APP_RUNNER_URL}/api/chat \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{"message": "Hello!"}'
```

### 12.3 Check CloudWatch Logs

**Navigate in AWS Console:**
1. AWS Console → **CloudWatch** → **Log groups**
2. Find `/aws/apprunner/enterprise-agentic-ai-backend`
3. Click to view log streams
4. Verify requests are being logged

### 12.4 End-to-End Verification Checklist

- [ ] CloudFront URL loads login page
- [ ] No JavaScript errors in browser console
- [ ] Login with password succeeds
- [ ] Chat interface displays
- [ ] Message sends and receives streaming response
- [ ] Tool usage works (search, market data)
- [ ] CloudWatch shows request logs
- [ ] Response time acceptable after warmup (<2s)

---

## Phase 1a Completion Checklist

### Prerequisites
- [x] Phase 0 complete and verified
- [x] AWS CLI v2 configured
- [x] Terraform 1.5.0+ installed
- [x] Bedrock model access approved

### AWS Setup
- [ ] Billing alert configured ($50/month)
- [ ] IAM permissions verified
- [ ] Account ID noted

### Terraform State
- [ ] S3 bucket created for state
- [ ] DynamoDB table created for locking
- [ ] Versioning enabled on bucket

### Secrets Manager
- [ ] Demo password secret created
- [ ] Auth token secret created
- [ ] Tavily API key secret created
- [ ] FMP API key secret created

### Terraform Infrastructure
- [ ] All modules created (networking, ecr, secrets, app-runner, s3-cloudfront)
- [ ] `terraform init` successful
- [ ] `terraform validate` passes
- [ ] `terraform apply` completed

### Backend
- [ ] Settings updated for AWS environment
- [ ] CORS configured for CloudFront
- [ ] Production Dockerfile created
- [ ] Build tested locally

### Deployment
- [ ] Docker image pushed to ECR
- [ ] App Runner service running
- [ ] Health endpoint responds
- [ ] S3 bucket has frontend files
- [ ] CloudFront distribution active

### Verification
- [ ] Login page accessible via CloudFront
- [ ] Authentication works
- [ ] Chat streaming works
- [ ] Tools execute correctly
- [ ] CloudWatch logs visible

---

## Common Issues and Solutions

### Issue: Terraform init fails with "Backend configuration changed"

**Symptoms:**
- Error about backend configuration not matching
- Cannot initialize Terraform

**Solution:**
```bash
# Remove local state (if migrating to remote)
rm -rf .terraform
rm -f .terraform.lock.hcl

# Reinitialize
terraform init -reconfigure
```

### Issue: ECR push fails with "no basic auth credentials"

**Symptoms:**
- `docker push` fails with authentication error

**Solution:**
```bash
# Re-authenticate (tokens expire after 12 hours)
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  $(aws sts get-caller-identity --query Account --output text).dkr.ecr.us-east-1.amazonaws.com
```

### Issue: App Runner shows "Service Unavailable"

**Symptoms:**
- Health endpoint returns 503
- Service not starting

**Solutions:**
1. **Wait for cold start:** First deployment takes 2-3 minutes
2. **Check logs:**
   ```bash
   aws logs tail /aws/apprunner/enterprise-agentic-ai-backend --region us-east-1
   ```
3. **Verify image exists in ECR:**
   ```bash
   aws ecr describe-images --repository-name enterprise-agentic-ai-backend --region us-east-1
   ```
4. **Check IAM permissions:** App Runner role needs ECR access

### Issue: CORS error in browser console

**Symptoms:**
- "Access-Control-Allow-Origin" error
- Chat requests fail

**Solution:**
1. Verify CORS in backend:
   ```bash
   curl -H "Origin: https://YOUR_CLOUDFRONT_DOMAIN.cloudfront.net" \
        -H "Access-Control-Request-Method: POST" \
        -X OPTIONS \
        ${APP_RUNNER_URL}/api/chat
   ```
2. Update `ALLOWED_ORIGINS` in App Runner environment variables
3. Redeploy App Runner (update Terraform and apply)

### Issue: CloudFront shows old content

**Symptoms:**
- Changes not appearing after S3 upload

**Solution:**
```bash
# Invalidate all cached content
aws cloudfront create-invalidation \
  --distribution-id ${DISTRIBUTION_ID} \
  --paths "/*"

# Wait 1-2 minutes for propagation
```

### Issue: Secrets Manager access denied

**Symptoms:**
- App Runner logs show "AccessDeniedException"
- Unable to load secrets

**Solution:**
1. Verify App Runner role has secrets policy attached
2. Verify secret ARNs are correct in Terraform
3. Check secrets exist in us-east-1 region

### Issue: Bedrock returns AccessDeniedException

**Symptoms:**
- Chat fails with "you don't have access to the model"

**Solution:**
1. Verify model access in Bedrock Console (Model access page)
2. Ensure region is us-east-1
3. Wait up to 24 hours for access approval

### Issue: Terraform state lock error

**Symptoms:**
- "Error acquiring the state lock"

**Solution:**
```bash
# Find and remove stale lock
aws dynamodb scan --table-name enterprise-agentic-ai-tflock

# Delete lock item (use LockID from scan)
aws dynamodb delete-item \
  --table-name enterprise-agentic-ai-tflock \
  --key '{"LockID":{"S":"YOUR_LOCK_ID"}}'
```

---

## Cost Monitoring

### Expected Costs (Approximate)

| Service | Cost | Notes |
|---------|------|-------|
| App Runner | $0-15/month | Scales to zero when idle |
| ECR | $0.10/GB/month | ~100MB image = ~$0.01 |
| S3 | $0.023/GB/month | Minimal for static files |
| CloudFront | $0-5/month | Based on requests |
| Secrets Manager | $1.60/month | 4 secrets × $0.40 |
| CloudWatch Logs | $0-2/month | Based on log volume |
| **Total** | **~$10-25/month** | When active, less when idle |

### Monitor Costs

**Navigate in AWS Console:**
1. Billing → Cost Explorer
2. Filter by service to see breakdown
3. Set up cost allocation tags for this project

---

## Cleanup Instructions

If you need to tear down the infrastructure (stops all costs):

### Full Cleanup

```bash
cd ~/Projects/aws-enterprise-agentic-ai/terraform/environments/dev

# Destroy all infrastructure
terraform destroy

# Manually delete (Terraform may not delete these):
# - S3 bucket contents (if versioning creates delete markers)
# - CloudWatch log groups
# - ECR images
```

### Keep State, Destroy Resources

```bash
# Destroy but keep Terraform state bucket
terraform destroy

# DON'T delete:
# - S3 bucket: enterprise-agentic-ai-tfstate-*
# - DynamoDB: enterprise-agentic-ai-tflock
# - Secrets Manager secrets (manual recreation required)
```

---

## Branch Management and Next Steps

### Save Phase 1a Work

**Commands:**
```bash
cd ~/Projects/aws-enterprise-agentic-ai

# Commit all changes
git add .
git commit -m "Complete Phase 1a: AWS deployment with App Runner, CloudFront, Secrets Manager"

# Tag Phase 1a completion
git tag -a v0.2.0-phase1a -m "Phase 1a complete - AWS cloud deployment"

# Push to remote
git push origin main
git push origin v0.2.0-phase1a
```

### Prepare for Phase 1b

Phase 1b adds:
- Aurora Serverless v2 database
- PostgresSaver for persistent checkpointing
- GitHub Actions CI/CD
- Rate limiting
- Enhanced health checks
- Structured logging improvements

**Create Phase 1b branch:**
```bash
git checkout -b phase-1b-production-hardening
```

### Document Your Deployment

Note these values for future reference:

| Item | Value |
|------|-------|
| CloudFront URL | `https://xxxxx.cloudfront.net` |
| App Runner URL | `https://xxxxx.us-east-1.awsapprunner.com` |
| S3 Bucket | `enterprise-agentic-ai-frontend-xxxxx` |
| ECR Repository | `enterprise-agentic-ai-backend` |
| Terraform State Bucket | `enterprise-agentic-ai-tfstate-xxx` |

---

## Summary

Phase 1a establishes AWS cloud deployment with:
- ✅ App Runner backend with LangGraph agent
- ✅ CloudFront + S3 frontend hosting
- ✅ Secrets Manager for secure credentials
- ✅ Bedrock integration for LLM
- ✅ Password-protected access
- ✅ Streaming chat functionality
- ✅ Cost-optimized infrastructure (~$10-25/month)

**Key Achievements:**
- Publicly accessible demo at CloudFront URL
- Secure secrets management (no credentials in code)
- Infrastructure as Code with Terraform
- Manual but repeatable deployment process
- Cold start handled with loading indicator

**Next Phase (1b):** Add production hardening:
- Persistent database (Aurora Serverless v2)
- Automated CI/CD (GitHub Actions)
- Enhanced security (rate limiting)
- Improved observability

**Estimated Time for Phase 1a:** 8-16 hours (completed)

**Success Criteria:** User can access site via CloudFront URL, login with password, and have a streaming chat conversation with the AI agent.
