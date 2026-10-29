variable "name_prefix" {
  description = "Secret name prefix (for example smart-hospital/dev)."
  type        = string
}

variable "recovery_window_in_days" {
  description = "Days a deleted secret can still be restored (0 deletes immediately)."
  type        = number
  default     = 7
}
