# Run recovery operations

The recovery design is a bounded at-least-once checkpoint runner, not a general workflow engine and not an exactly-once claim.

## Durable state

Each run records input reference/hash, cursor stage/state, checkpoint and run versions, pending gate, lease fields, reviewed artifact manifest, and command records.

## Restart triage

1. Load the run from Cosmos.
2. Verify the PRD Blob against `input_sha256`.
3. Inspect `cursor_state`:
   - terminal run: do nothing
   - `awaiting_gate`: keep the gate open; do not replay prior stages
   - completed stage: resume the next pipeline boundary
   - running/pending stage: reacquire a lease before retrying
4. Verify no unexpired lease belongs to another worker.
5. Resume with the same execution profile and provider policy.

## Operator conflicts

Gate commands require an idempotency key and may carry expected gate version. A stale version returns 409 without writing. Identical retry returns the original result. Reusing a key with another payload returns `idempotency_conflict`.

## Safety

- Never reconstruct execution solely from event history.
- Never rerun a completed irreversible stage without checking its artifact/PR evidence.
- Never use process-local `asyncio.Event` as durable gate authority.
- Never deliver synthetic or hash-mismatched artifacts.

## Current limit

The checkpoint schema, durable input, strict Cosmos writes, gate records, and recovery planner are implemented. Automated lease acquisition/renewal and startup scanning remain incomplete and must be verified before enabling multiple orchestrator replicas for active execution.
