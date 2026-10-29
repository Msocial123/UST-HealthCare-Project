variable "env" {
  description = "Value of the env tag the services report (unified service tagging)."
  type        = string
}

variable "cluster_name" {
  description = "EKS cluster name (kube_cluster_name tag)."
  type        = string
}

variable "namespace" {
  description = "Kubernetes namespace the services run in."
  type        = string
}

variable "services" {
  description = "Service names, as in the service tag (DD_SERVICE)."
  type        = list(string)
}

variable "availability_target" {
  description = "Availability SLO target in percent over 30 days."
  type        = number
  default     = 99.5
}

variable "latency_threshold_ms" {
  description = "p95 latency an SLO time slice must stay under, in milliseconds."
  type        = number
  default     = 500
}

variable "latency_target" {
  description = "Share of 5-minute slices (percent) that must meet the latency threshold."
  type        = number
  default     = 99.5
}

variable "sla_target" {
  description = "SLA availability in percent, shown as a reference line on the SLO dashboard."
  type        = number
  default     = 99.0
}

variable "notify" {
  description = "Datadog notification handles (for example @you@example.com) appended to monitor messages. Empty means no notifications."
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Tags added to every SLO and monitor."
  type        = list(string)
  default     = []
}
