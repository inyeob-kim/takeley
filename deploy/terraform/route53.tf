resource "aws_route53_zone" "new" {
  count = var.create_hosted_zone ? 1 : 0
  name  = var.domain_name

  tags = {
    Name    = var.domain_name
    Project = var.project
  }
}

data "aws_route53_zone" "existing" {
  count        = var.create_hosted_zone ? 0 : 1
  name         = var.domain_name
  private_zone = false
}

locals {
  zone_id = var.create_hosted_zone ? aws_route53_zone.new[0].zone_id : data.aws_route53_zone.existing[0].zone_id
}

resource "aws_route53_record" "api" {
  zone_id = local.zone_id
  name    = "api.${var.domain_name}"
  type    = "A"
  ttl     = 60
  records = [aws_eip.app.public_ip]
}

resource "aws_route53_record" "admin" {
  zone_id = local.zone_id
  name    = "admin.${var.domain_name}"
  type    = "A"
  ttl     = 60
  records = [aws_eip.app.public_ip]
}
