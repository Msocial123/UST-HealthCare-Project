output "api_key_secret_arn" {
  description = "ARN of the Datadog API key secret."
  value       = aws_secretsmanager_secret.api_key.arn
}

output "api_key_secret_name" {
  description = "Name of the Datadog API key secret."
  value       = aws_secretsmanager_secret.api_key.name
}

output "cluster_agent_token_secret_arn" {
  description = "ARN of the Cluster Agent token secret."
  value       = aws_secretsmanager_secret.cluster_agent_token.arn
}

output "cluster_agent_token_secret_name" {
  description = "Name of the Cluster Agent token secret."
  value       = aws_secretsmanager_secret.cluster_agent_token.name
}
