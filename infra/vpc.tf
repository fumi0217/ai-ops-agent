resource "aws_vpc" "my_vpc" {
  cidr_block           = "${local.private_ip}/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  instance_tenancy     = "default"
}

resource "aws_subnet" "public_subnet" {
  vpc_id                  = aws_vpc.my_vpc.id
  cidr_block              = "${local.private_ip}/20"
  availability_zone       = local.availability_zone
  map_public_ip_on_launch = true
}

resource "aws_internet_gateway" "my_gateway" {
  vpc_id = aws_vpc.my_vpc.id
}

resource "aws_route_table" "my_route_table" {
  vpc_id = aws_vpc.my_vpc.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.my_gateway.id
  }
}

resource "aws_route_table_association" "my_route_association" {
  subnet_id      = aws_subnet.public_subnet.id
  route_table_id = aws_route_table.my_route_table.id
}

resource "aws_security_group" "my_sec_group" {
  name                   = "ai-ops-agent security group"
  vpc_id                 = aws_vpc.my_vpc.id
  revoke_rules_on_delete = true

  lifecycle {
    create_before_destroy = true
  }
  timeouts {
    delete = "2m"
  }
}

resource "aws_vpc_security_group_egress_rule" "allow_all_traffic_ipv4" {
  security_group_id = aws_security_group.my_sec_group.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

resource "aws_vpc_security_group_ingress_rule" "allow_ssh" {
  security_group_id = aws_security_group.my_sec_group.id
  cidr_ipv4         = local.allowed_cidr
  ip_protocol       = "tcp"
  from_port         = 22
  to_port           = 22
}

resource "aws_vpc_security_group_ingress_rule" "allow_web_access" {
  security_group_id = aws_security_group.my_sec_group.id
  cidr_ipv4         = local.allowed_cidr
  ip_protocol       = "tcp"
  from_port         = 8000
  to_port           = 8000
}