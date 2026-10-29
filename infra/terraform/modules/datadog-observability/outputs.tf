output "infrastructure_dashboard_url" {
  description = "EKS infrastructure dashboard."
  value       = "https://app.datadoghq.com${datadog_dashboard_json.infrastructure.url}"
}

output "service_slo_dashboard_url" {
  description = "Service SLI/SLO/SLA dashboard."
  value       = "https://app.datadoghq.com${datadog_dashboard_json.service_slo.url}"
}

output "slo_ids" {
  description = "SLO IDs per service."
  value = { for s in var.services : s => {
    availability = datadog_service_level_objective.availability[s].id
    latency      = datadog_service_level_objective.latency[s].id
  } }
}
