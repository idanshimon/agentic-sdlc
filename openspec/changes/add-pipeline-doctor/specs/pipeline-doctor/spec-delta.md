# Spec delta — capability: pipeline-doctor

## Added

### Pipeline Doctor agent

A scheduled Foundry-registered agent that consumes the Decision Ledger and
produces one of two outputs per drift signal: an auto-fix (within bounded
envelope) or a change proposal (PR opened on the relevant standards bundle).

### Drift signals

The Doctor monitors five signal types initially:

1. `autopilot_rejection_rate_high` — autopilot decisions on an ambiguity class
   are being rejected by HITL reviewers > 25% over a 7-day window.
2. `cost_per_decision_climbing` — a stage's mean cost-per-decision exceeds
   1.5× the 30-day baseline.
3. `class_drift_unexpected` — a new ambiguity class is appearing with frequency
   > 5% but has no precedent entries.
4. `bundle_rule_unused` — a bundle rule has zero `bundle_refs` matches over
   the last 30 days.
5. `phi_class_violation` — an orchestrator stage rejected an attempted PHI
   write that should have been blocked earlier.

### Envelope contract

Each bundle declares its allowed auto-fixes at
`standards-bundles/<dept>/v<n>/envelope.yaml`. The envelope MUST specify:

- `allowed_auto_fixes` — list of rule patterns, bounds (min/max/max_delta),
  and required preconditions (e.g. drift signal duration).
- `forbidden` — list of rule patterns or properties that block auto-fix
  even if envelope bounds are met.

### Hard-coded constraints (override any envelope)

- PHI rules (`phi: true`) are NEVER auto-fixed.
- Deny rules (`rule_pattern: "deny/*"`) are NEVER auto-fixed (cannot be loosened).
- Auto-fix is rate-limited to 5 / department / 7-day-window.

### Outputs

**Auto-fix outputs:**
- Writes a `runtime` ledger entry with `actor.id = "pipeline-doctor"` and
  `kind = "auto_fix"`.
- Emits notification to configured Teams/Slack channel.
- Returns the entry ID for downstream traceability.

**Change-proposal outputs:**
- Opens a PR on `standards-bundles/<dept>` repo (or directory in v0.7 demo).
- PR title format: `[<blast_class>] Doctor proposes <rule-id> change: <one-line>`
- PR body renders the ADR template + drift evidence + recommended diff.
- PR labels: `pipeline-doctor`, `standards-change`, `blast/<class>`.
- PR reviewers assigned from `standards-bundles/<dept>/v<n>/reviewers.yaml`.

## Modified

### Decision Ledger schema

The Doctor relies on `bundle_refs` and `blast_class` fields added in the
`extend-ledger-runtime-meta-entries` change. Doctor's auto-fix entries
populate `bundle_refs` to maintain attribution; change proposals carry
the proposed bundle change in their PR diff (not in the ledger).
