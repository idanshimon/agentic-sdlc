#!/usr/bin/env bash
set -uo pipefail
PAYLOAD="$(cat)"
[[ -z "${LEDGER_MCP_URL:-}" || -z "${LEDGER_MCP_TOKEN:-}" ]] && { echo "{}"; exit 0; }

session_id=$(echo "$PAYLOAD" | jq -r '.session_id // empty')
reason=$(echo "$PAYLOAD" | jq -r '.reason // "complete"')
cwd=$(echo "$PAYLOAD" | jq -r '.cwd // empty')
team_id="${LEDGER_TEAM_ID:-team-demo}"

curl -sS --max-time 3 \
  -H "Authorization: Bearer $LEDGER_MCP_TOKEN" \
  -H "Content-Type: application/json" \
  -X POST "$LEDGER_MCP_URL/tools/ledger.write_runtime" \
  -d "$(jq -n --arg t "$team_id" --arg sid "$session_id" \
    --arg r "$reason" --arg c "$cwd" \
    '{team_id: $t, agent_session_id: $sid, runtime_kind: "ide_session_summary",
      actor: {kind: "agent", id: "github-copilot-ide"},
      decision: ("session ended: " + $r + " in " + $c), bundle_refs: []}')" \
  >/dev/null 2>&1 || true
echo "{}"
exit 0
