# Clinical platform - AWS foundation for the six FastAPI services (us-east-1):
# VPC across 2 AZs (2 public + 2 private subnets, IGW, NAT gateway, route tables), security groups,
# six private ECR repositories, the EKS cluster clinical-platform-eks with a managed node group, and the IAM roles they need.

module "vpc" {
  source = "../../modules/vpc"

  name                     = var.project_name
  cluster_name             = var.eks_cluster_name
  vpc_cidr                 = var.vpc_cidr
  availability_zones       = var.availability_zones
  public_subnet_cidrs      = var.public_subnet_cidrs
  private_app_subnet_cidrs = var.private_subnet_cidrs
  single_nat_gateway       = var.single_nat_gateway
}

module "security_groups" {
  source = "../../modules/security-groups"

  name                        = var.project_name
  vpc_id                      = module.vpc.vpc_id
  control_plane_ingress_cidrs = [module.vpc.vpc_cidr]
}

module "iam" {
  source = "../../modules/iam"

  name = var.project_name
}

module "ecr" {
  source = "../../modules/ecr"

  name_prefix          = var.project_name
  repository_names     = var.services
  image_tag_mutability = var.ecr_image_tag_mutability
  force_delete         = var.ecr_force_delete
}

module "eks" {
  source = "../../modules/eks"

  cluster_name                  = var.eks_cluster_name
  cluster_version               = var.eks_cluster_version
  cluster_role_arn              = module.iam.eks_cluster_role_arn
  node_role_arn                 = module.iam.eks_node_role_arn
  subnet_ids                    = module.vpc.private_app_subnet_ids
  additional_security_group_ids = [module.security_groups.control_plane_security_group_id]
  endpoint_public_access        = var.eks_endpoint_public_access
  endpoint_public_access_cidrs  = var.eks_endpoint_public_access_cidrs
  cluster_admin_principal_arns  = var.eks_cluster_admin_principal_arns
  node_instance_types           = var.eks_node_instance_types
  node_capacity_type            = var.eks_node_capacity_type
  node_disk_size                = var.eks_node_disk_size
  node_min_size                 = var.eks_node_min_size
  node_max_size                 = var.eks_node_max_size
  node_desired_size             = var.eks_node_desired_size

  # Role policies must exist before the cluster/nodes are created and stay until after they are deleted.
  depends_on = [module.iam]
}
