# Smart Hospital - dev environment. Every input for this environment is set here.
# Values marked CHANGE ME must be edited before the first `terraform plan`.

# ---------- General ----------
aws_region          = "us-east-1"
allowed_account_ids = ["165742853391"]
project_name        = "smart-hospital"
environment         = "dev"
tags = {
  Owner      = "devops"
  CostCenter = "training"
}

# ---------- Network (10.20.0.0/16, two AZs) ----------
vpc_cidr                 = "10.20.0.0/16"
availability_zones       = ["us-east-1a", "us-east-1b"]
public_subnet_cidrs      = ["10.20.1.0/24", "10.20.2.0/24"]
private_app_subnet_cidrs = ["10.20.11.0/24", "10.20.12.0/24"]
private_db_subnet_cidrs  = ["10.20.21.0/24", "10.20.22.0/24"]
single_nat_gateway       = true # one NAT gateway in AZ A, as in the diagram

# ---------- EKS ----------
eks_cluster_version              = "1.34"
eks_endpoint_public_access_cidrs = ["0.0.0.0/0"] # CHANGE ME: restrict to office/VPN CIDRs (GitHub-hosted runners need public access)
eks_cluster_admin_principal_arns = []            # e.g. ["arn:aws:iam::123456789012:role/Admin"]
eks_node_instance_types          = ["t3.medium"]
eks_node_capacity_type           = "ON_DEMAND"
eks_node_disk_size               = 20
eks_node_min_size                = 2
eks_node_max_size                = 3
eks_node_desired_size            = 2
kubernetes_namespace             = "smart-hospital"

# ---------- The eight FastAPI microservices (container port 8000) ----------
# Each Kubernetes Service must be type NodePort with the node_port below; the ALB routes by path.
# Lower priority numbers are evaluated first: scheduling's /providers/*/... routes sit ahead of provider-service.
services = {
  "identity-service" = {
    node_port     = 30081
    path_patterns = ["/api/v1/auth*", "/api/v1/users*", "/api/v1/roles*", "/api/v1/identity*"]
    priority      = 100
    db_name       = "identity_db"
  }
  "patient-service" = {
    node_port     = 30082
    path_patterns = ["/api/v1/patients*"]
    priority      = 200
    db_name       = "patient_db"
  }
  "provider-service" = {
    node_port     = 30083
    path_patterns = ["/api/v1/providers*", "/api/v1/specialties*"]
    priority      = 300
    db_name       = "provider_db"
  }
  "facility-service" = {
    node_port     = 30084
    path_patterns = ["/api/v1/facilities*", "/api/v1/departments*"]
    priority      = 400
    db_name       = "facility_db"
  }
  "scheduling-service" = {
    node_port = 30085
    path_patterns = [
      "/api/v1/providers/*/working-hours*",
      "/api/v1/providers/*/exceptions*",
      "/api/v1/providers/*/slots*",
      "/api/v1/working-hours*",
      "/api/v1/exceptions*",
    ]
    priority = 50
    db_name  = "scheduling_db"
  }
  "appointment-service" = {
    node_port     = 30086
    path_patterns = ["/api/v1/appointments*"]
    priority      = 600
    db_name       = "appointment_db"
  }
  "encounter-service" = {
    node_port     = 30087
    path_patterns = ["/api/v1/encounters*", "/api/v1/visits*"]
    priority      = 700
    db_name       = "encounter_db"
  }
  "notification-service" = {
    node_port     = 30088
    path_patterns = ["/api/v1/notifications*"]
    priority      = 800
    db_name       = "notification_db"
  }
}

# ---------- ECR ----------
ecr_image_tag_mutability = "IMMUTABLE"
ecr_force_delete         = false

# ---------- RDS for PostgreSQL (single-AZ, cost optimized) ----------
rds_engine_version          = "16"
rds_instance_class          = "db.t3.micro"
rds_allocated_storage       = 20
rds_max_allocated_storage   = 50
rds_multi_az                = false
rds_backup_retention_period = 7
rds_deletion_protection     = true
rds_skip_final_snapshot     = false

secrets_recovery_window_in_days = 7

# ---------- DNS / TLS / edge ----------
hosted_zone_name             = null      # No custom domain yet: HTTP on the ALB DNS name, no ACM/DNS/SES. Set an existing public Route 53 zone (e.g. "example.com") to enable HTTPS.
api_subdomain                = "api.dev" # API served at https://api.dev.<hosted_zone_name>
alb_ingress_cidrs            = ["0.0.0.0/0"]
alb_deletion_protection      = false
enable_waf                   = true
waf_rate_limit_per_5_minutes = 2000

# ---------- CI/CD (GitHub Actions OIDC) ----------
github_repository           = "Msocial123/UST-HealthCare-Project"
github_allowed_subjects     = ["ref:refs/heads/main"]
github_create_oidc_provider = true # set false if the account already has the GitHub OIDC provider

# ---------- Additional services ----------
enable_sqs                  = true
enable_ses                  = true
enable_shared_bucket        = true
shared_bucket_force_destroy = false
notification_service_name   = "notification-service"
