output "state_bucket_name" {
  description = "Pass to `terraform init -backend-config=\"bucket=<value>\"` in each environment."
  value       = aws_s3_bucket.state.id
}

output "state_bucket_arn" {
  description = "ARN of the Terraform state bucket."
  value       = aws_s3_bucket.state.arn
}
