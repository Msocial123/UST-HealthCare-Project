#!/usr/bin/env bash
# Installs the AWS Load Balancer Controller into kube-system using the IRSA role from
# infra/terraform/environments/clinical-platform (output lb_controller_role_arn).
# Needs helm, kubectl context for clinical-platform-eks and AWS credentials.
set -euo pipefail
CLUSTER=${CLUSTER:-clinical-platform-eks}
REGION=${REGION:-us-east-1}
CHART_VERSION=${CHART_VERSION:-3.6.2}
TF_DIR="$(cd "$(dirname "$0")/../../terraform/environments/clinical-platform" && pwd)"
ROLE_ARN=${LB_CONTROLLER_ROLE_ARN:-$(terraform -chdir="$TF_DIR" output -raw lb_controller_role_arn)}
VPC_ID=$(aws eks describe-cluster --name "$CLUSTER" --region "$REGION" --query cluster.resourcesVpcConfig.vpcId --output text)

helm repo add eks https://aws.github.io/eks-charts >/dev/null 2>&1 || true
helm repo update eks >/dev/null
helm upgrade --install aws-load-balancer-controller eks/aws-load-balancer-controller \
  --namespace kube-system \
  --version "$CHART_VERSION" \
  --set clusterName="$CLUSTER" \
  --set region="$REGION" \
  --set vpcId="$VPC_ID" \
  --set serviceAccount.create=true \
  --set serviceAccount.name=aws-load-balancer-controller \
  --set serviceAccount.annotations."eks\.amazonaws\.com/role-arn"="$ROLE_ARN" \
  --wait --timeout 5m
kubectl -n kube-system rollout status deploy/aws-load-balancer-controller --timeout=180s
