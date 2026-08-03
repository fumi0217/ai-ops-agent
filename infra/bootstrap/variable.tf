variable "aws_region" {
  type    = string
  default = "ap-northeast-3"
}

variable "github_repository" {
  type        = string
  default     = "fumi0217/ai-ops-agent"
  description = "GitHub \"owner/repo\" this bootstrap grants OIDC trust to."
}

variable "state_bucket_name" {
  type        = string
  default     = ""
  description = "S3 bucket name for infra/'s remote state. Leave empty to auto-generate a globally-unique name from the AWS account id."
}
