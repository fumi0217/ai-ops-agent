output "ec2_info" {
  value = <<-EOF
I am using:
  name: ${aws_instance.my_public_vm.tags["Name"]}
  ami: ${aws_instance.my_public_vm.ami}
  public ip: ${aws_instance.my_public_vm.public_ip}
EOF
}