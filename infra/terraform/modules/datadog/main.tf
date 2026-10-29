# Secrets the Datadog Agent on EKS reads through the External Secrets Operator.
# The API key value is never managed by Terraform (so it never lands in state); put it in once with:
#   aws secretsmanager put-secret-value --secret-id <api_key_secret_name> --secret-string '{"api_key":"..."}'

resource "aws_secretsmanager_secret" "api_key" {
  name                    = "${var.name_prefix}/datadog/api-key"
  description             = "Datadog API key used by the Datadog Agent (value set out of band)"
  recovery_window_in_days = var.recovery_window_in_days
}

# Shared secret between the node Agents and the Cluster Agent.
resource "random_password" "cluster_agent_token" {
  length  = 32
  special = false
}

resource "aws_secretsmanager_secret" "cluster_agent_token" {
  name                    = "${var.name_prefix}/datadog/cluster-agent-token"
  description             = "Datadog Cluster Agent authentication token"
  recovery_window_in_days = var.recovery_window_in_days
}

resource "aws_secretsmanager_secret_version" "cluster_agent_token" {
  secret_id     = aws_secretsmanager_secret.cluster_agent_token.id
  secret_string = jsonencode({ token = random_password.cluster_agent_token.result })
}
