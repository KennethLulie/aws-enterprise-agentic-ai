#------------------------------------------------------------------------------
# Secrets Module - Outputs
#------------------------------------------------------------------------------

output "secrets_access_policy_arn" {
  description = "ARN of the IAM policy for secrets access"
  value       = aws_iam_policy.secrets_access.arn
}

output "secret_arns" {
  description = "List of secret ARN patterns for this project"
  value = [
    "arn:aws:secretsmanager:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:secret:${var.project_name}/*"
  ]
}

output "secret_prefix" {
  description = "Prefix used for all project secrets"
  value       = var.project_name
}
