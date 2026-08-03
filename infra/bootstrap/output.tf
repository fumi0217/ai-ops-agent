output "state_bucket_name" {
  value = aws_s3_bucket.tfstate.id
}

output "state_bucket_region" {
  value = var.aws_region
}

output "oidc_provider_arn" {
  value = aws_iam_openid_connect_provider.github_actions.arn
}

output "github_actions_role_arn" {
  value = aws_iam_role.github_actions.arn
}
