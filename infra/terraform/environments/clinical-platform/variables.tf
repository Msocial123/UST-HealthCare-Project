# ---------- General ----------
variable "aws_region" {
  description = "AWS region for every resource."
  type        = string
  default     = "us-east-1"
}

variable "allowed_account_ids" {
  description = "Optional guard: Terraform refuses to run against any other AWS account. Pass at runtime (TF_VAR_allowed_account_ids), not in code."
  type        = list(string)
  default     = []
}

variable "project_name" {
  description = "Name prefix for all resources and the ECR repository namespace."
  type        = string
  default     = "clinical-platform"
}

variable "tags" {
  description = "Extra tags applied to every resource."
  type        = map(string)
  default     = {}
}

# ---------- Network ----------
variable "vpc_cidr" {
  description = "VPC CIDR block."
  type        = string
}

variable "availability_zones" {
  description = "Exactly two availability zones."
  type        = list(string)

  validation {
    condition     = length(var.availability_zones) == 2
    error_message = "This platform uses exactly two availability zones."
  }
}

variable "public_subnet_cidrs" {
  description = "Public subnet CIDRs (NAT gateway, future load balancers), one per AZ."
  type        = list(string)
}

variable "private_subnet_cidrs" {
  description = "Private subnet CIDRs (EKS control plane ENIs and worker nodes), one per AZ."
  type        = list(string)
}

variable "single_nat_gateway" {
  description = "true: one NAT gateway shared by both private subnets (cheaper). false: one per AZ."
  type        = bool
  default     = true
}

# ---------- ECR ----------
variable "services" {
  description = "Application services; one private ECR repository <project_name>/<service> is created per entry."
  type        = set(string)
}

variable "ecr_image_tag_mutability" {
  description = "MUTABLE or IMMUTABLE."
  type        = string
  default     = "IMMUTABLE"
}

variable "ecr_force_delete" {
  description = "Allow destroy to delete repositories that still contain images."
  type        = bool
  default     = false
}

# ---------- EKS ----------
variable "eks_cluster_name" {
  description = "EKS cluster name."
  type        = string
  default     = "clinical-platform-eks"
}

variable "eks_cluster_version" {
  description = "Kubernetes version of the EKS control plane."
  type        = string
}

variable "eks_endpoint_public_access" {
  description = "Expose the Kubernetes API endpoint publicly."
  type        = bool
  default     = true
}

variable "eks_endpoint_public_access_cidrs" {
  description = "CIDRs allowed to reach the public Kubernetes API endpoint. 0.0.0.0/0 is rejected."
  type        = list(string)

  validation {
    condition     = length(var.eks_endpoint_public_access_cidrs) > 0 && !contains(var.eks_endpoint_public_access_cidrs, "0.0.0.0/0") && alltrue([for c in var.eks_endpoint_public_access_cidrs : can(cidrhost(c, 0))])
    error_message = "Provide at least one valid CIDR; 0.0.0.0/0 is not allowed for the EKS API endpoint."
  }
}

variable "eks_cluster_admin_principal_arns" {
  description = "Extra IAM principals granted cluster-admin through EKS access entries. Pass at runtime; do not commit account-specific ARNs."
  type        = list(string)
  default     = []
}

variable "eks_node_instance_types" {
  description = "Instance types for the managed node group."
  type        = list(string)
}

variable "eks_node_capacity_type" {
  description = "ON_DEMAND or SPOT."
  type        = string
  default     = "ON_DEMAND"
}

variable "eks_node_disk_size" {
  description = "Worker node root volume size (GiB)."
  type        = number
  default     = 20
}

variable "eks_node_min_size" {
  description = "Minimum worker nodes."
  type        = number
}

variable "eks_node_max_size" {
  description = "Maximum worker nodes."
  type        = number
}

variable "eks_node_desired_size" {
  description = "Initial worker nodes."
  type        = number
}
