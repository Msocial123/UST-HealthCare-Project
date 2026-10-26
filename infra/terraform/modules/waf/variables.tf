variable "name" {
  description = "Web ACL name."
  type        = string
}

variable "resource_arn" {
  description = "ARN of the ALB to protect."
  type        = string
}

variable "rate_limit_per_5_minutes" {
  description = "Requests per source IP per 5 minutes before the IP is blocked."
  type        = number
  default     = 2000
}

variable "managed_rule_groups" {
  description = "AWS managed rule groups, in evaluation order."
  type        = list(string)
  default = [
    "AWSManagedRulesAmazonIpReputationList",
    "AWSManagedRulesCommonRuleSet",
    "AWSManagedRulesKnownBadInputsRuleSet",
    "AWSManagedRulesSQLiRuleSet",
  ]
}
