# Smart Hospital - Terraform infrastructure (AWS, us-east-1)

Terraform for the AWS architecture in the Smart Hospital diagram: 8 FastAPI microservices on Amazon EKS, behind an
HTTPS Application Load Balancer, with one Amazon RDS for PostgreSQL instance holding a separate database and login per service.

**Not created on purpose:** CloudWatch (logs, metrics, alarms), Container Insights, X-Ray, VPC Flow Logs, RDS
Performance Insights/Enhanced Monitoring/log exports, EKS control-plane logging and WAF CloudWatch metrics. Monitoring
is handled by Datadog, which is set up separately.

## Layout

```
infra/terraform/
├── bootstrap/              # one-time: S3 bucket for remote state (local state)
├── environments/
│   └── dev/                # dev root module: backend.tf, main.tf, variables.tf, outputs.tf, terraform.tfvars
└── modules/
    ├── vpc/                # VPC 10.20.0.0/16, public / private-app / private-db subnets in 2 AZs, IGW, NAT gateway
    ├── iam/                # EKS cluster role and worker node role
    ├── eks/                # EKS cluster, managed node group (t3.medium, min 2 / max 3), add-ons, IRSA OIDC provider, KMS
    ├── ecr/                # 8 ECR repositories (scan on push, immutable tags, lifecycle policy)
    ├── rds/                # RDS for PostgreSQL (single-AZ, encrypted, TLS forced, master password managed in Secrets Manager)
    ├── secrets/            # Secrets Manager: per-service DB credentials + shared JWT signing key
    ├── service-irsa/       # one IAM role per service, bound to its Kubernetes service account
    ├── github-oidc/        # GitHub Actions OIDC role: push to ECR, deploy to the app namespace in EKS
    ├── acm/                # ACM certificate with Route 53 DNS validation
    ├── alb/                # internet-facing ALB, HTTP->HTTPS redirect, path routing to each service, Route 53 alias
    ├── waf/                # AWS WAF (managed rule groups + per-IP rate limit)            [optional]
    ├── sqs/                # notification queue + dead-letter queue                       [optional]
    ├── ses/                # SES domain identity with DKIM records                        [optional]
    └── s3/                 # shared-files bucket                                          [optional]
```

Every input of the dev environment is set in `environments/dev/terraform.tfvars`.

## Remote state and locking

- State is stored in the S3 bucket `smart-hospital-tfstate-<account-id>-us-east-1` (versioned, encrypted, public access
  blocked, TLS-only bucket policy, old versions expire after 90 days), under the key `smart-hospital/dev/terraform.tfstate`.
- Locking uses **S3 native state locking** (`use_lockfile = true`, Terraform >= 1.10): Terraform writes
  `<key>.tflock` with a conditional write, so a second `plan`/`apply` waits or fails instead of corrupting state.
  HashiCorp has deprecated DynamoDB-based locking, so no DynamoDB table is created.
- A backend block cannot read variables, so the account-specific bucket name is passed with `-backend-config` at init.

## Prerequisites

- Terraform >= 1.10 (validated with 1.17.0), AWS CLI v2, kubectl.
- AWS credentials for the target account with permission to create the resources above.
- An existing **public Route 53 hosted zone** in the account (needed for the ACM certificate, the API record and SES).

## First-time setup

```bash
# 1. Create the state bucket (once per AWS account)
cd infra/terraform/bootstrap
terraform init
terraform apply

# 2. Edit the CHANGE ME values in environments/dev/terraform.tfvars:
#    hosted_zone_name, allowed_account_ids, eks_endpoint_public_access_cidrs (and optionally eks_cluster_admin_principal_arns)

# 3. Initialise the dev environment against the remote backend
cd ../environments/dev
terraform init -backend-config="bucket=$(terraform -chdir=../../bootstrap output -raw state_bucket_name)"

# 4. Plan and apply (terraform.tfvars is loaded automatically)
terraform plan -out=tfplan
terraform apply tfplan

# 5. kubectl access
$(terraform output -raw kubeconfig_command)
```

Keep the bootstrap `terraform.tfstate` file safe (it is git-ignored) or migrate it into the bucket afterwards.

## How the application plugs in

- **Images:** push to the URLs in `terraform output ecr_repository_urls` (`smart-hospital/<service>`). Tags are
  immutable; tag with the git SHA.
- **CI/CD:** GitHub Actions assumes `terraform output github_actions_role_arn` through OIDC (no stored AWS keys).
  It may push to the 8 repositories and has the EKS edit policy in the `smart-hospital` namespace only. Allowed
  branches are set by `github_allowed_subjects`.
- **Kubernetes Services:** each service is exposed as `type: NodePort` on the port in
  `terraform output service_node_ports` (container port 8000). The ALB target groups use the worker node Auto Scaling
  group and health-check `/health`. No AWS Load Balancer Controller is needed.

  | Service | NodePort | ALB paths |
  |---|---|---|
  | identity-service | 30081 | `/api/v1/auth*`, `/api/v1/users*`, `/api/v1/roles*`, `/api/v1/identity*` |
  | patient-service | 30082 | `/api/v1/patients*` |
  | provider-service | 30083 | `/api/v1/providers*`, `/api/v1/specialties*` |
  | facility-service | 30084 | `/api/v1/facilities*`, `/api/v1/departments*` |
  | scheduling-service | 30085 | `/api/v1/providers/*/working-hours*`, `/api/v1/providers/*/exceptions*`, `/api/v1/providers/*/slots*`, `/api/v1/working-hours*`, `/api/v1/exceptions*` (evaluated before provider-service) |
  | appointment-service | 30086 | `/api/v1/appointments*` |
  | encounter-service | 30087 | `/api/v1/encounters*`, `/api/v1/visits*` |
  | notification-service | 30088 | `/api/v1/notifications*` |

- **Secrets:** each service's Kubernetes service account (named after the service, in `smart-hospital`) is annotated
  with `eks.amazonaws.com/role-arn: <terraform output service_role_arns[service]>`. That role can read only
  `smart-hospital/dev/<service>/database` and `smart-hospital/dev/shared/jwt-signing-key`. notification-service also
  gets SQS and SES send permissions.
- **Databases:** Terraform creates the RDS instance and one credentials secret per service, but it cannot reach the
  private database to run SQL. Create each database and login once from inside the cluster, using the master
  credentials (`terraform output rds_master_user_secret_arn`) and the values in each service secret:

  ```sql
  CREATE ROLE identity_service LOGIN PASSWORD '<password from smart-hospital/dev/identity-service/database>';
  CREATE DATABASE identity_db OWNER identity_service;
  REVOKE ALL ON DATABASE identity_db FROM PUBLIC;
  -- repeat for each service (role = service name with "_", database = db_name in terraform.tfvars)
  ```

  Then run each service's `alembic upgrade head` against its own database.

## Cost and safety notes (dev)

- Billable resources: EKS control plane, 2-3 t3.medium nodes, 1 NAT gateway, ALB, db.t3.micro RDS, WAF web ACL and
  rules, Secrets Manager secrets, KMS key. Set `enable_waf`, `enable_sqs`, `enable_ses` or `enable_shared_bucket` to
  `false` to skip the optional services.
- `rds_deletion_protection = true` and a final snapshot is taken on destroy. To tear dev down, first set
  `rds_deletion_protection = false` and apply.
- Generated passwords and the JWT key live in Secrets Manager **and** in Terraform state; the state bucket must stay
  private. Rotate them with `terraform apply -replace=...` on the matching `random_password`.
- The EKS public endpoint and the ALB are reachable from `0.0.0.0/0` by default; narrow
  `eks_endpoint_public_access_cidrs` and `alb_ingress_cidrs` where possible.
- SES starts in the sandbox (only verified recipients) until production access is requested.

## Checks

```bash
terraform fmt -check -recursive infra/terraform
terraform -chdir=infra/terraform/environments/dev init -backend=false && terraform -chdir=infra/terraform/environments/dev validate
terraform -chdir=infra/terraform/bootstrap init -backend=false && terraform -chdir=infra/terraform/bootstrap validate
```
