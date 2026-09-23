variable "aws_region" {
  type        = string
  description = "AWS region for TAKELEY (Seoul)."
  default     = "ap-northeast-2"
}

variable "project" {
  type    = string
  default = "takeley"
}

variable "domain_name" {
  type        = string
  description = "Apex domain registered in Route 53 (e.g. takeley.app). Required."
}

variable "create_hosted_zone" {
  type        = bool
  description = "If true, create a new Route 53 public hosted zone. If false, look up an existing zone for domain_name."
  default     = false
}

variable "ssh_ingress_cidr" {
  type        = string
  description = "CIDR allowed to SSH into the app instance (your public IP /32)."
}

variable "db_username" {
  type    = string
  default = "takeley"
}

variable "db_name" {
  type    = string
  default = "takeley"
}

variable "db_instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "app_instance_type" {
  type        = string
  description = "EC2 instance type (ARM Graviton for cost)."
  default     = "t4g.small"
}

variable "app_volume_gb" {
  type    = number
  default = 30
}

variable "ssh_public_key" {
  type        = string
  description = "SSH public key material for the app instance."
}

variable "letsencrypt_email" {
  type        = string
  description = "Email for Let's Encrypt / Certbot notices."
}
