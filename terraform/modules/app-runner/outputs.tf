#------------------------------------------------------------------------------
# App Runner Module - Outputs
#------------------------------------------------------------------------------

output "service_url" {
  value       = "https://${aws_apprunner_service.main.service_url}"
  description = "HTTPS URL of the App Runner service"
}

output "service_arn" {
  value       = aws_apprunner_service.main.arn
  description = "ARN of the App Runner service"
}

output "service_id" {
  value       = aws_apprunner_service.main.service_id
  description = "ID of the App Runner service"
}
