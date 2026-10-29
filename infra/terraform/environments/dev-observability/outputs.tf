output "infrastructure_dashboard_url" {
  description = "EKS infrastructure dashboard."
  value       = module.observability.infrastructure_dashboard_url
}

output "service_slo_dashboard_url" {
  description = "Service SLI/SLO/SLA dashboard."
  value       = module.observability.service_slo_dashboard_url
}

output "slo_ids" {
  description = "SLO IDs per service."
  value       = module.observability.slo_ids
}
