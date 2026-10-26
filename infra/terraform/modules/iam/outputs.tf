output "eks_cluster_role_arn" {
  description = "IAM role assumed by the EKS control plane."
  value       = aws_iam_role.eks_cluster.arn
}

output "eks_node_role_arn" {
  description = "IAM role assumed by the EKS worker nodes."
  value       = aws_iam_role.eks_node.arn
}

output "eks_node_role_name" {
  description = "Name of the EKS worker node role."
  value       = aws_iam_role.eks_node.name
}
