# Offline wiring test with mocked providers (no AWS account needed):
#   terraform init -backend=false && terraform test

mock_provider "aws" {
  mock_resource "aws_lb" {
    defaults = { arn = "arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/x/1" }
  }
  mock_resource "aws_lb_target_group" {
    defaults = { arn = "arn:aws:elasticloadbalancing:us-east-1:123456789012:targetgroup/x/1" }
  }
  mock_resource "aws_lb_listener" {
    defaults = { arn = "arn:aws:elasticloadbalancing:us-east-1:123456789012:listener/app/x/1/2" }
  }
  mock_resource "aws_iam_role" {
    defaults = { arn = "arn:aws:iam::123456789012:role/x" }
  }
  mock_resource "aws_wafv2_web_acl" {
    defaults = { arn = "arn:aws:wafv2:us-east-1:123456789012:regional/webacl/x/1" }
  }
  mock_resource "aws_kms_key" {
    defaults = { arn = "arn:aws:kms:us-east-1:123456789012:key/x" }
  }
  mock_resource "aws_iam_openid_connect_provider" {
    defaults = { arn = "arn:aws:iam::123456789012:oidc-provider/x" }
  }
  mock_resource "aws_ecr_repository" {
    defaults = { arn = "arn:aws:ecr:us-east-1:123456789012:repository/x" }
  }
  mock_resource "aws_secretsmanager_secret" {
    defaults = { arn = "arn:aws:secretsmanager:us-east-1:123456789012:secret:x" }
  }
  mock_resource "aws_sqs_queue" {
    defaults = { arn = "arn:aws:sqs:us-east-1:123456789012:x", id = "https://sqs.us-east-1.amazonaws.com/123456789012/x" }
  }
  mock_resource "aws_s3_bucket" {
    defaults = { arn = "arn:aws:s3:::x" }
  }
  mock_data "aws_caller_identity" {
    defaults = { account_id = "123456789012" }
  }
  mock_data "aws_route53_zone" {
    defaults = { zone_id = "Z123EXAMPLE" }
  }
  mock_data "aws_partition" {
    defaults = { partition = "aws" }
  }
  mock_data "aws_iam_policy_document" {
    defaults = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
  }
  mock_resource "aws_eks_cluster" {
    defaults = {
      arn                   = "arn:aws:eks:us-east-1:123456789012:cluster/smart-hospital-dev-eks"
      identity              = [{ oidc = [{ issuer = "https://oidc.eks.us-east-1.amazonaws.com/id/ABC" }] }]
      vpc_config            = { cluster_security_group_id = "sg-0123456789abcdef0" }
      certificate_authority = [{ data = "Y2E=" }]
    }
  }
  mock_resource "aws_eks_node_group" {
    defaults = { resources = [{ autoscaling_groups = [{ name = "eks-asg-1" }], remote_access_security_group_id = "" }] }
  }
  mock_resource "aws_db_instance" {
    defaults = { address = "db.local", port = 5432, master_user_secret = [{ secret_arn = "arn:aws:secretsmanager:us-east-1:123456789012:secret:rds", kms_key_id = "", secret_status = "active" }] }
  }
  mock_resource "aws_sesv2_email_identity" {
    defaults = { arn = "arn:aws:ses:us-east-1:123456789012:identity/example.com", dkim_signing_attributes = [{ tokens = ["a", "b", "c"], current_signing_key_length = "", domain_signing_private_key = "", domain_signing_selector = "", last_key_generation_timestamp = "", next_signing_key_length = "", signing_attributes_origin = "", status = "" }] }
  }
  mock_resource "aws_acm_certificate" {
    defaults = { arn = "arn:aws:acm:us-east-1:123456789012:certificate/x", domain_validation_options = [{ domain_name = "api.dev.example.com", resource_record_name = "_x.api.dev.example.com", resource_record_type = "CNAME", resource_record_value = "_y.acm" }] }
  }
}
mock_provider "tls" {
  mock_data "tls_certificate" {
    defaults = { certificates = [{ sha1_fingerprint = "9e99a48a9960b14926bb7f3b02e22da2b0ab7280" }] }
  }
}
mock_provider "random" {}

override_module {
  target  = module.ses
  outputs = { identity_arn = "arn:aws:ses:us-east-1:123456789012:identity/example.com" }
}

run "apply_dev" {
  command = apply

  variables {
    hosted_zone_name = "example.com"
  }

  assert {
    condition     = length(module.ecr.repository_urls) == 8
    error_message = "expected 8 ECR repositories"
  }
  assert {
    condition     = length(module.service_irsa.role_arns) == 8
    error_message = "expected 8 IRSA roles"
  }
  assert {
    condition     = length(module.secrets.db_secret_arns) == 8
    error_message = "expected 8 db secrets"
  }
  assert {
    condition     = length(module.alb.target_group_arns) == 8
    error_message = "expected 8 target groups"
  }
  assert {
    condition     = length(module.waf) == 1 && length(module.sqs) == 1 && length(module.ses) == 1 && length(module.shared_bucket) == 1
    error_message = "optional services should be enabled in dev"
  }
  assert {
    condition     = length(local.notification_statements) == 2
    error_message = "notification-service should get SQS and SES statements"
  }
}

run "optional_services_off" {
  command = plan
  variables {
    enable_waf           = false
    enable_sqs           = false
    hosted_zone_name     = "example.com"
    enable_ses           = false
    enable_shared_bucket = false
  }
  assert {
    condition     = length(module.waf) == 0 && length(local.notification_statements) == 0
    error_message = "optional services should be off"
  }
}

run "no_custom_domain" {
  command = plan

  variables {
    hosted_zone_name = null
  }

  assert {
    condition     = length(module.acm) == 0 && length(module.ses) == 0 && length(data.aws_route53_zone.public) == 0
    error_message = "Without a hosted zone, no ACM certificate, SES identity or zone lookup is created."
  }

  assert {
    condition     = length(module.alb.target_group_arns) == 8
    error_message = "All 8 services are still routed through the ALB."
  }

  assert {
    condition     = length(module.alb.listener_rule_priorities) == 18
    error_message = "One ALB listener rule per path pattern (18 in dev)."
  }
}
