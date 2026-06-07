## ADDED Requirements

### Requirement: LedgerEntry entry_type discriminator

Every Decision Ledger entry MUST carry an `entry_type` field with one of two values: `"runtime"` (decisions made during a pipeline run, IDE session, or coding-agent flow) or `"meta"` (changes to the standards rules themselves). Entries lacking the field MUST be treated as `"runtime"` for backward compatibility with v0.6.

#### Scenario: orchestrator writes a stage decision
- **WHEN** the pipeline orchestrator records a stage decision during a run
- **THEN** the persisted entry MUST have `entry_type = "runtime"` and `run_id` set

#### Scenario: standards-change PR merges
- **WHEN** a PR against `standards-bundles/` is merged
- **THEN** an entry MUST be written with `entry_type = "meta"` and `change_ticket_id` populated

### Requirement: bundle_refs attribution

Every entry where an agent applied a standards rule MUST populate `bundle_refs` as a list of fully-qualified rule references in the form `<dept>/<version>/<rule-id>`. Pipeline Doctor SHALL use this field to attribute drift signals per-bundle.

#### Scenario: agent applies a security rule
- **WHEN** an agent invokes rule `PHI-001` from `security/v0.1.0`
- **THEN** the resulting entry MUST contain `"security/v0.1.0/PHI-001"` in `bundle_refs`

#### Scenario: drift query by bundle
- **WHEN** Pipeline Doctor queries entries filtered by `bundle_refs` containing `finops/v0.1.0/COST-003`
- **THEN** Cosmos MUST return matching entries via the indexed `bundle_refs` path

### Requirement: meta-only fields on standards-change entries

A `meta` entry MUST carry `change_ticket_id`, `bundle_version_from`, `bundle_version_to`, `blast_class` (LOW | MED | HIGH), and at least one entry in `reviewers`. A `meta` entry MUST NOT carry `run_id` or `stage`. Optional fields include `canary_metrics` and `pr_url`.

#### Scenario: writing a meta entry without required fields
- **WHEN** the ledger receives a `meta` entry missing `change_ticket_id`
- **THEN** the write SHALL fail validation and return a 400 error

#### Scenario: meta entry with run_id
- **WHEN** a caller submits a `meta` entry with `run_id` set
- **THEN** the write SHALL be rejected with `"run_id is forbidden on meta entries"`

### Requirement: agent_session_id GitHub audit cross-reference

Entries originating from Agent-HQ-driven runtimes (cloud coding agent, IDE Copilot, chat bridges) MUST set `agent_session_id` to the GitHub Enterprise audit-log session ID, enabling compliance to join the Decision Ledger to GH's `actor:Copilot` audit log.

#### Scenario: cloud agent writes a runtime entry
- **WHEN** the cloud coding agent invokes `ledger.write_runtime` after a tool call
- **THEN** the entry MUST contain `agent_session_id` matching the GH audit session ID for that turn

### Requirement: runtime entries have correlation context

Every `runtime` entry MUST carry at least one of `run_id` or `agent_session_id`. Both entry types MUST set `team_id` (Cosmos partition key).

#### Scenario: runtime entry missing both correlation fields
- **WHEN** an entry has `entry_type = "runtime"` and neither `run_id` nor `agent_session_id`
- **THEN** the write SHALL fail validation

## MODIFIED Requirements

### Requirement: Cosmos indexing policy

The Cosmos container indexing policy MUST include indexed paths for `/entry_type/?`, `/bundle_refs/[]/?`, `/blast_class/?`, and `/agent_session_id/?` so that bundle-refs queries, blast-class queries, and audit-log joins return in p95 < 200ms.

#### Scenario: deploy applies indexing policy
- **WHEN** the Bicep deployment provisions the Cosmos container
- **THEN** the resulting indexing policy MUST contain all four indexed paths above

#### Scenario: query by entry_type
- **WHEN** a caller queries `entry_type = "meta"` over a 90-day window
- **THEN** the query SHALL complete in under 200ms p95
