# Remote state in S3 with S3 native state locking (a <key>.tflock object, Terraform >= 1.10).
# Backend blocks cannot read variables, so the account-specific bucket name is passed at init:
#   terraform init -backend-config="bucket=$(terraform -chdir=../../bootstrap output -raw state_bucket_name)"
terraform {
  backend "s3" {
    key          = "smart-hospital/dev/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }
}
