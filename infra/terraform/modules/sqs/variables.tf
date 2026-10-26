variable "name" {
  description = "Queue name (the dead-letter queue gets a -dlq suffix)."
  type        = string
}

variable "visibility_timeout_seconds" {
  description = "How long a received message stays hidden from other consumers."
  type        = number
  default     = 60
}

variable "message_retention_seconds" {
  description = "Retention of the main queue."
  type        = number
  default     = 345600
}

variable "max_receive_count" {
  description = "Receives before a message moves to the dead-letter queue."
  type        = number
  default     = 5
}
