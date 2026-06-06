#!/usr/bin/env bash
# deploy/scripts/02-build-and-push-images.sh
# Phase 2: builds + pushes 3 images via az acr build (no local docker required).
#
# v0.7-rc1 image set:
#   orchestrator        — Python 3.11 FastAPI
#   decision-ledger-mcp — Node 20 TS
#   pipeline-doctor     — Python 3.11 (depends on packages/ledger-core)
#
# Deferred:
#   ledger-insights-ui — Next.js (resolver-ui port not done yet, deferred to v0.7+1)
set -euo pipefail

RG="${RG:-rg-agentic-sdlc-v07-eastus2}"
TAG="${TAG:-0.7.0-rc1}"

if [[ ! -f /tmp/agentic-v07-base.json ]]; then
  ACR_NAME=$(az acr list --resource-group "$RG" --query '[0].name' -o tsv)
else
  ACR_NAME=$(jq -r '.properties.outputs.acrName.value' /tmp/agentic-v07-base.json)
fi

if [[ -z "$ACR_NAME" || "$ACR_NAME" == "null" ]]; then
  echo "ERROR: Could not resolve ACR name" >&2
  exit 1
fi

echo "ACR: $ACR_NAME"
echo "Tag: $TAG"

REPO_ROOT="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../.." &> /dev/null && pwd )"
echo "Repo root: $REPO_ROOT"

build() {
  local img="$1"; local context="$2"; local dockerfile="$3"; shift 3
  echo
  echo "=== Building $img:$TAG ==="
  if ! az acr build \
    --registry "$ACR_NAME" \
    --image "$img:$TAG" \
    --image "$img:latest" \
    --file "$dockerfile" \
    "$@" \
    "$context"; then
    echo "FAILED: $img"
    return 1
  fi
}

# 1. orchestrator (Python 3.11 FastAPI). Needs packages/ledger-core, so build
# from repo root context using Dockerfile.repo-root (parallels pipeline-doctor).
build orchestrator "$REPO_ROOT" "$REPO_ROOT/apps/orchestrator/Dockerfile.repo-root"

# 2. decision-ledger-mcp (Node TS). Build context: apps/decision-ledger-mcp/.
# The Dockerfile expects standards-bundles to be copied in at /app/standards-bundles
# at runtime via volume; for build, just package the app.
build decision-ledger-mcp "$REPO_ROOT/apps/decision-ledger-mcp" "$REPO_ROOT/apps/decision-ledger-mcp/Dockerfile"

# 3. pipeline-doctor (Python 3.11). Needs ledger-core wheel + standards-bundles.
# We use a Dockerfile that builds from repo root context to access both.
build pipeline-doctor "$REPO_ROOT" "$REPO_ROOT/apps/pipeline-doctor/Dockerfile.repo-root"

echo
echo "Done. Images in ACR:"
az acr repository list --name "$ACR_NAME" --output table

echo
echo "Next: bash deploy/scripts/03-deploy-apps.sh"
