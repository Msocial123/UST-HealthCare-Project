#!/usr/bin/env bash
# Deploys the six services to the clinical-platform namespace.
# Usage: IMAGE_TAG=<git short sha> ./deploy.sh   (needs kubectl context for clinical-platform-eks and AWS credentials)
set -euo pipefail
NS=clinical-platform
REGION=${REGION:-us-east-1}
IMAGE_TAG=${IMAGE_TAG:?set IMAGE_TAG to the pushed ECR image tag}
ACCOUNT_ID=${ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}
REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICES=(identity patient provider facility scheduling appointment)
rand() { python3 -c 'import secrets; print(secrets.token_hex(32))'; }

kubectl apply -f "$DIR/namespace.yaml"

# Secrets are generated once in-cluster and never written to disk or git.
if ! kubectl -n "$NS" get secret clinical-platform-jwt >/dev/null 2>&1; then
  kubectl -n "$NS" create secret generic clinical-platform-jwt --from-literal=JWT_SECRET_KEY="$(rand)"
fi
if ! kubectl -n "$NS" get secret clinical-platform-db >/dev/null 2>&1; then
  args=(--from-literal=POSTGRES_PASSWORD="$(rand)")
  for s in "${SERVICES[@]}"; do
    pw="$(rand)"
    args+=(--from-literal="${s}-password=${pw}" --from-literal="${s}-database-url=postgresql+psycopg://${s}_user:${pw}@postgres:5432/${s}")
  done
  kubectl -n "$NS" create secret generic clinical-platform-db "${args[@]}"
fi

kubectl apply -f "$DIR/config.yaml" -f "$DIR/postgres.yaml"
kubectl -n "$NS" rollout status deploy/postgres --timeout=180s

for s in "${SERVICES[@]}"; do
  sed -e "s#IMAGE_REGISTRY#${REGISTRY}#g" -e "s#IMAGE_TAG#${IMAGE_TAG}#g" "$DIR/${s}-service.yaml" | kubectl apply -f -
done
for s in "${SERVICES[@]}"; do
  kubectl -n "$NS" rollout status "deploy/${s}-service" --timeout=300s
done
