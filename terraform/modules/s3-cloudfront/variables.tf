#------------------------------------------------------------------------------
# S3-CloudFront Module - Variables
#------------------------------------------------------------------------------

variable "bucket_name" {
  type        = string
  description = "Name of the S3 bucket for frontend hosting"
}

variable "project_name" {
  type        = string
  description = "Project name for resource naming"
}

variable "environment" {
  type        = string
  default     = "dev"
  description = "Environment name (dev, staging, prod)"
}

variable "tags" {
  type        = map(string)
  default     = {}
  description = "Additional tags to apply to all resources"
}
