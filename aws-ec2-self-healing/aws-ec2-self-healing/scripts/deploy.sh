#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../terraform"
[ -f terraform.tfvars ] || { echo "Copy terraform.tfvars.example to terraform.tfvars first"; exit 1; }
terraform init
terraform validate
terraform apply
