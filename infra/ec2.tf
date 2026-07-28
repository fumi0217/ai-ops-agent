resource "aws_key_pair" "my_key" {
  key_name   = local.key_name
  public_key = local.public_key_val
}

resource "aws_instance" "my_public_vm" {
  ami                         = local.ami
  associate_public_ip_address = true
  availability_zone           = local.availability_zone
  instance_type               = "t3.medium"
  key_name                    = local.key_name
  placement_group             = null
  subnet_id                   = aws_subnet.public_subnet.id
  vpc_security_group_ids = [
    aws_security_group.my_sec_group.id,
  ]
  user_data = <<-EOF
        #!/bin/bash
        sudo dnf update -y
        sudo dnf install -y docker
        sudo systemctl enable docker
        sudo systemctl start docker
        sudo usermod -aG docker ec2-user
        sudo dnf install -y git
        EOF
  root_block_device {
    volume_size           = 30
    volume_type           = "gp3"
    delete_on_termination = true
  }
  tags = {
    Name = "public vm"
  }
}
