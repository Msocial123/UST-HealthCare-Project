variable "name" {
  description = "Name prefix (for example smart-hospital-dev). ALB and target group names are limited to 32 characters."
  type        = string
}

variable "vpc_id" {
  description = "VPC ID."
  type        = string
}

variable "public_subnet_ids" {
  description = "Public subnets for the internet-facing ALB."
  type        = list(string)
}

variable "ingress_cidrs" {
  description = "CIDRs allowed to reach the ALB on 80/443."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "enable_https" {
  description = "Serve HTTPS with certificate_arn and create the Route 53 alias. When false, the routes are served on plain HTTP at the ALB DNS name."
  type        = bool
  default     = true
}

variable "certificate_arn" {
  description = "ACM certificate for the HTTPS listener (required when enable_https)."
  type        = string
  default     = null
}

variable "ssl_policy" {
  description = "TLS policy of the HTTPS listener."
  type        = string
  default     = "ELBSecurityPolicy-TLS13-1-2-2021-06"
}

variable "node_security_group_id" {
  description = "Security group of the EKS worker nodes; the ALB is allowed in on each service NodePort."
  type        = string
}

variable "node_autoscaling_group_name" {
  description = "Auto Scaling group of the EKS managed node group; nodes are registered in every target group."
  type        = string
}

variable "services" {
  description = "Routing per service: Kubernetes NodePort, ALB path patterns (max 5), listener rule priority (lower wins) and health check path."
  type = map(object({
    node_port         = number
    path_patterns     = list(string)
    priority          = number
    health_check_path = optional(string, "/health")
  }))

  validation {
    condition     = alltrue([for s in values(var.services) : s.node_port >= 30000 && s.node_port <= 32767])
    error_message = "node_port must be in the Kubernetes NodePort range 30000-32767."
  }

  validation {
    condition     = alltrue([for s in values(var.services) : length(s.path_patterns) >= 1 && length(s.path_patterns) <= 5])
    error_message = "Each service needs 1 to 5 path patterns (ALB limit per rule)."
  }
}

variable "zone_id" {
  description = "Route 53 hosted zone for the alias record (required when enable_https)."
  type        = string
  default     = null
}

variable "dns_name" {
  description = "DNS name pointed at the ALB, for example api.dev.example.com (required when enable_https)."
  type        = string
  default     = null
}

variable "deletion_protection" {
  description = "Block deletion of the ALB."
  type        = bool
  default     = false
}
