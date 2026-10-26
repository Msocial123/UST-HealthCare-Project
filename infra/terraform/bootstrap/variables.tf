variable "aws_region" {
  description = "AWS region for the Terraform state bucket."
  type        = string
}

variable "project_name" {
  description = "Project name, used as the state bucket name prefix."
  type        = string
}

variable "noncurrent_version_retention_days" {
  description = "Days to keep superseded state file versions before they expire."
  type        = number
  default     = 90
}
