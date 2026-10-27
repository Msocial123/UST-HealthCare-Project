# Additional security group for the EKS control plane ENIs. EKS also creates its own cluster security group,
# which it attaches to the control plane and the managed nodes and which allows all traffic between them.
resource "aws_security_group" "control_plane" {
  name        = "${var.name}-eks-control-plane"
  description = "Additional EKS control plane SG: HTTPS to the private API endpoint from inside the VPC"
  vpc_id      = var.vpc_id

  tags = { Name = "${var.name}-eks-control-plane" }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_vpc_security_group_ingress_rule" "control_plane_https" {
  for_each = toset(var.control_plane_ingress_cidrs)

  security_group_id = aws_security_group.control_plane.id
  description       = "Kubernetes API (private endpoint)"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  cidr_ipv4         = each.value
}

resource "aws_vpc_security_group_egress_rule" "control_plane_all" {
  security_group_id = aws_security_group.control_plane.id
  description       = "Control plane to nodes and AWS APIs"
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}
