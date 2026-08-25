# Q2 — is the delivery target part of gate classification?

**Status:** answered with evidence, 2026-08-25. Recommendation: **yes, and the
window to act is open but finite.**

## Why this needed answering now

`add-per-run-delivery-target` deferred three questions. Two are design taste.
This one has a deadline attached, because precedent is accumulating against a
key that cannot be retroactively split.

## What the code actually does today

Four facts, each verified against the source rather than assumed.

**1. Both precedent paths are target-blind.**

`find_precedent` keys on `(team_id, ambiguity_class, slot_value_hash)`.
`query_class_history` — the rows the accuracy projection scores — keys on
`(team_id, ambiguity_class)`. Neither mentions the delivery target.

**2. The projection cannot see the target even if it wanted to.**

`query_class_history` uses an explicit column list:

```sql
SELECT TOP @n c.id, c.card_id, c.ambiguity_class, c.team_id,
       c.confidence_source, c.resolution_text, c.created_at
```

`target_repo` is not selected. A scorer cannot partition by a field it never
reads.

**3. No precedent-forming entry stamps the target.**

`main.py` writes five `LedgerEntry` values. **Zero** carry `target_repo` — the
count is literally 0. Only the deliver-stage entry records it, and that entry is
written *after* every gate decision has already been made and recorded.

**4. The target is not known when the decision is made.**

`_resolve_target_repo` is called inside `stage_deliver`, the last stage. The
autopilot/gate decision happens during resolution, many stages earlier. At the
moment the system decides *"may an agent resolve this alone"*, **nothing in the
run knows where the resulting code will land.**

## The conclusion

Fact 4 is decisive, and it is worse than "the key is missing a dimension".

The system currently grants autonomy **without knowing the blast radius of the
decision it is authorising.** A card resolved on autopilot is resolved
identically whether the run delivers to a scratch repository or to the
production service, because the destination is resolved after the decision that
should have accounted for it.

That is not a missing feature. It is the same defect this codebase keeps finding
in itself, in its most consequential position yet: **an autonomy decision that
implies it weighed something it never saw.**

## Why the window is still open, and how it closes

The window is open because of fact 3: **no precedent entry carries a target
today.** Nothing has to be migrated, because no history is target-attributed
yet. Adding the dimension now is a schema addition, not a data migration.

The window closes the moment two conditions hold together:

1. runs begin delivering to more than one target, and
2. precedent accumulates across them under the current blind key.

At that point the ledger contains rows that were decided under one blast radius
and are indistinguishable from rows decided under another. They cannot be split
afterwards — the information was never recorded. The only remedies are to
discard precedent (expensive, and it resets the teaching loop that is the
product's whole argument) or to keep granting autonomy on a key that conflates
sandbox and production.

Today `github_default_target_repo` is unset and there is one deployment, so
condition 1 does not hold. **The first customer running two products through one
orchestrator closes it.**

## Recommendation

Make the target part of the decision, not part of the delivery:

- resolve `target_repo` at **run creation**, not at the deliver stage
- stamp it on **every** precedent-forming entry, not only the delivered one
- add it to `query_class_history`'s column list
- key precedent on `(team, class, slot_hash, target_class)`

Note **`target_class`, not `target_repo`.** Keying on the raw repository would
fragment precedent per repo and starve the teaching loop — a team with twelve
services would accumulate twelve unrelated histories and never clear a
threshold. What governance actually cares about is blast radius: *production* vs
*sandbox* vs *internal*, declared per target in configuration. Precedent then
accumulates per blast class, which is both learnable and honest.

This preserves the property the projection already protects — one scorer, one
history, no disagreement between the autonomy gate and the replay report — while
making the thing being scored mean something specific.

## What this does not require

It does not require answering Q1 (declare vs inherit) or Q3 (installation
validation). Those are entry-path ergonomics. This is about what the system
knows at the moment it decides, and it is worth doing first.
