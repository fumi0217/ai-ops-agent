# Lets the EC2 instance itself query real AWS metrics about itself (see
# mcp_server/tools/aws_metrics.py) without static credentials. Read-only by
# design — no ec2:*Manage or mutating actions, since this role is reachable
# from inside the containers running on the instance.

data "aws_iam_policy_document" "ec2_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ec2_cloudwatch_read" {
  name               = "ai-ops-agent-ec2-cloudwatch-read"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
}

data "aws_iam_policy_document" "ec2_cloudwatch_read" {
  statement {
    sid       = "DescribeSelf"
    effect    = "Allow"
    actions   = ["ec2:DescribeInstances"]
    resources = ["*"] # EC2 Describe* calls don't support resource-level authorization.
  }

  statement {
    sid       = "CloudWatchRead"
    effect    = "Allow"
    actions   = ["cloudwatch:GetMetricStatistics"]
    resources = ["*"] # CloudWatch Get* calls don't support resource-level authorization.
  }
}

resource "aws_iam_role_policy" "ec2_cloudwatch_read" {
  name   = "cloudwatch-read"
  role   = aws_iam_role.ec2_cloudwatch_read.id
  policy = data.aws_iam_policy_document.ec2_cloudwatch_read.json
}

resource "aws_iam_instance_profile" "ec2_cloudwatch_read" {
  name = "ai-ops-agent-ec2-cloudwatch-read"
  role = aws_iam_role.ec2_cloudwatch_read.name
}
