## ADDED Requirements

### Requirement: Decision Ledger MCP server

A Node.js TypeScript MCP server MUST run at `apps/decision-ledger-mcp/` exposing the Decision Ledger as MCP tools to any GitHub runtime (cloud agent, CLI, VS Code). The server MUST support both stdio (default) and HTTP (for Container Apps deployment) transports. Authentication SHALL use bearer tokens scoped per team.

#### Scenario: stdio transport
- **WHEN** an MCP client connects via stdio
- **THEN** the server MUST accept the connection without HTTP listener startup

#### Scenario: HTTP transport with valid token
- **WHEN** an MCP client connects via HTTP with a bearer token scoped to `team_a`
- **THEN** the server MUST authenticate and scope all tool responses to `team_a` data only

#### Scenario: HTTP transport with missing token
- **WHEN** an MCP client connects via HTTP without a bearer token
- **THEN** the server MUST reject the connection with HTTP 401

### Requirement: Five MCP ledger tools

The Decision Ledger MCP server MUST expose at least these five tools: `ledger.query`, `ledger.write_runtime`, `ledger.find_precedent`, `ledger.get_bundle`, and `ledger.classify_phi`. Each tool MUST respond within 5 seconds (matching the hook timeout budget).

#### Scenario: ledger.query by team
- **WHEN** an agent calls `ledger.query` with `team_id = "team_a"` and a date range
- **THEN** the server MUST return only `team_a` entries within the range, in under 5 seconds

#### Scenario: ledger.find_precedent
- **WHEN** an agent calls `ledger.find_precedent` with `ambiguity_class = "AUTH-POLICY"`
- **THEN** the server MUST return prior decisions on that class ranked by recency

#### Scenario: ledger.write_runtime validation
- **WHEN** an agent calls `ledger.write_runtime` with an entry missing `team_id`
- **THEN** the server MUST reject the write with a schema error

### Requirement: Five lifecycle hooks

The repository MUST ship five lifecycle hooks at `.github/hooks/`: `session-start.json`, `user-prompt-submit.json`, `pre-tool-use.json`, `post-tool-use.json`, and `session-end.json`. Each hook MUST have both bash and PowerShell scripts, MUST honor a 5-second timeout, and MUST fail-open on infrastructure failures so MCP unavailability cannot block the user's IDE.

#### Scenario: PreToolUse blocks raw PHI
- **WHEN** the PreToolUse hook detects a tool call containing raw PHI (full DOB + name)
- **THEN** the hook MUST BLOCK the tool call and write a `phi_class_violation` ledger entry

#### Scenario: hook fail-open on MCP outage
- **WHEN** the MCP server is unreachable and a hook's 5-second timeout fires
- **THEN** the hook MUST allow the tool call to proceed and log a degraded-mode warning

#### Scenario: PostToolUse writes runtime entry
- **WHEN** a tool call completes successfully in an Agent-HQ session
- **THEN** the PostToolUse hook MUST write a `runtime` ledger entry with `agent_session_id` populated

### Requirement: Six custom agent files

`.github/agents/` MUST contain six custom agent files: `assessor.agent.md`, `architect.agent.md`, `codegen.agent.md`, `review-scan.agent.md`, `pipeline-doctor.agent.md`, and `standards-change.agent.md`. Each file MUST declare `persona`, `allowed_tools` (MCP server names), `bundle_subscriptions`, and `preferred_model` in YAML frontmatter that validates against `.github/agents/agent-frontmatter.schema.json`.

#### Scenario: missing required frontmatter field
- **WHEN** a custom agent file lacks `bundle_subscriptions` in frontmatter
- **THEN** CI MUST reject the PR introducing the malformed file

#### Scenario: SessionStart bundle injection
- **WHEN** the architect custom agent is invoked
- **THEN** the SessionStart hook MUST inject all bundles listed in `architect.agent.md`'s `bundle_subscriptions` via `ledger.get_bundle`

### Requirement: A365 attribution scripts

The repository MUST ship a one-time bootstrap script at `deploy/scripts/register-a365-agents.sh` that registers each `.github/agents/*.agent.md` as an A365 tenant agent identity, AND a fan-out worker at `deploy/scripts/sync-a365-from-ledger.py` that emits Microsoft Graph audit events for every new ledger entry.

#### Scenario: bootstrap registration
- **WHEN** `register-a365-agents.sh` runs against a clean tenant
- **THEN** every `.github/agents/*.agent.md` MUST be registered as an A365 agent identity exactly once

#### Scenario: fan-out worker emits Graph events
- **WHEN** a new ledger entry is written
- **THEN** the fan-out worker MUST emit a corresponding Microsoft Graph audit event within 60 seconds

## MODIFIED Requirements

### Requirement: AGENTS.md references custom agent inventory

The root `AGENTS.md` MUST reference the custom agent file inventory under `.github/agents/` and MUST list each agent's bundle subscriptions in the personas table.

#### Scenario: AGENTS.md missing an agent
- **WHEN** a new agent is added to `.github/agents/` but the personas table in `AGENTS.md` is not updated
- **THEN** CI MUST fail with `"AGENTS.md personas table out of date"`

### Requirement: Cosmos partition strategy unchanged

The Decision Ledger MCP server MUST use the same Cosmos partition key as the orchestrator (`/team_id`). No partition strategy change is permitted as part of this integration.

#### Scenario: cross-team query
- **WHEN** an MCP client scoped to `team_a` queries entries
- **THEN** Cosmos MUST scan only the `team_a` partition
