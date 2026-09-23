output "app_public_ip" {
  value       = aws_eip.app.public_ip
  description = "Elastic IP for the app instance"
}

output "app_instance_id" {
  value = aws_instance.app.id
}

output "rds_endpoint" {
  value       = aws_db_instance.postgres.address
  description = "RDS hostname (no port)"
}

output "rds_port" {
  value = aws_db_instance.postgres.port
}

output "database_url" {
  sensitive   = true
  description = "SQLAlchemy URL for backend .env"
  value = format(
    "postgresql+psycopg://%s:%s@%s:%s/%s",
    var.db_username,
    random_password.db.result,
    aws_db_instance.postgres.address,
    aws_db_instance.postgres.port,
    var.db_name,
  )
}

output "api_host" {
  value = "api.${var.domain_name}"
}

output "admin_host" {
  value = "admin.${var.domain_name}"
}

output "route53_zone_id" {
  value = local.zone_id
}

output "route53_name_servers" {
  value = var.create_hosted_zone ? aws_route53_zone.new[0].name_servers : data.aws_route53_zone.existing[0].name_servers
}

output "ssh_hint" {
  value = "ssh -i <private_key> ubuntu@${aws_eip.app.public_ip}"
}
