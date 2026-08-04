resource "aws_key_pair" "this" {
  key_name   = local.key_name
  public_key = local.public_key_val
}

resource "aws_instance" "this" {
  ami                         = local.ami
  associate_public_ip_address = true
  availability_zone           = local.availability_zone
  iam_instance_profile        = aws_iam_instance_profile.ec2_cloudwatch_read.name
  instance_type               = "t3.medium"
  key_name                    = local.key_name
  placement_group             = null
  subnet_id                   = aws_subnet.public_subnet.id
  vpc_security_group_ids = [
    aws_security_group.this.id,
  ]
  user_data = <<-EOF
        #!/bin/bash
        sudo dnf update -y
        sudo dnf install -y docker
        sudo systemctl enable docker
        sudo systemctl start docker
        sudo usermod -aG docker ec2-user
        sudo dnf install -y git
        sudo mkdir -p /usr/local/lib/docker/cli-plugins
        sudo curl -SL https://github.com/docker/compose/releases/download/v2.29.7/docker-compose-linux-x86_64 -o /usr/local/lib/docker/cli-plugins/docker-compose
        sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
        EOF
  root_block_device {
    volume_size           = 30
    volume_type           = "gp3"
    delete_on_termination = true
  }
  tags = {
    Name = "ai-ops-agent-server"
  }
}
