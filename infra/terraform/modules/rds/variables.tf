variable "identifier" {
  description = "RDS instance identifier."
  type        = string
}

variable "vpc_id" {
  description = "VPC ID."
  type        = string
}

variable "subnet_ids" {
  description = "Private database subnet IDs (at least two AZs)."
  type        = list(string)
}

variable "allowed_security_group_ids" {
  description = "Security groups allowed to connect on the PostgreSQL port (the EKS cluster/node security group)."
  type        = list(string)
}

variable "engine_version" {
  description = "PostgreSQL engine version (major, or major.minor)."
  type        = string
  default     = "16"
}

variable "instance_class" {
  description = "RDS instance class."
  type        = string
  default     = "db.t3.micro"
}

variable "allocated_storage" {
  description = "Initial storage, in GiB."
  type        = number
  default     = 20
}

variable "max_allocated_storage" {
  description = "Storage autoscaling ceiling, in GiB (0 disables storage autoscaling)."
  type        = number
  default     = 50
}

variable "multi_az" {
  description = "Run a standby in a second AZ."
  type        = bool
  default     = false
}

variable "master_username" {
  description = "Master user name. Its password is generated and stored in Secrets Manager by RDS."
  type        = string
  default     = "sh_admin"
}

variable "port" {
  description = "PostgreSQL port."
  type        = number
  default     = 5432
}

variable "backup_retention_period" {
  description = "Days of automated backups."
  type        = number
  default     = 7
}

variable "deletion_protection" {
  description = "Block deletion of the instance."
  type        = bool
  default     = true
}

variable "skip_final_snapshot" {
  description = "Skip the final snapshot on destroy. Keep false unless losing the data is acceptable."
  type        = bool
  default     = false
}
