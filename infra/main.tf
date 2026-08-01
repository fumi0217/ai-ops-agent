terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # See infra/bootstrap/README.md — bucket/region below come from that
  # root's `terraform output` (backend blocks can't reference variables, so
  # these are literals copied in by hand after the one-time bootstrap apply).
  backend "s3" {
    bucket       = "REPLACE_WITH_BOOTSTRAP_OUTPUT_state_bucket_name"
    key          = "infra/terraform.tfstate"
    region       = "ap-northeast-3"
    encrypt      = true
    use_lockfile = true
  }
}

data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }
}

locals {
  key_name          = "ai-ops-agent-key"
  public_key_val    = var.public_key_val
  ami               = length(var.ami) > 0 ? var.ami : data.aws_ami.al2023.id
  region            = var.region
  availability_zone = "${var.region}a"
  vpc_cidr_base     = var.vpc_cidr_base
  allowed_cidr      = "${var.my_ip}/32"
}



provider "aws" {
  region = local.region

  default_tags {
    tags = {
      ManagedBy = "Terraform-ai-ops-agent"
    }
  }
}