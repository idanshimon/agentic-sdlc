# Proposal: replay scoring and the disagreement metric

> **Status:** DRAFT (proposed)
> **Capability:** ledger / autonomy-governance
> **Related:**
>   - `add-graduated-autonomy-tier2` (defines autonomy earned per class — this
>     proposal supplies the evidence that earning is measured against)
>   - `add-teaching-signal-feedback` (flags retract precedent; replay measures
>     whether precedent deserved to be trusted in the first place)
>   - `add-slot-value-hash-to-runtime-schema` (this proposal corrects how that
>     field is interpreted downstream — see "Correction" below)

## Why

The system reports **autonomy earned** — the share of decisions the agent
resolved without a human. On live data that is 45%. The number is real, but on
its own it is not evidence of anything: it measures how much work the agent was
*allowed* to do, not whether it should have been.

A pipeline whose autonomy rate climbs while its error rate climbs looks like
success on every chart in this product and loses trust in a single incident.
That is the failure mode this proposal exists to prevent.

The missing number is the **disagreement rate**: when the agent resolved a
decision alone, how often did it diverge from what a human ruled on the same
question? Two supporting facts make this urgent rather than theoretical:

1. **The schema already anticipates it and nothing populates it.**
   `accuracy_score` and `sample_count` exist on every ledger entry. On all 229
   live entries `accuracy_score` is `0.0` and `sample_count` is `1` — the fields
   have never been computed. A governance surface with an always-zero accuracy
   column is worse than an absent one.

2. **Evidence accrues too slowly to be useful at onboarding.** Precedent is the
   asset this system builds, but a new tenant starts with none, so early
   autonomy decisions are made on no evidence at all. Replay solves this by
   scoring against outcomes that *already happened*, turning history the
   organisation already owns into a calibrated baseline immediately.

## What changes

A new pure-scoring module, `apps/orchestrator/replay.py`, plus a correction to
how precedent identity is derived across the UI.

### Replay scoring

Replay pairs a **human ruling** (ground truth) with an **autopilot decision on
the same question**, and reports per-class agreement. It is a read-only
projection: replay MUST NOT write to the decision ledger. Fabricating ledger
rows to populate a metric would corrupt the audit substrate the product exists
to protect.

Verdicts are deliberately conservative:

| Verdict | Meaning |
|---|---|
| `AUTONOMY EARNED` | Zero disagreements over a sufficient sample |
| `AUTONOMY DEFENSIBLE` | Disagreement at or under the class ceiling |
| `REVOKE AUTONOMY` | Disagreement above ceiling — agent is acting alone and getting it wrong |
| `INVARIANT — HUMAN ALWAYS` | Class may never be autopiloted, regardless of score |
| `INSUFFICIENT` | Fewer samples than the policy minimum — **no rate is reported** |
| `UNSCORED` | Outcome unknown — excluded from rates, never counted as agreement |

The last two matter most. A metric that reports a flattering `0.0%` from two
samples, or silently treats "we never checked" as "we agreed", is not a weaker
metric — it is a false one.

### Thresholds are governance, not constants

No threshold is hardcoded. `ReplayPolicy.from_bundle()` reads the same
`defaults:` shape the finops bundle already uses for `AUTOPILOT-THRESHOLD-*`:

```yaml
- id: REPLAY-MIN-SAMPLES
  defaults: { min_samples: 8 }
- id: REPLAY-CEILING-PHI
  ambiguity_class: phi-classification
  defaults: { disagreement_ceiling: 0.0 }
```

Two consequences, both intentional:

- Teams pinned to different bundle versions are judged by their own standards,
  exactly as autopilot confidence thresholds already work. Changing a threshold
  is a bundle change with a canary rollout, not a code deploy.
- Any rule carrying `phi_locked: true` contributes its class to the invariant
  set automatically. An invariant declared for *enforcement* therefore cannot
  drift apart from the invariant used for *autonomy scoring*.

Built-in fallbacks apply only when no policy is supplied, and are deliberately
strict: an unconfigured system should under-grant autonomy, never over-grant it.

## Correction: precedent identity is `card_id`, not `slot_value_hash`

`slot_value_hash` was specified as `team + class + slot` and the UI's lineage
derivation keyed on it. On live data that is not what it contains:

```
distinct slot_value_hash values : 18
distinct ambiguity_class values : 18
hashes spanning >1 class        : 0
largest bucket                  : 63 entries, 52 distinct resolutions, 31 runs
```

It is a **class-level** label. Keying precedent on it groups every
scope-resolution decision ever made into a single chain — a graph that renders
convincingly and means nothing, and a disagreement rate of 100% produced by
comparing unrelated questions.

`card_id` (198 distinct values) is the identity of one decision question, and is
what both precedent and replay MUST key on. With the correction, live data
yields **16 genuine human→agent pairs**, 0% disagreement, two classes with
sufficient evidence to have earned autonomy and two correctly reported as
`INSUFFICIENT`.

This proposal does not change the ledger schema or rewrite any entry. It
corrects interpretation only.

## Impact

- **New:** `apps/orchestrator/replay.py`, `apps/orchestrator/tests/test_replay.py` (16 tests).
- **Changed:** `apps/ledger-insights-ui/src/lib/lineage.ts` and
  `src/lib/graph/build-lineage.ts` now bucket on `card_id`; fixtures updated.
- **Ledger:** no schema change, no writes, no migration. `accuracy_score`
  remains 0.0 until a scoring pass populates it — replay reports such entries as
  `UNSCORED` rather than assuming agreement.
- **Runtime:** none. Replay is invoked explicitly; it does not run in the
  request path.

## Risks

- **Small n at onboarding.** Most classes will report `INSUFFICIENT` for a
  while. This is correct behaviour and should be presented as such in the UI, not
  hidden — an operator seeing "not enough evidence" is better informed than one
  seeing a confident number derived from three samples.
- **Exact-match comparison understates agreement.** Two resolutions that mean
  the same thing but differ in wording count as a disagreement. This is
  deliberate: the metric must never be wrong in the flattering direction.
  Semantic equivalence scoring is possible future work and must be evaluated
  against human grading before being trusted.
- **Ground truth is assumed correct.** Replay measures agreement with the human
  ruling, not correctness. A systematically wrong human baseline yields a
  confident wrong metric; this is why flags (which retract precedent) remain the
  primary correction path.
