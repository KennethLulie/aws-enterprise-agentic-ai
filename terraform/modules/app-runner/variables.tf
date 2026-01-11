#------------------------------------------------------------------------------
# App Runner Module - Variables
#------------------------------------------------------------------------------

variable "service_name" {
  type        = string
  description = "Name of the App Runner service"
}

variable "ecr_repository_url" {
  type        = string
  description = "URL of the ECR repository containing the Docker image"
}

variable "image_tag" {
  type        = string
  default     = "latest"
  description = "Docker image tag to deploy"
}

variable "secrets_policy_arn" {
  type        = string
  description = "ARN of the IAM policy granting access to Secrets Manager"
}

variable "secret_arns" {
  type        = map(string)
  description = "Map of secret names to their ARNs (demo_password, auth_token_secret, tavily_api_key, fmp_api_key, database_url)"
}

variable "allowed_origins" {
  type        = string
  description = "Comma-separated list of allowed CORS origins"
}

variable "cpu" {
  type        = string
  default     = "1024"
  description = "CPU units for the App Runner service (1024 = 1 vCPU)"
}

variable "memory" {
  type        = string
  default     = "2048"
  description = "Memory in MB for the App Runner service (2048 = 2 GB)"
}

variable "tags" {
  type        = map(string)
  default     = {}
  description = "Additional tags to apply to all resources"
}
