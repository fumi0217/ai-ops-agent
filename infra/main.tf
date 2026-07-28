terraform {
    required_version = ">= 0.12"

    required_providers {
        aws = {
            source = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # 最終的にはバックエンドでs3とかgcsにstateは置く
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
  key_name = "terraform-key"
  public_key_val = var.public_key_val
  ami = length(var.ami) > 0 ? var.ami : data.aws_ami.al2023.id
  region = var.region
  availability_zone = "${var.region}a"
  private_ip = var.private_ip
  allowed_cidr = "${var.my_ip}/32"
}



provider "aws" {
  region = local.region

  default_tags {
    tags = {
      ManagedBy = "Terraform"
    }
  }
}