#!/usr/bin/env bash
# deploy/scripts/03-deploy-apps.sh
# Phase 3: deploys infra/apps.bicep (Container Apps + Container Job).
# Reads outputs from /tmp/agentic-v07-base.json (produced by 01-deploy-base.sh).
set -euo pipefail

RG="${RG:-rg-agentic-sdlc-v07-eastus2}"
SUB="${SUB:-b3a032cf-f672-4071-b7c8-2bcbe087bbd0}"

if [[ ! -f /tmp/agentic-v07-base.json ]]; then
  echo "ERROR: /tmp/agentic-v07-base.json not found. Run 01-deploy-base.sh first." >&2
  exit 1
fi

az account set --subscription "$SUB"

# Pull base outputs
ACR_NAME=$(jq -r '.properties.outputs.acrName.value' /tmp/agentic-v07-base.json)
ACR_LOGIN=$(jq -r '.properties.outputs.acrLoginServer.value' /tmp/agentic-v07-base.json)
COSMOS_EP=$(jq -r '.properties.outputs.cosmosEndpoint.value' /tmp/agentic-v07-base.json)
STORAGE=$(jq -r '.properties.outputs.storageAccountName.value' /tmp/agentic-v07-base.json)
MI_ID=$(jq -r '.properties.outputs.workloadMiId.value' /tmp/agentic-v07-base.json)
MI_CLIENT=$(jq -r '.properties.outputs.workloadMiClientId.value' /tmp/agentic-v07-base.json)
CAE_ID=$(jq -r '.properties.outputs.caeId.value' /tmp/agentic-v07-base.json)
APPI_CONN=$(jq -r '.properties.outputs.appInsightsConnectionString.value' /tmp/agentic-v07-base.json)

# Sanity check images exist in ACR
echo "Verifying images in ACR..."
for img in orchestrator decision-ledger-mcp pipeline-doctor; do
  if ! az acr repository show --name "$ACR_NAME" --image "$img:0.7.0-rc1" --output none 2>/dev/null; then
    echo "ERROR: $ACR_NAME/$img:0.7.0-rc1 missing. Run 02-build-and-push-images.sh first." >&2
    exit 1
  fi
  echo "  ✓ $img:0.7.0-rc1"
done

SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
INFRA_DIR="$( cd "$SCRIPT_DIR/../../infra" &> /dev/null && pwd )"

echo
echo "Phase 3: deploying $INFRA_DIR/apps.bicep ..."
DEPLOY_NAME="agentic-v07-apps-$(date +%Y%m%d-%H%M%S)"
az deployment group create \
  --name "$DEPLOY_NAME" \
  --resource-group "$RG" \
  --template-file "$INFRA_DIR/apps.bicep" \
  --parameters \
    acrLoginServer="$ACR_LOGIN" \
    cosmosEndpoint="$COSMOS_EP" \
    storageAccountName="$STORAGE" \
    workloadMiId="$MI_ID" \
    workloadMiClientId="$MI_CLIENT" \
    caeId="$CAE_ID" \
    appInsightsConnectionString="$APPI_CONN" \
  --output json > /tmp/agentic-v07-apps.json

echo
echo "Phase 3 complete. Workload URLs:"
jq -r '.properties.outputs | to_entries[] | "  \(.key) = \(.value.value)"' /tmp/agentic-v07-apps.json
