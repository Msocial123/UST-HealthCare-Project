resource "datadog_dashboard_json" "infrastructure" {
  dashboard = file("${path.module}/dashboards/eks-infrastructure.json")
}

resource "datadog_dashboard_json" "service_slo" {
  dashboard = templatefile("${path.module}/dashboards/service-slo.json.tftpl", {
    slo = merge(
      { for s in var.services : "${replace(s, "-", "_")}_availability" => datadog_service_level_objective.availability[s].id },
      { for s in var.services : "${replace(s, "-", "_")}_latency" => datadog_service_level_objective.latency[s].id },
    )
    availability_target  = var.availability_target
    latency_target       = var.latency_target
    latency_threshold_ms = var.latency_threshold_ms
    latency_threshold_s  = var.latency_threshold_ms / 1000
    sla_target           = var.sla_target
  })
}
