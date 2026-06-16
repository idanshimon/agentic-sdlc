#!/usr/bin/env bash
# experiments/sbm-cardiology/deploy/build-and-deploy.sh
#
# Build the pipeline-emitted SBM cardiology alert service into a container
# image, push to the existing v0.7 ACR, and deploy as a Container App on
# the existing CAE.
#
# Usage:
#   bash experiments/sbm-cardiology/deploy/build-and-deploy.sh \
#       --run-dir experiments/sbm-cardiology/runs/haiku-4-5-run-2 \
#       --tag haiku-4-5-run-2
#
# Defaults:
#   --rg            rg-agentic-sdlc-v07-eastus2
#   --acr           (resolved from RG)
#   --cae           (resolved from RG)
#   --app-name      ca-sbm-cardiology-alerts
#   --image-name    sbm-cardiology-alerts
#
# Outputs:
#   /tmp/sbm-deploy-<tag>.json — az containerapp output
#   Public ingress FQDN printed at end.
set -euo pipefail

RG="${RG:-rg-agentic-sdlc-v07-eastus2}"
APP_NAME="${APP_NAME:-ca-sbm-cardiology-alerts}"
IMAGE_NAME="${IMAGE_NAME:-sbm-cardiology-alerts}"
RUN_DIR=""
TAG=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --run-dir) RUN_DIR="$2"; shift 2 ;;
    --tag) TAG="$2"; shift 2 ;;
    --rg) RG="$2"; shift 2 ;;
    --app-name) APP_NAME="$2"; shift 2 ;;
    --image-name) IMAGE_NAME="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "$RUN_DIR" ]]; then
  echo "ERROR: --run-dir required (e.g. experiments/sbm-cardiology/runs/haiku-4-5-run-2)" >&2
  exit 2
fi
if [[ -z "$TAG" ]]; then
  TAG="$(basename "$RUN_DIR")"
fi

if [[ ! -f "$RUN_DIR/pr_payload/app.py" ]]; then
  echo "ERROR: $RUN_DIR/pr_payload/app.py not found — run the pipeline first" >&2
  exit 2
fi

# Sanity gate: the emitted Python MUST parse before we waste an ACR build.
python3 -c "import ast; ast.parse(open('$RUN_DIR/pr_payload/app.py').read())" \
  || { echo "ERROR: $RUN_DIR/pr_payload/app.py has Python syntax errors" >&2; exit 3; }
echo "✓ app.py parses"

if [[ -f "$RUN_DIR/pr_payload/tests/test_app.py" ]]; then
  python3 -c "import ast; ast.parse(open('$RUN_DIR/pr_payload/tests/test_app.py').read())" \
    || echo "WARN: tests/test_app.py has syntax errors (deploy continues; tests skipped)"
fi

# Resolve ACR + CAE from RG.
ACR_NAME=$(az acr list --resource-group "$RG" --query '[0].name' -o tsv 2>/dev/null || true)
if [[ -z "$ACR_NAME" || "$ACR_NAME" == "null" ]]; then
  echo "ERROR: Could not resolve ACR in RG=$RG" >&2
  exit 4
fi
echo "✓ ACR: $ACR_NAME"

CAE_NAME=$(az containerapp env list --resource-group "$RG" --query '[0].name' -o tsv 2>/dev/null || true)
if [[ -z "$CAE_NAME" || "$CAE_NAME" == "null" ]]; then
  echo "ERROR: Could not resolve Container Apps Environment in RG=$RG" >&2
  exit 4
fi
echo "✓ CAE: $CAE_NAME"

# Stage build context: app.py + tests/ + deploy/Dockerfile.
SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
BUILD_DIR=$(mktemp -d -t sbm-cardiology-build.XXXXXX)
trap 'rm -rf "$BUILD_DIR"' EXIT

cp "$RUN_DIR/pr_payload/app.py" "$BUILD_DIR/app.py"
mkdir -p "$BUILD_DIR/tests"
if [[ -f "$RUN_DIR/pr_payload/tests/test_app.py" ]]; then
  cp "$RUN_DIR/pr_payload/tests/test_app.py" "$BUILD_DIR/tests/test_app.py"
fi
cp "$SCRIPT_DIR/Dockerfile" "$BUILD_DIR/Dockerfile"
cp "$SCRIPT_DIR/requirements.txt" "$BUILD_DIR/requirements.txt"

echo
echo "=== ACR build: $ACR_NAME/$IMAGE_NAME:$TAG ==="
az acr build \
  --registry "$ACR_NAME" \
  --image "$IMAGE_NAME:$TAG" \
  --image "$IMAGE_NAME:latest" \
  --file Dockerfile \
  "$BUILD_DIR"

IMAGE_FULL="$ACR_NAME.azurecr.io/$IMAGE_NAME:$TAG"
echo "✓ Image: $IMAGE_FULL"

echo
echo "=== Container App: $APP_NAME ==="
# Idempotent: create if missing, update if exists.
if az containerapp show --resource-group "$RG" --name "$APP_NAME" > /dev/null 2>&1; then
  echo "Updating existing Container App"
  az containerapp update \
    --resource-group "$RG" \
    --name "$APP_NAME" \
    --image "$IMAGE_FULL" \
    > "/tmp/sbm-deploy-$TAG.json"
else
  echo "Creating new Container App"
  az containerapp create \
    --resource-group "$RG" \
    --name "$APP_NAME" \
    --environment "$CAE_NAME" \
    --image "$IMAGE_FULL" \
    --target-port 8000 \
    --ingress external \
    --registry-server "$ACR_NAME.azurecr.io" \
    --min-replicas 0 \
    --max-replicas 1 \
    --cpu 0.5 --memory 1.0Gi \
    --env-vars "PORT=8000" \
    > "/tmp/sbm-deploy-$TAG.json"
fi

FQDN=$(jq -r '.properties.configuration.ingress.fqdn // .properties.latestRevisionFqdn // empty' "/tmp/sbm-deploy-$TAG.json")
if [[ -z "$FQDN" ]]; then
  FQDN=$(az containerapp show --resource-group "$RG" --name "$APP_NAME" --query 'properties.configuration.ingress.fqdn' -o tsv)
fi

echo
echo "=========================================================="
echo "✓ Deployed: https://$FQDN"
echo "  Image:    $IMAGE_FULL"
echo "  Run:     $RUN_DIR"
echo "  Output:  /tmp/sbm-deploy-$TAG.json"
echo "=========================================================="

# Smoke test: poll until /healthz returns 200 (give it 60s for cold start).
echo
echo "Smoke-testing https://$FQDN/healthz ..."
for i in $(seq 1 20); do
  status=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 5 "https://$FQDN/healthz" || echo "000")
  if [[ "$status" == "200" ]]; then
    echo "✓ /healthz → 200 (attempt $i)"
    exit 0
  fi
  printf "  attempt %d: status=%s — sleeping 3s\n" "$i" "$status"
  sleep 3
done
echo "WARN: /healthz did not return 200 within 60s. Check Container App logs:"
echo "  az containerapp logs show --resource-group $RG --name $APP_NAME --follow"
exit 0
