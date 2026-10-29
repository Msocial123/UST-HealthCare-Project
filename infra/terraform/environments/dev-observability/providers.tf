# Keys come from the environment, never from tfvars: DD_API_KEY and DD_APP_KEY.
provider "datadog" {
  api_url = var.datadog_api_url
}
