#------------------------------------------------------------------------------
# ECR Module - Variables
#------------------------------------------------------------------------------

variable "repository_name" {
  type        = string
  description = "Name of the ECR repository"
}

variable "tags" {
  type        = map(string)
  default     = {}
  description = "Additional tags to apply to all resources"
}
