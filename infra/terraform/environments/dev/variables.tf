# ---------- General ----------
variable "aws_region" {
  description = "AWS region for every resource."
  type        = string

  validation {
    condition     = var.aws_region == "us-east-1"
    error_message = "This environment is built in us-east-1 only."
  }
}

variable "allowed_account_ids" {
  description = "If set, Terraform refuses to run against any other AWS account."
  type        = list(string)
  default     = []
}

variable "project_name" {
  description = "Project name, used as a name prefix."
  type        = string
}

variable "environment" {
  description = "Environment name (dev)."
  type        = string
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
  description = "Availability zones (AZ A, AZ B)."
  type        = list(string)
}

variable "public_subnet_cidrs" {
  description = "Public subnet CIDRs, one per AZ."
  type        = list(string)
}

variable "private_app_subnet_cidrs" {
  description = "Private application subnet CIDRs, one per AZ."
  type        = list(string)
}

variable "private_db_subnet_cidrs" {
  description = "Private database subnet CIDRs, one per AZ."
  type        = list(string)
}

variable "single_nat_gateway" {
  description = "Use one NAT gateway (AZ A) for all private app subnets."
  type        = bool
  default     = true
}

# ---------- EKS ----------
variable "eks_cluster_version" {
  description = "Kubernetes version of the EKS cluster."
  type        = string
}

variable "eks_endpoint_public_access_cidrs" {
  description = "CIDRs allowed to reach the public Kubernetes API endpoint."
  type        = list(string)
}

variable "eks_cluster_admin_principal_arns" {
  description = "Additional IAM principals (users/roles) given cluster-admin."
  type        = list(string)
  default     = []
}

variable "eks_node_instance_types" {
  description = "Worker node instance types."
  type        = list(string)
}

variable "eks_node_capacity_type" {
  description = "ON_DEMAND or SPOT."
  type        = string
  default     = "ON_DEMAND"
}

variable "eks_node_disk_size" {
  description = "Worker node root volume size, in GiB."
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

variable "kubernetes_namespace" {
  description = "Namespace the eight microservices are deployed into."
  type        = string
}

# ---------- Microservices ----------
variable "services" {
  description = "The eight microservices: ALB routing (NodePort, path patterns, rule priority) and database name."
  type = map(object({
    node_port         = number
    path_patterns     = list(string)
    priority          = number
    health_check_path = optional(string, "/health")
    db_name           = string
  }))
}

# ---------- ECR ----------
variable "ecr_image_tag_mutability" {
  description = "MUTABLE or IMMUTABLE image tags."
  type        = string
  default     = "IMMUTABLE"
}

variable "ecr_force_delete" {
  description = "Allow destroy to delete repositories that still hold images."
  type        = bool
  default     = false
}

# ---------- RDS ----------
variable "rds_engine_version" {
  description = "PostgreSQL version."
  type        = string
}

variable "rds_instance_class" {
  description = "RDS instance class."
  type        = string
}

variable "rds_allocated_storage" {
  description = "Initial storage, in GiB."
  type        = number
}

variable "rds_max_allocated_storage" {
  description = "Storage autoscaling ceiling, in GiB."
  type        = number
}

variable "rds_multi_az" {
  description = "Multi-AZ standby."
  type        = bool
  default     = false
}

variable "rds_backup_retention_period" {
  description = "Days of automated backups."
  type        = number
}

variable "rds_deletion_protection" {
  description = "Block deletion of the database."
  type        = bool
}

variable "rds_skip_final_snapshot" {
  description = "Skip the final snapshot on destroy."
  type        = bool
}

variable "secrets_recovery_window_in_days" {
  description = "Days a deleted Secrets Manager secret can be restored."
  type        = number
  default     = 7
}

# ---------- DNS / TLS / edge ----------
variable "hosted_zone_name" {
  description = "Existing public Route 53 hosted zone (for example example.com). null = no custom domain: no ACM certificate, DNS record or SES identity, and the API is plain HTTP on the ALB DNS name."
  type        = string
  default     = null
}

variable "api_subdomain" {
  description = "API host name inside the zone; the API is served at <api_subdomain>.<hosted_zone_name>."
  type        = string
}

variable "alb_ingress_cidrs" {
  description = "CIDRs allowed to reach the ALB."
  type        = list(string)
}

variable "alb_deletion_protection" {
  description = "Block deletion of the ALB."
  type        = bool
  default     = false
}

variable "enable_waf" {
  description = "Attach an AWS WAF web ACL to the ALB."
  type        = bool
  default     = true
}

variable "waf_rate_limit_per_5_minutes" {
  description = "WAF per-IP rate limit (requests per 5 minutes)."
  type        = number
  default     = 2000
}

# ---------- CI/CD ----------
variable "github_repository" {
  description = "GitHub repository (owner/name) allowed to assume the CI/CD role."
  type        = string
}

variable "github_allowed_subjects" {
  description = "OIDC sub claim suffixes allowed to assume the CI/CD role."
  type        = list(string)
}

variable "github_create_oidc_provider" {
  description = "Create the account-wide GitHub OIDC provider (false if it already exists)."
  type        = bool
  default     = true
}

# ---------- Additional services ----------
variable "enable_sqs" {
  description = "Create the notification SQS queue and dead-letter queue."
  type        = bool
  default     = true
}

variable "enable_ses" {
  description = "Verify the hosted zone domain in SES for notification email."
  type        = bool
  default     = true
}

variable "enable_shared_bucket" {
  description = "Create the shared-files S3 bucket."
  type        = bool
  default     = true
}

variable "shared_bucket_force_destroy" {
  description = "Allow destroy to delete a non-empty shared-files bucket."
  type        = bool
  default     = false
}

variable "notification_service_name" {
  description = "Key in var.services that receives SQS/SES permissions."
  type        = string
  default     = "notification-service"
}
