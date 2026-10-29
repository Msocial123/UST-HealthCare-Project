variable "datadog_api_url" {
  description = "Datadog API URL for the org's site (US1: https://api.datadoghq.com/)."
  type        = string
}

variable "env" {
  description = "env tag of the monitored services."
  type        = string
}

variable "cluster_name" {
  description = "EKS cluster name."
  type        = string
}

variable "namespace" {
  description = "Namespace the services run in."
  type        = string
}

variable "services" {
  description = "Monitored services."
  type        = list(string)
}

variable "availability_target" {
  description = "Availability SLO target (percent, 30 days)."
  type        = number
}

variable "latency_threshold_ms" {
  description = "p95 latency threshold in ms."
  type        = number
}

variable "latency_target" {
  description = "Latency SLO target (percent of 5-minute slices)."
  type        = number
}

variable "sla_target" {
  description = "SLA availability (percent)."
  type        = number
}

variable "notify" {
  description = "Datadog notification handles for monitors."
  type        = list(string)
  default     = []
}
