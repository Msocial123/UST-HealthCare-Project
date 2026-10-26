variable "domain_name" {
  description = "Primary certificate domain (for example api.dev.example.com)."
  type        = string
}

variable "subject_alternative_names" {
  description = "Extra names on the certificate."
  type        = list(string)
  default     = []
}

variable "zone_id" {
  description = "Route 53 hosted zone ID used for DNS validation."
  type        = string
}
