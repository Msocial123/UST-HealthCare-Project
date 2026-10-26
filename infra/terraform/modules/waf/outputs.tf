output "web_acl_arn" {
  description = "WAF web ACL ARN."
  value       = aws_wafv2_web_acl.this.arn
}
