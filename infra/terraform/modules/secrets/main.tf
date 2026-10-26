# Generated values are stored in Terraform state, so the state bucket must stay private and encrypted.

resource "random_password" "db" {
  for_each = var.service_databases

  length           = 32
  special          = true
  override_special = "-_"
}

resource "aws_secretsmanager_secret" "db" {
  for_each = var.service_databases

  name                    = "${var.name_prefix}/${each.key}/database"
  description             = "PostgreSQL credentials for ${each.key} (database ${each.value.db_name})"
  recovery_window_in_days = var.recovery_window_in_days
}

resource "aws_secretsmanager_secret_version" "db" {
  for_each = var.service_databases

  secret_id = aws_secretsmanager_secret.db[each.key].id
  secret_string = jsonencode({
    engine   = "postgres"
    host     = var.db_host
    port     = var.db_port
    dbname   = each.value.db_name
    username = each.value.db_username
    password = random_password.db[each.key].result
  })
}

# HS256 signing key issued by identity-service and verified by every other service.
resource "random_password" "jwt_signing_key" {
  length  = 64
  special = false
}

resource "aws_secretsmanager_secret" "jwt" {
  name                    = "${var.name_prefix}/shared/jwt-signing-key"
  description             = "JWT HS256 signing key shared by all services"
  recovery_window_in_days = var.recovery_window_in_days
}

resource "aws_secretsmanager_secret_version" "jwt" {
  secret_id = aws_secretsmanager_secret.jwt.id
  secret_string = jsonencode({
    kid = "dev-1"
    key = random_password.jwt_signing_key.result
  })
}
