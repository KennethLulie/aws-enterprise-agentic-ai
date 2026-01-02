#------------------------------------------------------------------------------
# Dev Environment - Outputs
#------------------------------------------------------------------------------

output "app_runner_url" {
  value       = module.app_runner.service_url
  description = "URL of the App Runner backend service"
}

output "cloudfront_url" {
  value       = module.s3_cloudfront.cloudfront_url
  description = "URL of the CloudFront frontend distribution"
}

output "cloudfront_distribution_id" {
  value       = module.s3_cloudfront.cloudfront_distribution_id
  description = "CloudFront distribution ID (for cache invalidation)"
}

output "ecr_repository_url" {
  value       = module.ecr.repository_url
  description = "ECR repository URL (for docker push)"
}

output "s3_bucket_name" {
  value       = module.s3_cloudfront.bucket_name
  description = "S3 bucket name for frontend files"
}
