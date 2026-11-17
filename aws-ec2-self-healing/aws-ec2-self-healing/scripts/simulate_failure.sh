#!/usr/bin/env bash
# Stops NGINX on the instance so the whole self-healing chain fires.
# Usage: ./simulate_failure.sh <instance-id> [region]
set -euo pipefail
INSTANCE_ID="${1:?Usage: $0 <instance-id> [region]}"
REGION="${2:-ap-south-1}"

aws ssm send-command \
  --region "$REGION" \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["systemctl stop nginx"]' \
  --comment "Chaos test: stop nginx" \
  --query "Command.CommandId" --output text

echo "NGINX stopped. Expect: alarm in ~2-3 min -> Lambda -> SSM restart -> Slack message."
