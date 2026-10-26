variable "name_prefix" {
  description = "Secret name prefix (for example smart-hospital/dev)."
  type        = string
}

variable "service_databases" {
  description = "Map of service name to its database name and login role name."
  type = map(object({
    db_name     = string
    db_username = string
  }))
}

variable "db_host" {
  description = "RDS host name written into each service's credentials secret."
  type        = string
}

variable "db_port" {
  description = "RDS port."
  type        = number
}

variable "recovery_window_in_days" {
  description = "Days a deleted secret can still be restored (0 deletes immediately)."
  type        = number
  default     = 7
}
