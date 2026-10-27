# Clinical platform inputs. No credentials, account IDs, passwords or tokens belong here:
# credentials come from the AWS credential chain, and account-specific values are passed as TF_VAR_* at runtime.

aws_region   = "us-east-1"
project_name = "clinical-platform"
tags = {
  Owner = "devops"
}

# ---------- Network (2 AZs) ----------
vpc_cidr             = "10.30.0.0/16"
availability_zones   = ["us-east-1a", "us-east-1b"]
public_subnet_cidrs  = ["10.30.1.0/24", "10.30.2.0/24"]
private_subnet_cidrs = ["10.30.11.0/24", "10.30.12.0/24"]
single_nat_gateway   = true

# ---------- ECR: clinical-platform/<service> ----------
services = [
  "appointment-service",
  "facility-service",
  "identity-service",
  "patient-service",
  "provider-service",
  "scheduling-service",
]
ecr_image_tag_mutability = "IMMUTABLE"
ecr_force_delete         = false

# ---------- EKS ----------
eks_cluster_name                 = "clinical-platform-eks"
eks_cluster_version              = "1.34"
eks_endpoint_public_access       = true
eks_endpoint_public_access_cidrs = ["140.232.64.0/26"] # Devin session egress range (docs.devin.ai). Add operator IPs at runtime via TF_VAR_eks_endpoint_public_access_cidrs
eks_node_instance_types          = ["t3.medium"]
eks_node_capacity_type           = "ON_DEMAND"
eks_node_disk_size               = 20
eks_node_min_size                = 2
eks_node_max_size                = 3
eks_node_desired_size            = 2
