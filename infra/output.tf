output "ec2_info" {
  value = <<-EOF
EC2 instance:
  name: ${aws_instance.this.tags["Name"]}
  ami: ${aws_instance.this.ami}
  public ip: ${aws_instance.this.public_ip}
EOF
}

output "ecr_repository_urls" {
  description = "For human reference only (e.g. `terraform output`) — docker-build.yml derives repository names independently, it doesn't read this."
  value       = { for k, v in aws_ecr_repository.this : k => v.repository_url }
}