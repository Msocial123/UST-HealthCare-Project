output "vpc_id" {
  description = "VPC ID."
  value       = module.vpc.vpc_id
}

output "private_app_subnet_ids" {
  description = "Private application subnet IDs."
  value       = module.vpc.private_app_subnet_ids
}

output "nat_gateway_public_ips" {
  description = "Egress IPs of the private subnets (allow-list these on external systems)."
  value       = module.vpc.nat_gateway_public_ips
}

output "eks_cluster_name" {
  description = "EKS cluster name."
  value       = module.eks.cluster_name
}

output "eks_cluster_endpoint" {
  description = "Kubernetes API endpoint."
  value       = module.eks.cluster_endpoint
}

output "kubeconfig_command" {
  description = "Command that writes a kubeconfig entry for the cluster."
  value       = "aws eks update-kubeconfig --region ${var.aws_region} --name ${module.eks.cluster_name}"
}

output "ecr_repository_urls" {
  description = "Service name to ECR repository URL."
  value       = module.ecr.repository_urls
}

output "rds_address" {
  description = "PostgreSQL host name (private)."
  value       = module.rds.address
}

output "rds_master_user_secret_arn" {
  description = "Secrets Manager secret holding the RDS master credentials."
  value       = module.rds.master_user_secret_arn
}

output "service_db_secret_arns" {
  description = "Service name to its database credentials secret ARN."
  value       = module.secrets.db_secret_arns
}

output "jwt_secret_arn" {
  description = "Shared JWT signing key secret ARN."
  value       = module.secrets.jwt_secret_arn
}

output "service_role_arns" {
  description = "Service name to IRSA role ARN (eks.amazonaws.com/role-arn service account annotation)."
  value       = module.service_irsa.role_arns
}

output "service_node_ports" {
  description = "Service name to the NodePort its Kubernetes Service must use."
  value       = { for k, s in var.services : k => s.node_port }
}

output "github_actions_role_arn" {
  description = "role-to-assume for aws-actions/configure-aws-credentials."
  value       = module.github_oidc.role_arn
}

output "alb_dns_name" {
  description = "AWS DNS name of the ALB."
  value       = module.alb.alb_dns_name
}

output "api_base_url" {
  description = "Public HTTPS base URL."
  value       = "https://${module.alb.api_fqdn}"
}

output "waf_web_acl_arn" {
  description = "WAF web ACL ARN (null when disabled)."
  value       = one(module.waf[*].web_acl_arn)
}

output "notification_queue_url" {
  description = "Notification SQS queue URL (null when disabled)."
  value       = one(module.sqs[*].queue_url)
}

output "ses_identity_arn" {
  description = "SES domain identity ARN (null when disabled)."
  value       = one(module.ses[*].identity_arn)
}

output "shared_bucket_name" {
  description = "Shared-files bucket (null when disabled)."
  value       = one(module.shared_bucket[*].bucket_name)
}
