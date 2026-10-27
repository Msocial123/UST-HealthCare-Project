# Remote state in S3 with S3 native state locking (Terraform >= 1.10). The bucket is created by ../../bootstrap.
# Backend blocks cannot read variables, so the account-specific bucket name is passed at init:
#   terraform init -backend-config="bucket=$(terraform -chdir=../../bootstrap output -raw state_bucket_name)"
terraform {
  backend "s3" {
    key          = "clinical-platform/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }
}
