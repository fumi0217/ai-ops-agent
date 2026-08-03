# One repository per actually-built Docker image (3), not per docker-compose
# service (4) — mock_services and chat_api share Dockerfile.light's image
# (see docker-compose.yml / docs/adr/0001), so a 4th repo would just
# duplicate identical content under a different name.

locals {
  ecr_repository_names = {
    light    = "ai-ops-agent-light"
    rag      = "ai-ops-agent-rag"
    frontend = "ai-ops-agent-frontend"
  }
}

resource "aws_ecr_repository" "this" {
  for_each = local.ecr_repository_names

  name                 = each.value
  image_tag_mutability = "MUTABLE" # docker-build.yml re-pushes a `latest` tag on every build to main.

  image_scanning_configuration {
    scan_on_push = true
  }

  force_delete = true # lets `terraform destroy` remove a repo even with images inside.
}

resource "aws_ecr_lifecycle_policy" "this" {
  for_each = aws_ecr_repository.this

  repository = each.value.name
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
        action = { type = "expire" }
      },
      {
        rulePriority = 2
        description  = "Keep only the last 10 tagged images"
        selection = {
          tagStatus      = "tagged"
          tagPatternList = ["*"]
          countType      = "imageCountMoreThan"
          countNumber    = 10
        }
        action = { type = "expire" }
      },
    ]
  })
}
