# Configuration Plane — capability spec

## ADDED Requirements

### Requirement: COE-authored organization model
The system SHALL read an authorable `config/org.yaml` defining departments,
teams (with department, m365_group, cost_center), and identity mapping
(entra_tenant_id, approver RBAC), and SHALL attribute every ledger entry to a
real team and identity resolved from it.

#### Scenario: decision attributed to a configured team
- **WHEN** a pipeline stage writes a decision for a run whose `team_id` matches a
  team in `config/org.yaml`
- **THEN** the ledger entry's `actor` and team attribution resolve to that team's
  configured cost_center and m365_group, not a placeholder

#### Scenario: unknown team is rejected, not silently anonymized
- **WHEN** a run references a `team_id` absent from `config/org.yaml`
- **THEN** the orchestrator refuses the run with an error citing the missing team
  rather than writing an anonymous ledger entry

### Requirement: authorable standards bundles with blast class and PHI lock
The system SHALL allow departments to author and version their own standards
bundles, each rule carrying `blast_class` (low|med|high) and `phi_locked`
(boolean), edited via governed PR write-back (never live mutation).

#### Scenario: editing a rule opens a governed PR
- **WHEN** a COE user edits a bundle rule through the config surface
- **THEN** the change opens a pull request against the customer repo's
  `standards-bundles/<dept>/` file and does not mutate the live bundle until merge

### Requirement: autonomy matrix as configuration
The system SHALL read a `config/autonomy.yaml` mapping each
(decision_class × team) to one of `gate`, `autopilot_above_threshold(t)`, or
`autopilot_always`, and SHALL drive resolver-gate behaviour from it instead of
code-resident logic.

#### Scenario: PHI classes cannot be configured open
- **WHEN** `config/autonomy.yaml` sets `phi-classification` or `auth-policy` to
  any autopilot mode
- **THEN** the validator rejects the config and the class remains hard-locked to
  human gate

#### Scenario: autopilot honors the configured threshold
- **WHEN** a non-locked decision class for a team is set to
  `autopilot_above_threshold(0.8)` and a precedent match scores 0.85
- **THEN** the resolver autopilots the decision and writes a ledger entry citing
  the autonomy rule and the precedent

### Requirement: model policy enforcement
The system SHALL read a `config/models.yaml` (allowlist, denylist, phi_eligible,
per-stage routing, cost_ceiling_usd) and SHALL enforce it at stage dispatch.

#### Scenario: denied model blocks the stage
- **WHEN** a stage's routed model is absent from the allowlist or present in the
  denylist
- **THEN** the run gates or fails with a ledger entry citing the model-policy rule

#### Scenario: PHI-adjacent stage requires a cleared model
- **WHEN** a stage handling PHI-classified content routes to a model not in
  `phi_eligible`
- **THEN** the orchestrator refuses the stage and records the refusal with the
  governing rule reference

### Requirement: unified compliance query surface
The system SHALL expose a single query endpoint and UI that returns, per AI
decision, the decision, its rationale, the governing bundle rule version, the
actor kind and identity, and the cost — filterable by phi_class, date range,
actor kind, and team, across all decision-producing surfaces.

#### Scenario: the acceptance query returns complete rows
- **WHEN** a compliance user queries all decisions with `phi_class=high` over the
  last 30 days
- **THEN** each returned row includes a non-null governing rule version, actor
  identity, model used, and cost, with no placeholder or fabricated values

#### Scenario: cross-surface capable
- **WHEN** decisions exist from more than one producing surface (pipeline plus a
  future connector)
- **THEN** the same query returns rows from all surfaces without a surface-specific
  code path
