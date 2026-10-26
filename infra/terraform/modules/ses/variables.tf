variable "domain" {
  description = "Sending domain to verify in SES (for example dev.example.com)."
  type        = string
}

variable "zone_id" {
  description = "Route 53 hosted zone that serves the domain (DKIM records are created there)."
  type        = string
}
