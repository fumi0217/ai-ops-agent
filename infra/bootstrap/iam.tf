# GitHub Actions OIDC federation — CI assumes this role via short-lived
# tokens, no long-lived AWS access keys stored anywhere. See
# docs/adr/0011-github-actions-oidc-cicd.md.

data "tls_certificate" "github_actions" {
  url = "https://token.actions.githubusercontent.com/.well-known/openid-configuration"
}

resource "aws_iam_openid_connect_provider" "github_actions" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.github_actions.certificates[0].sha1_fingerprint]
}

# One shared role for both workflows (terraform.yml and docker-build.yml).
# Splitting into two roles would double the trust-policy/IAM-policy upkeep
# for a single-repo, single-environment project with no isolation upside —
# the policy below (not the trust) is what actually enforces least privilege.
data "aws_iam_policy_document" "github_actions_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github_actions.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    # Scoped to exactly this repo's main-branch and pull_request contexts.
    # The `sub` claim for a run tied to a ref (push, workflow_dispatch, ...)
    # is the same `ref:refs/heads/main` regardless of which event triggered
    # it, so this covers both terraform.yml's push-triggered apply and
    # docker-build.yml's workflow_dispatch-triggered ECR push. pull_request
    # is needed because terraform.yml's PR job runs a real `terraform plan`
    # against AWS to diff; docker-build.yml's PR job never assumes this role
    # at all (build-only, see .github/workflows/docker-build.yml).
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values = [
        "repo:${var.github_repository}:ref:refs/heads/main",
        "repo:${var.github_repository}:pull_request",
      ]
    }
  }
}

resource "aws_iam_role" "github_actions" {
  name               = "ai-ops-agent-github-actions"
  assume_role_policy = data.aws_iam_policy_document.github_actions_trust.json
}

data "aws_iam_policy_document" "github_actions_permissions" {
  statement {
    sid       = "Ec2Describe"
    effect    = "Allow"
    actions   = ["ec2:Describe*"]
    resources = ["*"] # AWS doesn't support resource-level auth for EC2 Describe* calls.
  }

  statement {
    sid    = "Ec2Manage"
    effect = "Allow"
    actions = [
      "ec2:CreateVpc", "ec2:DeleteVpc", "ec2:ModifyVpcAttribute",
      "ec2:CreateSubnet", "ec2:DeleteSubnet", "ec2:ModifySubnetAttribute",
      "ec2:CreateInternetGateway", "ec2:DeleteInternetGateway",
      "ec2:AttachInternetGateway", "ec2:DetachInternetGateway",
      "ec2:CreateRouteTable", "ec2:DeleteRouteTable",
      "ec2:CreateRoute", "ec2:DeleteRoute", "ec2:ReplaceRoute",
      "ec2:AssociateRouteTable", "ec2:DisassociateRouteTable", "ec2:ReplaceRouteTableAssociation",
      "ec2:CreateSecurityGroup", "ec2:DeleteSecurityGroup",
      "ec2:AuthorizeSecurityGroupIngress", "ec2:AuthorizeSecurityGroupEgress",
      "ec2:RevokeSecurityGroupIngress", "ec2:RevokeSecurityGroupEgress",
      "ec2:ModifySecurityGroupRules",
      "ec2:CreateTags", "ec2:DeleteTags",
      "ec2:ImportKeyPair", "ec2:DeleteKeyPair",
      "ec2:RunInstances", "ec2:TerminateInstances",
      "ec2:StopInstances", "ec2:StartInstances", "ec2:ModifyInstanceAttribute",
      "ec2:CreateVolume", "ec2:DeleteVolume", "ec2:AttachVolume", "ec2:DetachVolume", "ec2:ModifyVolume",
    ]
    resources = ["*"] # Terraform manages a whole VPC's worth of resources created together; scoping further isn't practical for most of these actions.
  }

  statement {
    sid       = "EcrAuth"
    effect    = "Allow"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"] # ECR API hard requirement — this action has no resource-level permissions.
  }

  statement {
    sid    = "EcrManageAndPushPull"
    effect = "Allow"
    actions = [
      "ecr:CreateRepository", "ecr:DeleteRepository", "ecr:DescribeRepositories",
      "ecr:DescribeImages", "ecr:ListImages",
      "ecr:PutLifecyclePolicy", "ecr:GetLifecyclePolicy", "ecr:DeleteLifecyclePolicy",
      "ecr:TagResource", "ecr:UntagResource", "ecr:ListTagsForResource",
      "ecr:BatchCheckLayerAvailability", "ecr:GetDownloadUrlForLayer", "ecr:BatchGetImage",
      "ecr:InitiateLayerUpload", "ecr:UploadLayerPart", "ecr:CompleteLayerUpload", "ecr:PutImage",
    ]
    resources = [
      for name in ["light", "rag", "frontend"] :
      "arn:aws:ecr:${var.aws_region}:${data.aws_caller_identity.current.account_id}:repository/ai-ops-agent-${name}"
    ]
  }

  statement {
    sid       = "S3StateList"
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.tfstate.arn]
  }

  statement {
    sid    = "S3StateObjects"
    effect = "Allow"
    actions = [
      "s3:GetObject", "s3:PutObject", "s3:DeleteObject",
    ]
    resources = [
      "${aws_s3_bucket.tfstate.arn}/infra/terraform.tfstate",
      "${aws_s3_bucket.tfstate.arn}/infra/terraform.tfstate.tflock",
    ]
  }

  # infra/'s only IAM resource: the EC2 instance's CloudWatch-read role +
  # instance profile (see infra/iam.tf). Scoped to those two resource names
  # specifically, not iam:* — this role must not be able to manage arbitrary
  # IAM resources, including its own.
  statement {
    sid    = "Ec2CloudwatchReadRoleManage"
    effect = "Allow"
    actions = [
      "iam:CreateRole", "iam:DeleteRole", "iam:GetRole", "iam:UpdateAssumeRolePolicy",
      "iam:TagRole", "iam:UntagRole",
      "iam:PutRolePolicy", "iam:DeleteRolePolicy", "iam:GetRolePolicy",
    ]
    resources = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/ai-ops-agent-ec2-cloudwatch-read"]
  }

  statement {
    sid    = "Ec2CloudwatchReadInstanceProfileManage"
    effect = "Allow"
    actions = [
      "iam:CreateInstanceProfile", "iam:DeleteInstanceProfile", "iam:GetInstanceProfile",
      "iam:AddRoleToInstanceProfile", "iam:RemoveRoleFromInstanceProfile",
      "iam:TagInstanceProfile", "iam:UntagInstanceProfile",
    ]
    resources = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:instance-profile/ai-ops-agent-ec2-cloudwatch-read"]
  }

  statement {
    sid       = "PassEc2CloudwatchReadRoleToEc2"
    effect    = "Allow"
    actions   = ["iam:PassRole"]
    resources = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/ai-ops-agent-ec2-cloudwatch-read"]

    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_policy" "github_actions" {
  name   = "ai-ops-agent-github-actions"
  policy = data.aws_iam_policy_document.github_actions_permissions.json
}

resource "aws_iam_role_policy_attachment" "github_actions" {
  role       = aws_iam_role.github_actions.name
  policy_arn = aws_iam_policy.github_actions.arn
}
