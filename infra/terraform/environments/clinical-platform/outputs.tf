output "vpc_id" {
  description = "VPC ID."
  value       = module.vpc.vpc_id
}

output "public_subnet_ids" {
  description = "Public subnet IDs."
  value       = module.vpc.public_subnet_ids
}

output "private_subnet_ids" {
  description = "Private subnet IDs (EKS)."
  value       = module.vpc.private_app_subnet_ids
}

output "nat_gateway_public_ips" {
  description = "Outbound public IPs of the private subnets."
  value       = module.vpc.nat_gateway_public_ips
}

output "ecr_repository_urls" {
  description = "Service name -> ECR repository URL."
  value       = module.ecr.repository_urls
}

output "eks_cluster_name" {
  description = "EKS cluster name."
  value       = module.eks.cluster_name
}

output "eks_cluster_endpoint" {
  description = "Kubernetes API endpoint."
  value       = module.eks.cluster_endpoint
}

output "eks_cluster_security_group_id" {
  description = "EKS-created cluster security group (control plane and nodes)."
  value       = module.eks.cluster_security_group_id
}

output "eks_oidc_provider_arn" {
  description = "IAM OIDC provider for IRSA."
  value       = module.eks.oidc_provider_arn
}

output "eks_cluster_role_arn" {
  description = "IAM role of the EKS control plane."
  value       = module.iam.eks_cluster_role_arn
}

output "eks_node_role_arn" {
  description = "IAM role of the worker nodes."
  value       = module.iam.eks_node_role_arn
}

output "kubeconfig_command" {
  description = "Command to configure kubectl for this cluster."
  value       = "aws eks update-kubeconfig --region ${var.aws_region} --name ${module.eks.cluster_name}"
}

output "lb_controller_role_arn" {
  description = "IAM role for the AWS Load Balancer Controller service account (eks.amazonaws.com/role-arn)."
  value       = aws_iam_role.lb_controller.arn
}
