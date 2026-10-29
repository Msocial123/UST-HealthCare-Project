locals {
  services = toset(var.services)
  tags     = concat(var.tags, ["env:${var.env}"])
}

# Availability SLI = (requests - 5xx errors) / requests, from APM trace metrics (/health probes are dropped by the trace agent).
resource "datadog_service_level_objective" "availability" {
  for_each = local.services

  name        = "${each.key} availability"
  type        = "metric"
  description = "Share of ${each.key} HTTP requests that did not fail with a 5xx error."
  tags        = concat(local.tags, ["service:${each.key}", "sli:availability"])

  query {
    numerator   = "sum:trace.fastapi.request.hits{env:${var.env},service:${each.key}}.as_count() - sum:trace.fastapi.request.errors{env:${var.env},service:${each.key}}.as_count()"
    denominator = "sum:trace.fastapi.request.hits{env:${var.env},service:${each.key}}.as_count()"
  }

  thresholds {
    timeframe = "30d"
    target    = var.availability_target
  }

  thresholds {
    timeframe = "7d"
    target    = var.availability_target
  }
}

# Latency SLI = share of 5-minute slices in which p95 request duration stays under the threshold.
resource "datadog_service_level_objective" "latency" {
  for_each = local.services

  name        = "${each.key} latency p95 <= ${var.latency_threshold_ms}ms"
  type        = "time_slice"
  description = "Share of 5-minute windows in which ${each.key} p95 latency was at most ${var.latency_threshold_ms} ms."
  tags        = concat(local.tags, ["service:${each.key}", "sli:latency"])

  sli_specification {
    time_slice {
      comparator             = "<="
      threshold              = var.latency_threshold_ms / 1000
      query_interval_seconds = 300
      query {
        formula {
          formula_expression = "query1"
        }
        query {
          metric_query {
            name  = "query1"
            query = "p95:trace.fastapi.request{env:${var.env},service:${each.key}}"
          }
        }
      }
    }
  }

  thresholds {
    timeframe = "30d"
    target    = var.latency_target
  }

  thresholds {
    timeframe = "7d"
    target    = var.latency_target
  }
}
