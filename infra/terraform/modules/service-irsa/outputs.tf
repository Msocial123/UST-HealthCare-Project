output "role_arns" {
  description = "Map of service name to IAM role ARN (annotate the service account with eks.amazonaws.com/role-arn)."
  value       = { for k, r in aws_iam_role.service : k => r.arn }
}
