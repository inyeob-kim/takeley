#!/usr/bin/env bash
# Step 1 helper: verify domain + Route 53 hosted zone after Amazon Registrar purchase.
set -euo pipefail

DOMAIN="${1:-}"
if [[ -z "$DOMAIN" ]]; then
  echo "Usage: $0 <domain>   e.g. $0 takeley.app"
  exit 1
fi

if ! command -v aws >/dev/null 2>&1; then
  echo "ERROR: aws CLI not found. Install: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
  echo "Then: aws configure  (region ap-northeast-2)"
  exit 1
fi

echo "== Caller =="
aws sts get-caller-identity

echo "== Registered domains (may be empty if still propagating) =="
aws route53domains list-domains --region us-east-1 --query "Domains[?DomainName=='$DOMAIN']" --output table || true

echo "== Hosted zones matching $DOMAIN =="
aws route53 list-hosted-zones-by-name --dns-name "$DOMAIN" \
  --query "HostedZones[?Name=='${DOMAIN}.']" --output table

ZONE_ID=$(aws route53 list-hosted-zones-by-name --dns-name "$DOMAIN" \
  --query "HostedZones[?Name=='${DOMAIN}.'].Id" --output text | head -1 | sed 's|/hostedzone/||')

if [[ -z "$ZONE_ID" || "$ZONE_ID" == "None" ]]; then
  echo "FAIL: No public hosted zone for $DOMAIN yet."
  echo "In AWS Console (Seoul or global Route 53): confirm Registrar purchase and that a hosted zone exists."
  exit 2
fi

echo "OK: hosted zone id=$ZONE_ID"
aws route53 get-hosted-zone --id "$ZONE_ID" --query 'DelegationSet.NameServers' --output table
echo "Next: fill deploy/terraform/terraform.tfvars and run scripts/02-terraform-apply.sh"
