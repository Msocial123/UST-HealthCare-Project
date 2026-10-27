variable "cluster_name" {
  description = "EKS cluster name."
  type        = string
}

variable "cluster_version" {
  description = "Kubernetes version of the EKS control plane (for example 1.34)."
  type        = string
}

variable "cluster_role_arn" {
  description = "IAM role ARN for the EKS control plane."
  type        = string
}

variable "node_role_arn" {
  description = "IAM role ARN for the managed node group."
  type        = string
}

variable "subnet_ids" {
  description = "Private application subnet IDs for the control plane ENIs and worker nodes."
  type        = list(string)
}

variable "additional_security_group_ids" {
  description = "Extra security groups attached to the control plane ENIs, in addition to the EKS-created cluster security group."
  type        = list(string)
  default     = []
}

variable "endpoint_public_access" {
  description = "Expose the Kubernetes API endpoint publicly (needed for GitHub-hosted runners and kubectl from outside the VPC)."
  type        = bool
  default     = true
}

variable "endpoint_public_access_cidrs" {
  description = "CIDRs allowed to reach the public Kubernetes API endpoint."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "cluster_admin_principal_arns" {
  description = "IAM user/role ARNs granted cluster-admin through EKS access entries (in addition to the identity that creates the cluster)."
  type        = list(string)
  default     = []
}

variable "node_instance_types" {
  description = "EC2 instance types for the managed node group."
  type        = list(string)
  default     = ["t3.medium"]
}

variable "node_capacity_type" {
  description = "ON_DEMAND or SPOT."
  type        = string
  default     = "ON_DEMAND"
}

variable "node_ami_type" {
  description = "EKS managed node group AMI type."
  type        = string
  default     = "AL2023_x86_64_STANDARD"
}

variable "node_disk_size" {
  description = "Root volume size of each worker node, in GiB."
  type        = number
  default     = 20
}

variable "node_min_size" {
  description = "Minimum number of worker nodes."
  type        = number
  default     = 2
}

variable "node_max_size" {
  description = "Maximum number of worker nodes."
  type        = number
  default     = 3
}

variable "node_desired_size" {
  description = "Initial number of worker nodes. Later changes made by an autoscaler are ignored."
  type        = number
  default     = 2
}

variable "cluster_addons" {
  description = "EKS managed add-ons to install. Empty version = AWS default version for the cluster."
  type = map(object({
    version = optional(string)
  }))
  default = {
    vpc-cni    = {}
    kube-proxy = {}
    coredns    = {}
  }
}
