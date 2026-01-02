#------------------------------------------------------------------------------
# ECR Module - Outputs
#------------------------------------------------------------------------------

output "repository_url" {
  value       = aws_ecr_repository.main.repository_url
  description = "URL of the ECR repository (for docker push)"
}

output "repository_arn" {
  value       = aws_ecr_repository.main.arn
  description = "ARN of the ECR repository"
}

output "registry_id" {
  value       = aws_ecr_repository.main.registry_id
  description = "Registry ID where the repository was created"
}
