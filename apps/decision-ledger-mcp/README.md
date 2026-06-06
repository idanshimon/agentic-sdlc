# decision-ledger-mcp

The Decision Ledger exposed as an MCP server. Used by:

- Hook scripts in `.github/hooks/scripts/` (HTTP transport)
- VS Code Copilot, Copilot CLI, GitHub coding agent (stdio transport via `mcp.json`)
- Any other GitHub runtime that speaks Model Context Protocol

## Tools

| Tool | Purpose |
|---|---|
| `ledger.query` | Read entries by team_id with filters (entry_type, agent_session_id, bundle_ref_prefix) |
| `ledger.write_runtime` | Write a runtime ledger entry (schema-validated) |
| `ledger.find_precedent` | Most recent precedent matching (team, ambiguity_class, slot_value_hash) |
| `ledger.get_bundle` | Fetch a standards bundle (rules + envelope + metadata) |
| `ledger.classify_phi` | PHI classifier (regex fast-path; same pattern as security/v0.1.0/PHI-001) |

## Transports

### stdio (default — for IDE / coding agent)

Configure in `.vscode/mcp.json` or `~/.copilot/mcp-config.json`:

```json
{
  "servers": {
    "decision-ledger": {
      "command": "node",
      "args": ["/path/to/dist/server.js"],
      "env": {
        "COSMOS_ENDPOINT": "https://...",
        "COSMOS_DB": "agentic-sdlc",
        "LEDGER_TEAM_ID": "team-cardiology"
      }
    }
  }
}
```

### http (for hook scripts)

The container ships in HTTP mode by default (port 3001):

```bash
curl -X POST http://decision-ledger-mcp:3001/tools/ledger.query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"team_id": "team-cardiology", "limit": 5}'
```

## Auth

Bearer tokens, per-team scoped. Token map is loaded from
`LEDGER_MCP_TOKENS` env (JSON string mapping token → team_id). In production,
replace with per-call Key Vault lookup or Entra App auth.

Each token is bound to one team. Cross-team queries are rejected (HTTP 401).

## Build + run

```bash
npm install
npm run build
LEDGER_MCP_TOKENS='{"dev-token":"team-demo"}' \
  COSMOS_ENDPOINT=https://... \
  npm run start:http
```

## Test

```bash
npm test
```
