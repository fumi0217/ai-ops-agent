# S3 bucket for infra/'s remote Terraform state. Locking uses Terraform's
# native S3 lockfile (use_lockfile in infra/main.tf's backend block) — no
# DynamoDB table. This is a single-operator project with no concurrent-apply
# need, so a lock table would just be another resource and another IAM
# surface for no real benefit.

resource "aws_s3_bucket" "tfstate" {
  bucket = local.state_bucket_name

  # Guards against `terraform destroy` on this bootstrap root accidentally
  # deleting the bucket that infra/'s state lives in.
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}
