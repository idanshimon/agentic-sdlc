# Spec delta: stabilize-run-lifecycle-execution / pipeline

## ADDED Requirements

### Requirement: Pipeline driver tasks MUST NOT be garbage-collected mid-run
Every background pipeline driver task MUST retain a strong reference for its
lifetime. Scheduling a driver with a discarded task reference is prohibited, since
the event loop keeps only a weak reference and may collect a running task.

#### Scenario: driver survives to completion
- **GIVEN** a run is submitted and its driver is scheduled
- **WHEN** no other reference to the task exists in local scope
- **THEN** the driver MUST still run to a terminal state
- **AND** it MUST NOT be garbage-collected mid-execution

### Requirement: Orchestrator-emitted events MUST be persisted to the run
Events emitted by the orchestrator driver (not only by stage generators) MUST be
appended to the run's durable event list, so a failure event and its traceback are
observable via the run API — not only on the live SSE stream.

#### Scenario: a driver failure is observable after the fact
- **GIVEN** a stage raises inside the driver loop
- **WHEN** the driver records a failed event with a traceback
- **THEN** that event MUST appear in `run.events` on a subsequent read
- **AND** the run status MUST be `failed`

### Requirement: The recovery lease MUST tolerate the owner's own writes
When enabled, the lease maintainer MUST NOT treat a compare-and-swap failure
caused by the same owner's concurrent writes as a takeover. It MUST re-read and
declare the lease lost ONLY when `lease_owner` has actually changed to another
worker (or the run vanished / the lease expired). A genuine takeover MUST still be
detected.

#### Scenario: event-driven etag churn does not abort the run
- **GIVEN** the recovery lease is enabled and the run emits many events
- **WHEN** the lease renewal CAS fails because the owner's own `_push` moved the etag
- **THEN** the maintainer MUST retry and keep the lease
- **AND** the run MUST NOT be aborted

#### Scenario: a real takeover is detected
- **GIVEN** the recovery lease is enabled
- **WHEN** another worker becomes `lease_owner`
- **THEN** the original maintainer MUST stop and signal lease-lost

### Requirement: Gate operations MUST resolve the run durably
Approve and finalize MUST locate the run even when it is not in process-local
memory, by rehydrating it from the durable store on a cache-miss. When a gate is
released on a rehydrated run with no live driver, execution MUST resume via a
freshly spawned continuation.

#### Scenario: approve after a replica change
- **GIVEN** a run awaiting a gate whose driver lived on a since-replaced replica
- **WHEN** an approve request lands on a different replica
- **THEN** the run MUST be rehydrated from the durable store
- **AND** the gate MUST be releasable without a 404

#### Scenario: released gate resumes a rehydrated run
- **GIVEN** a rehydrated run with an open gate and no live driver
- **WHEN** the gate is released
- **THEN** a continuation MUST be spawned to resume the next stage
- **AND** exactly one driver MUST run the remaining segment

### Requirement: Exactly one driver MUST execute each run segment
Gate continuation MUST NOT create two concurrent drivers for one run. A stage
driver MUST pause at a gate-open signal rather than running past it.

#### Scenario: no double-drive across a gate
- **GIVEN** a run reaches a gate during stage execution
- **WHEN** the gate opens
- **THEN** the driver MUST pause at the gate
- **AND** only one driver MUST continue after the gate is released

### Requirement: The durable run document MUST bound oversized payloads
Persisting a run MUST trim oversized generated-code payloads from the stored
document while retaining full artifacts in the live in-memory run for delivery.

#### Scenario: large code payloads do not bloat the stored doc
- **GIVEN** codegen emits multi-kilobyte app and test code
- **WHEN** the run is persisted after each event
- **THEN** the stored document MUST replace oversized code strings with a marker
- **AND** the live run MUST retain the full code for the deliver stage
