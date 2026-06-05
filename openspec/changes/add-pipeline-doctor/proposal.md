# Proposal: add Pipeline Doctor agent

> **Status:** DRAFT
> **Capability:** pipeline-doctor
> **Related:** master-v07-four-plane-architecture, extend-ledger-runtime-meta-entries

## Why

The v0.6 ledger captured every decision but had no consumer that fed back
into pipeline improvement. Compliance audited; finance reviewed costs;
engineering looked at class-drift charts. Nobody **acted** on the signal.

Pipeline Doctor is the missing consumer. It reads the ledger continuously
and produces one of two outputs:

1. **AUTO-FIX** — within explicitly bounded envelopes per department bundle.
   Examples: "lower autopilot confidence threshold for [auth-policy] from
   0.85 → 0.82 on team X" (within finops envelope `[0.80, 0.90]`).
2. **PROPOSE-CHANGE** — for everything outside envelopes. Opens a PR on
   the relevant `standards-bundles/<dept>` repo with an Architecture
   Decision Record (ADR) draft attached. Pipeline Doctor never directly
   merges; the standards-change-agent + committee handle that.

## What changes

A new app at `apps/pipeline-doctor/` and a new custom agent file at
`.github/agents/pipeline-doctor.agent.md`.

The Doctor is a Foundry-registered agent (one A365 identity), invoked
on a schedule via Container Job (every 1 hour by default, configurable).

### Components

```
apps/pipeline-doctor/
├── pipeline_doctor/
│   ├── __init__.py
│   ├── main.py                  # entrypoint (cron / Container Job)
│   ├── models.py                # DriftSignal, AutoFixProposal, ChangeProposal, EnvelopeCheck
│   ├── drift_detector.py        # reads ledger via packages/ledger-core, surfaces signals
│   ├── envelope_validator.py    # loads bundle envelope.yaml, validates proposed changes
│   ├── auto_fixer.py            # applies in-envelope changes, writes runtime ledger entry
│   └── change_proposer.py       # opens PR on standards-bundles/<dept> with ADR
├── tests/
└── pyproject.toml
```

### Drift signals (initial set)

| Signal | What triggers it | Auto-fix envelope (example) |
|---|---|---|
| `autopilot_rejection_rate_high` | > 25% rejection on a class for 7 days | Lower autopilot threshold ±0.05 (finops envelope) |
| `cost_per_decision_climbing` | Stage cost > 1.5× 30-day baseline | Switch provider per stage_provider_overrides (architect envelope) |
| `class_drift_unexpected` | New ambiguity class freq > 5% with no precedent | NO auto-fix; always proposes change |
| `bundle_rule_unused` | Rule with `bundle_refs` count = 0 over 30 days | Tag for committee review (no fix) |
| `phi_class_violation` | PHI rule rejected by orchestrator | NO auto-fix; immediate human escalation |

### Envelope schema

Each bundle declares its envelope at `standards-bundles/<dept>/v<n>/envelope.yaml`:

```yaml
# Example: finops envelope
allowed_auto_fixes:
  - rule_pattern: "autopilot/threshold/*"
    bounds:
      min: 0.80
      max: 0.95
      max_delta_per_run: 0.05
    requires:
      - drift_signal_present_for_days: 7
      - phi_class_not_high

forbidden:
  - phi: true   # PHI rules NEVER auto-fixed
  - rule_pattern: "deny/*"  # explicit-deny rules cannot be loosened
```

### Outputs

**Auto-fix:** writes a `runtime` ledger entry, kind = `auto_fix`, sets
`actor.kind = "agent"`, `actor.id = pipeline-doctor`. Emits a notification
to a configured Teams/Slack channel.

**Change proposal:** opens a PR on `standards-bundles/<dept>` with:
- Title: `[<blast_class>] Doctor proposes <rule-id> change: <one-line-summary>`
- Body: ADR draft (template at `apps/pipeline-doctor/templates/adr.md.j2`),
  drift signal evidence, recommended diff, blast classification rationale,
  required reviewers list pulled from `reviewers.yaml`.
- Labels: `pipeline-doctor`, `standards-change`, `blast/<class>`.
- Reviewers: assigned per `reviewers.yaml`.

## Why this design (the constraints)

**Pipeline Doctor cannot directly change rules.** Even on highest confidence.
Reason: a doctor that auto-merges PHI rule changes is the failure mode that
ends the engagement. Every rule change is a human-attributed decision, even
if the proposal was machine-authored.

**Auto-fix is bounded by envelopes declared per-bundle.** The doctor cannot
unilaterally exceed a bound. Envelope changes themselves require a
standards-change PR (so the bounds are governance-controlled, not doctor-controlled).

**PHI rules can never be auto-fixed.** Hard-coded check in `envelope_validator.py`:
if any rule with `phi: true` is in scope, auto-fix is rejected at the validator
boundary. Even if a bundle's envelope.yaml accidentally allows it, the validator
overrides.

## Risks and rollback

| Risk | Mitigation | Rollback |
|---|---|---|
| Auto-fix produces wrong threshold | Envelope bounds + dry-run mode for first N runs | Toggle `auto_fix.enabled = false` in config |
| Doctor opens PR storm | Rate limit: 5 PRs / dept / week max | `change_proposer.enabled = false` |
| Doctor misses signal | Ledger query has retention window of 90 days; signals re-evaluated each run | Increase scheduled frequency or run manually |

## Test targets

- Unit: 25 cases minimum
  - Envelope validation (PHI block, deny-rule block, bound enforcement)
  - Drift signal detection (each of 5 signal types)
  - Auto-fix payload construction (correct ledger fields)
  - Change-proposer PR-body template rendering
- Integration: against synthetic ledger fixture (10 runtime entries → expect 1 auto-fix + 1 change proposal)
- E2E: live ledger query → verify Doctor produces output without errors
