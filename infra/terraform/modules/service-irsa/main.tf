# One IAM role per microservice, assumable only by that service's Kubernetes service account.

data "aws_iam_policy_document" "assume" {
  for_each = var.services

  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [var.oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${var.oidc_issuer}:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "${var.oidc_issuer}:sub"
      values   = ["system:serviceaccount:${var.namespace}:${each.key}"]
    }
  }
}

resource "aws_iam_role" "service" {
  for_each = var.services

  name               = "${var.name}-${each.key}"
  assume_role_policy = data.aws_iam_policy_document.assume[each.key].json
}

data "aws_iam_policy_document" "service" {
  for_each = var.services

  statement {
    sid       = "ReadOwnSecrets"
    actions   = ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"]
    resources = each.value.secret_arns
  }

  dynamic "statement" {
    for_each = each.value.extra_statements

    content {
      sid       = statement.value.sid
      actions   = statement.value.actions
      resources = statement.value.resources
    }
  }
}

resource "aws_iam_role_policy" "service" {
  for_each = var.services

  name   = "service-access"
  role   = aws_iam_role.service[each.key].id
  policy = data.aws_iam_policy_document.service[each.key].json
}
