# Security & Secrets Management

This document explains how secrets (API keys, passwords, credentials) are managed in this project to ensure security across local development, CI/CD, and production environments.

## Overview

**Core Principle:** Secrets should NEVER be committed to the repository.

| Environment | Secrets Storage | How It Works |
|-------------|-----------------|--------------|
| **Local Development** | `.env` file | Gitignored, created from `.env.example` |
| **CI/CD (GitHub Actions)** | GitHub Secrets | Configured in repository settings |
| **Production (AWS)** | AWS Secrets Manager | Loaded automatically by the application |

---

## Local Development Setup

### Step 1: Create Your .env File

```bash
# Copy the template
cp .env.example .env

# Edit with your actual values
# Use your preferred editor
```

### Step 2: Fill In Your API Keys

Open `.env` and replace the placeholder values with your actual keys:

| Variable | Where to Get It |
|----------|-----------------|
| `AWS_ACCESS_KEY_ID` | AWS Console → IAM → Users → Security credentials |
| `AWS_SECRET_ACCESS_KEY` | AWS Console → IAM → Users → Security credentials |
| `TAVILY_API_KEY` | https://tavily.com → Dashboard |
| `PINECONE_API_KEY` | https://pinecone.io → Dashboard |
| `OPENWEATHER_API_KEY` | https://openweathermap.org/api → Dashboard |

### Step 3: Verify .env is Gitignored

```bash
# This should output ".env"
git check-ignore .env

# If it doesn't, check your .gitignore file
```

**CRITICAL:** If `git check-ignore .env` doesn't output `.env`, your secrets could be committed!

---

## Production Deployment (AWS)

For production, secrets are stored in AWS Secrets Manager and loaded automatically.

### AWS Secrets Manager Setup

1. **Create Secret in AWS Console:**
   - Go to AWS Secrets Manager in us-east-1
   - Create a new secret
   - Store as key/value pairs

2. **Required Secrets:**
   ```
   DEMO_PASSWORD      → Password for demo access
   TAVILY_API_KEY     → Tavily search API key
   PINECONE_API_KEY   → Pinecone vector database key
   OPENWEATHER_API_KEY → OpenWeatherMap API key (optional)
   ```

3. **Backend Configuration:**
   - When `ENVIRONMENT=aws`, the application automatically loads from Secrets Manager
   - See `backend/src/config/settings.py` for implementation details

### Terraform Integration

Secrets are referenced by ARN in Terraform, never as plaintext:

```hcl
# Example: Reference secret in App Runner
resource "aws_apprunner_service" "backend" {
  # ...
  instance_configuration {
    environment_variables = {
      ENVIRONMENT = "aws"
      # Secrets loaded from Secrets Manager by the application
    }
  }
}
```

---

## CI/CD (GitHub Actions)

### Required GitHub Secrets

Configure these in your repository settings (Settings → Secrets → Actions):

| Secret Name | Description |
|-------------|-------------|
| `AWS_ACCESS_KEY_ID` | IAM user access key for deployment |
| `AWS_SECRET_ACCESS_KEY` | IAM user secret key for deployment |
| `AWS_REGION` | Should be `us-east-1` |

### Usage in Workflows

```yaml
# .github/workflows/deploy.yml
- name: Configure AWS credentials
  uses: aws-actions/configure-aws-credentials@v4
  with:
    aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
    aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
    aws-region: ${{ secrets.AWS_REGION }}
```

---

## Automated Secret Scanning

This project uses multiple layers of secret detection to prevent accidental commits:

### 1. Pre-commit Hooks (detect-secrets)

Runs automatically before each commit:

```bash
# Install pre-commit hooks
pip install pre-commit
pre-commit install

# Run manually
pre-commit run --all-files
```

### 2. Gitleaks

Additional scanning with custom rules for project-specific API keys:

```bash
# Install gitleaks
brew install gitleaks  # macOS
# or download from https://github.com/gitleaks/gitleaks/releases

# Run scan
gitleaks detect --source . -v
```

### 3. GitHub Secret Scanning

If enabled on your repository, GitHub will automatically scan for known secret patterns.

---

## What To Do If You Accidentally Commit a Secret

**Act immediately!** Even if you remove the secret in a subsequent commit, it remains in git history.

### Step 1: Revoke the Compromised Credential

- **AWS Keys:** Delete in IAM console immediately
- **Tavily/Pinecone/etc.:** Regenerate API key in respective dashboards

### Step 2: Remove from Git History

```bash
# Option 1: Use git-filter-repo (recommended)
pip install git-filter-repo
git filter-repo --invert-paths --path <file-with-secret>

# Option 2: Use BFG Repo-Cleaner
# https://rtyley.github.io/bfg-repo-cleaner/
```

### Step 3: Force Push

```bash
git push --force --all
git push --force --tags
```

### Step 4: Generate New Credentials

Create new API keys/credentials and update your `.env` file.

---

## Security Best Practices

### DO:
- ✅ Use `.env.example` as a template (safe to commit)
- ✅ Keep your `.env` file gitignored
- ✅ Use AWS Secrets Manager for production
- ✅ Use GitHub Secrets for CI/CD
- ✅ Run `pre-commit` hooks before committing
- ✅ Rotate credentials periodically
- ✅ Use least-privilege IAM permissions

### DON'T:
- ❌ Commit `.env` files with real values
- ❌ Put secrets in code, even temporarily
- ❌ Share secrets via chat/email (use a password manager)
- ❌ Use the same secrets across environments
- ❌ Ignore pre-commit hook failures

---

## Files Reference

| File | Purpose | Committed? |
|------|---------|------------|
| `.env.example` | Template showing required variables | ✅ Yes |
| `.env` | Your actual secrets | ❌ No (gitignored) |
| `.gitignore` | Ensures `.env` is not committed | ✅ Yes |
| `.pre-commit-config.yaml` | Secret scanning hooks | ✅ Yes |
| `.gitleaks.toml` | Gitleaks configuration | ✅ Yes |
| `.secrets.baseline` | detect-secrets baseline | ✅ Yes |

---

## Troubleshooting

### "detect-secrets found a secret"

If pre-commit fails with a secret detection:

1. **If it's a real secret:** Remove it immediately, revoke, and regenerate
2. **If it's a false positive:** Add to `.secrets.baseline`:
   ```bash
   detect-secrets scan --baseline .secrets.baseline
   ```

### ".env not found"

```bash
cp .env.example .env
# Then fill in your values
```

### "AccessDenied from AWS"

- Check your AWS credentials are correct in `.env`
- Verify IAM permissions include the required services
- Ensure you're using us-east-1 region

---

## Questions?

For security-related questions or to report a vulnerability, please open a GitHub issue or contact the repository owner directly.

