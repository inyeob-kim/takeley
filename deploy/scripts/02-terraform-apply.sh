#!/usr/bin/env bash
# Step 2–5: terraform apply (SG, RDS, EC2+EIP, Route53 api/admin A records)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TF="$ROOT/terraform"
cd "$TF"

if ! command -v terraform >/dev/null 2>&1; then
  echo "ERROR: terraform not found. Install from https://developer.hashicorp.com/terraform/install"
  exit 1
fi

if ! command -v aws >/dev/null 2>&1; then
  echo "ERROR: aws CLI not found / not configured."
  exit 1
fi

if [[ ! -f terraform.tfvars ]]; then
  echo "ERROR: missing $TF/terraform.tfvars"
  echo "Copy terraform.tfvars.example → terraform.tfvars and set domain_name, ssh_*, email."
  exit 1
fi

terraform init
terraform plan -out=tfplan
terraform apply tfplan

echo ""
echo "== Outputs (sensitive DB URL redacted in UI; use -raw) =="
terraform output app_public_ip
terraform output api_host
terraform output admin_host
terraform output rds_endpoint
echo "DATABASE_URL=$(terraform output -raw database_url)"
echo ""
echo "Next: scripts/03-deploy-app.sh <ssh-key> \$(terraform output -raw app_public_ip)"
