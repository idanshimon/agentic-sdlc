#!/usr/bin/env bash
# Build and push apps/ledger-insights-ui to Azure Container Registry.
#
# Threads NEXT_PUBLIC_* as build args into the Dockerfile (they are inlined
# into the JS bundle at `next build` time — runtime env vars are too late).
# Build context is monorepo root so /changes can read openspec/ from disk.
#
# Usage:
#   bash scripts/build-ledger-insights-ui.sh                  # use defaults
#   ACR_NAME=myregistry bash scripts/build-ledger-insights-ui.sh
#   NEXT_PUBLIC_DEMO_MODE=0 NEXT_PUBLIC_ORCHESTRATOR_URL=https://... \
#       bash scripts/build-ledger-insights-ui.sh
#
# Refuses to build a Demo-Mode-disabled image without an EasyAuth check
# (spec REQ-9 — guards the Demo Mode rip-out transition).

set -euo pipefail

# ---------- config (env-overridable) ----------
ACR_NAME="${ACR_NAME:-cragenticsdlc}"
IMAGE_NAME="${IMAGE_NAME:-ledger-insights-ui}"
RESOURCE_GROUP="${RESOURCE_GROUP:-rg-agentic-sdlc-eastus2}"
CONTAINER_APP_NAME="${CONTAINER_APP_NAME:-ca-ledger-ui}"

NEXT_PUBLIC_DEMO_MODE="${NEXT_PUBLIC_DEMO_MODE:-1}"
NEXT_PUBLIC_ORCHESTRATOR_URL="${NEXT_PUBLIC_ORCHESTRATOR_URL:-https://ca-orchestrator.placeholder.eastus2.azurecontainerapps.io}"
NEXT_PUBLIC_LEDGER_MCP_URL="${NEXT_PUBLIC_LEDGER_MCP_URL:-https://ca-ledger-mcp.placeholder.eastus2.azurecontainerapps.io}"

# ---------- paths ----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DOCKERFILE_PATH="apps/ledger-insights-ui/Dockerfile"

cd "$REPO_ROOT"

# ---------- preflight ----------
if [[ ! -f "$DOCKERFILE_PATH" ]]; then
    echo "ERROR: $DOCKERFILE_PATH not found. Run from repo root." >&2
    exit 1
fi

if ! command -v az >/dev/null 2>&1; then
    echo "ERROR: az CLI not found. Install with 'brew install azure-cli'." >&2
    exit 1
fi

if ! git rev-parse --git-dir >/dev/null 2>&1; then
    echo "ERROR: not a git repository." >&2
    exit 1
fi

GIT_SHA="$(git rev-parse --short HEAD)"
IMAGE_TAG="$GIT_SHA"

# ---------- spec REQ-9: refuse rip-out without EasyAuth ----------
if [[ "$NEXT_PUBLIC_DEMO_MODE" == "0" ]]; then
    echo ">> NEXT_PUBLIC_DEMO_MODE=0 — checking EasyAuth on $CONTAINER_APP_NAME..."
    AUTH_CONFIG=$(az containerapp auth show \
        --name "$CONTAINER_APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query "properties.platform.enabled" \
        -o tsv 2>/dev/null || echo "false")
    if [[ "$AUTH_CONFIG" != "true" ]]; then
        echo "ERROR: Demo Mode rip-out (NEXT_PUBLIC_DEMO_MODE=0) requires EasyAuth." >&2
        echo "       $CONTAINER_APP_NAME has no active auth config." >&2
        echo "       Spec ref: openspec/changes/add-ledger-insights-ui-deploy/specs/ledger-insights-ui-deploy/spec.md REQ-9" >&2
        exit 1
    fi
    echo ">> EasyAuth is enabled — proceeding."
fi

# ---------- summary ----------
cat <<EOF
== ledger-insights-ui ACR build =================================
Repo root        : $REPO_ROOT
Dockerfile       : $DOCKERFILE_PATH
Registry         : $ACR_NAME
Image            : $IMAGE_NAME:$IMAGE_TAG (+ :latest)
Build args:
  NEXT_PUBLIC_DEMO_MODE         = $NEXT_PUBLIC_DEMO_MODE
  NEXT_PUBLIC_ORCHESTRATOR_URL  = $NEXT_PUBLIC_ORCHESTRATOR_URL
  NEXT_PUBLIC_LEDGER_MCP_URL    = $NEXT_PUBLIC_LEDGER_MCP_URL
=================================================================
EOF

# ---------- build ----------
az acr build \
    --registry "$ACR_NAME" \
    --image "$IMAGE_NAME:$IMAGE_TAG" \
    --image "$IMAGE_NAME:latest" \
    --file "$DOCKERFILE_PATH" \
    --build-arg "NEXT_PUBLIC_DEMO_MODE=$NEXT_PUBLIC_DEMO_MODE" \
    --build-arg "NEXT_PUBLIC_ORCHESTRATOR_URL=$NEXT_PUBLIC_ORCHESTRATOR_URL" \
    --build-arg "NEXT_PUBLIC_LEDGER_MCP_URL=$NEXT_PUBLIC_LEDGER_MCP_URL" \
    .

echo
echo "== Build complete =============================================="
echo "Image:  $ACR_NAME.azurecr.io/$IMAGE_NAME:$IMAGE_TAG"
echo "Latest: $ACR_NAME.azurecr.io/$IMAGE_NAME:latest"
echo

# ---------- digest ----------
DIGEST=$(az acr repository show \
    --name "$ACR_NAME" \
    --image "$IMAGE_NAME:$IMAGE_TAG" \
    --query "digest" \
    -o tsv 2>/dev/null || echo "(unable to fetch — push may still be propagating)")
echo "Digest: $DIGEST"
echo
echo "Next: bash scripts/smoke-ledger-insights-ui.sh https://<fqdn>/"
