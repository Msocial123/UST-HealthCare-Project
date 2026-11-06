# Offline test of the OIDC trust subjects (no AWS account needed):
#   terraform init -backend=false && terraform test

mock_provider "aws" {
  mock_data "aws_caller_identity" {
    defaults = { account_id = "123456789012" }
  }
  mock_data "aws_partition" {
    defaults = { partition = "aws" }
  }
  mock_data "aws_iam_policy_document" {
    defaults = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
  }
}

variables {
  name                  = "smart-hospital-test"
  github_repository     = "Msocial123/UST-HealthCare-Project"
  allowed_subjects      = ["ref:refs/heads/main"]
  ecr_repository_arns   = ["arn:aws:ecr:us-east-1:123456789012:repository/x"]
  cluster_name          = "smart-hospital-test-eks"
  cluster_arn           = "arn:aws:eks:us-east-1:123456789012:cluster/smart-hospital-test-eks"
  kubernetes_namespaces = ["smart-hospital"]
}

run "legacy_subject_only_by_default" {
  command = plan

  assert {
    condition     = output.trusted_subjects == ["repo:Msocial123/UST-HealthCare-Project:ref:refs/heads/main"]
    error_message = "Without github_immutable_repository only the owner/name subject should be trusted."
  }
}

run "immutable_subject_added_when_set" {
  command = plan

  variables {
    github_immutable_repository = "Msocial123@83748367/UST-HealthCare-Project@1418833915"
    allowed_subjects            = ["ref:refs/heads/main", "environment:dev"]
  }

  assert {
    condition = output.trusted_subjects == [
      "repo:Msocial123/UST-HealthCare-Project:ref:refs/heads/main",
      "repo:Msocial123@83748367/UST-HealthCare-Project@1418833915:ref:refs/heads/main",
      "repo:Msocial123/UST-HealthCare-Project:environment:dev",
      "repo:Msocial123@83748367/UST-HealthCare-Project@1418833915:environment:dev",
    ]
    error_message = "Both subject forms should be trusted for every allowed subject, and nothing else."
  }
}
