resource "aws_acm_certificate" "this" {
  domain_name               = var.domain_name
  subject_alternative_names = var.subject_alternative_names
  validation_method         = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

locals {
  # Keyed by the configured names (known at plan time), not by the computed validation options.
  validation_options = { for o in aws_acm_certificate.this.domain_validation_options : o.domain_name => o }
}

resource "aws_route53_record" "validation" {
  for_each = toset(concat([var.domain_name], var.subject_alternative_names))

  zone_id         = var.zone_id
  name            = local.validation_options[each.key].resource_record_name
  type            = local.validation_options[each.key].resource_record_type
  records         = [local.validation_options[each.key].resource_record_value]
  ttl             = 60
  allow_overwrite = true
}

resource "aws_acm_certificate_validation" "this" {
  certificate_arn         = aws_acm_certificate.this.arn
  validation_record_fqdns = [for r in aws_route53_record.validation : r.fqdn]
}
