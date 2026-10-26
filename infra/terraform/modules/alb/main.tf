resource "aws_security_group" "alb" {
  name        = "${var.name}-alb-sg"
  description = "Public HTTPS entry point"
  vpc_id      = var.vpc_id

  tags = { Name = "${var.name}-alb-sg" }
}

resource "aws_vpc_security_group_ingress_rule" "alb" {
  for_each = { for pair in setproduct([80, 443], var.ingress_cidrs) : "${pair[0]}-${pair[1]}" => pair }

  security_group_id = aws_security_group.alb.id
  cidr_ipv4         = each.value[1]
  ip_protocol       = "tcp"
  from_port         = each.value[0]
  to_port           = each.value[0]
  description       = each.value[0] == 80 ? "HTTP (redirected to HTTPS)" : "HTTPS"
}

resource "aws_vpc_security_group_egress_rule" "alb_to_nodes" {
  for_each = var.services

  security_group_id            = aws_security_group.alb.id
  referenced_security_group_id = var.node_security_group_id
  ip_protocol                  = "tcp"
  from_port                    = each.value.node_port
  to_port                      = each.value.node_port
  description                  = "${each.key} NodePort"
}

resource "aws_vpc_security_group_ingress_rule" "nodes_from_alb" {
  for_each = var.services

  security_group_id            = var.node_security_group_id
  referenced_security_group_id = aws_security_group.alb.id
  ip_protocol                  = "tcp"
  from_port                    = each.value.node_port
  to_port                      = each.value.node_port
  description                  = "ALB to ${each.key} NodePort"
}

resource "aws_lb" "this" {
  name               = "${var.name}-alb"
  load_balancer_type = "application"
  internal           = false
  security_groups    = [aws_security_group.alb.id]
  subnets            = var.public_subnet_ids

  drop_invalid_header_fields = true
  enable_deletion_protection = var.deletion_protection
}

resource "aws_lb_target_group" "service" {
  for_each = var.services

  name                 = trimsuffix(substr("${var.name}-${trimsuffix(each.key, "-service")}", 0, 32), "-")
  port                 = each.value.node_port
  protocol             = "HTTP"
  target_type          = "instance"
  vpc_id               = var.vpc_id
  deregistration_delay = 30

  health_check {
    path                = each.value.health_check_path
    matcher             = "200"
    interval            = 15
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
}

resource "aws_autoscaling_attachment" "service" {
  for_each = var.services

  autoscaling_group_name = var.node_autoscaling_group_name
  lb_target_group_arn    = aws_lb_target_group.service[each.key].arn
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"

    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.this.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = var.ssl_policy
  certificate_arn   = var.certificate_arn

  default_action {
    type = "fixed-response"

    fixed_response {
      content_type = "application/json"
      status_code  = "404"
      message_body = jsonencode({ error = { code = "not_found", message = "No route", details = [] } })
    }
  }
}

resource "aws_lb_listener_rule" "service" {
  for_each = var.services

  listener_arn = aws_lb_listener.https.arn
  priority     = each.value.priority

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.service[each.key].arn
  }

  condition {
    path_pattern {
      values = each.value.path_patterns
    }
  }
}

resource "aws_route53_record" "alb" {
  zone_id = var.zone_id
  name    = var.dns_name
  type    = "A"

  alias {
    name                   = aws_lb.this.dns_name
    zone_id                = aws_lb.this.zone_id
    evaluate_target_health = true
  }
}
