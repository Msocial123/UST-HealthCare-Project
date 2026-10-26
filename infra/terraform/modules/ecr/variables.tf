variable "name_prefix" {
  description = "Repository name prefix; each repository is <name_prefix>/<service>."
  type        = string
}

variable "repository_names" {
  description = "Service names; one ECR repository is created per name."
  type        = set(string)
}

variable "image_tag_mutability" {
  description = "MUTABLE or IMMUTABLE. IMMUTABLE stops a pushed tag (for example a git SHA) from being overwritten."
  type        = string
  default     = "IMMUTABLE"

  validation {
    condition     = contains(["MUTABLE", "IMMUTABLE"], var.image_tag_mutability)
    error_message = "image_tag_mutability must be MUTABLE or IMMUTABLE."
  }
}

variable "max_tagged_images" {
  description = "Number of most recent tagged images kept per repository."
  type        = number
  default     = 30
}

variable "untagged_image_expiry_days" {
  description = "Days after which untagged images are deleted."
  type        = number
  default     = 7
}

variable "force_delete" {
  description = "Allow terraform destroy to delete repositories that still contain images."
  type        = bool
  default     = false
}
