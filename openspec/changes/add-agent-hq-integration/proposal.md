# Proposal: add Agent HQ integration

> **Status:** DRAFT
> **Capability:** agent-hq-integration
> **Related:** master-v07-four-plane-architecture, extend-ledger-runtime-meta-entries

## Why

In v0.6, the Decision Ledger only saw orchestrator pipeline runs. ~80% of
agentic activity (engineer IDE sessions, GH coding-agent issue→PR flows,
chat-bridged issue assignments from Slack/Teams/Linear/Boards) was
invisible. Compliance audited 20% of the surface, blind on the rest.

GitHub Universe 2025 introduced Agent HQ + AGENTS.md + Custom Agents +
Skills + Hooks + MCP — a coherent set of primitives that let us close the
gap WITHOUT rebuilding Mission Control. The orchestrator stays the heavy
lane; Agent HQ becomes the medium and light lanes; all three feed the
same ledger.

## What changes

Three integration points:

1. **Decision Ledger MCP server** — a Node.js TS MCP server at
   `apps/decision-ledger-mcp/` exposing the ledger to any GH runtime
   (cloud agent, CLI, VS Code) as a set of MCP tools.
2. **Hook bundle** at `.github/hooks/` — five lifecycle hooks that write
   ledger entries from IDE Copilot sessions, including a PreToolUse hook
   that BLOCKS PHI writes per `security/v0.1.0/PHI-001`.
3. **Custom agents** at `.github/agents/` — Copilot-side mirrors of our
   Foundry pipeline agents. Same persona, different runtime. Engineer
   working in VS Code on a refactor invokes the SAME `architect` persona
   the orchestrator uses, with the SAME bundle subscriptions.

### Decision Ledger MCP tools

The MCP server exposes:

| Tool name | Description |
|---|---|
| `ledger.query` | Read entries by team_id, run_id, agent_session_id, bundle_ref, date range |
| `ledger.write_runtime` | Write a runtime entry (validates against schema) |
| `ledger.find_precedent` | Given an ambiguity class, return prior decisions ordered by recency + similarity |
| `ledger.get_bundle` | Fetch a standards bundle by dept + version (cached) |
| `ledger.classify_phi` | Run the PHI classifier (SAME one the orchestrator uses, served via MCP) |

Auth: bearer token (per-team, scoped). Token issuance is a Container Apps secret.
The MCP server runs as its own Container App with private ingress.

### Hook bundle

Five hooks at `.github/hooks/*.json`, each with bash + powershell scripts
at `.github/hooks/scripts/`:

| Hook | Fires on | Action |
|---|---|---|
| `session-start.json` | SessionStart | Inject AGENTS.md context + recent ledger entries on touched files |
| `user-prompt-submit.json` | UserPromptSubmit | Capture intent (`logger.info(prompt[:200])`) |
| `pre-tool-use.json` | PreToolUse | PHI classifier check; BLOCK if raw MRN/DOB; PASS if redacted |
| `post-tool-use.json` | PostToolUse | Write runtime ledger entry with diff summary |
| `session-end.json` | SessionEnd | Write summary entry with session-aggregated stats |

### Custom agents

| File | Persona | Bundle reads | Tools allowed |
|---|---|---|---|
| `assessor.agent.md` | Classify ambiguities into typed cards | security, privacy | ledger MCP, file-read |
| `architect.agent.md` | Propose architecture given resolved decisions | architect, security | ledger MCP, file-read, file-write (strict path scope) |
| `codegen.agent.md` | Generate code aligned to architecture | architect, security | file-edit, terminal (limited), ledger MCP |
| `review-scan.agent.md` | Pre-merge review (SBOM + SAST + secret scan) | security | terminal (read-only scanners), ledger MCP |
| `pipeline-doctor.agent.md` | Drift detection + auto-fix + change-proposal | finops, all (read) | ledger MCP, gh CLI |
| `standards-change.agent.md` | Triage standards-change PRs | (all, meta) | gh CLI, file-read |

## Why this design

**MCP server, not REST direct.** The MCP protocol is the GH-blessed way to
expose tools. Wraps cleanly in any GH runtime, gets enterprise allow-list
governance for free, gets future Mission Control integration for free.
Underlying storage (Cosmos) is unchanged.

**Hooks for IDE coverage, not VS Code extension.** Hooks are open-standard
and work across cloud-agent + CLI + VS Code. A custom extension would only
cover one surface, require Marketplace publishing, and create a separate
audit story.

**Custom agents reference the same prompt library as Foundry agents.**
The prompt library file (`prompt_library.py` from v0.6) is exposed via the
MCP server's `ledger.get_prompt(stage, model)` tool. Custom agents pull the
same prompt the orchestrator uses. One source of truth for stage personas.

## A365 attribution

Every custom agent is registered as an A365 tenant agent identity at
deployment time (one-time bootstrap script: `deploy/scripts/register-a365-agents.sh`).
Each agent gets a stable `agent_principal_id`. Ledger entries written from
IDE Copilot sessions populate `actor.id = agent_principal_id`.

A separate fan-out worker reads new ledger entries and emits Microsoft Graph
audit events keyed on these IDs, so A365's admin pane sees the full
decision-level signal without polling Cosmos. Best-effort: if Graph emission
fails, the ledger entry still persists.

## Risks and rollback

| Risk | Mitigation | Rollback |
|---|---|---|
| Copilot SDK is technical preview (Jan 2026), API may change | Pin SDK version in `package.json`; isolate SDK calls behind `apps/decision-ledger-mcp/src/copilot-sdk-client.ts` | Replace SDK calls with REST direct against `api.github.com/agents/...` |
| Hook script kills IDE responsiveness | All hooks have 5s timeout; fail-open (don't block on infrastructure failures) | Per-hook `enabled: false` toggle in repo config |
| MCP server overload under heavy IDE usage | Container App with HPA scaling; rate-limit per team | Disable MCP from copilot-instructions; fall back to no IDE coverage |
| GH audit log → Graph fan-out endpoint shape uncertain | Build fan-out as Container Job with retry + DLQ; ledger writes are independent | Disable fan-out, fall back to direct Cosmos query in A365 PowerShell |

## Honest limitations

- **GHE.com Data Residency does not yet support Coding Agent.** EU /
  data-sovereignty customers are limited to the orchestrator pipeline lane
  + IDE hooks until GitHub closes that gap.
  (gh.com/community/discussions/167952)
- **Custom Agent files are read at session start but their ledger writes
  depend on the hooks firing.** A misconfigured `.github/hooks/` directory
  silently produces zero ledger coverage. Validation: `scripts/validate-hook-bundle.sh`.

## Test targets

- Unit (MCP server): 15 cases (tool routing, MCP protocol compliance, auth, schema)
- Unit (hooks): 10 cases (PHI classifier integration, ledger write, fail-open behavior)
- Integration: synthetic IDE session against MCP server → ledger query confirms entries
- E2E: real VS Code session + real Copilot agent + hook bundle → ledger entries visible
  in `/telemetry`
