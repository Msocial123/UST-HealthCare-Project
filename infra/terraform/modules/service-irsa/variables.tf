variable "name" {
  description = "Name prefix for the service roles (for example smart-hospital-dev)."
  type        = string
}

variable "oidc_provider_arn" {
  description = "EKS IAM OIDC provider ARN."
  type        = string
}

variable "oidc_issuer" {
  description = "EKS OIDC issuer without https:// (for example oidc.eks.us-east-1.amazonaws.com/id/XXXX)."
  type        = string
}

variable "namespace" {
  description = "Kubernetes namespace of the service accounts."
  type        = string
}

variable "services" {
  description = "Per service: the Secrets Manager secrets it may read and any extra IAM statements. The Kubernetes service account name is the map key."
  type = map(object({
    secret_arns = list(string)
    extra_statements = optional(list(object({
      sid       = string
      actions   = list(string)
      resources = list(string)
    })), [])
  }))
}
