#------------------------------------------------------------------------------
# App Runner Module - Main
# Creates App Runner service with IAM roles for ECR and Bedrock access
#------------------------------------------------------------------------------

locals {
  common_tags = merge(var.tags, {
    Module = "app-runner"
  })
}

#------------------------------------------------------------------------------
# IAM Role for ECR Access (used during image pull)
#------------------------------------------------------------------------------

data "aws_iam_policy_document" "ecr_access_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["build.apprunner.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ecr_access" {
  name               = "${var.service_name}-ecr-access"
  assume_role_policy = data.aws_iam_policy_document.ecr_access_trust.json

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "ecr_access" {
  role       = aws_iam_role.ecr_access.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess"
}

#------------------------------------------------------------------------------
# IAM Role for Instance (used at runtime)
#------------------------------------------------------------------------------

data "aws_iam_policy_document" "instance_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["tasks.apprunner.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "instance" {
  name               = "${var.service_name}-instance"
  assume_role_policy = data.aws_iam_policy_document.instance_trust.json

  tags = local.common_tags
}

# Attach secrets access policy (passed from secrets module)
resource "aws_iam_role_policy_attachment" "secrets_access" {
  role       = aws_iam_role.instance.name
  policy_arn = var.secrets_policy_arn
}

# Inline policy for Bedrock access
data "aws_iam_policy_document" "bedrock_access" {
  statement {
    sid    = "AllowBedrockInvoke"
    effect = "Allow"

    actions = [
      "bedrock:InvokeModel",
      "bedrock:InvokeModelWithResponseStream"
    ]

    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "bedrock_access" {
  name   = "bedrock-access"
  role   = aws_iam_role.instance.id
  policy = data.aws_iam_policy_document.bedrock_access.json
}

# Inline policy for CloudWatch Logs
data "aws_iam_policy_document" "cloudwatch_logs" {
  statement {
    sid    = "AllowCloudWatchLogs"
    effect = "Allow"

    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]

    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "cloudwatch_logs" {
  name   = "cloudwatch-logs"
  role   = aws_iam_role.instance.id
  policy = data.aws_iam_policy_document.cloudwatch_logs.json
}

#------------------------------------------------------------------------------
# App Runner Service
#------------------------------------------------------------------------------

resource "aws_apprunner_service" "main" {
  service_name = var.service_name

  source_configuration {
    authentication_configuration {
      access_role_arn = aws_iam_role.ecr_access.arn
    }

    auto_deployments_enabled = false

    image_repository {
      image_identifier      = "${var.ecr_repository_url}:${var.image_tag}"
      image_repository_type = "ECR"

      image_configuration {
        port = "8000"

        # Runtime environment variables
        runtime_environment_variables = {
          ENVIRONMENT     = "aws"
          AWS_REGION      = "us-east-1"
          LOG_LEVEL       = "INFO"
          ALLOWED_ORIGINS = var.allowed_origins
        }

        # Runtime environment secrets (format: ARN:jsonKey::)
        runtime_environment_secrets = {
          DEMO_PASSWORD       = "${var.secret_arns["demo_password"]}:password::"
          AUTH_TOKEN_SECRET   = "${var.secret_arns["auth_token_secret"]}:secret::"
          TAVILY_API_KEY      = "${var.secret_arns["tavily_api_key"]}:api_key::"
          FMP_API_KEY         = "${var.secret_arns["fmp_api_key"]}:api_key::"
          DATABASE_URL        = "${var.secret_arns["database_url"]}:url::"
          # Phase 2b: RAG and Knowledge Graph secrets
          PINECONE_API_KEY    = "${var.secret_arns["pinecone"]}:api_key::"
          PINECONE_INDEX_NAME = "${var.secret_arns["pinecone"]}:index_name::"
          NEO4J_URI           = "${var.secret_arns["neo4j"]}:uri::"
          NEO4J_USER          = "${var.secret_arns["neo4j"]}:user::"
          NEO4J_PASSWORD      = "${var.secret_arns["neo4j"]}:password::"
        }
      }
    }
  }

  instance_configuration {
    cpu               = var.cpu
    memory            = var.memory
    instance_role_arn = aws_iam_role.instance.arn
  }

  health_check_configuration {
    protocol = "HTTP"
    path     = "/health"
    interval = 10
  }

  network_configuration {
    egress_configuration {
      egress_type = "DEFAULT"
    }
  }

  tags = merge(local.common_tags, {
    Name = var.service_name
  })

  # Wait for IAM roles to be fully propagated
  depends_on = [
    aws_iam_role_policy_attachment.ecr_access,
    aws_iam_role_policy_attachment.secrets_access,
    aws_iam_role_policy.bedrock_access,
    aws_iam_role_policy.cloudwatch_logs
  ]
}
