# Deployment (GitOps)

```
git push ──► GitHub Actions (build-push.yml) ──► ECR  smart-hospital/<service>:<sha12>
                 │
                 └─► commits image.tag to deploy/helm/<service>/dev-values.yaml
                                       │
Argo CD (polls Git every ~3 min) ◄─────┘──► EKS namespace smart-hospital ──► Terraform ALB (NodePorts 30081-30086)
```

| Path | What it is |
|---|---|
| `helm/microservice/` | Library chart shared by all services: Deployment, NodePort Service, IRSA ServiceAccount, ConfigMap, ExternalSecret, Alembic migration Job |
| `helm/<service>/values.yaml` | Stable definition of the service (port, NodePort, probes, resources, common env). Not touched by rollouts |
| `helm/<service>/dev-values.yaml` | dev overrides: **image tag**, replicas, IAM role, Secrets Manager names, feature flags |
| `helm/db-bootstrap/` | Job that creates each service's PostgreSQL role and database on RDS (idempotent) |
| `argocd/install-values.yaml`, `argocd/bootstrap.sh` | One-time Argo CD install |
| `argocd/root-app.yaml` | App of apps, points Argo CD at `argocd/apps` |
| `argocd/apps/` | External Secrets Operator, db-bootstrap, and an ApplicationSet with one Application per `helm/*-service` folder |

All Applications sync automatically with `prune` and `selfHeal`: manual changes in the cluster are reverted to what Git says.

## Services

| Service | Port | NodePort | Calls |
|---|---|---|---|
| identity-service | 8001 | 30081 | |
| patient-service | 8002 | 30082 | |
| provider-service | 8003 | 30083 | |
| facility-service | 8004 | 30084 | |
| scheduling-service | 8005 | 30085 | `http://facility-service:8004` |
| appointment-service | 8006 | 30086 | `http://scheduling-service:8005` |

Services call each other by Kubernetes Service DNS name. External traffic enters through the Terraform ALB
(`terraform output alb_dns_name`), which routes `/api/v1/...` paths to each service's NodePort.
encounter-service and notification-service have AWS resources but no code yet; add `services/<name>/` and
`deploy/helm/<name>/` and the ApplicationSet picks them up.

## Secrets

No secret is stored in Git. The External Secrets Operator reads, through each service account's IAM role (IRSA),
`smart-hospital/dev/<service>/database` and `smart-hospital/dev/shared/jwt-signing-key` from AWS Secrets Manager
and writes the Kubernetes Secret `<service>-env` (`DATABASE_URL`, `JWT_SECRET_KEY`, `JWT_KEY_ID`).
GitHub Actions authenticates to AWS with OIDC (`smart-hospital-dev-github-actions`); there are no AWS keys in GitHub.

## Rollout and rollback

- **Rollout:** merge a change under `services/<service>/` to `main`. CI builds `<sha12>`, pushes it to ECR and
  sets `image.tag` in that service's `dev-values.yaml`. Argo CD runs the migration Job, then rolls the Deployment
  (`maxUnavailable: 0`). To roll out by hand, edit `image.tag` in `dev-values.yaml` and merge.
- **Rollback:** `git revert <the deploy(dev) commit>` (or set `image.tag` back to an earlier tag) and merge.
  Argo CD syncs the old image. Migrations are not downgraded automatically; run `alembic downgrade` deliberately
  if a schema change must be undone.
- Replicas and feature flags (`APPOINTMENTS_ENABLED`, `SCHEDULING_ADVICE_ENABLED`) are changed the same way, in `dev-values.yaml`.

## First-time setup

1. `infra/terraform/bootstrap`, then `infra/terraform/environments/dev`: `terraform apply`.
2. Put `terraform output -raw rds_master_user_secret_arn` into `helm/db-bootstrap/dev-values.yaml` (`masterSecret`).
3. Build and push the first images: run the **Build and push images** workflow with `all` (or push from a workstation).
4. `aws eks update-kubeconfig --name smart-hospital-dev-eks --region us-east-1`, then `deploy/argocd/bootstrap.sh`
   (pass a branch name to follow a branch other than `main`).
5. Argo CD UI (not exposed publicly): `kubectl -n argocd port-forward svc/argocd-server 8080:443`, open
   https://localhost:8080, user `admin`, password from the `argocd-initial-admin-secret` Secret.

## Check locally

```
for c in helm/*-service; do helm dependency build $c; helm lint $c -f $c/dev-values.yaml; done
helm template patient-service helm/patient-service -f helm/patient-service/dev-values.yaml
```
