#------------------------------------------------------------------------------
# Secrets Module - Main Configuration
# References existing AWS Secrets Manager secrets and creates IAM policy
#------------------------------------------------------------------------------
# 
# This module does NOT create secrets - they are created manually or via CLI.
# It references existing secrets and provides IAM access policies.
#
# Expected secrets (create manually before running terraform):
# - enterprise-agentic-ai/demo-password
# - enterprise-agentic-ai/auth-token-secret
#
# Optional secrets (for Phase 2+ tools):
# - enterprise-agentic-ai/tavily-api-key
# - enterprise-agentic-ai/fmp-api-key
# - enterprise-agentic-ai/database-url
#------------------------------------------------------------------------------

locals {
  secret_prefix = var.project_name

  # List of secret names this application may need
  # These are referenced by ARN pattern, not data source (to avoid errors if they don't exist)
  secret_names = [
    "demo-password",
    "auth-token-secret",
    "tavily-api-key",
    "fmp-api-key",
    "database-url",
    "pinecone", # Phase 2b: RAG (keys: api_key, index_name)
    "neo4j",    # Phase 2b: Knowledge Graph (keys: uri, user, password)
  ]
}

#------------------------------------------------------------------------------
# Data Sources
#------------------------------------------------------------------------------

data "aws_region" "current" {}

data "aws_caller_identity" "current" {}

# Look up actual secret ARNs (includes random suffix added by AWS)
data "aws_secretsmanager_secret" "demo_password" {
  name = "${local.secret_prefix}/demo-password"
}

data "aws_secretsmanager_secret" "auth_token_secret" {
  name = "${local.secret_prefix}/auth-token-secret"
}

data "aws_secretsmanager_secret" "tavily_api_key" {
  name = "${local.secret_prefix}/tavily-api-key"
}

data "aws_secretsmanager_secret" "fmp_api_key" {
  name = "${local.secret_prefix}/fmp-api-key"
}

data "aws_secretsmanager_secret" "database_url" {
  name = "${local.secret_prefix}/database-url"
}

data "aws_secretsmanager_secret" "pinecone" {
  name = "${local.secret_prefix}/pinecone"
}

data "aws_secretsmanager_secret" "neo4j" {
  name = "${local.secret_prefix}/neo4j"
}

#------------------------------------------------------------------------------
# IAM Policy for Secrets Access
# Grants read access to all project secrets
#------------------------------------------------------------------------------

resource "aws_iam_policy" "secrets_access" {
  name        = "${var.project_name}-${var.environment}-secrets-access"
  description = "IAM policy for accessing ${var.project_name} secrets"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "SecretsManagerReadAccess"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret",
        ]
        Resource = [
          "arn:aws:secretsmanager:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:secret:${local.secret_prefix}/*"
        ]
      }
    ]
  })

  tags = var.tags
}
