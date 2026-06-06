#!/usr/bin/env bash
# Hook: UserPromptSubmit — capture intent to ledger.
set -uo pipefail

PAYLOAD="$(cat)"
[[ -z "${LEDGER_MCP_URL:-}" || -z "${LEDGER_MCP_TOKEN:-}" ]] && { echo "{}"; exit 0; }

session_id=$(echo "$PAYLOAD" | jq -r '.session_id // empty')
prompt=$(echo "$PAYLOAD" | jq -r '.user_prompt // empty' | head -c 200)
[[ -z "$prompt" ]] && { echo "{}"; exit 0; }

team_id="${LEDGER_TEAM_ID:-team-demo}"
agent_id="${COPILOT_AGENT_ID:-github-copilot-ide}"

curl -sS --max-time 3 \
  -H "Authorization: Bearer $LEDGER_MCP_TOKEN" \
  -H "Content-Type: application/json" \
  -X POST "$LEDGER_MCP_URL/tools/ledger.write_runtime" \
  -d "$(jq -n \
    --arg t "$team_id" \
    --arg sid "$session_id" \
    --arg aid "$agent_id" \
    --arg p "$prompt" \
    '{team_id: $t, agent_session_id: $sid, runtime_kind: "ide_session_summary",
      actor: {kind: "human", id: env.USER // "ide-user"},
      decision: ("intent: " + $p), bundle_refs: []}')" \
  >/dev/null 2>&1 || true
echo "{}"
exit 0
