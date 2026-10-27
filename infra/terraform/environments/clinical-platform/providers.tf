# Credentials come from the standard AWS chain (environment variables, profile, SSO or role); never from this code.
provider "aws" {
  region = var.aws_region

  allowed_account_ids = length(var.allowed_account_ids) > 0 ? var.allowed_account_ids : null

  default_tags {
    tags = merge(var.tags, {
      Project   = var.project_name
      ManagedBy = "terraform"
    })
  }
}
