output "control_plane_security_group_id" {
  description = "Additional security group attached to the EKS control plane."
  value       = aws_security_group.control_plane.id
}
