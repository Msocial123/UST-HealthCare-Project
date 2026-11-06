output "role_arn" {
  description = "Role ARN for aws-actions/configure-aws-credentials (role-to-assume)."
  value       = aws_iam_role.github_actions.arn
}

output "trusted_subjects" {
  description = "OIDC sub claims the role trusts."
  value       = local.trusted_subjects
}
