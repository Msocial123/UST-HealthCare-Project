variable "name" {
  description = "Name prefix for the security groups (for example clinical-platform)."
  type        = string
}

variable "vpc_id" {
  description = "VPC the security groups belong to."
  type        = string
}

variable "control_plane_ingress_cidrs" {
  description = "CIDRs allowed to reach the private Kubernetes API endpoint on 443 (normally the VPC CIDR)."
  type        = list(string)
}
