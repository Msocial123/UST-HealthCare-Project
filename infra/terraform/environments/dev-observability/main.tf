module "observability" {
  source = "../../modules/datadog-observability"

  env                  = var.env
  cluster_name         = var.cluster_name
  namespace            = var.namespace
  services             = var.services
  availability_target  = var.availability_target
  latency_threshold_ms = var.latency_threshold_ms
  latency_target       = var.latency_target
  sla_target           = var.sla_target
  notify               = var.notify
  tags                 = ["project:smart-hospital", "managed-by:terraform"]
}
