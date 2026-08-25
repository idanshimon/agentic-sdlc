# Compute `accuracy_score` as a read-time projection

> **Status:** PROPOSED (filed 2026-08-18)
> **Capability:** autonomy-precedent (MODIFIED)
> **Severity:** High — the `autopilot_above_threshold` autonomy mode has never
> been able to grant autonomy, and the field it depends on is computed by nothing.

## Why

`LedgerEntry.accuracy_score` is declared in two models
(`apps/orchestrator/models.py`, `packages/ledger-core/ledger_core/models.py`),
defaults to `0.0`, is read in exactly one place, and **is never assigned
anywhere in the codebase**.

The consequence is live in `apps/orchestrator/main.py`:

```python
score = getattr(precedent, "accuracy_score", 0.0) if precedent else 0.0
if not precedent or score < rule.threshold:
    run.autopilot_overrides.append(card.card_id)   # always gates
```

Because the score is structurally `0.0`, any rule with
`mode: autopilot_above_threshold` and a threshold above zero **always gates**.
The mode is dead code wearing a working mode's name: the config plane accepts
it, the docs describe it, operators can select it, and it has never once
granted autonomy.

This fails *safe*, which is exactly why it went unnoticed — the system looks
conservative rather than broken. But a governance control that cannot fire is
not a conservative control, it is an absent one, and a threshold an operator
tunes with no effect is worse than no threshold at all.

`apps/orchestrator/replay.py` already documents the gap honestly:

> `accuracy_score` on live ledger entries is currently 0.0 for every row —
> nothing has ever computed it.

## What changes

`find_precedent` returns a precedent entry whose `accuracy_score` is **derived
at read time** from the historical agreement record for that
`(team_id, ambiguity_class)` group, using the existing `replay.py` scorer.

Nothing is written to the ledger.

### Why read-time projection and not a materialised field

Writing a derived score into ledger rows was considered and rejected. The
ledger is the audit substrate; `replay.py` states the constraint directly:

> A replay NEVER writes to the decision ledger. Scoring is a read-only
> projection; inventing ledger rows to make a metric look populated would
> corrupt the audit substrate this system exists to protect.

A materialised score is also stale by construction — it reflects the agreement
record at write time, not at the moment autonomy is being decided. The decision
that matters is "should this be autopiloted *now*", so the number must be
computed *now*.

### Semantics

The score is the **agreement rate of prior autopilot decisions against the
human ruling on the same card**, per `(team_id, ambiguity_class)`:

```
accuracy_score = agreements / scored
```

reusing `score_replay`, `cases_from_ledger`, and `_equivalent` unchanged. This
matters: a second scorer with slightly different semantics would let the
autonomy gate and the operator-facing replay report disagree about the same
history, and the operator would have no way to tell which was lying.

### Fails closed

The existing scorer's honesty constraints carry over intact:

- **Insufficient evidence yields `0.0`, never a flattering number.** Below
  `policy.min_samples` scored cases, the score is `0.0` and the card gates.
  `ClassScore.disagreement_rate` already returns `None` in this case; `None`
  becomes `0.0` at the gate rather than being treated as "no disagreements".
- **Unscored history is not agreement.** Cases with no human ruling are
  excluded from the denominator, never counted as agreements.
- **An invariant class is never eligible**, however well it scores. This is
  checked before the threshold comparison, not after.
- **A scoring failure gates.** Any exception computing the projection yields
  `0.0` and a warning — the autonomy path never inherits a score from a
  partially-failed computation.

## What this deliberately does NOT do

- It does not change any threshold. Thresholds stay governance, owned by the
  finops bundle and resolved from the team's pin.
- It does not enable autonomy for any class that is not already configured for
  `autopilot_above_threshold`.
- It does not backfill or modify historical ledger entries.
- It does not change `find_precedent`'s matching semantics — the precedent
  *lookup* still keys on `(team, class, slot_value_hash)`. Only the score
  attached to the returned entry is new.

The net effect is narrow: a mode that could never fire can now fire, exactly
when the recorded history supports it.

## Risk

This flips a dead safety-gate into a live autonomy path. The mitigations are
that the evidence bar is the bundle's `min_samples` (default 5, deliberately
strict), that insufficient evidence gates, and that every autopilot decision
still writes a ledger entry carrying its `autonomy_ref` — so a grant made on
this basis is auditable after the fact and revocable by rolling the pin.

## Verification

- Unit tests for the projection: exact-agreement history scores 1.0; mixed
  history scores the true rate; below-min-samples scores 0.0; unscored history
  scores 0.0; an invariant class never grants regardless of score.
- A regression test asserting `autopilot_above_threshold` **gates** when the
  history is insufficient — the current behaviour, which must not change.
- A test asserting it **grants** when the history clears the threshold — the
  behaviour that has never worked.
- Full orchestrator suite green.
