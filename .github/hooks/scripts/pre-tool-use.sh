#!/usr/bin/env bash
# Hook: PreToolUse — PHI guard.
#
# Inspects the proposed tool input for raw PHI. If detected:
#   - BLOCK the tool call (emit {"allow": false, "reason": "..."})
#   - Write a runtime ledger entry of kind "phi_block"
# If not detected:
#   - Allow the call to proceed (emit {"allow": true})
#
# Fail-open: if MCP is unreachable, allow (don't punish the engineer for
# infrastructure failures).
set -uo pipefail

PAYLOAD="$(cat)"
tool_name=$(echo "$PAYLOAD" | jq -r '.tool_name // empty')
tool_input=$(echo "$PAYLOAD" | jq -r '.tool_input // empty' | head -c 8000)

# Local fast-path PHI detection (regex-based; matches security/v0.1.0/PHI-001 pattern)
phi_pattern='(MRN|patient_id|SSN|DOB[[:space:]_-]*[0-9]{4})'
if echo "$tool_input" | grep -qE "$phi_pattern"; then
    # Confirm via Ledger MCP classify_phi tool (gives us the canonical bundle_ref)
    bundle_ref="security/v0.1.0/PHI-001"
    detail="raw PHI pattern detected in tool input"
    
    # Write phi_block ledger entry (best-effort)
    if [[ -n "${LEDGER_MCP_URL:-}" && -n "${LEDGER_MCP_TOKEN:-}" ]]; then
        team_id="${LEDGER_TEAM_ID:-team-demo}"
        session_id=$(echo "$PAYLOAD" | jq -r '.session_id // empty')
        curl -sS --max-time 3 \
          -H "Authorization: Bearer $LEDGER_MCP_TOKEN" \
          -H "Content-Type: application/json" \
          -X POST "$LEDGER_MCP_URL/tools/ledger.write_runtime" \
          -d "$(jq -n --arg t "$team_id" --arg sid "$session_id" --arg br "$bundle_ref" \
            --arg d "blocked: $detail (tool=$tool_name)" \
            '{team_id: $t, agent_session_id: $sid, runtime_kind: "phi_block",
              actor: {kind: "agent", id: "github-copilot-ide"},
              decision: $d, phi_class: "high", bundle_refs: [$br]}')" \
          >/dev/null 2>&1 || true
    fi
    
    # BLOCK the tool call
    jq -n --arg r "$detail (cited: $bundle_ref). Use redacted_id() helper." \
      '{allow: false, reason: $r}'
    exit 0
fi

# No PHI detected — allow.
echo '{"allow": true}'
exit 0
