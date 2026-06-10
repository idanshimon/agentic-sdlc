#!/usr/bin/env bash
# deploy/scripts/06-migrate-apps-to-vnet.sh
# Phase 4b: migrate ca-orchestrator / ca-ledger-mcp / ca-ledger-ui from
# cae-agentic-tj6c673gu6x5w (public) to cae-agentic-v07-vnet (VNET-integrated).
#
# Strategy: create NEW apps with -vnet suffix on the new env, verify, then
# customers point at the new FQDNs. Old apps stay running for rollback window.
# Cleanup is a separate script.
#
# Idempotent — safe to re-run; existing -vnet apps get updated in place.

set -euo pipefail

RG="${RG:-rg-agentic-sdlc-v07-eastus2}"
OLD_CAE="${OLD_CAE:-cae-agentic-tj6c673gu6x5w}"
NEW_CAE="${NEW_CAE:-cae-agentic-v07-vnet}"
SUB="${SUB:-b3a032cf-f672-4071-b7c8-2bcbe087bbd0}"

az account set --subscription "$SUB"

echo "=== Migration plan ==="
echo "  From: $OLD_CAE"
echo "  To:   $NEW_CAE"
echo "  RG:   $RG"
echo ""

# Get the new CAE env ID
NEW_CAE_ID=$(az containerapp env show -n "$NEW_CAE" -g "$RG" --query id -o tsv)
NEW_CAE_DOMAIN=$(az containerapp env show -n "$NEW_CAE" -g "$RG" --query properties.defaultDomain -o tsv)
echo "  New env id:     $NEW_CAE_ID"
echo "  New env domain: $NEW_CAE_DOMAIN"
echo ""

if [[ -z "$NEW_CAE_ID" || -z "$NEW_CAE_DOMAIN" ]]; then
  echo "ERROR: new CAE env not found or not ready. Run Phase 4 bicep first."
  exit 1
fi

# Apps to migrate
APPS=("ca-orchestrator" "ca-ledger-mcp" "ca-ledger-ui")

for APP in "${APPS[@]}"; do
  NEW_APP="${APP}-vnet"
  echo ""
  echo "=== Migrating $APP → $NEW_APP ==="

  # Capture the full source definition
  SRC_JSON=$(az containerapp show -n "$APP" -g "$RG" -o json)

  # Extract values needed for the new app
  IMAGE=$(echo "$SRC_JSON" | jq -r '.properties.template.containers[0].image')
  TARGET_PORT=$(echo "$SRC_JSON" | jq -r '.properties.configuration.ingress.targetPort')
  CPU=$(echo "$SRC_JSON" | jq -r '.properties.template.containers[0].resources.cpu')
  MEMORY=$(echo "$SRC_JSON" | jq -r '.properties.template.containers[0].resources.memory')
  MIN_REP=$(echo "$SRC_JSON" | jq -r '.properties.template.scale.minReplicas')
  MAX_REP=$(echo "$SRC_JSON" | jq -r '.properties.template.scale.maxReplicas')
  MI_ID=$(echo "$SRC_JSON" | jq -r '.identity.userAssignedIdentities | keys[0]')

  echo "  image:       $IMAGE"
  echo "  targetPort:  $TARGET_PORT"
  echo "  resources:   $CPU CPU / $MEMORY"
  echo "  scale:       $MIN_REP–$MAX_REP"
  echo "  MI:          ${MI_ID##*/}"

  # Save env vars as a file for --env-vars-file
  ENV_FILE="/tmp/cae-migration/$APP.env.yaml"
  mkdir -p /tmp/cae-migration
  echo "$SRC_JSON" | jq -r '.properties.template.containers[0].env[] |
    if .secretRef then
      "- name: \(.name)\n  secretRef: \(.secretRef)"
    else
      "- name: \(.name)\n  value: \"\(.value)\""
    end' > "$ENV_FILE"

  # Save secrets for --secrets
  SECRETS_FILE="/tmp/cae-migration/$APP.secrets.txt"
  echo "$SRC_JSON" | jq -r '.properties.configuration.secrets[] | .name' > "$SECRETS_FILE"

  echo "  envVars saved to: $ENV_FILE ($(wc -l < $ENV_FILE) lines)"
  echo "  secrets:          $(cat $SECRETS_FILE | tr '\n' ' ')"

  # Check if new app already exists
  if az containerapp show -n "$NEW_APP" -g "$RG" -o none 2>/dev/null; then
    echo "  → $NEW_APP exists, updating image..."
    az containerapp update \
      -n "$NEW_APP" \
      -g "$RG" \
      --image "$IMAGE" \
      --output none
    echo "  ✓ updated"
  else
    echo "  → creating $NEW_APP on $NEW_CAE..."
    echo "  (NOTE: this script creates the shell only — env vars + secrets need a follow-up update"
    echo "         because az containerapp create can't accept secrets-by-name without value)"
    az containerapp create \
      -n "$NEW_APP" \
      -g "$RG" \
      --environment "$NEW_CAE_ID" \
      --image "$IMAGE" \
      --target-port "$TARGET_PORT" \
      --ingress external \
      --transport auto \
      --cpu "$CPU" \
      --memory "$MEMORY" \
      --min-replicas "$MIN_REP" \
      --max-replicas "$MAX_REP" \
      --user-assigned "$MI_ID" \
      --registry-server "acragenticsdlctj6c673gu6x5w.azurecr.io" \
      --registry-identity "$MI_ID" \
      --output none
    echo "  ✓ created (env vars + secrets still need wiring — see next step)"
  fi

  # Report the new FQDN
  NEW_FQDN=$(az containerapp show -n "$NEW_APP" -g "$RG" --query properties.configuration.ingress.fqdn -o tsv)
  echo "  → new FQDN: https://$NEW_FQDN"
done

echo ""
echo "=== Done ==="
echo ""
echo "Next:"
echo "  1. Copy secrets from old apps to new apps:"
echo "     bash deploy/scripts/06b-copy-secrets-to-vnet-apps.sh"
echo "  2. Copy env vars from old apps to new apps:"
echo "     bash deploy/scripts/06c-copy-env-to-vnet-apps.sh"
echo "  3. Smoke-test the new FQDNs:"
echo "     bash deploy/scripts/04-smoke-test.sh --env=vnet"
echo "  4. Update skill 'Live URLs' to point at the new FQDNs."
