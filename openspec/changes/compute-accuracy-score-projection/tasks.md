# Tasks: compute-accuracy-score-projection

**Test targets:** `apps/orchestrator/tests/test_accuracy_projection.py`,
`apps/orchestrator/tests/test_autonomy_threshold_grant.py`. Run with
`.venv/bin/python -m pytest apps/orchestrator/tests/ -q`.

## Phase 0 — Establish that the field is dead, not just unused

- [x] 0.1 Grep every assignment of `accuracy_score` across the repo. Result: declared in two models, read in one place, **assigned nowhere**.
- [x] 0.2 Trace the consequence in `main.py`: `score` is structurally `0.0`, so `score < rule.threshold` is always true and `autopilot_above_threshold` can never grant autonomy.
- [x] 0.3 Confirm `replay.py` already documents the gap ("nothing has ever computed it") and refuses to count unscored entries as agreements — the honesty constraints to inherit.

## Phase 1 — RED: encode the semantics as failing tests

- [x] 1.1 Granting path: full agreement at or above `min_samples` scores 1.0.
- [x] 1.2 Mixed history scores the true rate, never rounded toward granting.
- [x] 1.3 **Load-bearing:** below `min_samples`, a perfect 4-for-4 record scores 0.0.
- [x] 1.4 Unscored history is excluded from the denominator, never counted as agreement.
- [x] 1.5 Scoping: sibling classes and other teams do not contribute.
- [x] 1.6 An invariant class scores 0.0 despite a perfect record.
- [x] 1.7 Malformed rows score 0.0 rather than raising.
- [x] 1.8 The projection does not mutate its input.
- [x] 1.9 Run RED — `ModuleNotFoundError`, as expected.

## Phase 2 — GREEN: the projection

- [x] 2.1 `apps/orchestrator/accuracy.py` — `project_accuracy_score()`, pure, no I/O, no writes.
- [x] 2.2 Reuse `score_replay` / `cases_from_ledger` / `_equivalent` unchanged so the autonomy gate and the replay report cannot disagree about the same history.
- [x] 2.3 Invariant check FIRST, so a perfect history can never bypass it.
- [x] 2.4 Below `min_samples` → 0.0; any exception → 0.0 with a warning. Every ambiguous path gates.
- [x] 2.5 12/12 unit tests green.

## Phase 3 — Wire it into the gate

- [x] 3.1 `query_class_history()` on `LedgerClient` — raw dicts (the scorer reads row fields directly), partition-scoped, read-only.
- [x] 3.2 Replace the dead `getattr(precedent, "accuracy_score", 0.0)` read in `main.py` with the read-time projection.
- [x] 3.3 End-to-end tests: gates on thin evidence, gates on a disagreeing record, **grants when the record clears the threshold** (the path that has never worked), and the projection never writes.

## Phase 4 — Fix the test harness that was passing for the wrong reason

- [x] 4.1 First harness patched a non-existent `_autonomy_rule_for` with `raising=False`. It silently did nothing: `rule` was `None`, execution fell through to the legacy HYBRID path, and both "must gate" assertions failed while the threshold branch never ran.
- [x] 4.2 Second attempt patched `main.AUTONOMY_MATRIX` → `AttributeError`. `main.py` imports the name INSIDE the function, so it must be patched on the `autonomy` module (as `test_autonomy_ref.py` does).
- [x] 4.3 All 4 end-to-end tests green, including both gating tests — now green for the right reason. Rationale recorded in the helper docstring so the trap is not re-entered.

## Phase 5 — Review

- [ ] 5.1 Reviewer approval. This flips a dead safety-gate into a live autonomy path.
- [ ] 5.2 Confirm `bundle-enforce` and the full suite pass on the PR.
