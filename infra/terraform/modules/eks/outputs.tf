output "cluster_name" {
  description = "EKS cluster name."
  value       = aws_eks_cluster.this.name
}

output "cluster_arn" {
  description = "EKS cluster ARN."
  value       = aws_eks_cluster.this.arn
}

output "cluster_endpoint" {
  description = "Kubernetes API endpoint."
  value       = aws_eks_cluster.this.endpoint
}

output "cluster_certificate_authority_data" {
  description = "Base64 cluster CA certificate."
  value       = aws_eks_cluster.this.certificate_authority[0].data
}

output "cluster_security_group_id" {
  description = "EKS-created cluster security group, attached to the control plane and the managed nodes."
  value       = aws_eks_cluster.this.vpc_config[0].cluster_security_group_id
}

output "oidc_provider_arn" {
  description = "IAM OIDC provider ARN used by IRSA roles."
  value       = aws_iam_openid_connect_provider.this.arn
}

output "oidc_issuer" {
  description = "OIDC issuer host/path without the https:// prefix."
  value       = replace(aws_eks_cluster.this.identity[0].oidc[0].issuer, "https://", "")
}

output "node_group_autoscaling_group_name" {
  description = "Auto Scaling group behind the managed node group (ALB target groups attach to it)."
  value       = aws_eks_node_group.this.resources[0].autoscaling_groups[0].name
}
