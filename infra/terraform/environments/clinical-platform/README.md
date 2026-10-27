# Clinical platform — AWS foundation (Terraform, us-east-1)

This Terraform root creates the AWS foundation for the six services: appointment, facility, identity, patient,
provider and scheduling. It reuses the shared modules in `../../modules`.

| Area | What is created | Module |
|---|---|---|
| Network | VPC `10.30.0.0/16` across 2 AZs. Contains 2 public and 2 private subnets, an Internet gateway, 1 NAT gateway (with an Elastic IP), a public route table, one private route table per AZ, and a default security group with all rules removed. | `vpc` |
| Security groups | An extra security group on the EKS control plane: HTTPS (443) from inside the VPC only. EKS also creates its own cluster security group, shared by the control plane and nodes. | `security-groups` |
| IAM | EKS cluster role (`AmazonEKSClusterPolicy`). Node role (`AmazonEKSWorkerNodePolicy`, `AmazonEKS_CNI_Policy`, `AmazonEC2ContainerRegistryReadOnly`). An OIDC provider so Kubernetes service accounts can use IAM roles (IRSA). | `iam`, `eks` |
| ECR | 6 private repositories, `clinical-platform/<service>`. Images are scanned on push, tags are immutable, and storage is AES-256 encrypted. A lifecycle policy expires untagged images after 7 days and keeps the 30 newest tagged images. | `ecr` |
| EKS | Cluster `clinical-platform-eks` (Kubernetes 1.34) in the private subnets, with Kubernetes secrets encrypted by a KMS key. A managed node group of t3.medium nodes (min 2, desired 2, max 3, AL2023). Add-ons: vpc-cni, kube-proxy and coredns. | `eks` |

## Credentials and account-specific values

Nothing secret or account-specific is in this code.

- **AWS credentials:** come from the standard chain: `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`, a profile, SSO or a role.
- **Account guard (optional):** pass it at runtime with `export TF_VAR_allowed_account_ids='["<account-id>"]'`.
- **Extra cluster admins (optional):** `export TF_VAR_eks_cluster_admin_principal_arns='["arn:aws:iam::<account-id>:role/<role>"]'`.
  The identity that creates the cluster is made cluster admin automatically.

## Usage

```bash
cd infra/terraform/environments/clinical-platform

# Remote state: create the state bucket once, then point init at it.
terraform -chdir=../../bootstrap init && terraform -chdir=../../bootstrap apply
terraform init -backend-config="bucket=$(terraform -chdir=../../bootstrap output -raw state_bucket_name)"

terraform fmt -check -recursive ../..
terraform validate
terraform plan -out=tfplan
terraform apply tfplan          # only after the plan has been reviewed and approved
$(terraform output -raw kubeconfig_command)
```

**Planning before the state bucket exists:** create a git-ignored `backend_override.tf` containing
`terraform { backend "local" {} }` and run `terraform init`. When the bucket exists, delete the override and run
`terraform init -migrate-state`.

## Cost and security notes

- **Billable resources:** EKS control plane, 2–3 t3.medium nodes, 1 NAT gateway plus its Elastic IP, a KMS key, and ECR storage.
- **Public API endpoint:** the Kubernetes API is public and open to `0.0.0.0/0` by default. Restrict
  `eks_endpoint_public_access_cidrs`, or set `eks_endpoint_public_access = false` and use a VPN or bastion.
- **Single NAT gateway:** if AZ `us-east-1a` fails, the private subnets lose outbound internet access. Set
  `single_nat_gateway = false` to run one NAT gateway per AZ.
- **Logging off:** EKS control-plane logging and VPC flow logs are off, following the repository's existing decision to
  use Datadog for monitoring.
