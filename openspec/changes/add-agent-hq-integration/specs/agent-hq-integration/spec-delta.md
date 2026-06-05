# Spec delta — capability: agent-hq-integration

## Added

### Decision Ledger MCP server

A Node.js TypeScript MCP server at `apps/decision-ledger-mcp/` exposing the
Decision Ledger as MCP tools to any GitHub runtime (cloud agent, CLI, VS Code).

Tools:
- `ledger.query` — read entries by team, run, session, bundle ref, date range
- `ledger.write_runtime` — write a runtime entry (validated against schema)
- `ledger.find_precedent` — given an ambiguity class, return prior decisions
- `ledger.get_bundle` — fetch a standards bundle by dept + version
- `ledger.classify_phi` — run the PHI classifier (same one the orchestrator uses)

Transport: stdio (default) and HTTP (for Container Apps deployment).
Auth: bearer token, per-team scoped.

### Hook bundle

Five lifecycle hooks at `.github/hooks/`:

| Hook | Lifecycle event | Purpose |
|---|---|---|
| `session-start.json` | SessionStart | Inject AGENTS.md + ledger context |
| `user-prompt-submit.json` | UserPromptSubmit | Capture intent |
| `pre-tool-use.json` | PreToolUse | PHI classifier; BLOCK on raw PHI |
| `post-tool-use.json` | PostToolUse | Write runtime ledger entry |
| `session-end.json` | SessionEnd | Write summary entry |

Each hook has bash and PowerShell scripts. Timeout 5s, fail-open on
infrastructure failures.

### Custom agents

Six custom agent files at `.github/agents/`:

- `assessor.agent.md`
- `architect.agent.md`
- `codegen.agent.md`
- `review-scan.agent.md`
- `pipeline-doctor.agent.md`
- `standards-change.agent.md`

Each declares: persona, allowed tools (MCP server names), bundle subscriptions,
preferred model.

### A365 attribution

- One-time bootstrap script `deploy/scripts/register-a365-agents.sh` that
  registers each `.github/agents/*.agent.md` as an A365 tenant agent identity.
- Fan-out worker `deploy/scripts/sync-a365-from-ledger.py` that emits
  Microsoft Graph audit events for every new ledger entry.

## Modified

### AGENTS.md

Updated to reference the agent file inventory and the bundle subscriptions.

### Cosmos partition strategy

Unchanged (`/team_id`). MCP server uses the same partition key.

## Constraints

- Hooks fail-open. An MCP unavailability cannot block the user's IDE.
- The MCP server has 5s response budget per tool call (matches hook timeout).
- PHI rules remain enforceable client-side (the classifier check) AND
  server-side (the orchestrator review-scan stage).
