output "db_secret_arns" {
  description = "Map of service name to its database credentials secret ARN."
  value       = { for k, s in aws_secretsmanager_secret.db : k => s.arn }
}

output "jwt_secret_arn" {
  description = "ARN of the shared JWT signing key secret."
  value       = aws_secretsmanager_secret.jwt.arn
}
