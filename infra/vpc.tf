resource "aws_vpc" "this" {
  cidr_block           = "${local.vpc_cidr_base}/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  instance_tenancy     = "default"
}

resource "aws_subnet" "public_subnet" {
  vpc_id                  = aws_vpc.this.id
  cidr_block              = "${local.vpc_cidr_base}/20"
  availability_zone       = local.availability_zone
  map_public_ip_on_launch = true
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this.id
  }
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public_subnet.id
  route_table_id = aws_route_table.public.id
}

resource "aws_security_group" "this" {
  name                   = "ai-ops-agent security group"
  vpc_id                 = aws_vpc.this.id
  revoke_rules_on_delete = true

  lifecycle {
    create_before_destroy = true
  }
  timeouts {
    delete = "2m"
  }
}

resource "aws_vpc_security_group_egress_rule" "allow_all_traffic_ipv4" {
  security_group_id = aws_security_group.this.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

resource "aws_vpc_security_group_ingress_rule" "allow_ssh" {
  security_group_id = aws_security_group.this.id
  cidr_ipv4         = local.allowed_cidr
  ip_protocol       = "tcp"
  from_port         = 22
  to_port           = 22
}

resource "aws_vpc_security_group_ingress_rule" "allow_web_access" {
  security_group_id = aws_security_group.this.id
  cidr_ipv4         = local.allowed_cidr
  ip_protocol       = "tcp"
  from_port         = 8000
  to_port           = 8000
}
