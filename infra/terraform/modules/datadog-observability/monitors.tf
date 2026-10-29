locals {
  notify = join(" ", var.notify)

  # Multi-window burn-rate alerts (Google SRE workbook): fast burn pages, slow burn warns.
  burn_rates = {
    fast = { long = "1h", short = "5m", threshold = 14.4 }
    slow = { long = "6h", short = "30m", threshold = 6 }
  }
  slo_burn = { for pair in setproduct(var.services, keys(local.burn_rates)) : "${pair[0]}-${pair[1]}" => {
    service = pair[0]
    speed   = pair[1]
  } }
}

resource "datadog_monitor" "slo_burn_rate" {
  for_each = local.slo_burn

  name    = "[smart-hospital ${var.env}] ${each.value.service} availability SLO ${each.value.speed} burn"
  type    = "slo alert"
  message = "${each.value.service} is burning its ${var.availability_target}% availability error budget ${local.burn_rates[each.value.speed].threshold}x faster than allowed (${local.burn_rates[each.value.speed].long}/${local.burn_rates[each.value.speed].short} windows). ${local.notify}"
  query   = "burn_rate(\"${datadog_service_level_objective.availability[each.value.service].id}\").over(\"30d\").long_window(\"${local.burn_rates[each.value.speed].long}\").short_window(\"${local.burn_rates[each.value.speed].short}\") > ${local.burn_rates[each.value.speed].threshold}"
  tags    = concat(local.tags, ["service:${each.value.service}"])

  monitor_thresholds {
    critical = local.burn_rates[each.value.speed].threshold
  }
}

resource "datadog_monitor" "latency_budget" {
  for_each = local.services

  name    = "[smart-hospital ${var.env}] ${each.key} latency SLO error budget"
  type    = "slo alert"
  message = "${each.key} has used most of its p95 latency error budget for the last 30 days. ${local.notify}"
  query   = "error_budget(\"${datadog_service_level_objective.latency[each.key].id}\").over(\"30d\") > 90"
  tags    = concat(local.tags, ["service:${each.key}"])

  monitor_thresholds {
    critical = 90
    warning  = 75
  }
}

resource "datadog_monitor" "replicas_unavailable" {
  name    = "[smart-hospital ${var.env}] deployment has unavailable replicas"
  type    = "query alert"
  message = "{{kube_deployment.name}} in ${var.namespace} has had unavailable replicas for 10 minutes. ${local.notify}"
  query   = "max(last_10m):max:kubernetes_state.deployment.replicas_unavailable{kube_cluster_name:${var.cluster_name},kube_namespace:${var.namespace}} by {kube_deployment} > 0"
  tags    = local.tags

  monitor_thresholds {
    critical = 0
  }
}

resource "datadog_monitor" "container_restarts" {
  name    = "[smart-hospital ${var.env}] container restarting"
  type    = "query alert"
  message = "A container of {{kube_deployment.name}} restarted more than 3 times in 30 minutes. ${local.notify}"
  query   = "change(sum(last_30m),last_30m):sum:kubernetes.containers.restarts{kube_cluster_name:${var.cluster_name},kube_namespace:${var.namespace}} by {kube_deployment} > 3"
  tags    = local.tags

  monitor_thresholds {
    critical = 3
  }
}

resource "datadog_monitor" "node_cpu" {
  name    = "[smart-hospital ${var.env}] node CPU above 85%"
  type    = "query alert"
  message = "Node {{host.name}} CPU has been above 85% for 15 minutes. ${local.notify}"
  query   = "avg(last_15m):100 - avg:system.cpu.idle{kube_cluster_name:${var.cluster_name}} by {host} > 85"
  tags    = local.tags

  monitor_thresholds {
    critical = 85
    warning  = 70
  }
}

resource "datadog_monitor" "node_memory" {
  name    = "[smart-hospital ${var.env}] node memory above 85%"
  type    = "query alert"
  message = "Node {{host.name}} memory use has been above 85% for 15 minutes. ${local.notify}"
  query   = "avg(last_15m):100 - avg:system.mem.pct_usable{kube_cluster_name:${var.cluster_name}} by {host} * 100 > 85"
  tags    = local.tags

  monitor_thresholds {
    critical = 85
    warning  = 70
  }
}

resource "datadog_monitor" "error_logs" {
  name    = "[smart-hospital ${var.env}] error log spike"
  type    = "log alert"
  message = "{{service.name}} logged more than 20 errors in 5 minutes. ${local.notify}"
  query   = "logs(\"env:${var.env} kube_namespace:${var.namespace} status:error\").index(\"*\").rollup(\"count\").by(\"service\").last(\"5m\") > 20"
  tags    = local.tags

  monitor_thresholds {
    critical = 20
  }
}
