# Proposal: stabilize run lifecycle execution

> **Status:** SHIPPED (retroactive) — v0.7, orchestrator `ca-orchestrator-vnet--0000040`
> **Capabilities:** pipeline, ledger
> **Commits:** dccffc4, a47c977, 160db7f, 3db1310, c01eb16, 9460029, 94be94e, e172ac4, 8e5528e, dc03b49, 16241ba

## Why

Once a real LLM was wired in, runs began failing silently between codegen and
review-scan with no exception, no failed event, and no traceback. Root-causing
this exposed a family of run-lifecycle execution bugs that stub-fast runs never
triggered:

1. **Driver tasks were garbage-collected mid-run.** `asyncio.create_task(...)` for
   the pipeline driver discarded the task reference; the event loop keeps only a
   weak reference, so the driver could be GC'd mid-execution — dying with no
   exception anywhere.
2. **Orchestrator-emitted events were not persisted.** `_push` queued events to SSE
   and saved the run, but never appended them to `run.events` — so every driver
   failure event (and its traceback) was invisible in the API. This is why the
   failure looked silent.
3. **The recovery lease aborted healthy runs.** `maintain_lease` treated any CAS
   failure as a takeover, but the pipeline's own per-event `_push` bumps the etag
   constantly — so the lease declared itself lost mid-codegen (where events fire
   fastest) and aborted the run.
4. **Gate approvals 404'd after any replica change.** `approve`/`finalize` looked
   up the run only in the in-memory `_runs` map; a replica swap or scale event lost
   it, and the gate could not be released.
5. **Gate continuations double-drove or stalled.** `_drive_from_stage` ran past
   `gate_open` events instead of pausing, causing two concurrent drivers to fight
   over one run; and a released gate on a rehydrated run had no live driver to wake.
6. **Oversized code payloads bloated the durable run doc**, growing every save.

Individually small; together they made real (non-stub) runs unable to complete.

## KEEP / SWAP / ADD / OUT

### KEEP
- The event-sourced run model, SSE stream, and gate/approve semantics.
- Cosmos as the durable run + ledger store; the CAS save path.
- The single-driver-per-run execution model.

### SWAP
- Fire-and-forget `create_task` for drivers → a strong-referenced `_spawn` helper.
- CAS-failure-means-takeover → re-read and only lose the lease on a real owner change.
- In-memory-only gate lookup → Cosmos rehydration on cache-miss.
- `_drive_from_stage` running past gates → pausing at `gate_open`; `_open_gate`
  blocks-and-continues so exactly one driver runs each segment.

### ADD
- Per-stage traceback capture into the failed event.
- Trimming of oversized code payloads from the persisted run doc only (live
  in-memory run keeps full artifacts for delivery).
- `ENABLE_RECOVERY_LEASE` flag (safe default) with a CAS-race-resistant maintainer.

### OUT
- Full externalization of run artifacts to blob storage (payload trim is sufficient).
- Multi-writer conflict resolution beyond single-driver + lease ownership.

## Verification

- 440 orchestrator tests pass (`test_lease_cas_race.py` added; existing lease and
  recovery tests retained).
- Live end-to-end: real GPT-4.1 runs complete through review-scan → deliver;
  two concurrent runs (`a0fc5180` + `2e85b98f`) completed with the recovery lease
  ENABLED, both opening real PRs (#8, #9), proving multi-replica safety.
