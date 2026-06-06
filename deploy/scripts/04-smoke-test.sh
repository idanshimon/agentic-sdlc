#!/usr/bin/env bash
# deploy/scripts/04-smoke-test.sh
# After phase 3 (apps deployed), verify the workloads are healthy + writeable.
set -uo pipefail

if [[ ! -f /tmp/agentic-v07-apps.json ]]; then
  echo "ERROR: /tmp/agentic-v07-apps.json missing. Run 03-deploy-apps.sh first." >&2
  exit 1
fi

ORCH_FQDN=$(jq -r '.properties.outputs.orchestratorFqdn.value' /tmp/agentic-v07-apps.json)
MCP_FQDN=$(jq -r '.properties.outputs.ledgerMcpFqdn.value' /tmp/agentic-v07-apps.json)

echo "=== v0.7 smoke test ==="
echo "Orchestrator: https://$ORCH_FQDN"
echo "Ledger MCP:   https://$MCP_FQDN"
echo

# 1. Orchestrator health
echo "--- 1. Orchestrator /healthz ---"
ORCH_STATUS=$(curl -sS -o /tmp/orch-health.txt -w "%{http_code}" --max-time 10 "https://$ORCH_FQDN/healthz" || echo "000")
echo "  HTTP $ORCH_STATUS"
[[ -s /tmp/orch-health.txt ]] && cat /tmp/orch-health.txt
echo

# 2. Ledger MCP health
echo "--- 2. Ledger MCP /healthz ---"
MCP_STATUS=$(curl -sS -o /tmp/mcp-health.txt -w "%{http_code}" --max-time 10 "https://$MCP_FQDN/healthz" || echo "000")
echo "  HTTP $MCP_STATUS"
[[ -s /tmp/mcp-health.txt ]] && cat /tmp/mcp-health.txt
echo

# 3. Ledger MCP /tools (list)
echo "--- 3. Ledger MCP /tools ---"
TOOLS_STATUS=$(curl -sS -o /tmp/mcp-tools.txt -w "%{http_code}" --max-time 10 "https://$MCP_FQDN/tools" || echo "000")
echo "  HTTP $TOOLS_STATUS"
if [[ "$TOOLS_STATUS" == "200" ]]; then
  jq -r '.tools[] | "  ✓ \(.name) — \(.description[:60])"' /tmp/mcp-tools.txt
fi
echo

# 4. PHI classifier (auth required: Bearer team-demo token)
echo "--- 4. PHI classifier on raw MRN (should detect) ---"
TOKEN_FILE="/tmp/agentic-v07-token"
if [[ ! -s "$TOKEN_FILE" ]]; then
  echo "  ⚠ $TOKEN_FILE missing — skipping (run 03-deploy-apps.sh to generate)"
  PHI_STATUS="skip"
else
  PHI_STATUS=$(curl -sS -o /tmp/phi-test.txt -w "%{http_code}" --max-time 10 \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $(cat "$TOKEN_FILE")" \
    -d '{"text": "logger.info(f\"patient {MRN} updated\")", "team_id": "team-demo"}' \
    "https://$MCP_FQDN/tools/ledger.classify_phi" || echo "000")
  echo "  HTTP $PHI_STATUS"
  if [[ -s /tmp/phi-test.txt ]]; then
    cat /tmp/phi-test.txt | jq .
  fi
fi
echo

# Summary
echo "=== Summary ==="
[[ "$ORCH_STATUS" == "200" ]] && echo "  ✓ orchestrator UP" || echo "  ✗ orchestrator DOWN ($ORCH_STATUS)"
[[ "$MCP_STATUS" == "200" ]] && echo "  ✓ ledger-mcp UP" || echo "  ✗ ledger-mcp DOWN ($MCP_STATUS)"
[[ "$TOOLS_STATUS" == "200" ]] && echo "  ✓ ledger-mcp tools listing OK" || echo "  ✗ tools listing failed ($TOOLS_STATUS)"
[[ "$PHI_STATUS" == "200" ]] && echo "  ✓ PHI classifier responding" || echo "  ✗ PHI classifier failed ($PHI_STATUS)"
