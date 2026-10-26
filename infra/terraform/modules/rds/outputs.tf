output "address" {
  description = "RDS host name."
  value       = aws_db_instance.this.address
}

output "port" {
  description = "RDS port."
  value       = aws_db_instance.this.port
}

output "security_group_id" {
  description = "Security group of the RDS instance."
  value       = aws_security_group.this.id
}

output "master_user_secret_arn" {
  description = "Secrets Manager secret (managed by RDS) holding the master credentials."
  value       = aws_db_instance.this.master_user_secret[0].secret_arn
}
