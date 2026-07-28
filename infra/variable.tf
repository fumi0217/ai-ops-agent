variable "region" {
  type = string
  default = "ap-northeast-3"
}

variable "my_ip" {
  type = string
}

variable "private_ip" {
  type = string
  default = "192.168.0.0"
}

variable "public_key_val" {
  type = string
}

variable "ami" {
  type = string
  default = ""
}