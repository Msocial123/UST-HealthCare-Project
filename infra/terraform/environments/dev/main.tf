# Smart Hospital - dev environment (us-east-1).
# Built from the architecture diagram, minus the AWS monitoring services (CloudWatch, Container Insights,
# X-Ray): monitoring is done with Datadog, so no AWS-native logging/metrics/tracing is enabled here.

data "aws_caller_identity" "current" {}

data "aws_route53_zone" "public" {
  count = local.use_custom_domain ? 1 : 0

  name         = var.hosted_zone_name
  private_zone = false
}

locals {
  name              = "${var.project_name}-${var.environment}"
  cluster_name      = "${local.name}-eks"
  use_custom_domain = var.hosted_zone_name != null
  api_fqdn          = local.use_custom_domain ? "${var.api_subdomain}.${var.hosted_zone_name}" : null
  zone_id           = one(data.aws_route53_zone.public[*].zone_id)

  service_databases = {
    for k, s in var.services : k => {
      db_name     = s.db_name
      db_username = replace(k, "-", "_")
    }
  }

  notification_statements = [
    for st in [
      {
        sid = "NotificationQueue"
        actions = [
          "sqs:SendMessage",
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:ChangeMessageVisibility",
          "sqs:GetQueueAttributes",
          "sqs:GetQueueUrl",
        ]
        resources = concat(module.sqs[*].queue_arn, module.sqs[*].dlq_arn)
      },
      {
        sid       = "NotificationEmail"
        actions   = ["ses:SendEmail", "ses:SendRawEmail"]
        resources = module.ses[*].identity_arn
      },
    ] : st if length(st.resources) > 0
  ]
}

module "vpc" {
  source = "../../modules/vpc"

  name                     = local.name
  cluster_name             = local.cluster_name
  vpc_cidr                 = var.vpc_cidr
  availability_zones       = var.availability_zones
  public_subnet_cidrs      = var.public_subnet_cidrs
  private_app_subnet_cidrs = var.private_app_subnet_cidrs
  private_db_subnet_cidrs  = var.private_db_subnet_cidrs
  single_nat_gateway       = var.single_nat_gateway
}

module "iam" {
  source = "../../modules/iam"

  name = local.name
}

module "ecr" {
  source = "../../modules/ecr"

  name_prefix          = var.project_name
  repository_names     = toset(keys(var.services))
  image_tag_mutability = var.ecr_image_tag_mutability
  force_delete         = var.ecr_force_delete
}

module "eks" {
  source = "../../modules/eks"

  cluster_name                 = local.cluster_name
  cluster_version              = var.eks_cluster_version
  cluster_role_arn             = module.iam.eks_cluster_role_arn
  node_role_arn                = module.iam.eks_node_role_arn
  subnet_ids                   = module.vpc.private_app_subnet_ids
  endpoint_public_access_cidrs = var.eks_endpoint_public_access_cidrs
  cluster_admin_principal_arns = var.eks_cluster_admin_principal_arns
  node_instance_types          = var.eks_node_instance_types
  node_capacity_type           = var.eks_node_capacity_type
  node_disk_size               = var.eks_node_disk_size
  node_min_size                = var.eks_node_min_size
  node_max_size                = var.eks_node_max_size
  node_desired_size            = var.eks_node_desired_size

  # Role policies must exist before the cluster/nodes are created and stay until after they are deleted.
  depends_on = [module.iam]
}

module "rds" {
  source = "../../modules/rds"

  identifier                 = "${local.name}-postgres"
  vpc_id                     = module.vpc.vpc_id
  subnet_ids                 = module.vpc.private_db_subnet_ids
  allowed_security_group_ids = [module.eks.cluster_security_group_id]
  engine_version             = var.rds_engine_version
  instance_class             = var.rds_instance_class
  allocated_storage          = var.rds_allocated_storage
  max_allocated_storage      = var.rds_max_allocated_storage
  multi_az                   = var.rds_multi_az
  backup_retention_period    = var.rds_backup_retention_period
  deletion_protection        = var.rds_deletion_protection
  skip_final_snapshot        = var.rds_skip_final_snapshot
}

module "secrets" {
  source = "../../modules/secrets"

  name_prefix             = "${var.project_name}/${var.environment}"
  service_databases       = local.service_databases
  db_host                 = module.rds.address
  db_port                 = module.rds.port
  recovery_window_in_days = var.secrets_recovery_window_in_days
}

module "sqs" {
  source = "../../modules/sqs"
  count  = var.enable_sqs ? 1 : 0

  name = "${local.name}-notifications"
}

module "ses" {
  source = "../../modules/ses"
  count  = var.enable_ses && local.use_custom_domain ? 1 : 0

  domain  = var.hosted_zone_name
  zone_id = local.zone_id
}

module "shared_bucket" {
  source = "../../modules/s3"
  count  = var.enable_shared_bucket ? 1 : 0

  bucket_name   = "${local.name}-shared-files-${data.aws_caller_identity.current.account_id}"
  force_destroy = var.shared_bucket_force_destroy
}

module "service_irsa" {
  source = "../../modules/service-irsa"

  name              = local.name
  oidc_provider_arn = module.eks.oidc_provider_arn
  oidc_issuer       = module.eks.oidc_issuer
  namespace         = var.kubernetes_namespace

  services = {
    for k in keys(var.services) : k => {
      secret_arns      = [module.secrets.db_secret_arns[k], module.secrets.jwt_secret_arn]
      extra_statements = [for st in local.notification_statements : st if k == var.notification_service_name]
    }
  }
}

# Kubernetes Job (service account db-bootstrap) that creates each service's PostgreSQL role and database
# using the RDS-managed master password.
module "db_bootstrap_irsa" {
  source = "../../modules/service-irsa"

  name              = local.name
  oidc_provider_arn = module.eks.oidc_provider_arn
  oidc_issuer       = module.eks.oidc_issuer
  namespace         = var.kubernetes_namespace

  services = {
    "db-bootstrap" = {
      secret_arns      = concat([module.rds.master_user_secret_arn], values(module.secrets.db_secret_arns))
      extra_statements = []
    }
  }
}

# Datadog Agent secrets, readable only by the datadog-secrets service account in the datadog namespace.
module "datadog" {
  source = "../../modules/datadog"

  name_prefix             = "${var.project_name}/${var.environment}"
  recovery_window_in_days = var.secrets_recovery_window_in_days
}

module "datadog_irsa" {
  source = "../../modules/service-irsa"

  name              = local.name
  oidc_provider_arn = module.eks.oidc_provider_arn
  oidc_issuer       = module.eks.oidc_issuer
  namespace         = "datadog"

  services = {
    "datadog-secrets" = {
      secret_arns      = [module.datadog.api_key_secret_arn, module.datadog.cluster_agent_token_secret_arn]
      extra_statements = []
    }
  }
}

module "github_oidc" {
  source = "../../modules/github-oidc"

  name                  = local.name
  create_oidc_provider  = var.github_create_oidc_provider
  github_repository     = var.github_repository
  allowed_subjects      = var.github_allowed_subjects
  ecr_repository_arns   = values(module.ecr.repository_arns)
  cluster_name          = module.eks.cluster_name
  cluster_arn           = module.eks.cluster_arn
  kubernetes_namespaces = [var.kubernetes_namespace]
}

module "acm" {
  source = "../../modules/acm"
  count  = local.use_custom_domain ? 1 : 0

  domain_name = local.api_fqdn
  zone_id     = local.zone_id
}

module "alb" {
  source = "../../modules/alb"

  name                        = local.name
  vpc_id                      = module.vpc.vpc_id
  public_subnet_ids           = module.vpc.public_subnet_ids
  ingress_cidrs               = var.alb_ingress_cidrs
  enable_https                = local.use_custom_domain
  certificate_arn             = one(module.acm[*].certificate_arn)
  node_security_group_id      = module.eks.cluster_security_group_id
  node_autoscaling_group_name = module.eks.node_group_autoscaling_group_name
  zone_id                     = local.zone_id
  dns_name                    = local.api_fqdn
  deletion_protection         = var.alb_deletion_protection

  services = {
    for k, s in var.services : k => {
      node_port         = s.node_port
      path_patterns     = s.path_patterns
      priority          = s.priority
      health_check_path = s.health_check_path
    }
  }
}

module "waf" {
  source = "../../modules/waf"
  count  = var.enable_waf ? 1 : 0

  name                     = "${local.name}-web-acl"
  resource_arn             = module.alb.alb_arn
  rate_limit_per_5_minutes = var.waf_rate_limit_per_5_minutes
}
