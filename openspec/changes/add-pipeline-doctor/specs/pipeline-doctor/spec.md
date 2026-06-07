## ADDED Requirements

### Requirement: Pipeline Doctor scheduled agent

A scheduled Foundry-registered agent named `pipeline-doctor` MUST consume the Decision Ledger and produce one of two outputs per drift signal: an auto-fix entry (within bounded envelope) or a change proposal (PR opened on the relevant standards bundle).

#### Scenario: scheduled run with no drift
- **WHEN** Pipeline Doctor runs on schedule and no drift signals fire
- **THEN** the run MUST exit with no auto-fix entries and no PRs opened

#### Scenario: drift signal triggers output
- **WHEN** any monitored drift signal exceeds its threshold
- **THEN** Pipeline Doctor MUST emit either an auto-fix runtime entry or a standards-change PR

### Requirement: Five monitored drift signals

Pipeline Doctor MUST monitor at least the five v0.1 signal types: `autopilot_rejection_rate_high`, `cost_per_decision_climbing`, `class_drift_unexpected`, `bundle_rule_unused`, and `phi_class_violation`. Each signal SHALL have an explicit threshold and observation window.

#### Scenario: autopilot rejection rate over threshold
- **WHEN** autopilot decisions on an ambiguity class are rejected by HITL reviewers > 25% over a 7-day window
- **THEN** the `autopilot_rejection_rate_high` signal MUST fire

#### Scenario: cost climb
- **WHEN** a stage's mean cost-per-decision exceeds 1.5× the 30-day baseline
- **THEN** the `cost_per_decision_climbing` signal MUST fire

#### Scenario: PHI violation detected
- **WHEN** an orchestrator stage rejects an attempted PHI write that should have been blocked earlier
- **THEN** the `phi_class_violation` signal MUST fire and a HIGH-priority change proposal MUST be opened

### Requirement: Envelope contract per bundle

Each bundle MUST declare its allowed auto-fixes at `standards-bundles/<dept>/v<n>/envelope.yaml`. The envelope MUST specify `allowed_auto_fixes` (rule patterns + bounds + preconditions) and `forbidden` (rule patterns or properties that block auto-fix). Pipeline Doctor MUST refuse to auto-fix any rule outside the envelope.

#### Scenario: out-of-envelope rule
- **WHEN** Pipeline Doctor detects drift on a rule not in `allowed_auto_fixes`
- **THEN** Pipeline Doctor MUST open a change proposal PR rather than auto-fix

### Requirement: Hard-coded auto-fix prohibitions

Pipeline Doctor MUST NEVER auto-fix any rule with `phi: true`, MUST NEVER auto-fix any rule matching `deny/*` (deny rules cannot be loosened), and MUST rate-limit auto-fixes to a maximum of 5 per department per 7-day window.

#### Scenario: PHI auto-fix attempt
- **WHEN** envelope bounds appear to permit auto-fix of a `phi: true` rule
- **THEN** Pipeline Doctor MUST refuse and open a change proposal PR instead

#### Scenario: rate limit hit
- **WHEN** 5 auto-fixes have already landed for `security/v0.1.0` within a 7-day window
- **THEN** the 6th drift signal in that window MUST produce a change proposal PR, not an auto-fix

### Requirement: Auto-fix output shape

When Pipeline Doctor applies an auto-fix, it MUST write a `runtime` ledger entry with `actor.id = "pipeline-doctor"` and `kind = "auto_fix"`. It MUST emit a notification to the configured Teams/Slack channel and MUST return the entry ID for downstream traceability.

#### Scenario: auto-fix lands successfully
- **WHEN** Pipeline Doctor applies an envelope-bounded auto-fix
- **THEN** a `runtime` entry MUST be written with `actor.id = "pipeline-doctor"` and `kind = "auto_fix"` AND a Teams/Slack notification MUST be sent within 30 seconds

### Requirement: Change-proposal PR shape

When Pipeline Doctor opens a change proposal PR on `standards-bundles/<dept>`, the PR title MUST follow `[<blast_class>] Doctor proposes <rule-id> change: <one-line>`. The PR body MUST render the ADR template plus drift evidence plus the recommended diff. PR labels MUST include `pipeline-doctor`, `standards-change`, and `blast/<class>`. Reviewers MUST be assigned from `standards-bundles/<dept>/v<n>/reviewers.yaml`.

#### Scenario: PR title formatting
- **WHEN** Pipeline Doctor opens a HIGH-blast change proposal for rule `PHI-001`
- **THEN** the PR title MUST start with `[HIGH] Doctor proposes PHI-001 change: `

#### Scenario: PR labeling
- **WHEN** any change-proposal PR opens
- **THEN** the PR labels MUST include `pipeline-doctor`, `standards-change`, and `blast/<class>`

## MODIFIED Requirements

### Requirement: Decision Ledger schema usage

Pipeline Doctor MUST rely on the `bundle_refs` and `blast_class` fields added in the `extend-ledger-runtime-meta-entries` change. Auto-fix entries MUST populate `bundle_refs` to maintain attribution. Change-proposal PRs SHALL carry the proposed bundle change in their PR diff (NOT in the ledger entry).

#### Scenario: auto-fix entry attribution
- **WHEN** Pipeline Doctor writes an auto-fix entry against rule `cost-001` in `finops/v0.1.0`
- **THEN** the entry's `bundle_refs` MUST contain `"finops/v0.1.0/cost-001"`
