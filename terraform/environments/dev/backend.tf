# Terraform Backend Configuration
# Manages state storage in S3 with native S3 locking

terraform {
  required_version = ">= 1.10.0"

  # Provider requirements
  # See DEVELOPMENT_REFERENCE.md for version specifications
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }

  # S3 backend for remote state storage
  # Prerequisites (created manually):
  # - S3 bucket: enterprise-agentic-ai-tfstate-kl (with versioning enabled)
  # Note: use_lockfile uses S3's native conditional writes for locking (no DynamoDB needed)
  backend "s3" {
    bucket       = "enterprise-agentic-ai-tfstate-kl"
    key          = "dev/terraform.tfstate"
    region       = "us-east-1"
    use_lockfile = true
    encrypt      = true
  }
}

# AWS Provider Configuration
provider "aws" {
  region = "us-east-1"

  # Default tags applied to all resources
  # See infrastructure.mdc for tagging requirements
  default_tags {
    tags = {
      Project     = "enterprise-agentic-ai"
      Environment = "dev"
      ManagedBy   = "terraform"
    }
  }
}
