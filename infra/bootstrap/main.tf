terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
  }

  # Deliberately local state. This root creates the S3 bucket that infra/'s
  # own state will live in, so it can't depend on that bucket itself. Apply
  # this once, manually, with your own AWS credentials — never from CI. See
  # README.md in this directory.
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      ManagedBy = "Terraform-bootstrap"
    }
  }
}

data "aws_caller_identity" "current" {}

locals {
  # coalesce() skips both null and "" — an unset (default "") state_bucket_name
  # falls through to the generated name below.
  state_bucket_name = coalesce(
    var.state_bucket_name,
    "ai-ops-agent-tfstate-${data.aws_caller_identity.current.account_id}",
  )
}
