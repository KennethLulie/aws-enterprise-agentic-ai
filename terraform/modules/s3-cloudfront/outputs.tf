#------------------------------------------------------------------------------
# S3-CloudFront Module - Outputs
#------------------------------------------------------------------------------

output "bucket_name" {
  value       = aws_s3_bucket.frontend.id
  description = "Name of the S3 bucket"
}

output "bucket_arn" {
  value       = aws_s3_bucket.frontend.arn
  description = "ARN of the S3 bucket"
}

output "cloudfront_distribution_id" {
  value       = aws_cloudfront_distribution.frontend.id
  description = "ID of the CloudFront distribution (for cache invalidation)"
}

output "cloudfront_domain_name" {
  value       = aws_cloudfront_distribution.frontend.domain_name
  description = "Domain name of the CloudFront distribution (e.g., d1234.cloudfront.net)"
}

output "cloudfront_url" {
  value       = "https://${aws_cloudfront_distribution.frontend.domain_name}"
  description = "Full HTTPS URL of the CloudFront distribution"
}
