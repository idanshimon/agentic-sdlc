# Hook bundle — Decision Ledger lifecycle integration

These five hooks make every Copilot session in this repo (cloud agent, CLI,
or VS Code) write to the Decision Ledger. Without this bundle, IDE Copilot
activity is invisible to the audit substrate.

## Hooks

| Hook | Lifecycle event | Purpose |
|---|---|---|
| `session-start.json` | SessionStart | Inject AGENTS.md guardrails + recent ledger entries on touched files |
| `user-prompt-submit.json` | UserPromptSubmit | Capture intent (truncated to 200 chars) |
| `pre-tool-use.json` | PreToolUse | PHI classifier; BLOCK on raw MRN/SSN/DOB |
| `post-tool-use.json` | PostToolUse | Write a runtime ledger entry summarizing the tool call |
| `session-end.json` | SessionEnd | Write summary entry with aggregated stats |

## Environment contract

Each script reads:

| Var | Required? | Purpose |
|---|---|---|
| `LEDGER_MCP_URL` | yes (else fail-open) | Decision Ledger MCP server base URL |
| `LEDGER_MCP_TOKEN` | yes | Bearer token (per-team scoped) |
| `LEDGER_TEAM_ID` | no (default `team-demo`) | Team partition key |
| `COPILOT_AGENT_ID` | no | Override agent identity attribution |
| `GITHUB_REPOSITORY_DIR` | no (default cwd) | Repo root for AGENTS.md lookup |

## Fail-open contract

Every script exits 0 with empty/`{"allow": true}` output when:
- The MCP URL/token is not configured
- The MCP server is unreachable
- Any unexpected error occurs

This is **deliberate**. Hooks must not block engineer productivity due to
infrastructure failures. PHI guard is the one exception: if the local
regex check fires, the call is BLOCKED regardless of MCP availability.

## Validation

After installing this bundle:

```bash
./.github/hooks/scripts/validate-bundle.sh
```

Checks:
- All 10 scripts exist and are executable
- All 5 JSON configs parse
- Required tools (`jq`, `curl`) are on PATH

## Honest limitations

- **Hooks fire CLIENT-side.** A user with a tampered hook config can bypass
  PHI detection. Server-side enforcement (the orchestrator's review-scan stage,
  bundle rules with `severity: BLOCK`) is the authoritative gate.
- **Local PHI regex is a fast path, not the canonical classifier.** The
  canonical classifier is `ledger.classify_phi` on the MCP server, which uses
  the same model the orchestrator uses. The local regex is the always-available
  fallback so PHI gets blocked even when MCP is down.
- **`session-end` is not guaranteed to fire.** If Copilot is killed (kill -9,
  IDE crash), no summary entry is written. The orchestrator's run-state
  reconciliation handles the gap; coding-agent flows close cleanly.
