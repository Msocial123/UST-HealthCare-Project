output "alb_arn" {
  description = "ALB ARN."
  value       = aws_lb.this.arn
}

output "alb_dns_name" {
  description = "AWS-generated ALB DNS name."
  value       = aws_lb.this.dns_name
}

output "alb_security_group_id" {
  description = "Security group of the ALB."
  value       = aws_security_group.alb.id
}

output "api_fqdn" {
  description = "Public API host name (null when enable_https is false)."
  value       = one(aws_route53_record.alb[*].fqdn)
}

output "target_group_arns" {
  description = "Map of service name to target group ARN."
  value       = { for k, t in aws_lb_target_group.service : k => t.arn }
}

output "listener_rule_priorities" {
  description = "Map of <service>-<index> to listener rule priority."
  value       = { for k, r in local.path_rules : k => r.priority }
}
