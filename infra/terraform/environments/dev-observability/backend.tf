# Separate state from environments/dev so the AWS stack never needs Datadog keys. Same bucket, S3 native locking:
#   terraform init -backend-config="bucket=$(terraform -chdir=../../bootstrap output -raw state_bucket_name)"
terraform {
  backend "s3" {
    key          = "smart-hospital/dev-observability/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }
}
