# Proposal: extend RuntimeEntrySchema with slot_value_hash

> **Status:** DRAFT (filed 2026-06-16 during stabilization pass)
> **Capability:** ledger (extends `extend-ledger-runtime-meta-entries` + `add-teaching-signal-feedback`)
> **Severity:** product gap — Track B's pause/flag/replay write tools work, but `findPrecedent`'s exclusion logic is unreachable because resolver-written entries never carry the `slot_value_hash` field that `findPrecedent` matches on.

## Why

Track B (`add-teaching-signal-feedback`) gave operators four typed write paths to influence pipeline behavior: `add_feedback`, `flag_decision`, `request_replay`, `pause_class`. The pause/flag tools are designed to make `findPrecedent` skip the corresponding precedents on subsequent runs. The pause path short-circuits, the flag path excludes specific ids — both are implemented in `cosmos-client.ts::findPrecedent`.

Discovered during 2026-06-16 stabilization while running the full demo end-to-end: **`findPrecedent` returns `entry: null` for every query against `team-demo`, even when there should be matching precedents**, because the SELECT requires `c.slot_value_hash=@s` AND the writeable `RuntimeEntrySchema` doesn't include `slot_value_hash` as a field. So:

1. Resolver writes a stage_decision via `ledger.write_runtime` → schema silently drops `slot_value_hash` (zod `.parse()` doesn't error on unknown fields by default)
2. Operator pauses the ambiguity_class via `ledger.pause_class`
3. New run hits the same ambiguity_card → orchestrator calls `findPrecedent(team_id, ambiguity_class, slot_value_hash)`
4. The pause-check short-circuit fires and returns `null`. BUT: even without a pause, the SELECT would also return null because no entry carries the hash.

Net effect: Track B's write tools work and entries are auditable, but the *teaching* part of "the operator teaches the pipeline" is unobservable.

This was filed-but-deferred during stabilization because:
- All 4 Track B write tools verified working (3 entries landed in Cosmos)
- The pause/flag exclusion logic is correct in code
- Closing the gap requires schema + resolver changes that cross the AGENTS.md non-trivial threshold

## What changes

### `apps/decision-ledger-mcp/src/schema.ts::RuntimeEntrySchema`

Add `slot_value_hash` as an optional string field on `RuntimeEntrySchema`. Required ONLY when `runtime_kind === "stage_decision"` (the case `findPrecedent` searches). Other runtime_kinds (feedback_thumbs, decision_flagged, replay_requested, class_paused) explicitly ignore it.

```ts
export const RuntimeEntrySchema = z.object({
  // ... existing fields
  slot_value_hash: z.string().optional(),
}).superRefine((e, ctx) => {
  // Existing teaching-signal refinements stay
  // ...
  // NEW: stage_decision entries SHOULD carry slot_value_hash so
  // findPrecedent can match them. We don't HARD-require it (some
  // legacy seeded entries don't have it) but we warn via a soft path.
  if ((e.runtime_kind ?? "stage_decision") === "stage_decision" && !e.slot_value_hash) {
    // No ctx.addIssue — allow but it will never be returned by findPrecedent.
    // Resolver-side wrapper is what enforces this; see below.
  }
});
```

### `apps/orchestrator/_pipeline_stages.py` — compute hash on write

The resolver's `_record_decision_to_ledger` (or wherever the stage_decision write happens) MUST compute `slot_value_hash` from the ambiguity_card's slot value before calling `ledger.write_runtime`. Suggested:

```python
import hashlib
def _slot_value_hash(card: AmbiguityCard, decision: GateDecision) -> str:
    # Stable across re-runs of the same logical card+decision combination.
    # SHA-256 over (ambiguity_class || JSON-canonical decision payload).
    payload = json.dumps({
        "class": card.ambiguity_class,
        "kind": decision.kind,       # accept | swap | reject
        "option_id": decision.option_id,
    }, sort_keys=True)
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()
```

The hash MUST be deterministic — same logical decision on a different team / different time produces the same hash. That's what makes "this kind of decision was already made; reuse the precedent" work.

### Existing entries

Out of scope to backfill. New runs will write hashes; old runs (the 25 seeded SBM entries) won't have them and won't be findable as precedents, which is the current (latent-broken) state anyway — no regression.

## Impact

- `findPrecedent` becomes useful for the first time
- Track B's pause + flag exclusion logic becomes observable: `find_precedent(paused_class)` returns null because the pause check fires; `find_precedent(unflagged_class)` returns a real entry; `find_precedent(flagged_class)` returns null because the flag excludes; demo becomes recordable
- Adds one field to ledger writes; backward compatible
- Old entries without `slot_value_hash` continue to coexist; they're just never returned by findPrecedent

## Verification

- Unit test: write a stage_decision with explicit `slot_value_hash`, call `find_precedent` with matching hash → returns the entry
- Unit test: write a stage_decision, pause the class, call `find_precedent` → returns null (pause check fires)
- Unit test: write a stage_decision, flag it, call `find_precedent` → returns null (flag exclusion fires)
- Integration test: run the SBM pipeline twice with the same fixture, second run should hit `find_precedent` and skip the LLM call for at least one class
- Live verification: re-run the SBM cardiology fixture with `slot_value_hash` flowing through; verify `find_precedent` returns the haiku-4-5 identifier-format ruling; flag it; re-run; verify findPrecedent now returns null and the orchestrator falls back to a fresh LLM call

## Out of scope

- Backfilling slot_value_hash on historical entries (the 25 SBM seeds; the 3 teaching signals from 2026-06-16 stabilization)
- Changing the hash algorithm (SHA-256 is sufficient; deterministic is the only requirement)
- Cross-team precedent lookups (still partition-scoped by team_id — by design)
