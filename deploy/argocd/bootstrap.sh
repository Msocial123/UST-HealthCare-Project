#!/usr/bin/env bash
# One-time Argo CD install on the dev EKS cluster. After this, everything is delivered from Git:
# Argo CD syncs deploy/argocd/apps, which creates the External Secrets Operator, db-bootstrap and one
# Application per deploy/helm/*-service chart.
#
# Usage: deploy/argocd/bootstrap.sh [git-revision]   (default: main)
set -euo pipefail

ARGOCD_CHART_VERSION="10.11.6"
REVISION="${1:-main}"
HERE="$(cd "$(dirname "$0")" && pwd)"

helm repo add argo https://argoproj.github.io/argo-helm >/dev/null
helm repo update argo >/dev/null

helm upgrade --install argocd argo/argo-cd \
  --namespace argocd --create-namespace \
  --version "$ARGOCD_CHART_VERSION" \
  --values "$HERE/install-values.yaml" \
  --wait --timeout 10m

# REVISION other than main lets you test a feature branch before merging; re-run without an argument afterwards.
sed -e "s|targetRevision: main|targetRevision: ${REVISION}|" -e "s|value: main|value: ${REVISION}|" "$HERE/root-app.yaml" |
  kubectl apply -f -

echo "Argo CD is installed and following '${REVISION}'."
echo "UI: https://$(kubectl -n argocd get svc argocd-server -o jsonpath='{.status.loadBalancer.ingress[0].hostname}') (user: admin; self-signed certificate, DNS can take a few minutes)"
echo "Initial admin password: kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d"
