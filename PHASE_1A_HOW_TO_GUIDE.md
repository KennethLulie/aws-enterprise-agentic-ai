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
- [Terraform Infrastructure - Stages 1-3](#5-terraform-infrastructure---stages-1-3)
- [Backend Updates for AWS](#6-backend-updates-for-aws)
- [Production Docker Build](#7-production-docker-build)
- [ECR Repository and Image Push](#8-ecr-repository-and-image-push)
- [App Runner Deployment (Terraform Stage 4)](#9-app-runner-deployment-terraform-stage-4)
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

**📋 This guide is designed to be followed linearly.** Complete each section in order (1→2→3→...→12). There is no jumping back and forth.

**Overall Phase 1a Workflow:**
1. **Prerequisites** (Section 1): Verify Phase 0 complete, AWS CLI configured
2. **AWS Setup** (Section 2): Billing alerts, IAM permissions verification
3. **Terraform State** (Section 3): Create S3 bucket and DynamoDB table for state
4. **Secrets Manager** (Section 4): Store all secrets (password, API keys)
5. **Terraform Stages 1-3** (Section 5): Networking, ECR repository, S3/CloudFront
6. **Backend Updates** (Section 6): CORS, environment detection, CloudWatch logging
7. **Docker Build** (Section 7): Create production Dockerfile
8. **ECR Push** (Section 8): Build and push Docker image to ECR
9. **Terraform Stage 4 + App Runner** (Section 9): Deploy backend (needs image from Section 8)
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

**Navigate in AWS Console:**
1. Sign in to AWS Console: https://console.aws.amazon.com
2. In the search bar at the top, type **"Bedrock"** and click **Amazon Bedrock**
3. In the left sidebar, scroll down and click **Model access** (under "Bedrock configurations")
4. Click **Modify model access** button (orange button, top right)
5. Find and check these models:
   - ✅ Amazon → **Amazon Nova Pro**
   - ✅ Amazon → **Amazon Nova Lite**
   - ✅ Anthropic → **Claude 3.5 Sonnet** (for fallback)
6. Scroll to bottom, click **Next**
7. Review and click **Submit**
8. Wait for "Access granted" status (can take up to 24 hours, usually faster)

### 1.5 Check Current IAM Permissions (Quick Test)

Phase 1a requires permissions for multiple AWS services. This section does a **quick check** to see if you already have the necessary permissions. If any tests fail, **don't worry** - Section 2.3 will walk you through adding the required policies.

**Required services:**
- S3 (storage) - for frontend and Terraform state
- ECR (container registry) - for Docker images
- App Runner (compute) - for backend
- CloudFront (CDN) - for frontend distribution
- Secrets Manager - for passwords and API keys
- IAM - for creating roles
- VPC/EC2 - for networking
- CloudWatch - for logging
- DynamoDB - for Terraform state locking
- Bedrock - for LLM access

**Quick permission test (tests a subset of services):**
```bash
# Test 1: S3 access (for frontend hosting and Terraform state)
aws s3 ls
# Expected: List of buckets (or empty list if no buckets exist)

# Test 2: ECR access (for Docker images)
aws ecr describe-repositories --region us-east-1
# Expected: List of repositories (or empty list)

# Test 3: Secrets Manager access
aws secretsmanager list-secrets --region us-east-1
# Expected: List of secrets (or empty list)

# Test 4: VPC/EC2 access (for networking)
aws ec2 describe-vpcs --region us-east-1
# Expected: List of VPCs (should have at least the default VPC)

# Test 5: IAM access (for creating roles)
aws iam get-user
# Expected: Your IAM user details
```

**Interpreting results:**

| Result | Meaning | Action |
|--------|---------|--------|
| Commands return data (or empty lists) | ✅ You have basic permissions | Continue to Section 1.6 |
| "AccessDenied" error | ❌ Missing permissions | Continue anyway - Section 2.3 will add them |
| "InvalidClientTokenId" error | ❌ AWS CLI not configured | Go back to Section 1.2 |

**Note:** These tests only check a subset of permissions. Even if all pass, you may still need to add policies in Section 2.3. The full permission set will be configured there.

### 1.6 Prerequisites Checklist

Before proceeding to Section 2, verify these items:

- [ ] Phase 0 services start and work locally
- [ ] AWS CLI v2 installed and configured (`aws --version`)
- [ ] AWS credentials working (`aws sts get-caller-identity`)
- [ ] AWS region set to us-east-1 (`aws configure get region`)
- [ ] Terraform 1.5.0+ installed (`terraform --version`)
- [ ] AWS Bedrock model access approved (or request submitted)
- [ ] Quick permission test run (Section 1.5) - failures OK, will fix in Section 2.3

**Note:** If the permission tests in Section 1.5 failed, that's expected for new AWS accounts. Section 2.3 will walk you through adding all required permissions.

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
2. Click on your **account name** (top right corner, shows your name or account alias)
3. In the dropdown menu, click **Billing and Cost Management**
4. In the left sidebar, scroll down to "Budgets and Planning" section
5. Click **Budgets**
6. Click the **Create budget** button (orange button)

**Step 1 - Budget Setup:**
- Choose budget type: Select **Customize (advanced)**
- Budget type: Select **Cost budget - Recommended**
- Click **Next**

**Step 2 - Set Budget:**
- Budget name: `enterprise-agentic-ai-demo`
- Period: **Monthly**
- Budget renewal type: **Recurring budget**
- Start month: (current month)
- Budgeting method: **Fixed**
- Enter your budgeted amount: **50.00** (USD)
- All other settings: leave as default
- Click **Next**

**Step 3 - Configure Alerts:**
- Click **Add an alert threshold**
- Alert #1 settings:
  - Threshold: **80** % of budgeted amount (Actual)
  - Notification preferences: **Email**
  - Email recipients: Enter your email address
- Click **Next**

**Step 4 - Review and Create:**
- Review settings
- Click **Create budget**

**Verification:** You should see your budget in the list with "Current vs. budgeted" showing $0.00 / $50.00

### 2.2 Verify Cost Explorer Access

**Navigate in AWS Console:**
1. Billing and Cost Management → **Cost Explorer**
2. If prompted, click **Enable Cost Explorer** (takes up to 24 hours to populate)

### 2.3 Add Required IAM Permissions

This section ensures your IAM user has all the permissions needed for Phase 1a. Even if the quick test in Section 1.5 passed, you should still review and add any missing policies here.

**Required AWS managed policies:**

| Policy | Purpose | Why Needed |
|--------|---------|------------|
| `AmazonEC2FullAccess` | VPC, subnets, security groups | Terraform creates networking |
| `AmazonS3FullAccess` | Frontend hosting, Terraform state | S3 buckets for frontend and state |
| `CloudFrontFullAccess` | CDN distribution | CloudFront for frontend |
| `AWSAppRunnerFullAccess` | Backend deployment | App Runner for backend |
| `AmazonEC2ContainerRegistryFullAccess` | Docker image storage | ECR for Docker images |
| `SecretsManagerReadWrite` | Password and API key storage | Secrets for auth and API keys |
| `IAMFullAccess` | Create roles for App Runner | IAM roles for App Runner |
| `AmazonDynamoDBFullAccess` | Terraform state locking | DynamoDB for TF state lock |
| `CloudWatchLogsFullAccess` | Application logging | Logs from App Runner |
| `AmazonBedrockFullAccess` | LLM access | AI model access |

**⚠️ Security Note:** These are broad permissions suitable for development/demo. Production environments should use more restrictive custom policies with least-privilege access.

**Step-by-step: Add policies to your IAM user**

1. **Open IAM Console:**
   - Sign in to AWS Console: https://console.aws.amazon.com
   - In the search bar, type **"IAM"** and click **IAM**

2. **Find your user:**
   - In the left sidebar, click **Users**
   - Click on your username in the list

3. **Check existing policies:**
   - Click the **Permissions** tab
   - Review the "Permissions policies" list
   - Note which policies you already have (skip those below)

4. **Add missing policies:**
   - Click **Add permissions** button → Select **Add permissions**
   - Select **Attach policies directly** (third option)
   - Search for and check each missing policy:

   | Search for | Check this policy |
   |------------|-------------------|
   | `EC2Full` | AmazonEC2FullAccess |
   | `S3Full` | AmazonS3FullAccess |
   | `CloudFront` | CloudFrontFullAccess |
   | `AppRunner` | AWSAppRunnerFullAccess |
   | `ContainerRegistry` | AmazonEC2ContainerRegistryFullAccess |
   | `SecretsManager` | SecretsManagerReadWrite |
   | `IAMFull` | IAMFullAccess |
   | `DynamoDB` | AmazonDynamoDBFullAccess |
   | `CloudWatchLogs` | CloudWatchLogsFullAccess |
   | `Bedrock` | AmazonBedrockFullAccess |

5. **Apply permissions:**
   - Click **Next** → Review → **Add permissions**

**Verify permissions were added:**
```bash
# Re-run the permission tests from Section 1.5
aws s3 ls
aws ecr describe-repositories --region us-east-1
aws secretsmanager list-secrets --region us-east-1
aws ec2 describe-vpcs --region us-east-1
aws iam get-user

# Additional tests for newly added permissions
aws apprunner list-services --region us-east-1
aws cloudfront list-distributions --max-items 1
aws dynamodb list-tables --region us-east-1
```

All commands should complete without "AccessDenied" errors. Empty lists are fine - that just means no resources exist yet.

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

### Why We Create These Manually (Not with Terraform)

You might wonder: "Why aren't we using Terraform to create these resources?"

**The chicken-and-egg problem:** Terraform stores its state (a record of all resources it manages) in a "backend." We're using S3 for state storage and DynamoDB for state locking. But Terraform needs its backend to exist BEFORE it can manage any infrastructure.

You can't use Terraform to create the place where Terraform stores its data - that place has to exist first!

**These "bootstrap" resources:**
- Are created once and rarely modified
- Cost almost nothing (~$0-1/month with minimal usage)
- Are intentionally NOT managed by Terraform
- Should NOT be deleted unless you're completely done with the project

Everything AFTER this section will be managed by Terraform. This is the only manual AWS setup (besides Secrets Manager in Section 4).

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
1. Sign in to AWS Console: https://console.aws.amazon.com
2. Ensure region is **US East (N. Virginia) us-east-1** (top right dropdown)
3. In the search bar, type **"DynamoDB"** and click **DynamoDB**
4. Click **Create table** (orange button)

**Table Details (Step 1):**

| Setting | Value | Notes |
|---------|-------|-------|
| **Table name** | `enterprise-agentic-ai-tflock` | Exact name required |
| **Partition key** | `LockID` | ⚠️ **Case-sensitive!** Must be exactly `LockID` |
| **Partition key type** | `String` | Select from dropdown |
| **Sort key** | ❌ **Leave unchecked** | Do NOT add a sort key |

**Table Settings (Step 2):**

| Setting | Value | Notes |
|---------|-------|-------|
| **Table settings** | ✅ **Default settings** | Select this option |

When "Default settings" is selected, AWS uses sensible defaults:
- Table class: DynamoDB Standard
- Capacity mode: On-demand (pay per request)
- Encryption: AWS owned key

**⚠️ Do NOT select "Customize settings"** unless you specifically need to change something. The defaults are correct for Terraform state locking.

<details>
<summary>📋 What "Default settings" includes (click to expand)</summary>

If you're curious, here's what the defaults set:
- **Table class:** DynamoDB Standard (not Standard-IA)
- **Read/write capacity:** On-demand (no provisioned capacity to manage)
- **Encryption at rest:** Owned by Amazon DynamoDB (free)
- **Deletion protection:** Disabled
- **Resource-based policy:** None

All of these are appropriate for a Terraform state lock table with minimal usage.
</details>

**Create the table:**
1. Review your settings:
   - Table name: `enterprise-agentic-ai-tflock`
   - Partition key: `LockID` (String)
   - No sort key
   - Default settings selected
2. Click **Create table** (orange button at bottom)
3. Wait for status to change from "Creating" to "Active" (usually 10-30 seconds)

**Verification:**
```bash
# Check table was created and is active
aws dynamodb describe-table --table-name enterprise-agentic-ai-tflock --query 'Table.TableStatus'
```

**Expected output:** `"ACTIVE"`

**If you get an error:**
- `ResourceNotFoundException`: Table wasn't created - go back and create it
- `AccessDeniedException`: Missing DynamoDB permissions - see Section 2.3

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

## 5. Terraform Infrastructure - Stages 1-3

### What We're Doing
Writing and applying Terraform configurations for infrastructure that doesn't depend on your application code: VPC/networking, ECR repository (empty), S3/CloudFront (empty). 

**Note:** This guide is designed to be followed linearly from start to finish. Terraform is split into two sections because of a real dependency:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         WHY TERRAFORM IS SPLIT                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Section 5 (here): Create infrastructure that CAN exist empty              │
│  ┌────────────────────────────────────────────────────────────┐             │
│  │ Stage 1: Networking (VPC, subnets) ✓                       │             │
│  │ Stage 2: ECR Repository (empty, waiting for image) ✓       │             │
│  │ Stage 3: S3 + CloudFront (empty, waiting for files) ✓      │             │
│  └────────────────────────────────────────────────────────────┘             │
│                              │                                              │
│                              ▼                                              │
│  Sections 6-8: Build what goes IN the infrastructure                        │
│  ┌────────────────────────────────────────────────────────────┐             │
│  │ Section 6: Update backend code for AWS                     │             │
│  │ Section 7: Build production Docker image                   │             │
│  │ Section 8: Push image to ECR (fills the empty repo) ───────┼──┐          │
│  └────────────────────────────────────────────────────────────┘  │          │
│                                                                  │          │
│  Section 9: Create infrastructure that NEEDS the image          │          │
│  ┌────────────────────────────────────────────────────────────┐  │          │
│  │ Stage 4: App Runner (pulls image from ECR) ◀───────────────┼──┘          │
│  └────────────────────────────────────────────────────────────┘             │
│                                                                             │
│  ✓ Follow sections 5 → 6 → 7 → 8 → 9 in order. No jumping around.          │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Why This Matters
- **Infrastructure as Code:** Reproducible, version-controlled infrastructure
- **Consistency:** Same infrastructure every time
- **Documentation:** Terraform files document what exists

### 5.1 Terraform Module Structure

We'll create this directory structure:

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

**Create the directory structure:**
```bash
cd ~/Projects/aws-enterprise-agentic-ai

# Create all Terraform directories
mkdir -p terraform/environments/dev
mkdir -p terraform/modules/networking
mkdir -p terraform/modules/ecr
mkdir -p terraform/modules/app-runner
mkdir -p terraform/modules/s3-cloudfront
mkdir -p terraform/modules/secrets

# Verify structure
find terraform -type d | sort
```

**Expected Output:**
```
terraform
terraform/environments
terraform/environments/dev
terraform/modules
terraform/modules/app-runner
terraform/modules/ecr
terraform/modules/networking
terraform/modules/s3-cloudfront
terraform/modules/secrets
```

### 5.2 Create State Backend Configuration

**Agent Prompt:**
```
Create `terraform/environments/dev/backend.tf`

Contents:
1. Terraform block with required_version >= 1.5.0
2. Required providers: hashicorp/aws ~> 5.0, hashicorp/random ~> 3.0
3. S3 backend configuration (inside terraform block):
   - bucket = "REPLACE_WITH_YOUR_BUCKET_NAME"
   - key = "dev/terraform.tfstate"
   - region = "us-east-1"
   - dynamodb_table = "enterprise-agentic-ai-tflock"
   - encrypt = true
4. AWS provider with region us-east-1 and default_tags:
   - Project = "enterprise-agentic-ai"
   - Environment = "dev"
   - ManagedBy = "terraform"

Configuration:
- Backend block goes INSIDE the terraform block (not separate)
- Use Terraform HCL syntax, not JSON
- Include comments explaining each section

Reference:
- Terraform S3 backend docs: https://developer.hashicorp.com/terraform/language/settings/backends/s3
- AWS provider docs: https://registry.terraform.io/providers/hashicorp/aws/latest/docs

Verify: cd terraform/environments/dev && terraform validate
```

**After running the prompt:** Replace `REPLACE_WITH_YOUR_BUCKET_NAME` with your actual bucket name from Section 3 (e.g., `enterprise-agentic-ai-tfstate-jd`)

### 5.3 Create Networking Module

**Agent Prompt:**
```
Create Terraform networking module at `terraform/modules/networking/`

Files to create: main.tf, variables.tf, outputs.tf

Resources in main.tf:
1. aws_vpc - CIDR var.vpc_cidr (default 10.0.0.0/16), enable DNS hostnames/support
2. aws_internet_gateway - attach to VPC
3. aws_subnet (x2) - public subnets in us-east-1a (10.0.1.0/24) and us-east-1b (10.0.2.0/24), map_public_ip_on_launch = true
4. aws_route_table - route 0.0.0.0/0 to IGW
5. aws_route_table_association (x2) - associate subnets with route table
6. aws_security_group - for future VPC connector, egress-only (all outbound allowed)

Variables in variables.tf:
- project_name (string, required)
- environment (string, default "dev")
- vpc_cidr (string, default "10.0.0.0/16")
- tags (map(string), default {})

Outputs in outputs.tf:
- vpc_id
- public_subnet_ids (list)
- security_group_id

Configuration:
- Tag all resources with: Name = "${var.project_name}-${var.environment}-<resource>"
- Merge var.tags into all resource tags
- No NAT Gateway (cost optimization - Phase 1b adds if needed)

Reference:
- AWS VPC Terraform docs
- Phase 1a uses public subnets only (App Runner has public internet access by default)

Verify: cd terraform/environments/dev && terraform validate
```

### 5.4 Create ECR Module

**Agent Prompt:**
```
Create Terraform ECR module at `terraform/modules/ecr/`

Files to create: main.tf, variables.tf, outputs.tf

Resources in main.tf:
1. aws_ecr_repository
   - name = var.repository_name
   - image_tag_mutability = "MUTABLE" (allows :latest overwrites)
   - image_scanning_configuration { scan_on_push = true }
2. aws_ecr_lifecycle_policy
   - Expire untagged images after 1 day
   - Keep only last 10 tagged images
   - Use jsonencode() for policy document

Variables in variables.tf:
- repository_name (string, required)
- tags (map(string), default {})

Outputs in outputs.tf:
- repository_url (for docker push)
- repository_arn
- registry_id

Configuration:
- Lifecycle policy keeps costs low by cleaning old images
- MUTABLE tags for development (can overwrite :latest)
- Scan on push for security

Reference:
- AWS ECR Terraform: https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ecr_repository
- Cost: ~$0.10/GB/month storage

Verify: cd terraform/environments/dev && terraform validate
```

### 5.5 Create Secrets Module

**Agent Prompt:**
```
Create Terraform secrets module at `terraform/modules/secrets/`

Files to create: main.tf, variables.tf, outputs.tf

Resources in main.tf:
1. Data sources (reference EXISTING secrets, don't create):
   - data "aws_secretsmanager_secret" "demo_password" { name = "enterprise-agentic-ai/demo-password" }
   - data "aws_secretsmanager_secret" "auth_token_secret" { name = "enterprise-agentic-ai/auth-token-secret" }
   - data "aws_secretsmanager_secret" "tavily_api_key" { name = "enterprise-agentic-ai/tavily-api-key" }
   - data "aws_secretsmanager_secret" "fmp_api_key" { name = "enterprise-agentic-ai/fmp-api-key" }

2. IAM policy document allowing:
   - Actions: secretsmanager:GetSecretValue, secretsmanager:DescribeSecret
   - Resources: ARNs of all four secrets

3. aws_iam_policy using the policy document

Variables in variables.tf:
- project_name (string, required)
- environment (string, default "dev")
- tags (map(string), default {})

Outputs in outputs.tf:
- secret_arns = { demo_password = ..., auth_token_secret = ..., tavily_api_key = ..., fmp_api_key = ... }
- secrets_access_policy_arn

Configuration:
- Secrets were created manually in Section 4 - we're only referencing them
- IAM policy allows App Runner to read these secrets
- Use data sources, not resources (secrets already exist)

Reference:
- _security.mdc "Secrets Management"
- Secrets created in Section 4 of this guide

Verify: cd terraform/environments/dev && terraform validate
```

### 5.6 Create App Runner Module

**Agent Prompt:**
```
Create Terraform App Runner module at `terraform/modules/app-runner/`

Files to create: main.tf, variables.tf, outputs.tf

Resources in main.tf:
1. aws_iam_role for ECR access:
   - Trust: build.apprunner.amazonaws.com
   - Attach: AmazonEC2ContainerRegistryReadOnly (managed policy)

2. aws_iam_role for instance:
   - Trust: tasks.apprunner.amazonaws.com
   - Attach: var.secrets_policy_arn (passed from secrets module)
   - Inline policy for Bedrock: bedrock:InvokeModel, bedrock:InvokeModelWithResponseStream on resource "*"
   - Inline policy for CloudWatch Logs: logs:CreateLogGroup, logs:CreateLogStream, logs:PutLogEvents

3. aws_apprunner_service:
   - source_configuration.authentication_configuration.access_role_arn = ECR role
   - source_configuration.auto_deployments_enabled = false
   - source_configuration.image_repository:
     - image_identifier = "${var.ecr_repository_url}:${var.image_tag}"
     - image_repository_type = "ECR"
     - image_configuration.port = "8000"
   - instance_configuration: cpu = var.cpu, memory = var.memory, instance_role_arn = instance role
   - health_check_configuration: protocol = "HTTP", path = "/health", interval = 10
   - network_configuration.egress_configuration.egress_type = "DEFAULT"

Environment variables (in image_configuration):
- runtime_environment_variables:
  - ENVIRONMENT = "aws"
  - AWS_REGION = "us-east-1"
  - LOG_LEVEL = "INFO"
  - ALLOWED_ORIGINS = var.allowed_origins

- runtime_environment_secrets (CRITICAL FORMAT - ARN:jsonKey::):
  - DEMO_PASSWORD = "${var.secret_arns["demo_password"]}:password::"
  - AUTH_TOKEN_SECRET = "${var.secret_arns["auth_token_secret"]}:secret::"
  - TAVILY_API_KEY = "${var.secret_arns["tavily_api_key"]}:api_key::"
  - FMP_API_KEY = "${var.secret_arns["fmp_api_key"]}:api_key::"

Variables in variables.tf:
- service_name (string, required)
- ecr_repository_url (string, required)
- image_tag (string, default "latest")
- secrets_policy_arn (string, required)
- secret_arns (map(string), required)
- allowed_origins (string, required)
- cpu (string, default "1024")
- memory (string, default "2048")
- tags (map(string), default {})

Outputs in outputs.tf:
- service_url (the https://... URL)
- service_arn
- service_id

Configuration:
- Secret format is ARN:jsonKey:: (the trailing colons are required)
- CPU 1024 = 1 vCPU, memory 2048 = 2 GB
- Health check on /health endpoint

Reference:
- App Runner Terraform: https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/apprunner_service
- App Runner secrets: https://docs.aws.amazon.com/apprunner/latest/dg/manage-configure-secrets.html
- Cost: ~$0.007/vCPU-hour when running, scales to zero when idle

Verify: cd terraform/environments/dev && terraform validate
```

### 5.7 Create S3-CloudFront Module

**Agent Prompt:**
```
Create Terraform S3-CloudFront module at `terraform/modules/s3-cloudfront/`

Files to create: main.tf, variables.tf, outputs.tf

Resources in main.tf:
1. aws_s3_bucket - bucket name from var.bucket_name
2. aws_s3_bucket_versioning - enabled
3. aws_s3_bucket_ownership_controls - BucketOwnerEnforced
4. aws_s3_bucket_public_access_block - block ALL public access (all 4 = true)
5. aws_cloudfront_origin_access_control (OAC, NOT legacy OAI):
   - origin_access_control_origin_type = "s3"
   - signing_behavior = "always"
   - signing_protocol = "sigv4"
6. aws_s3_bucket_policy:
   - Allow s3:GetObject from CloudFront service principal
   - Condition: AWS:SourceArn = CloudFront distribution ARN
7. aws_cloudfront_distribution:
   - origin: S3 bucket_regional_domain_name with OAC
   - default_root_object = "index.html"
   - price_class = "PriceClass_100" (US/Canada/Europe only - cost opt)
   - http_version = "http2and3"
   - default_cache_behavior:
     - viewer_protocol_policy = "redirect-to-https"
     - cache_policy_id = "658327ea-f89d-4fab-a63d-7e88639e58f6" (CachingOptimized)
     - compress = true
   - custom_error_response for 403 and 404 → /index.html with 200 (SPA routing)
   - viewer_certificate: cloudfront_default_certificate = true

Variables in variables.tf:
- bucket_name (string, required)
- project_name (string, required)
- environment (string, default "dev")
- tags (map(string), default {})

Outputs in outputs.tf:
- bucket_name
- bucket_arn
- cloudfront_distribution_id (for cache invalidation)
- cloudfront_domain_name (e.g., d1234.cloudfront.net)
- cloudfront_url (https://... full URL)

Configuration:
- Use OAC (Origin Access Control), NOT OAI (deprecated)
- Use bucket_regional_domain_name, not bucket_domain_name
- SPA routing: 403/404 errors return /index.html with 200

Reference:
- CloudFront OAC docs: https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-s3.html
- Cache policy IDs: https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/using-managed-cache-policies.html
- Cost: ~$0.085/GB data transfer, minimal for demo

Verify: cd terraform/environments/dev && terraform validate
```

### 5.8 Create Dev Environment Main Configuration

**Agent Prompt:**
```
Create Terraform dev environment at `terraform/environments/dev/`

Files to create: main.tf, variables.tf, outputs.tf

Contents of main.tf:
1. locals block:
   - project_name = "enterprise-agentic-ai"
   - environment = "dev"
   - common_tags = { Project, Environment, ManagedBy = "terraform" }

2. Data sources:
   - data "aws_region" "current" {}
   - data "aws_caller_identity" "current" {}

3. random_string for unique S3 bucket name (length=8, special=false, upper=false)

4. Module calls (order matters):
   a. module "networking" - source = "../../modules/networking"
   b. module "ecr" - repository_name = "${local.project_name}-backend"
   c. module "secrets" - references existing secrets
   d. module "s3_cloudfront" - bucket_name with random suffix
   e. module "app_runner" - uses outputs from ecr, secrets, s3_cloudfront
      - allowed_origins = "https://${module.s3_cloudfront.cloudfront_domain_name},http://localhost:3000"
      - depends_on = [module.ecr, module.secrets, module.s3_cloudfront]

Contents of variables.tf:
- Empty or placeholder comment (we use locals for this environment)

Contents of outputs.tf:
- app_runner_url = module.app_runner.service_url
- cloudfront_url = module.s3_cloudfront.cloudfront_url
- cloudfront_distribution_id = module.s3_cloudfront.cloudfront_distribution_id
- ecr_repository_url = module.ecr.repository_url
- s3_bucket_name = module.s3_cloudfront.bucket_name

Configuration:
- Pass local.common_tags to all modules
- App Runner depends on other modules for their outputs
- allowed_origins includes both CloudFront (prod) and localhost (dev)

Reference:
- Terraform module sources use relative paths
- All modules defined in terraform/modules/

Verify: cd terraform/environments/dev && terraform validate
```

### 5.9 Update .gitignore for Terraform

**Agent Prompt:**
```
Update `.gitignore` to include Terraform patterns

Add these patterns if not already present:
- .terraform/
- *.tfstate
- *.tfstate.*
- *.tfvars
- !*.tfvars.example
- .terraform.lock.hcl
- crash.log
- override.tf
- override.tf.json
- *_override.tf
- *_override.tf.json

Also create `terraform/environments/dev/terraform.tfvars.example`:
- Empty file with comment: "# No required variables - using locals in main.tf"

Reference:
- Terraform gitignore best practices
- tfvars files may contain secrets, always gitignore

Verify: grep -q "tfstate" .gitignore && echo "OK"
```

### 5.10 Initialize, Validate, and Review Terraform Plan

**Commands:**
```bash
cd ~/Projects/aws-enterprise-agentic-ai/terraform/environments/dev

# Initialize Terraform (downloads providers, configures backend)
terraform init

# Validate configuration syntax
terraform validate

# Generate and save plan for review
terraform plan -out=tfplan.out
```

**Expected Output:**
- `terraform init`: "Terraform has been successfully initialized!"
- `terraform validate`: "Success! The configuration is valid."
- `terraform plan`: Shows resources to be created

**⚠️ CRITICAL: Review Plan Before Applying**
**Highly Recommended to have LLM additionally do a santity check!**
Before typing `yes` on any apply, carefully review the plan output:

| Check | Expected | If Wrong - STOP |
|-------|----------|-----------------|
| Resources to add | 18-25 resources | If >30: may have duplicates or errors |
| Resources to destroy | 0 (first apply) | Should never destroy on fresh apply |
| Resources to change | 0 (first apply) | Nothing should change yet |
| Region | us-east-1 | Wrong region = duplicate infrastructure |

**Expected Resources (Phase 1a Full Apply):**

| Module | Resources | Approximate Count |
|--------|-----------|-------------------|
| networking | VPC, IGW, 2 Subnets, Route Table, 2 Associations, Security Group | 8 |
| ecr | Repository, Lifecycle Policy | 2 |
| secrets | Data sources (no resources created), IAM Policy | 1 |
| s3_cloudfront | S3 Bucket + settings, CloudFront Distribution, OAC, Bucket Policy | 6-8 |
| app_runner | Service, 2 IAM Roles, Role Policies | 4-6 |
| other | Random string for bucket naming | 1 |
| **Total** | | **18-25** |

**🚨 RED FLAGS - Stop Immediately If You See:**

| Unexpected Resource | Why It's Bad | Monthly Cost |
|---------------------|--------------|--------------|
| `aws_nat_gateway` | Not needed for Phase 1a | ~$32 + data |
| `aws_db_instance` (RDS) | Database is Phase 1b | ~$15-50 |
| `aws_eip` (Elastic IP) | Not needed | $3.60 if unattached |
| `aws_ecs_cluster` | Wrong compute service | Varies |
| `aws_lambda_function` | Not in Phase 1a | Varies |
| Multiple `aws_apprunner_service` | Should only be 1 | ~$25 each |
| Resources in wrong region | Duplicates | 2x cost |

**If you see any red flags:** Do NOT apply. Review your Terraform code for errors.

### 5.11 Staged Apply: Stages 1-3

Apply Terraform in stages to catch issues early and limit blast radius. This section covers Stages 1-3. Stage 4 (App Runner) is applied in Section 9 after your Docker image is ready.

**Why Staged Apply:**
- Catches configuration errors before creating expensive resources
- Easier to debug issues when fewer resources change
- Allows verification at each step
- Limits cost exposure if something goes wrong

**Stage 1: Networking (Free resources)**
```bash
cd ~/Projects/aws-enterprise-agentic-ai/terraform/environments/dev

terraform apply -target=module.networking
```

When prompted, review the plan. You should see output like this:

**Note I highly recommend using an LLM to double check all plan output! Terraform can be risky to use if it makes unneeded resources!**

```terraform
Terraform will perform the following actions:

  # module.networking.aws_internet_gateway.main will be created
  # module.networking.aws_route_table.main will be created
  # module.networking.aws_route_table_association.public[0] will be created
  # module.networking.aws_route_table_association.public[1] will be created
  # module.networking.aws_security_group.default will be created
  # module.networking.aws_subnet.public[0] will be created
  # module.networking.aws_subnet.public[1] will be created
  # module.networking.aws_vpc.main will be created


Plan: 8 to add, 0 to change, 0 to destroy.

─────────────────────────────────────────────────────────────────────────────

Note: You didn't use the -out option to save this plan, so Terraform can't
guarantee to take exactly these actions if you run "terraform apply" now.
```

**What to check:**
- **8 resources to add** (matches expected count)
- **All resources have correct tags**: `Project=enterprise-agentic-ai`, `Environment=dev`, `ManagedBy=terraform`
- **VPC CIDR**: `10.0.0.0/16` (standard private range)
- **No costs shown** (VPC resources are free)
- **No resources being destroyed** (fresh deployment)

Type `yes` only if the plan shows ~8 resources to create with the correct project tags.

**Verify Stage 1:**
```bash
aws ec2 describe-vpcs --region us-east-1 \
  --filters "Name=tag:Project,Values=enterprise-agentic-ai" \
  --query 'Vpcs[].VpcId'
```

**Stage 2: ECR (Near-free)**
```bash
terraform apply -target=module.ecr
```

When prompted, review the plan. You should see output like this:

**again review the output in a LLM to be safe**

```terraform
Terraform will perform the following actions:

  # module.ecr.aws_ecr_lifecycle_policy.main will be created
  # module.ecr.aws_ecr_repository.backend will be created

Plan: 2 to add, 0 to change, 0 to destroy.
```

**What to check:**
- **2 resources to add** (ECR repository + lifecycle policy)
- **Repository name**: `enterprise-agentic-ai/backend`
- **Correct tags**: `Project=enterprise-agentic-ai`, `Environment=dev`, `ManagedBy=terraform`
- **Scan on push enabled** for security
- **Lifecycle policy** keeps last 10 images to control costs

Type `yes` only if you see 2 resources with the correct repository name and tags.

**Verify Stage 2:**
```bash
aws ecr describe-repositories --region us-east-1 \
  --query 'repositories[?contains(repositoryName, `enterprise-agentic-ai`)].repositoryName'
```

**Stage 3: S3 + CloudFront**
```bash
terraform apply -target=module.s3_cloudfront
```

When prompted, review the plan. You should see output like this:

**again review the plan to ensure it is correct in an LLM**

```terraform
Terraform will perform the following actions:

  # module.s3_cloudfront.aws_cloudfront_distribution.main will be created
  # module.s3_cloudfront.aws_cloudfront_origin_access_control.main will be created
  # module.s3_cloudfront.aws_s3_bucket.frontend will be created
  # module.s3_cloudfront.aws_s3_bucket_policy.frontend will be created
  # module.s3_cloudfront.aws_s3_bucket_public_access_block.frontend will be created
 
Plan: 6 to add, 0 to change, 0 to destroy.
```

**What to check:**
- **6 resources to add** (S3 bucket, bucket policy, public access block, CloudFront distribution, OAC)
- **S3 bucket region**: `us-east-1`
- **CloudFront price class**: `PriceClass_100` (cheapest, US/Europe)
- **Security**: Public access blocked, CloudFront-only access via OAC
- **Correct tags** on all resources: `Project=enterprise-agentic-ai`, `Environment=dev`, `ManagedBy=terraform`

Type `yes` only if you see 6 resources with secure CloudFront+S3 configuration.

**Verify Stage 3:**
```bash
# Check S3 bucket
aws s3 ls | grep enterprise-agentic-ai

# Check CloudFront (may take a few minutes to deploy)
aws cloudfront list-distributions \
  --query 'DistributionList.Items[?contains(Origins.Items[0].DomainName, `enterprise-agentic-ai`)].DomainName'
```

**✅ CHECKPOINT: Terraform Stages 1-3 Complete**

You've created the AWS infrastructure that can exist without your application code:

| What You Created | Status |
|------------------|--------|
| VPC and networking (Stage 1) | ✅ Ready |
| ECR repository (Stage 2) | ✅ Created, empty - waiting for your Docker image |
| S3 bucket + CloudFront (Stage 3) | ✅ Created, empty - waiting for frontend files |

**Continue to Section 6 below.** The next sections will:
- Update your backend code for AWS (Section 6)
- Build a production Docker image (Section 7)
- Push that image to ECR (Section 8)
- Then Section 9 applies the final Terraform stage (App Runner) which needs that image

**The guide is linear** - just keep following the sections in order.

### 5.12 Verify Resource Count

After each stage, verify only expected resources were created:

**Command:**
```bash
# Count all Terraform-managed resources
terraform state list | wc -l

# List all resources (review for unexpected items)
terraform state list
```

**Expected counts after each stage:**

| After Terraform Stage | Expected Count | If Higher |
|-------------|----------------|-----------|
| Stage 1 (networking) | 8-10 | Review for duplicates |
| Stage 2 (+ecr) | 10-12 | Check for extra repos |
| Stage 3 (+s3_cloudfront) | 16-20 | Check for extra distributions |
| Stage 4 (+app_runner) - Section 9 | 20-26 | Check for extra services |

**Check for Runaway Resources (should all be empty for Phase 1a):**
```bash
# These should return empty results:
aws rds describe-db-instances --region us-east-1 --query 'DBInstances[].DBInstanceIdentifier'
aws ec2 describe-nat-gateways --region us-east-1 --query 'NatGateways[?State!=`deleted`].NatGatewayId'
aws ecs list-clusters --region us-east-1
```

If any return results, investigate immediately - you may have unexpected resources incurring costs.

### 5.13 Emergency Rollback

If something goes wrong during Terraform apply, here's how to recover:

**Scenario 1: Cancel Mid-Apply**
```bash
# Press Ctrl+C during apply
# Some resources may be partially created

# Check current state
terraform plan

# Either complete the apply or destroy
terraform apply   # Complete what was started
# OR
terraform destroy  # Remove everything
```

**Scenario 2: Destroy Specific Module**
```bash
# Remove only App Runner (keeps other resources)
terraform destroy -target=module.app_runner

# Remove only S3/CloudFront
terraform destroy -target=module.s3_cloudfront
```

**Scenario 3: Full Destroy (Nuclear Option)**
```bash
cd ~/Projects/aws-enterprise-agentic-ai/terraform/environments/dev

# Destroy ALL Terraform-managed resources
terraform destroy
```

Type `yes` to confirm. This removes everything Terraform created.

**After Destroy - Verify Cleanup:**
```bash
# Check no resources remain
aws ec2 describe-vpcs --region us-east-1 \
  --filters "Name=tag:Project,Values=enterprise-agentic-ai" \
  --query 'Vpcs[].VpcId'

# Check App Runner
aws apprunner list-services --region us-east-1

# Check ECR
aws ecr describe-repositories --region us-east-1 \
  --query 'repositories[?contains(repositoryName, `enterprise-agentic-ai`)].repositoryName'
```

**Note:** These resources are NOT managed by Terraform and must be deleted manually if needed:
- Terraform state S3 bucket (`enterprise-agentic-ai-tfstate-*`)
- Terraform lock DynamoDB table (`enterprise-agentic-ai-tflock`)
- Secrets Manager secrets (created manually in Section 4)
- CloudWatch log groups (created automatically by AWS)

### 5.14 Terraform Infrastructure Checklist

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
- [ ] Plan reviewed - no red flag resources
- [ ] Stage 1 applied - networking resources created
- [ ] Stage 2 applied - ECR repository created
- [ ] Stage 3 applied - S3 bucket and CloudFront distribution created
- [ ] Resource count matches expectations (16-20 after Stage 3)

---

## 6. Backend Updates for AWS

### What We're Doing
Updating the FastAPI backend to work in AWS: environment detection, CORS configuration for CloudFront, and CloudWatch logging.

### Why This Matters
- **Environment Detection:** App needs to know it's running in AWS to load secrets correctly
- **CORS:** Frontend on CloudFront needs to call App Runner API across origins
- **Logging:** CloudWatch integration for observability

### 6.1 Update Settings for AWS

**Agent Prompt:**
```
Review and update `backend/src/config/settings.py` for AWS environment

Changes:
1. Add Secrets Manager integration when ENVIRONMENT=aws
2. Load secrets from these secret names:
   - enterprise-agentic-ai/demo-password (key: "password")
   - enterprise-agentic-ai/auth-token-secret (key: "secret")
   - enterprise-agentic-ai/tavily-api-key (key: "api_key")
   - enterprise-agentic-ai/fmp-api-key (key: "api_key")
3. Cache secrets in memory (don't fetch on every request)
4. Fallback to env vars when ENVIRONMENT=local

Configuration:
- Use boto3 secretsmanager client
- Parse JSON response to extract the specific key
- Add ALLOWED_ORIGINS setting (comma-separated string, default "http://localhost:3000")
- Handle errors gracefully with logging

Reference:
- _security.mdc "Secrets Management"
- Existing settings.py patterns (Pydantic Settings)
- boto3 docs: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/secretsmanager.html

Verify: docker-compose exec backend python -c "from src.config.settings import Settings; s = Settings(); print(s.environment)"
```

### 6.2 Update CORS Configuration

**Agent Prompt:**
```
Review and update `backend/src/api/main.py` CORS configuration

Changes:
1. Read ALLOWED_ORIGINS from settings (comma-separated string)
2. Split into list for CORSMiddleware allow_origins parameter
3. Keep defaults working for local dev (http://localhost:3000)
4. Support CloudFront URLs (https://xxxxx.cloudfront.net)

Configuration:
- allow_methods: ["GET", "POST", "OPTIONS"]
- allow_headers: ["Content-Type", "Authorization", "Cookie"]
- allow_credentials: True (for cookies/auth)
- expose_headers: ["Content-Type"]

Reference:
- FastAPI CORS docs: https://fastapi.tiangolo.com/tutorial/cors/
- Existing main.py CORS setup
- App Runner passes ALLOWED_ORIGINS env var

Verify: docker-compose exec backend python -c "from src.api.main import app; print('CORS configured')"
```

### 6.3 Verify CloudWatch-Compatible Logging

**Agent Prompt:**
```
Review logging configuration in `backend/src/` for CloudWatch compatibility

Verify these are in place (add if missing):
1. structlog configured for JSON output (already done in Phase 0)
2. LOG_LEVEL env var respected (default: INFO for aws, DEBUG for local)
3. conversation_id included in log context
4. No sensitive data logged (passwords, API keys)

Configuration:
- JSON logs work best with CloudWatch Logs Insights
- LOG_LEVEL set via App Runner environment variable
- Existing structlog setup should already handle this

Reference:
- backend.mdc "Logging Configuration"
- CloudWatch Logs Insights query syntax

Verify: docker-compose logs backend 2>&1 | head -5  # Should see JSON formatted logs
```

**Note:** If Phase 0 logging is already JSON-formatted with structlog, this step may require no changes. Just verify.

### 6.4 Create Production Dockerfile

**Agent Prompt:**
```
Create `backend/Dockerfile` (production, not Dockerfile.dev)

Structure:
1. Multi-stage build (builder + production stages)
2. Base image: python:3.11-slim
3. Non-root user for security

Builder stage:
- Install build dependencies
- Copy and install requirements.txt
- Use pip wheel for faster installs

Production stage:
- Copy wheels from builder
- Copy only src/ directory (not tests, scripts)
- Create non-root user (appuser)
- Set WORKDIR /app

Environment variables:
- PYTHONUNBUFFERED=1
- PYTHONDONTWRITEBYTECODE=1

Startup command:
- CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
- NO --reload flag (production)
- Workers: 1 (App Runner scales instances, not workers)

Configuration:
- EXPOSE 8000
- HEALTHCHECK CMD curl -f http://localhost:8000/health || exit 1

Reference:
- Docker multi-stage build best practices
- backend.mdc "Docker Configuration"
- Existing Dockerfile.dev for reference

Verify: docker build -t test-prod -f backend/Dockerfile backend/ && docker run --rm test-prod python --version
```

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

### 6.6 Verify Code Quality

Before proceeding, run linting and type checking to catch any issues:

**Commands:**
```bash
cd ~/Projects/aws-enterprise-agentic-ai

# Start dev containers if not running
docker-compose up -d

# Run type checking
docker-compose exec backend mypy src/

# Run linter
docker-compose exec backend ruff check src/

# Run formatter check (should pass if code is formatted)
docker-compose exec backend ruff format --check src/

# Run tests
docker-compose exec backend pytest tests/ -v
```

**Expected Output:**
- `mypy`: "Success: no issues found" (or only expected warnings)
- `ruff check`: No errors (warnings are acceptable)
- `ruff format`: "X files would be left unchanged" (all files formatted)
- `pytest`: All tests pass

**If there are errors:**
```bash
# Auto-fix formatting
docker-compose exec backend ruff format src/

# Auto-fix some linting issues
docker-compose exec backend ruff check --fix src/

# For type errors, manually fix in the code
```

### 6.7 Backend Updates Checklist

- [ ] Settings.py updated for AWS Secrets Manager
- [ ] CORS configuration updated for CloudFront
- [ ] Logging compatible with CloudWatch
- [ ] Production Dockerfile created
- [ ] Production build tested locally
- [ ] Health endpoint works in production build
- [ ] Type checking passes (`mypy src/`)
- [ ] Linting passes (`ruff check src/`)
- [ ] Tests pass (`pytest tests/`)

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

## 9. App Runner Deployment (Terraform Stage 4)

### What We're Doing
Applying the final Terraform stage to create App Runner, which deploys your backend as a running service.

**Why is this a separate section?** App Runner needs to pull a Docker image from ECR. In Section 5, you created an empty ECR repository. In Section 8, you pushed your image to it. Now App Runner can be created because it has an image to pull.

### Why This Matters
- **Managed Compute:** App Runner handles scaling, load balancing, HTTPS
- **Cost Optimization:** Scales to zero when idle
- **Simplicity:** No Kubernetes or ECS complexity

### Prerequisites for This Section
Before proceeding, verify:
- [ ] Terraform Stages 1-3 applied (Section 5 complete)
- [ ] Backend code updated for AWS (Section 6 complete)
- [ ] Docker image pushed to ECR (Section 8 complete)

### 9.1 Apply Terraform Stage 4 (App Runner)

This completes the Terraform deployment. Stages 1-3 were applied in Section 5.

**Commands:**
```bash
cd ~/Projects/aws-enterprise-agentic-ai/terraform/environments/dev

# Preview what will be created
terraform plan

# Apply App Runner and any remaining resources
terraform apply
```

**⚠️ Review the plan carefully before typing `yes`:**
**Again sanity check plan with LLM in addition to manual check**
| Check | Expected | If Wrong |
|-------|----------|----------|
| Resources to add | 4-8 (App Runner service, IAM roles) | Too many = investigate |
| Resources to change | 0-2 (minor updates OK) | Many changes = review carefully |
| Resources to destroy | 0 | STOP if destroying resources |

**Expected new resources:**
- `aws_apprunner_service` (1)
- `aws_iam_role` (2 - ECR access role, instance role)
- `aws_iam_role_policy` or `aws_iam_role_policy_attachment` (2-4)

**🚨 If you see unexpected resources, do NOT apply.** Review your Terraform code.

**Expected Duration:** 3-5 minutes for App Runner to provision

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

### 9.5 Verify Final Resource Count

After App Runner deployment, verify total resource count:

```bash
cd ~/Projects/aws-enterprise-agentic-ai/terraform/environments/dev

# Count all resources
terraform state list | wc -l
# Expected: 20-26 resources

# List all resources for review
terraform state list
```

**Final expected resources:**

| Module | Resources |
|--------|-----------|
| networking | VPC, IGW, 2 subnets, route table, 2 associations, security group |
| ecr | Repository, lifecycle policy |
| secrets | IAM policy (data sources don't count) |
| s3_cloudfront | S3 bucket + settings, CloudFront, OAC, bucket policy |
| app_runner | Service, 2 IAM roles, role policies |
| random | Random string |

**Verify no unexpected expensive resources:**
```bash
# All should return empty:
aws rds describe-db-instances --region us-east-1 --query 'DBInstances[].DBInstanceIdentifier'
aws ec2 describe-nat-gateways --region us-east-1 --query 'NatGateways[?State!=`deleted`].NatGatewayId'
```

### 9.6 App Runner Deployment Checklist

- [ ] `terraform apply` completed successfully
- [ ] App Runner service running (green status in Console)
- [ ] Health endpoint responds (`curl ${APP_RUNNER_URL}/health`)
- [ ] No errors in application logs
- [ ] Resource count is 20-26 (no unexpected resources)
- [ ] No NAT Gateways or RDS instances created

---

## 10. Frontend Build and S3 Upload

### What We're Doing
Building the Next.js static export and uploading it to S3 for CloudFront distribution.

### Why This Matters
- **Static Export:** No server needed, just HTML/JS/CSS files
- **Cost Optimization:** S3 hosting is very cheap
- **Performance:** CloudFront edge caching globally

### 10.1 Update Frontend API Configuration

**Agent Prompt:**
```
Review and update `frontend/src/lib/api.ts` for production API URL

Changes:
1. Read API URL from NEXT_PUBLIC_API_URL environment variable
2. Default to "http://localhost:8000" when not set
3. Ensure all fetch/EventSource calls use this base URL
4. No changes to SSE/streaming logic needed

Configuration:
- NEXT_PUBLIC_ prefix required for client-side env vars in Next.js
- Build command will pass: NEXT_PUBLIC_API_URL=${APP_RUNNER_URL} npm run build
- Verify next.config.ts passes env vars through (should already work)

Reference:
- frontend.mdc "API Configuration"
- Next.js env vars: https://nextjs.org/docs/app/building-your-application/configuring/environment-variables
- Existing api.ts implementation

Verify: grep -r "NEXT_PUBLIC_API_URL" frontend/src/
```

**Note:** If Phase 0 already uses `NEXT_PUBLIC_API_URL`, this step may require no changes. Just verify.

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
- [ ] Phase 0 complete and verified (services start, health endpoint works)
- [ ] AWS CLI v2 configured (`aws sts get-caller-identity` works)
- [ ] Terraform 1.5.0+ installed (`terraform --version`)
- [ ] Bedrock model access approved (Nova Pro, Nova Lite, Claude)
- [ ] IAM permissions verified (S3, ECR, App Runner, etc.)

### AWS Setup (Section 2)
- [ ] Billing alert configured ($50/month threshold)
- [ ] Cost Explorer enabled
- [ ] Account ID noted for later use

### Terraform State (Section 3)
- [ ] S3 bucket created for state with versioning
- [ ] DynamoDB table created with `LockID` partition key
- [ ] Both resources in us-east-1 region

### Secrets Manager (Section 4)
- [ ] Demo password secret created
- [ ] Auth token secret created (64-char random)
- [ ] Tavily API key secret created
- [ ] FMP API key secret created
- [ ] All secrets verified via `aws secretsmanager list-secrets`

### Terraform Infrastructure (Section 5)
- [ ] All 5 modules created (networking, ecr, secrets, app-runner, s3-cloudfront)
- [ ] `terraform init` successful
- [ ] `terraform validate` passes
- [ ] Plan reviewed - no unexpected resources (no NAT Gateway, RDS)
- [ ] Stage 1 (networking) applied and verified
- [ ] Stage 2 (ECR) applied and verified
- [ ] Stage 3 (S3/CloudFront) applied and verified

### Backend Code (Section 6)
- [ ] Settings.py updated for AWS Secrets Manager
- [ ] CORS configured for CloudFront URLs
- [ ] Logging compatible with CloudWatch (JSON format)
- [ ] Production Dockerfile created (multi-stage, non-root user)
- [ ] Production build tested locally (port 8001)
- [ ] Code quality verified (mypy, ruff, pytest pass)

### Docker/ECR (Sections 7-8)
- [ ] Production image builds successfully
- [ ] Image tagged as `latest` and `v1.0.0`
- [ ] Docker authenticated to ECR
- [ ] Image pushed and visible in ECR

### App Runner (Section 9)
- [ ] Stage 4 (App Runner) applied
- [ ] Service shows "Running" in AWS Console
- [ ] Health endpoint responds (`curl ${APP_RUNNER_URL}/health`)
- [ ] No errors in application logs
- [ ] Total resource count is 20-26

### Frontend (Sections 10-11)
- [ ] Frontend built with `NEXT_PUBLIC_API_URL` set
- [ ] Files uploaded to S3 (`aws s3 sync`)
- [ ] CloudFront cache invalidated
- [ ] CloudFront URL accessible

### Cost Verification
- [ ] No NAT Gateways created
- [ ] No RDS instances created
- [ ] No unattached Elastic IPs
- [ ] Cost Explorer shows only expected services

### End-to-End Testing (Section 12)
- [ ] Login page loads via CloudFront
- [ ] No JavaScript errors in browser console
- [ ] Login with password succeeds
- [ ] Chat interface displays correctly
- [ ] Message sends and receives streaming response
- [ ] Tool usage works (search, market data)
- [ ] CloudWatch logs show requests
- [ ] Response time <2s after warmup

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

### Expected Costs (Phase 1a)

| Service | Idle Cost | Active Cost | Notes |
|---------|-----------|-------------|-------|
| VPC/Networking | $0 | $0 | No NAT Gateway in Phase 1a |
| App Runner | $0 | $5-15 | Scales to zero when idle |
| ECR | $0.01 | $0.01 | ~100MB image storage |
| S3 | $0.01 | $0.05 | Static files only |
| CloudFront | $0 | $1-5 | Request-based pricing |
| Secrets Manager | $1.60 | $1.60 | 4 secrets × $0.40/month |
| DynamoDB (TF state) | $0 | $0.50 | On-demand, minimal usage |
| CloudWatch Logs | $0 | $0.50-2 | Based on log volume |
| **Total Idle** | **~$2-3** | | Demo not in use |
| **Total Active** | | **~$10-25** | During active demo usage |

### 🚨 Cost Red Flags

If you see these charges, investigate immediately - you may have misconfigured resources:

| Unexpected Charge | Likely Cause | Monthly Cost |
|-------------------|--------------|--------------|
| NAT Gateway | Terraform created NAT Gateway (not needed) | ~$32 + data |
| RDS | Database instance running (Phase 1b only) | ~$15-50 |
| Elastic IP (unattached) | Orphaned EIP | $3.60 |
| App Runner running 24/7 | Not scaling to zero | ~$25-50 |
| Multiple CloudFront distributions | Duplicate deployments | Varies |
| Large S3 storage | Old/duplicate files | $0.023/GB |

### Check Your Costs Immediately After Deploy

**Within 24 hours of deployment:**

1. AWS Console → Billing → Cost Explorer
2. Filter by: 
   - Date: Today
   - Group by: Service
3. Verify only expected services appear
4. Set up daily cost alerts if not already done

**Quick cost check command:**
```bash
# Check for expensive resources that shouldn't exist
aws rds describe-db-instances --region us-east-1 --query 'DBInstances[].DBInstanceIdentifier'
aws ec2 describe-nat-gateways --region us-east-1 --query 'NatGateways[?State!=`deleted`].NatGatewayId'
aws ec2 describe-addresses --region us-east-1 --query 'Addresses[?AssociationId==null].PublicIp'
```

All three commands should return empty results (`[]`).

### Monitor Ongoing Costs

**Navigate in AWS Console:**
1. Billing → Cost Explorer
2. Filter by service to see breakdown
3. Set up cost allocation tags for this project

**Weekly cost review:**
- Check Cost Explorer weekly during active development
- Review any services with unexpected charges
- Verify App Runner is scaling to zero when not in use

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

## Files Created/Modified in Phase 1a

### New Files Created

| File | Purpose |
|------|---------|
| `terraform/environments/dev/backend.tf` | Terraform state backend configuration (S3 + DynamoDB) |
| `terraform/environments/dev/main.tf` | Main Terraform configuration with module calls |
| `terraform/environments/dev/variables.tf` | Input variables for dev environment |
| `terraform/environments/dev/outputs.tf` | Output values (URLs, IDs) |
| `terraform/environments/dev/terraform.tfvars` | Variable values (gitignored) |
| `terraform/modules/networking/main.tf` | VPC, subnets, IGW, route tables |
| `terraform/modules/networking/variables.tf` | Networking module variables |
| `terraform/modules/networking/outputs.tf` | VPC ID, subnet IDs |
| `terraform/modules/ecr/main.tf` | ECR repository and lifecycle policy |
| `terraform/modules/ecr/variables.tf` | ECR module variables |
| `terraform/modules/ecr/outputs.tf` | Repository URL, ARN |
| `terraform/modules/secrets/main.tf` | Secrets data sources and IAM policy |
| `terraform/modules/secrets/variables.tf` | Secrets module variables |
| `terraform/modules/secrets/outputs.tf` | Secret ARNs, policy ARN |
| `terraform/modules/app-runner/main.tf` | App Runner service, IAM roles |
| `terraform/modules/app-runner/variables.tf` | App Runner module variables |
| `terraform/modules/app-runner/outputs.tf` | Service URL, ARN |
| `terraform/modules/s3-cloudfront/main.tf` | S3 bucket, CloudFront distribution, OAC |
| `terraform/modules/s3-cloudfront/variables.tf` | S3/CloudFront module variables |
| `terraform/modules/s3-cloudfront/outputs.tf` | CloudFront URL, bucket name, distribution ID |
| `backend/Dockerfile` | Production Docker image (multi-stage build) |

### Files Modified

| File | Changes |
|------|---------|
| `backend/src/config/settings.py` | AWS Secrets Manager integration, ALLOWED_ORIGINS |
| `backend/src/api/main.py` | CORS configuration for CloudFront |
| `.gitignore` | Terraform patterns (*.tfstate, .terraform/, etc.) |

### Files NOT Created (Exist from Phase 0)

| File | Status |
|------|--------|
| `backend/Dockerfile.dev` | Development Dockerfile (Phase 0) |
| `backend/requirements.txt` | Python dependencies (Phase 0) |
| `frontend/package.json` | Node dependencies (Phase 0) |
| `docker-compose.yml` | Local development (Phase 0) |
| `.env.example` | Environment template (Phase 0) |

### AWS Resources Created (via Terraform)

| Resource Type | Count | Names/Details |
|---------------|-------|---------------|
| VPC | 1 | `enterprise-agentic-ai-dev-vpc` |
| Subnets | 2 | Public subnets in us-east-1a, us-east-1b |
| Internet Gateway | 1 | Attached to VPC |
| Route Table | 1 | Routes 0.0.0.0/0 to IGW |
| Security Group | 1 | Egress-only for future VPC connector |
| ECR Repository | 1 | `enterprise-agentic-ai-backend` |
| S3 Bucket | 1 | `enterprise-agentic-ai-frontend-<random>` |
| CloudFront Distribution | 1 | Serves S3 bucket |
| CloudFront OAC | 1 | Origin Access Control for S3 |
| App Runner Service | 1 | Backend API |
| IAM Roles | 2 | ECR access role, instance role |
| IAM Policies | 2-4 | Secrets access, Bedrock access, CloudWatch |

### AWS Resources Created Manually (Section 3-4)

| Resource | Name |
|----------|------|
| S3 Bucket (TF state) | `enterprise-agentic-ai-tfstate-<initials>` |
| DynamoDB Table | `enterprise-agentic-ai-tflock` |
| Secret | `enterprise-agentic-ai/demo-password` |
| Secret | `enterprise-agentic-ai/auth-token-secret` |
| Secret | `enterprise-agentic-ai/tavily-api-key` |
| Secret | `enterprise-agentic-ai/fmp-api-key` |

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
