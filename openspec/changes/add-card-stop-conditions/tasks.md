# Tasks: stop conditions on ambiguity cards

Checkboxes are ticked ONLY when the work is verifiably done — not when it is
planned. An unticked box on shipped work is the same class of defect as a BLOCK
rule with no scanner: an artifact that misreports reality.

## Phase 0 — governance

- [x] Write the proposal (`proposal.md`)
- [x] Write the spec delta with normative requirements (`specs/pipeline/spec.md`)
- [ ] Roster review + approval per the bundle's declared reviewers
- [ ] Resolve the three open questions in the proposal

## Phase 1 — schema (additive, no behaviour change)

- [ ] Add `StopKind` enum: `scope | dependency | data | cost | confidence`
- [ ] Add `StopCondition` model (`statement`, `kind`, `detectable`, `mechanism`)
- [ ] Add optional `stop_conditions: list[StopCondition]` to `AmbiguityCard`
- [ ] Validator: reject `detectable: true` with an empty `mechanism`
- [ ] Validator: an LLM-judgement mechanism coerces `detectable` to `false`
- [ ] Unit tests for both validators, including the coercion path

## Phase 2 — assessor emits conditions

- [ ] Extend the assessor prompt to emit stop conditions per card
- [ ] Prompt library entry + version bump
- [ ] Golden-file test: a PRD with a known scope boundary yields a `scope` condition
- [ ] Test: the assessor emitting zero conditions remains legal

## Phase 3 — enforcement at the resolve gate

- [ ] Breached condition forces a human gate regardless of earned autonomy
- [ ] Gate reason cites the breached condition
- [ ] Test: invariant class still gates when all conditions are satisfied
- [ ] Test: satisfied conditions are not counted as promotion evidence

## Phase 4 — downstream evaluation

- [ ] Deterministic evaluator for `StopKind.dependency` (new external dep introduced)
- [ ] Deterministic evaluator for `StopKind.data` (new store / schema migration)
- [ ] Deterministic evaluator for `StopKind.cost` (blast radius exceeded)
- [ ] Stage failure cites the breached condition
- [ ] `scope` and `confidence` evaluators — DEFERRED, ship as advisory first

## Phase 5 — ledger + surfaces

- [ ] Record declared vs. evaluated conditions on the resolution entry
- [ ] Compliance view distinguishes "none declared" from "all satisfied"
- [ ] UI renders advisory conditions visibly differently from enforced ones
- [ ] Card detail shows conditions with their mechanism (or "advisory")

## Phase 6 — docs

- [ ] `docs/onboarding-and-operation.md` — how to author a stop condition
- [ ] README — one honest line on what is enforced vs. advisory today
- [ ] CHANGELOG delta

## Explicitly out of scope

- Reusable versioned stop conditions in bundles (`security/v0.2.0/STOP-001`) —
  likely the right end state, tracked as open question 3, not this change.
- Any mechanism that widens what the agent may do autonomously.
- Backfilling stop conditions onto historical cards.
