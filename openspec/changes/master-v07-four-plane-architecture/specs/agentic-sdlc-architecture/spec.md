## ADDED Requirements

### Requirement: Four-plane architecture composition

The v0.7 reference design MUST compose exactly four logical planes plus one cross-plane component:

- Plane 1 — Standards: per-department versioned policy bundles, committee-reviewed.
- Plane 2 — Pipeline: 9-stage governed pipeline with GitHub delivery as default.
- Plane 3 — Ledger: two entry types (`runtime`, `meta`), exposed via orchestrator, MCP server, and manual API.
- Plane 4 — Agent HQ: coding-agent + IDE + chat-bridge runtime lanes, ledger-covered.
- Cross-plane: Pipeline Doctor — reads the ledger continuously, auto-fixes within envelopes, proposes standards changes via PR.

#### Scenario: a deployed v0.7 environment
- **WHEN** an operator inspects the deployment topology
- **THEN** all four planes plus Pipeline Doctor MUST be present and observable

#### Scenario: missing plane
- **WHEN** any of the four planes is absent or non-functional
- **THEN** the deployment SHALL be considered non-conforming to v0.7

### Requirement: 100% ledger coverage of agentic activity

The Decision Ledger MUST receive entries from three distinct writer surfaces — orchestrator (pipeline lane), Agent HQ (coding-agent + IDE lanes), and manual API (human override) — and all three SHALL persist into the same Cosmos container with `/team_id` partitioning.

#### Scenario: pipeline run writes
- **WHEN** the orchestrator completes a pipeline stage
- **THEN** a `runtime` entry MUST be written from the orchestrator surface

#### Scenario: cloud coding agent session
- **WHEN** the GitHub cloud coding agent completes a tool call
- **THEN** a `runtime` entry MUST be written via the Agent HQ surface with `agent_session_id` populated

#### Scenario: manual override
- **WHEN** a human submits an override via the manual API
- **THEN** a `runtime` entry MUST be written with `actor.kind = "human"`

#### Scenario: cross-surface query
- **WHEN** the /telemetry dashboard queries the last 24 hours
- **THEN** entries from all three writer surfaces MUST be returned in a single query against one container

### Requirement: GitHub-as-target with ADO opt-in

The Deliver stage MUST default to GitHub as the delivery target. ADO delivery SHALL remain supported via the `deliver_provider` config flag for legacy customers (HCA-style targets) but MUST NOT be the default.

#### Scenario: default deploy
- **WHEN** a fresh v0.7 environment is deployed without overrides
- **THEN** the Deliver stage MUST be configured for GitHub delivery

#### Scenario: ADO opt-in
- **WHEN** a customer config sets `deliver_provider = "ado"`
- **THEN** the orchestrator SHALL execute ADO delivery and refuse to fall through to GitHub silently

### Requirement: v0.6 verified substrate preserved

v0.7 MUST preserve the v0.6 verified-working substrate end-to-end: Foundry-registered agents, the prompt library (42 variants × 6 stages × 7 providers), VNET private endpoints, Managed-Identity-only data-plane auth, and the `/telemetry` dashboard. None of these MAY be removed as part of v0.7 adoption.

#### Scenario: prompt library intact
- **WHEN** the orchestrator selects a prompt for a stage
- **THEN** all 42 variants × 6 stages × 7 providers MUST resolve from the prompt library

#### Scenario: data-plane auth
- **WHEN** any orchestrator component reads from Cosmos, Storage, or Key Vault
- **THEN** the call MUST authenticate via Managed Identity (no account keys, no connection strings with keys)

### Requirement: Honest end-to-end demo

A live deployed v0.7 environment MUST be available at documented URLs and MUST exercise all four planes including at least one `meta` ledger entry produced by a real standards-change committee flow. Stub-only or mocked demos SHALL NOT count as conforming.

#### Scenario: demo entry verification
- **WHEN** a customer follows the demo script end-to-end
- **THEN** at least one `runtime` entry from each writer surface AND at least one `meta` entry MUST be present in the ledger queryable via /telemetry

## MODIFIED Requirements

### Requirement: Telemetry covers both entry types

The `/telemetry` dashboard MUST render both `runtime` and `meta` entries, with filters for `entry_type`, `bundle_refs`, `blast_class`, and `actor.kind`. Cost-per-decision SHALL be computed across runtime entries only.

#### Scenario: filter by meta
- **WHEN** an operator filters /telemetry to `entry_type = "meta"`
- **THEN** only standards-change ledger entries MUST render, with reviewer roster and bundle-version transition surfaced

#### Scenario: cost-per-decision excludes meta
- **WHEN** /telemetry computes cost-per-decision for a 30-day window
- **THEN** the calculation MUST exclude `meta` entries (which have no `cost_usd`)
