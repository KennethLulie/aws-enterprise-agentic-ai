#------------------------------------------------------------------------------
# Secrets Module - Outputs
#------------------------------------------------------------------------------

output "secrets_access_policy_arn" {
  description = "ARN of the IAM policy for secrets access"
  value       = aws_iam_policy.secrets_access.arn
}

output "secret_arns" {
  description = "Map of secret names to their actual ARNs (with AWS-generated suffix) for App Runner"
  value = {
    demo_password     = data.aws_secretsmanager_secret.demo_password.arn
    auth_token_secret = data.aws_secretsmanager_secret.auth_token_secret.arn
    tavily_api_key    = data.aws_secretsmanager_secret.tavily_api_key.arn
    fmp_api_key       = data.aws_secretsmanager_secret.fmp_api_key.arn
    database_url      = data.aws_secretsmanager_secret.database_url.arn
    pinecone          = data.aws_secretsmanager_secret.pinecone.arn
    neo4j             = data.aws_secretsmanager_secret.neo4j.arn
  }
}

output "secret_prefix" {
  description = "Prefix used for all project secrets"
  value       = var.project_name
}
