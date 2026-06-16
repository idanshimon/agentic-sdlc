# Spec delta: ship-operator-grade-pipeline-workflow / ledger-decision-audit

## ADDED Requirements

### Requirement: Every decision ledger entry MUST pin its prompt resolution chain

When a stage helper resolves a prompt via the `PromptCatalog` and stashes the chain on `run.prompt_chain_by_stage[stage]`, every `LedgerEntry` produced by that stage's decisions MUST set `prompt_resolution_path` to that chain. The chain MUST be the full inheritance walk (team → persona → global) with the matched scope marked, NOT only the matched step.

Pre-Phase-2 ledger entries (no chain pinned by the orchestrator at write time) MUST render as "chain unavailable (pre-v2)" in operator surfaces, NOT as silent missing data.

#### Scenario: per-card approve writes ledger entry with chain

- **GIVEN** a run where the assessor stage resolved its prompt to `(global, assessor-global, v1)` and stashed the chain
- **WHEN** the operator approves a card via `POST /api/runs/{run_id}/approve`
- **THEN** the resulting LedgerEntry written to Cosmos MUST have `prompt_resolution_path` populated
- **AND** the chain MUST contain at least one entry with `matched: true`
- **AND** the matched entry MUST have `prompt_id`, `version`, `git_sha`, and `owner_persona` fields populated

#### Scenario: legacy entry with no chain renders as "unavailable"

- **GIVEN** a LedgerEntry written before the Phase 2.6 chain-pinning fix shipped
- **WHEN** the operator views the entry on `/decisions`
- **THEN** the PromptChainBadge MUST render the italic hint "chain unavailable (pre-v2)"
- **AND** the entry MUST still display all other fields (decision, rationale, actor, cost, bundle citations)

### Requirement: LedgerEntry schema MUST include entry_type discriminator

`LedgerEntry` MUST have a required `entry_type: str` field with default value `"runtime"`. This discriminator allows `ledger-core.CosmosLedger.write_entry()` to partition runtime entries from meta entries (drift detection, autopilot summaries, etc.).

#### Scenario: a default-constructed LedgerEntry serializes with entry_type

- **GIVEN** a `LedgerEntry` constructed with only the required fields (team_id, run_id, decision, actor, rationale, model_used)
- **WHEN** the entry is serialized via `model_dump()`
- **THEN** the output dict MUST include `"entry_type": "runtime"`
- **AND** `ledger-core.write_entry()` MUST accept the entry without raising AttributeError

### Requirement: Orchestrator MUST expose a run-scoped ledger read endpoint

The orchestrator MUST expose `GET /api/runs/{run_id}/ledger` returning all ledger entries written for that run, bypassing the ledger-mcp's per-token team-partition RBAC. The endpoint uses the orchestrator's already-authenticated Cosmos client so operator surfaces can render decision details without separate auth flow.

#### Scenario: run ledger endpoint returns entries with chain pinned

- **GIVEN** a run with 5 decisions written through the per-card approve path
- **WHEN** `GET /api/runs/{run_id}/ledger` is called
- **THEN** the response MUST be HTTP 200 with `{run_id, team_id, count: 5, entries: [...]}`
- **AND** each entry MUST include `prompt_resolution_path` showing the full chain
