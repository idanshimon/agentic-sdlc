#!/usr/bin/env bash
# Hook: PostToolUse — log every tool call to the ledger.
set -uo pipefail
PAYLOAD="$(cat)"
[[ -z "${LEDGER_MCP_URL:-}" || -z "${LEDGER_MCP_TOKEN:-}" ]] && { echo "{}"; exit 0; }

tool_name=$(echo "$PAYLOAD" | jq -r '.tool_name // empty')
result_kind=$(echo "$PAYLOAD" | jq -r '.tool_result.result_type // "unknown"')
session_id=$(echo "$PAYLOAD" | jq -r '.session_id // empty')
text_summary=$(echo "$PAYLOAD" | jq -r '.tool_result.text_result_for_llm // empty' | head -c 200)

team_id="${LEDGER_TEAM_ID:-team-demo}"

curl -sS --max-time 3 \
  -H "Authorization: Bearer $LEDGER_MCP_TOKEN" \
  -H "Content-Type: application/json" \
  -X POST "$LEDGER_MCP_URL/tools/ledger.write_runtime" \
  -d "$(jq -n \
    --arg t "$team_id" \
    --arg sid "$session_id" \
    --arg tn "$tool_name" \
    --arg rk "$result_kind" \
    --arg ts "$text_summary" \
    '{team_id: $t, agent_session_id: $sid, runtime_kind: "ide_tool_call",
      actor: {kind: "agent", id: "github-copilot-ide"},
      decision: ($tn + " " + $rk + ": " + $ts), bundle_refs: []}')" \
  >/dev/null 2>&1 || true
echo "{}"
exit 0
