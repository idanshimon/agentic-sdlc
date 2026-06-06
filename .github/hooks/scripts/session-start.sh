#!/usr/bin/env bash
# Hook: SessionStart
# Reads AGENTS.md + queries Ledger MCP for recent entries on the session's
# working directory. Emits an additionalContext key so Copilot loads it
# at the top of the conversation.
#
# Env contract (set by Copilot):
#   HERMES_HOOK_PAYLOAD — JSON on stdin
#   LEDGER_MCP_URL      — Decision Ledger MCP server URL
#   LEDGER_MCP_TOKEN    — bearer token (per-team scoped)
#   GITHUB_REPOSITORY   — owner/repo
#
# Output contract: JSON on stdout with optional `additionalContext`.
# Failure mode: exit 0 with empty output (fail-open).

set -uo pipefail

REPO_DIR="${GITHUB_REPOSITORY_DIR:-$(pwd)}"
AGENTS_MD="$REPO_DIR/AGENTS.md"
PAYLOAD="$(cat)"

# Load AGENTS.md (truncated to keep prompt tight)
agents_md_content=""
if [[ -f "$AGENTS_MD" ]]; then
  agents_md_content="$(head -c 4000 "$AGENTS_MD")"
fi

# Ledger MCP is optional — fail-open if not configured
ledger_recent=""
if [[ -n "${LEDGER_MCP_URL:-}" && -n "${LEDGER_MCP_TOKEN:-}" ]]; then
  team_id="${LEDGER_TEAM_ID:-team-demo}"
  ledger_recent=$(curl -sS --max-time 4 \
    -H "Authorization: Bearer $LEDGER_MCP_TOKEN" \
    -H "Content-Type: application/json" \
    -X POST "$LEDGER_MCP_URL/tools/ledger.query" \
    -d "{\"team_id\":\"$team_id\",\"limit\":5}" \
    2>/dev/null || echo "")
fi

# Emit additionalContext
context=""
if [[ -n "$agents_md_content" ]]; then
  context+="## Repository agent guardrails (AGENTS.md)\n\n$agents_md_content\n\n"
fi
if [[ -n "$ledger_recent" ]]; then
  context+="## Recent Decision Ledger entries (last 5 for this team)\n\n\`\`\`json\n$ledger_recent\n\`\`\`\n"
fi

if [[ -n "$context" ]]; then
  jq -n --arg ctx "$context" '{additionalContext: $ctx}'
else
  echo "{}"
fi

exit 0
