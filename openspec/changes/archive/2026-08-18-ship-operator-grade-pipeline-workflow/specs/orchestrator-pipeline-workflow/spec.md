# Spec delta: ship-operator-grade-pipeline-workflow / orchestrator-pipeline-workflow

## ADDED Requirements

### Requirement: Pipeline run state MUST persist to Cosmos on every stage event

The orchestrator MUST write the full `RunState` to Cosmos via `_ledger.save_run(run)` after every stage event push (not only at pipeline completion or failure). The write MUST be failure-tolerant: a Cosmos blip MUST log a warning and continue the running pipeline, never abort it.

This invariant prevents the "zombie run" failure mode where pod death (revision rollover, OOM, scale-to-zero eviction) leaves runs frozen at the ingest snapshot while in-memory state had progressed.

#### Scenario: pipeline events trigger durable writes

- **GIVEN** an orchestrator pod with `_ledger` configured (Cosmos available)
- **WHEN** the pipeline emits any non-sentinel `StageEvent` (ingest_started, assessor_completed, gate_open, etc.) via `_push(run_id, ev)`
- **THEN** the orchestrator MUST call `await _ledger.save_run(run)` after pushing to the queue
- **AND** the Cosmos doc for `run_id` MUST reflect the latest `RunState` within one stage transition

#### Scenario: Cosmos write failure does not crash the pipeline

- **GIVEN** a pipeline currently executing with `_ledger` configured
- **WHEN** `await _ledger.save_run(run)` raises any exception (network, throttle, partition unavailable)
- **THEN** the orchestrator MUST log the failure with `(run_id, ev.stage, ev.status)` context
- **AND** the pipeline MUST continue executing the next stage
- **AND** the SSE event MUST still be delivered to subscribers

### Requirement: Pipeline MUST expose a finalize endpoint for resolver gate closure

The orchestrator MUST expose `POST /api/runs/{run_id}/finalize` that explicitly closes the resolver gate after the operator has approved per-card decisions. The endpoint MUST validate that every gating card has a recorded decision before releasing the gate.

This contract pairs with the resolver gate's per-card approve loop: each `POST /approve` records one decision; `POST /finalize` releases the gate exactly once. Non-resolver gates (e.g. design_review) auto-release on the back of their approve call and do not require finalize.

#### Scenario: finalize closes resolver gate after all cards decided

- **GIVEN** a run with 5 resolver gating cards, all approved via `POST /approve`
- **WHEN** `POST /api/runs/{run_id}/finalize` is called with an empty body
- **THEN** the response MUST be `{ok: true, gate_closed: true, decisions_count: 5, next_stage: "architect"}`
- **AND** the run's status MUST flip from `awaiting_gate` to `running`
- **AND** the architect stage MUST start within the next pipeline tick

### Requirement: Approve endpoint MUST distinguish per-card resolver decisions from gate-level approvals

`POST /api/runs/{run_id}/approve` MUST treat a request as a gate-level approval when EITHER `card_id is None` OR `decision.gate is set and != "resolver"`. Per-card resolver decisions (no gate field, real card_id) MUST be blocked when the resolver gate is closed (audit-safety invariant); gate-level approvals MUST bypass that block.

This dual contract allows UI components to send synthetic card_ids to satisfy pydantic schema validation while still routing to whichever gate is open.

#### Scenario: design_review gate-level approval with synthetic card_id is accepted

- **GIVEN** a run with status=awaiting_gate, current_stage=design_review
- **WHEN** `POST /approve` is called with `{card_id: "design-review-<rid>", decision_kind: "accept", gate: "design_review", resolution_text: "..."}`
- **THEN** the response MUST be HTTP 200 with `{ok: true}`
- **AND** the orchestrator MUST call `_release_gate(run_id)` after the decision write

#### Scenario: per-card resolver decision after gate closure is rejected

- **GIVEN** a run with status=running, current_stage=architect (resolver gate already closed)
- **WHEN** `POST /approve` is called with `{card_id: "some-resolver-card-id", decision_kind: "accept", option_index: 0}` (no gate field)
- **THEN** the response MUST be HTTP 409
- **AND** the error message MUST include "resolver gate is closed"

### Requirement: Admin endpoint MUST allow cleanup of zombie runs

The orchestrator MUST expose `POST /api/admin/runs/{run_id}/mark_failed` that reads the run from Cosmos (no in-memory dependency), flips status to FAILED, appends an audit-trail StageEvent recording the cleanup reason, and writes back via `save_run()`.

This is a one-off cleanup surface for runs zombified by pod death before per-event persistence shipped. NOT a permanent admin surface — v1.0 production posture requires proper RBAC.

#### Scenario: zombie run is marked failed honestly with audit trail

- **GIVEN** a run that persists in Cosmos with status=running, events=[], decisions=[] from before per-event-save
- **WHEN** `POST /api/admin/runs/{run_id}/mark_failed` is called with `{reason: "lost to revision rollover"}`
- **THEN** the response MUST be HTTP 200 with `{ok: true, run_id, status: "failed", reason}`
- **AND** the Cosmos doc MUST have `status=FAILED` after the call
- **AND** the run's events array MUST contain a StageEvent with status="failed" and message containing "Admin cleanup: lost to revision rollover"
