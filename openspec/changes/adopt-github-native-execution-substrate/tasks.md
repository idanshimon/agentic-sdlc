# Tasks: adopt-github-native-execution-substrate

> **Status: DRAFT** (opened 2026-08-12)
> Phases 0–1 are substrate-independent and land on the current runtime first.
> No stage migrates until its GitHub equivalent is proven on a live run.

## 0 — Grounding (no code)

- [ ] 0.1 Confirm custom deployment protection rule callback shape + timeout budget (design Q2)
- [ ] 0.2 Decide per-stage vs per-run job granularity (design Q1) — record in design.md
- [ ] 0.3 Decide endorsement policy for promoted invariant-class lessons (design Q3)
- [ ] 0.4 Inventory every ACA-only dependency a migrated stage would lose (private endpoints first)

## 1 — Ledger schema: alternatives, confidence, gate reason

- [ ] 1.1 Add `rejected_options`, `decision_confidence`, `gate_reason` to `LedgerEntry`
      (`packages/ledger-core/ledger_core/models.py`)
- [ ] 1.2 Define the `GateReason` literal (7 values) alongside the existing vocab
- [ ] 1.3 Populate `rejected_options` at the resolve site (`apps/orchestrator/main.py` ~1878-1930)
      from `AmbiguityCard.options`
- [ ] 1.4 Stamp `gate_reason` on every gate-opening entry: invariant, autonomy tier, low precedent
- [ ] 1.5 Record `decision_confidence` on the autopilot path (`main.py:413-479`)
- [ ] 1.6 Assert no gate evaluation reads `decision_confidence` — confidence is evidence, not authority
- [ ] 1.7 Backward-compat: new fields default empty on pre-existing entries; no historical mutation

**Test targets:** `packages/ledger-core/tests/test_models.py`, `apps/orchestrator/tests/`
- multi-option card persists exactly the unselected options
- single-option card yields empty `rejected_options` and is not flagged as missing data
- `decision_confidence: 1.0` on a `phi-classification` card still gates
- pre-existing entry deserializes with new fields empty
- every gate-opening entry carries a non-null `gate_reason`

## 2 — Bundle citation honesty

- [ ] 2.1 Delete the hardcoded `bundle_refs` at `apps/orchestrator/stages/deliver_github.py:161`
- [ ] 2.2 Stamp `bundle_refs` in all seven stages, not only assessor (`main.py:475`, `main.py:1918`)
- [ ] 2.3 Distinguish rule-evaluated citation from subscription-set citation on the entry
- [ ] 2.4 Repo scan: no standards rule ID literal in stage implementation code

**Test targets:** `apps/orchestrator/tests/`
- completed run has non-empty `bundle_refs` on every stage-decision entry
- scan finds no hardcoded rule ID outside `standards-bundles/`

## 3 — Run-scoped artifact store

- [ ] 3.1 Store interface: write/read/append by name, run-scoped
- [ ] 3.2 Concurrent-safe append
- [ ] 3.3 Migrate architect → codegen handoff off the stage payload
- [ ] 3.4 Migrate review-scan findings accumulation
- [ ] 3.5 Lifecycle: entries are discarded with the run

**Test targets:** `apps/orchestrator/tests/`
- handoff exceeding the prior payload limit completes without truncation
- two concurrent appenders both land
- a new run cannot read a prior run's entries

## 4 — Run budget + operator halt

- [ ] 4.1 Declared budget: max stage retries, max run duration, idle timeout
- [ ] 4.2 Exhaustion halts and opens a gate with `gate_reason: budget_exceeded`
- [ ] 4.3 Idle timeout halts with `gate_reason: stalled`
- [ ] 4.4 Operator halt endpoint; ledger entry attributed `actor.kind: human`,
      `gate_reason: operator_requested`

**Test targets:** `apps/orchestrator/tests/`
- third failure under a two-retry budget halts with `budget_exceeded`, not a generic failure
- halt is attributed to the operator

## 5 — Teaching loop: make `accuracy_score` compute

> This closes the audit's most serious finding: `accuracy_score` is `0.0` on all 229 live entries.

- [ ] 5.1 Retrospective job (scheduled workflow) sampling completed runs at random across the window
- [ ] 5.2 Compute and write `accuracy_score` for examined decisions
- [ ] 5.3 Tentative lessons: recorded, weight below injection floor, never injected
- [ ] 5.4 Promotion only on recurrence of the same pattern at the same stage on a separate run
- [ ] 5.5 Asymmetric weighting (harm costs more than help gains) + decay for presented-but-unused
- [ ] 5.6 Archive below floor with a recorded tombstone reason; retire contradicted lessons
- [ ] 5.7 Lessons keyed by `(ambiguity_class, slot_value_hash)` — org-scoped, reusable across teams
- [ ] 5.8 PHI block on lesson content; human endorsement required for `INVARIANT_CLASSES` lessons
- [ ] 5.9 Reconcile with `add-teaching-signal-feedback` (42/56) — do not duplicate its shipped parts

**Test targets:** `apps/orchestrator/tests/`, `apps/pipeline-doctor/tests/`
- retrospective produces at least one non-zero `accuracy_score`, traceable to its run
- single observation is never injected
- same-stage recurrence promotes; different-stage recurrence does not
- harmful + helpful outcome nets below the starting weight
- lesson containing PHI is blocked and the block is recorded

## 6 — GitHub substrate: identity and the gate

- [ ] 6.1 OIDC federation to Azure; remove stored service-principal secrets from workflow auth
- [ ] 6.2 Environment with required reviewers for the resolver gate
- [ ] 6.3 Custom deployment protection rule calling the control plane for the classification verdict
- [ ] 6.4 Fail closed: unreachable control plane denies approval, records `gate_reason: stalled`
- [ ] 6.5 Prove the 409 holds through the GitHub approval path on a `phi-classification` card

### 6a — Harden the native gate (research findings; do NOT skip)

- [ ] 6a.1 Disable administrator bypass on every gating Environment — **it is ON by default**
- [ ] 6a.2 Enable "prevent self-review" on every gating Environment
- [ ] 6a.3 Enforce N-of-M named-approver quorum in the control plane by evaluating the approval
      set against `standards-bundles/<dept>/<version>/reviewers.yaml` (`required_approvers`,
      `must_include_roles` per `blast_class` — the policy already exists as data); the
      Environment's 1-of-6 approval MUST NOT be treated as the quorum authority
- [ ] 6a.4 Governance scan that fails when a gating Environment has bypass re-enabled (drift)
- [ ] 6a.5 Agent jobs carry no write permissions; writes materialize in a separate scoped job
- [ ] 6a.6 Deny-by-default network egress allowlist on agent-executing stages
- [ ] 6a.7 Pin the agentic-workflow toolchain to an explicit version; no floating references
- [ ] 6a.8 Author the preview-dependency inventory: maturity + fallback per dependency
      (custom deployment protection rules = public preview; toolchain = research-stage)
- [ ] 6a.9 Record the data-residency blocker: the Copilot coding agent lane is unavailable on
      data-residency deployments — substrate choice is per-customer

### 6b — Retention (regulatory, not optional)

- [ ] 6b.1 Confirm decision records persist in the control-plane store independent of
      Actions log/artifact retention (which is days, not years)
- [ ] 6b.2 Enable enterprise audit-log streaming to an external sink with write-once retention
- [ ] 6b.3 Document the retention period against the binding obligations: 6 years
      (HIPAA §164.316(b)(2)(i)), ≥6 months for AI logs (EU AI Act Art. 26)

**Test targets:** `apps/orchestrator/tests/`, plus live verification (see §8)
- verdict endpoint reports hard-gated for invariant classes
- unreachable control plane denies rather than allows
- quorum policy rejects a single approval when two distinct approvers are required
- governance scan fails an Environment with administrator bypass enabled

## 7 — Stage migration (flag-gated, one stage at a time)

- [ ] 7.1 Migration flag per stage; prior path remains functional
- [ ] 7.2 Phase 1 — `review_scan` (deterministic, already has `bundle-enforce.yml`, no consumer)
- [ ] 7.3 Phase 2 — resolver gate via Environment (depends on §6)
- [ ] 7.4 Phase 3 — `architect`, `test_plan`, `codegen` on the GitHub agent runtime
      using existing `.github/agents/` personas
- [ ] 7.5 Per-stage rollback proven: disable one flag, other stages unaffected
- [ ] 7.6 Phase 4 — decommission the prior stage executor only after every stage has a
      recorded live GitHub run

## 8 — Live verification (tests passing is not sufficient)

- [ ] 8.1 `phi-classification` card approved via the GitHub Environment path, submitted as `bulk`,
      observed HTTP 409 — not a unit test
- [ ] 8.2 Live ledger entry read back from Cosmos with non-empty `rejected_options`
- [ ] 8.3 Live entry with `accuracy_score != 0.0` and the retrospective run identified
- [ ] 8.4 Live run authenticating to Azure by federated token, no stored secret
- [ ] 8.5 Stage handoff exceeding the prior payload limit completing on the substrate
- [ ] 8.6 Report status split: verified live / verified locally / implemented-not-proven / blocked

## Rollback plan

Every phase is independently reversible.

| Phase | Rollback |
|---|---|
| 1, 2 | New ledger fields are additive and default empty. Revert the write sites; existing entries are unaffected because none were mutated. |
| 3 | Artifact store sits behind the stage-handoff interface. Revert to payload-passing; the truncation limit returns but no data is lost. |
| 4 | Budget and halt are additive. Disable the budget check; runs behave as before. |
| 5 | Retrospective is a scheduled job. Disable the schedule. Promoted lessons stop being written; injection is gated by weight, so tentative lessons were never influencing runs. Archive promoted lessons rather than deleting — they are ledger entries and the ledger is append-only. |
| 6 | Environment protection is additive to the existing in-app approval path, which remains functional. Remove the protection rule; approvals route as they do today. The classification verdict is computed by the control plane either way. |
| 7 | Per-stage flag. Disable to return that stage to the prior executor. No cross-stage coupling. Phase 4 decommission is the only irreversible step and is gated on §8 evidence for every stage. |

**Irreversible step:** Phase 4 (7.6) only. It MUST NOT proceed until 8.1–8.5 are recorded for
every stage.
