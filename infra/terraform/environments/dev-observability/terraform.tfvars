datadog_api_url = "https://api.datadoghq.com/"

env          = "dev"
cluster_name = "smart-hospital-dev-eks"
namespace    = "smart-hospital"

services = [
  "identity-service",
  "patient-service",
  "provider-service",
  "facility-service",
  "scheduling-service",
  "appointment-service",
]

availability_target  = 99.5
latency_threshold_ms = 500
latency_target       = 99.5
sla_target           = 99.0

# Add handles such as "@team@example.com" or "@slack-channel" to get notified.
notify = []
