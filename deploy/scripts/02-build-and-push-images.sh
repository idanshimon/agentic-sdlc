#!/usr/bin/env bash
# deploy/scripts/02-build-and-push-images.sh
# Builds + pushes the four images to ACR via az acr build (no local docker required).
set -euo pipefail

RG="${RG:-rg-agentic-sdlc-v07-eastus}"
TAG="${TAG:-0.7.0-rc1}"

# Discover ACR name from RG
ACR_NAME=$(az acr list --resource-group "$RG" --query '[0].name' -o tsv)
if [[ -z "$ACR_NAME" ]]; then
  echo "ERROR: No ACR found in $RG. Run 01-create-rg-and-infra.sh first." >&2
  exit 1
fi
echo "Using ACR: $ACR_NAME"
echo "Tag: $TAG"

REPO_ROOT="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../.." &> /dev/null && pwd )"
echo "Repo root: $REPO_ROOT"

build() {
  local img="$1"; local context="$2"; local dockerfile="$3"; shift 3
  echo
  echo "=== Building $img:$TAG ==="
  az acr build \
    --registry "$ACR_NAME" \
    --image "$img:$TAG" \
    --image "$img:latest" \
    --file "$dockerfile" \
    "$@" \
    "$context" \
    2>&1 | tail -20
}

# 1. orchestrator
build orchestrator "$REPO_ROOT/apps/orchestrator" "$REPO_ROOT/apps/orchestrator/Dockerfile"

# 2. decision-ledger-mcp
build decision-ledger-mcp "$REPO_ROOT/apps/decision-ledger-mcp" "$REPO_ROOT/apps/decision-ledger-mcp/Dockerfile"

# 3. pipeline-doctor (needs ledger-core + standards-bundles in build context)
# Strategy: build context = repo root, dockerfile = apps/pipeline-doctor/Dockerfile
# Update Dockerfile path expectations later; for v0.7 demo we use a flatter Dockerfile.

# 4. ledger-insights-ui — placeholder until UI is ported
echo
echo "NOTE: ledger-insights-ui not yet ported from v0.6 resolver-ui — skipping build."
echo "      Orchestrator + ledger-mcp + pipeline-doctor will be deployable."

echo
echo "Done. Images in ACR:"
az acr repository list --name "$ACR_NAME" --output table
