#------------------------------------------------------------------------------
# ECR Module - Main
# Creates ECR repository with lifecycle policy for cost optimization
#------------------------------------------------------------------------------

locals {
  common_tags = merge(var.tags, {
    Module = "ecr"
  })
}

#------------------------------------------------------------------------------
# ECR Repository
#------------------------------------------------------------------------------

resource "aws_ecr_repository" "main" {
  name                 = var.repository_name
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = merge(local.common_tags, {
    Name = var.repository_name
  })
}

#------------------------------------------------------------------------------
# Lifecycle Policy
# - Expire untagged images after 1 day
# - Keep only last 10 tagged images
#------------------------------------------------------------------------------

resource "aws_ecr_lifecycle_policy" "main" {
  repository = aws_ecr_repository.main.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Expire untagged images after 1 day"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 1
        }
        action = {
          type = "expire"
        }
      },
      {
        rulePriority = 2
        description  = "Keep only last 10 tagged images"
        selection = {
          tagStatus     = "tagged"
          tagPrefixList = ["v", "latest"]
          countType     = "imageCountMoreThan"
          countNumber   = 10
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}
