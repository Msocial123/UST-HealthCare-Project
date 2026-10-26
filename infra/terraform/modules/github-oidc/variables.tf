variable "name" {
  description = "Name prefix for the CI/CD role (for example smart-hospital-dev)."
  type        = string
}

variable "create_oidc_provider" {
  description = "Create the GitHub Actions OIDC provider. Set false if the AWS account already has token.actions.githubusercontent.com."
  type        = bool
  default     = true
}

variable "github_repository" {
  description = "GitHub repository allowed to assume the role, as owner/name."
  type        = string
}

variable "allowed_subjects" {
  description = "OIDC sub claims (after repo:<owner/name>:) allowed to assume the role, for example ref:refs/heads/main or environment:dev."
  type        = list(string)
  default     = ["ref:refs/heads/main"]
}

variable "ecr_repository_arns" {
  description = "ECR repositories the pipeline may push to."
  type        = list(string)
}

variable "cluster_name" {
  description = "EKS cluster the pipeline deploys to."
  type        = string
}

variable "cluster_arn" {
  description = "EKS cluster ARN."
  type        = string
}

variable "kubernetes_namespaces" {
  description = "Namespaces where the pipeline gets the EKS edit access policy."
  type        = list(string)
}
