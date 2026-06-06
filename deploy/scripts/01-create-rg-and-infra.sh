#!/usr/bin/env bash
# deploy/scripts/01-create-rg-and-infra.sh
# Creates the v0.7 RG + deploys infra/main.bicep.
# Idempotent — safe to re-run.
set -euo pipefail

RG="${RG:-rg-agentic-sdlc-v07-eastus}"
LOC="${LOC:-eastus}"
SUB="${SUB:-b3a032cf-f672-4071-b7c8-2bcbe087bbd0}"

echo "Subscription: $SUB"
echo "Resource group: $RG ($LOC)"
echo

# 1. Sub
az account set --subscription "$SUB"

# 2. RG
if ! az group show --name "$RG" --output none 2>/dev/null; then
  echo "Creating RG..."
  az group create --name "$RG" --location "$LOC" --output none
else
  echo "RG already exists, skipping create"
fi

# 3. Bicep deploy
SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
INFRA_DIR="$( cd "$SCRIPT_DIR/../../infra" &> /dev/null && pwd )"

echo
echo "Deploying $INFRA_DIR/main.bicep ..."
DEPLOY_NAME="agentic-v07-$(date +%Y%m%d-%H%M%S)"
az deployment group create \
  --name "$DEPLOY_NAME" \
  --resource-group "$RG" \
  --template-file "$INFRA_DIR/main.bicep" \
  --output json > /tmp/agentic-v07-deploy.json

echo
echo "Deploy complete. Outputs:"
jq -r '.properties.outputs | to_entries[] | "  \(.key) = \(.value.value)"' /tmp/agentic-v07-deploy.json
echo
echo "Outputs saved to /tmp/agentic-v07-deploy.json"
