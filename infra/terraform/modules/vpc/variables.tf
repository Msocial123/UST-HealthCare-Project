variable "name" {
  description = "Name prefix for VPC resources (for example smart-hospital-dev)."
  type        = string
}

variable "cluster_name" {
  description = "EKS cluster name, used for the kubernetes.io/cluster subnet tags."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block of the VPC."
  type        = string
}

variable "availability_zones" {
  description = "Availability zones, in the same order as the subnet CIDR lists."
  type        = list(string)

  validation {
    condition     = length(var.availability_zones) >= 2
    error_message = "EKS, the ALB and the RDS subnet group need at least two availability zones."
  }
}

variable "public_subnet_cidrs" {
  description = "Public subnet CIDRs (ALB, NAT gateway), one per availability zone."
  type        = list(string)
}

variable "private_app_subnet_cidrs" {
  description = "Private application subnet CIDRs (EKS worker nodes), one per availability zone."
  type        = list(string)
}

variable "private_db_subnet_cidrs" {
  description = "Private database subnet CIDRs (RDS), one per availability zone."
  type        = list(string)
}

variable "single_nat_gateway" {
  description = "true: one NAT gateway in the first AZ shared by all private subnets (cheaper). false: one NAT gateway per AZ."
  type        = bool
  default     = true
}
