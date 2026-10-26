output "identity_arn" {
  description = "SES domain identity ARN."
  value       = aws_sesv2_email_identity.this.arn
}
