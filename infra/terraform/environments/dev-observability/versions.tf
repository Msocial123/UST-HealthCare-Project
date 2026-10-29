terraform {
  required_version = ">= 1.10.0"

  required_providers {
    datadog = {
      source  = "DataDog/datadog"
      version = "~> 3.60"
    }
  }
}
