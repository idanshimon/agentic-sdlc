#!/usr/bin/env bash
# deploy/scripts/01-deploy-base.sh
# Phase 1: deploys infra/base.bicep (everything except Container Apps).
# Idempotent — safe to re-run.
set -euo pipefail

RG="${RG:-rg-agentic-sdlc-v07-eastus2}"
LOC="${LOC:-eastus2}"
SUB="${SUB:-b3a032cf-f672-4071-b7c8-2bcbe087bbd0}"

echo "Subscription: $SUB"
echo "Resource group: $RG ($LOC)"
echo

az account set --subscription "$SUB"

if ! az group show --name "$RG" --output none 2>/dev/null; then
  echo "Creating RG..."
  az group create --name "$RG" --location "$LOC" --output none
else
  echo "RG already exists, skipping create"
fi

SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
INFRA_DIR="$( cd "$SCRIPT_DIR/../../infra" &> /dev/null && pwd )"

echo
echo "Phase 1: deploying $INFRA_DIR/base.bicep ..."
DEPLOY_NAME="agentic-v07-base-$(date +%Y%m%d-%H%M%S)"
az deployment group create \
  --name "$DEPLOY_NAME" \
  --resource-group "$RG" \
  --template-file "$INFRA_DIR/base.bicep" \
  --output json > /tmp/agentic-v07-base.json

echo
echo "Phase 1 complete. Outputs:"
jq -r '.properties.outputs | to_entries[] | "  \(.key) = \(.value.value)"' /tmp/agentic-v07-base.json
echo
echo "Saved to /tmp/agentic-v07-base.json"
echo
echo "Next: bash deploy/scripts/02-build-and-push-images.sh"
