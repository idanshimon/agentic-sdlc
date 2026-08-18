# Tasks: stabilize-run-lifecycle-execution

> **Status: 100% shipped in v0.7** (orchestrator `--0000040`). All sections complete.

## 1 — Driver task lifetime

- [x] 1.1 Add `_background_tasks` set + `_spawn()` strong-ref helper *(commit dccffc4)*
- [x] 1.2 Route all pipeline driver spawns through `_spawn` (submit, rerun, recovery) *(commit dccffc4)*
- [x] 1.3 Null-guard `_spawn` for test harnesses that stub `create_task` *(commit dccffc4)*

## 2 — Failure visibility

- [x] 2.1 Surface per-stage exceptions with full traceback in the failed event *(commit 16241ba)*
- [x] 2.2 Persist orchestrator-emitted events into `run.events` in `_push` *(commit dc03b49)*
- [x] 2.3 Per-stage markers + BaseException capture in `_drive` and `_drive_from_stage` *(commits 2ab354c, b323d02)*

## 3 — Recovery lease

- [x] 3.1 Gate the recovery lease behind `ENABLE_RECOVERY_LEASE` (default off) *(commit 94be94e)*
- [x] 3.2 Claim the lease before spawning a gate continuation *(commit 3db1310)*
- [x] 3.3 Make `maintain_lease` survive own-write CAS churn; lose lease only on real owner change *(commit e172ac4)*

## 4 — Gate lifecycle

- [x] 4.1 Rehydrate the run from Cosmos on cache-miss in approve/finalize *(commit a47c977)*
- [x] 4.2 Spawn a pipeline continuation when a gate is released on a rehydrated run *(commit 160db7f)*
- [x] 4.3 `_drive_from_stage` stops at `gate_open` (was double-driving past gates) *(commit c01eb16)*
- [x] 4.4 `_open_gate` blocks-and-continues; don't double-spawn post-gate *(commit 9460029)*

## 5 — Durable doc size

- [x] 5.1 Trim oversized code payloads from the persisted run doc only *(commit 8e5528e)*

## Delta from original plan

Retroactive. This work was not planned as a change — it emerged from
root-causing a single silent failure that turned out to be a family of
lifecycle bugs. The lease fix (3.3) additionally re-enabled safe horizontal
scale (min=1/max=3 with `ENABLE_RECOVERY_LEASE=1`), which was previously
unattainable because the lease aborted every run.
