#------------------------------------------------------------------------------
# Dev Environment - Main Configuration
# Wires together all modules for the development environment
#------------------------------------------------------------------------------

locals {
  project_name = "enterprise-agentic-ai"
  environment  = "dev"

  common_tags = {
    Project     = local.project_name
    Environment = local.environment
    ManagedBy   = "terraform"
  }
}

#------------------------------------------------------------------------------
# Data Sources
#------------------------------------------------------------------------------

data "aws_region" "current" {}

data "aws_caller_identity" "current" {}

#------------------------------------------------------------------------------
# Random String for Unique S3 Bucket Name
#------------------------------------------------------------------------------

resource "random_string" "bucket_suffix" {
  length  = 8
  special = false
  upper   = false
}

#------------------------------------------------------------------------------
# Networking Module
# Creates VPC, subnets, internet gateway, and security group
#------------------------------------------------------------------------------

module "networking" {
  source = "../../modules/networking"

  project_name = local.project_name
  environment  = local.environment
  tags         = local.common_tags
}

#------------------------------------------------------------------------------
# ECR Module
# Creates container registry for backend Docker images
#------------------------------------------------------------------------------

module "ecr" {
  source = "../../modules/ecr"

  repository_name = "${local.project_name}-backend"
  tags            = local.common_tags
}

#------------------------------------------------------------------------------
# Secrets Module
# References existing secrets and creates IAM policy for access
#------------------------------------------------------------------------------

module "secrets" {
  source = "../../modules/secrets"

  project_name = local.project_name
  environment  = local.environment
  tags         = local.common_tags
}

#------------------------------------------------------------------------------
# S3-CloudFront Module
# Creates frontend hosting with CDN
#------------------------------------------------------------------------------

module "s3_cloudfront" {
  source = "../../modules/s3-cloudfront"

  bucket_name  = "${local.project_name}-frontend-${random_string.bucket_suffix.result}"
  project_name = local.project_name
  environment  = local.environment
  tags         = local.common_tags
}

#------------------------------------------------------------------------------
# App Runner Module
# Creates backend service with Bedrock and Secrets Manager access
#------------------------------------------------------------------------------

module "app_runner" {
  source = "../../modules/app-runner"

  service_name       = "${local.project_name}-${local.environment}-backend"
  ecr_repository_url = module.ecr.repository_url
  image_tag          = "latest"
  secrets_policy_arn = module.secrets.secrets_access_policy_arn
  secret_arns        = module.secrets.secret_arns
  allowed_origins    = "https://${module.s3_cloudfront.cloudfront_domain_name},http://localhost:3000"
  tags               = local.common_tags

  depends_on = [
    module.ecr,
    module.secrets,
    module.s3_cloudfront
  ]
}
