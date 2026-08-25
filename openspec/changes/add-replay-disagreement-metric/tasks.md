# Tasks: add-replay-disagreement-metric

**Implementation:** `apps/orchestrator/replay.py` (pure scorer, no I/O).

## Phase 1 — The scorer

- [x] 1.1 `ReplayPolicy` reads thresholds from the caller (resolved from the team's pinned bundle), with deliberately strict built-in fallbacks. An unconfigured system must under-grant autonomy, never over-grant it.
- [x] 1.2 `ClassScore` / `ReplayReport` — per-class agreements, disagreements, and the isolated autopilot disagreement rate.
- [x] 1.3 `score_replay()` — pure fold over cases. No I/O, no writes.
- [x] 1.4 `_equivalent()` — normalises whitespace and case only. Fuzzy matching would inflate the agreement rate, which is the one direction this metric must never err in.

## Phase 2 — Honesty constraints (the point, not decoration)

- [x] 2.1 Replay NEVER writes to the decision ledger. Scoring is a read-only projection; inventing rows to populate a metric would corrupt the audit substrate.
- [x] 2.2 Below `min_samples`, report `INSUFFICIENT` — never a flattering number computed from n=2.
- [x] 2.3 Unscored entries are reported `UNSCORED` and excluded from rates, never counted as agreements. Counting "we never checked" as "we agreed" is how a disagreement metric becomes a lie.
- [x] 2.4 An invariant class is never eligible for autonomy however well it scores, but is still measured — a high disagreement rate on a gated class means the suggestions are poor, which is worth knowing.

## Phase 3 — Precedent identity

- [x] 3.1 Key `cases_from_ledger` on `card_id`, not `slot_value_hash`. On live data the hash maps 1:1 onto `ambiguity_class` (18 hashes, 18 classes; one hash covered 63 entries with 52 distinct resolutions across 31 runs), so pairing on it compares unrelated questions and reports ~100% disagreement — confidently wrong, the worst kind for a governance surface.

## Phase 4 — Spec hygiene (2026-08-18)

- [x] 4.1 **Found during an OpenSpec audit:** three requirements stated their normative MUST only in the header, which `openspec validate --strict` rejects, and this change had no `tasks.md`. Fixed; validation passes.

## Phase 5 — Consumers

- [x] 5.1 The scorer is now also the source for the read-time `accuracy_score` projection (see `compute-accuracy-score-projection`). Reused unchanged and deliberately so: a second scorer with slightly different semantics would let the autonomy gate and this report disagree about the same history, with no way for an operator to tell which was lying.
- [ ] 5.2 Reviewer approval.
