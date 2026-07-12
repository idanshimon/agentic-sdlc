# Spec delta: enterprise production hardening

## ADDED Requirements

### Requirement: Mutations MUST use authoritative identity and authorization
Every mutating API MUST authenticate a human or workload principal, authorize its role and team scope, and derive actor identity from validated claims. Request-body actor strings MUST NOT be authoritative.

#### Scenario: operator cannot decide for another team
- **GIVEN** a principal authorized only for `team-a`
- **WHEN** it submits a gate decision for a `team-b` run
- **THEN** the server MUST return 403
- **AND** no decision or ledger entry MAY be written

#### Scenario: production refuses disabled authentication
- **GIVEN** the service runs under the production execution profile
- **WHEN** `AUTH_MODE=disabled`
- **THEN** startup MUST fail with a clear configuration error

### Requirement: Production model execution MUST fail closed
Provider failures in production MUST be categorized, audited, and terminate the stage/run after bounded retry. Synthetic output MAY exist only in explicit demo/test profiles and MUST block delivery.

#### Scenario: provider outage cannot produce a pull request
- **GIVEN** production profile and a provider that remains unavailable
- **WHEN** bounded retries are exhausted
- **THEN** the run MUST fail with `provider_unavailable`
- **AND** no synthetic stage output or delivery PR MAY be created

### Requirement: Reviewed and delivered artifacts MUST be byte-identical
CodeGen MUST produce a typed artifact manifest with SHA-256 per file. Review and Deliver MUST consume the same manifest, and delivery MUST reject a hash mismatch.

#### Scenario: artifact changes after review
- **GIVEN** Review records hash H for `src/main.py`
- **WHEN** Deliver receives different bytes with hash H2
- **THEN** delivery MUST fail closed
- **AND** the mismatch MUST be auditable

### Requirement: Run execution MUST be resumable from durable checkpoints
Run input, cursor, checkpoints, pending gate, versions, and lease state MUST persist. A worker restart MUST be able to resume from the next incomplete stage without duplicating completed transitions.

#### Scenario: restart while waiting at a gate
- **GIVEN** a run persisted with an open resolver gate
- **WHEN** the process restarts
- **THEN** the recovered run MUST remain awaiting that durable gate
- **AND** an approved durable command MUST wake/resume execution
- **AND** completed stages MUST NOT rerun

### Requirement: Decision commands MUST be idempotent and version-checked
Gate decisions/finalization MUST require an idempotency key and expected gate/run version. Replays return the prior result; stale versions or key reuse with different payload return conflict.

#### Scenario: double-click approval
- **GIVEN** two identical approval requests with one idempotency key
- **WHEN** both arrive
- **THEN** exactly one immutable decision event MUST be written
- **AND** both callers MUST receive the same effective result

### Requirement: GitHub review-loop dispatch MUST be authenticated, exact, and replay-safe
The system MUST expose an authenticated dispatch endpoint keyed by repository, PR number, and head SHA. It MUST review the exact head bytes and preserve Tier A/B/C and hard escalation floors.

#### Scenario: workflow retries dispatch
- **GIVEN** the same PR/head SHA is dispatched twice
- **WHEN** both requests authenticate as the GitHub workload
- **THEN** they MUST resolve to the same loop ID
- **AND** remediation/merge MUST NOT execute twice

### Requirement: SSE recovery MUST establish a new connection
After an SSE error, the client MUST create a new EventSource using bounded backoff and retain polling fallback.

#### Scenario: revision rollover
- **GIVEN** an active stream fails during deployment
- **WHEN** reconnect delay elapses
- **THEN** a second EventSource MUST be created
- **AND** duplicate events MUST not render twice

### Requirement: Review-loop identity and disposition MUST be structured
Every loop MUST carry loop ID, repo, PR, head SHA, attempt, tier, verdict reference, and terminal disposition. UI MUST distinguish awaiting merge, merged, escalated, advisory, and failed.

#### Scenario: Tier-B convergence
- **GIVEN** a Tier-B loop reaches PASS
- **WHEN** the UI renders the terminal state before human merge
- **THEN** it MUST display `PASSED_AWAITING_MERGE`
- **AND** MUST NOT display `MERGED`

### Requirement: Assurance MUST expose independent dimensions
The platform MUST separately report deterministic policy, build/tests, dependency/security scans, semantic review, and mandatory-human status. Unexecuted dimensions MUST remain unknown/not-run.

#### Scenario: deterministic scan passes but tests did not run
- **GIVEN** deterministic bundle checks pass
- **AND** build/tests were not executed
- **WHEN** assurance is rendered
- **THEN** deterministic policy MUST show PASS
- **AND** build/tests MUST show NOT_RUN or UNKNOWN
- **AND** the overall result MUST NOT claim fully verified

### Requirement: GitHub enforcement posture MUST be verifiable
The repository MUST provide governance files and a read-only verifier for rulesets, required checks, environments, Actions policy, scanning, and runners. Files alone MUST NOT be presented as proof that admin controls are active.

#### Scenario: workflow exists but check is not required
- **GIVEN** the bundle workflow exists on the default branch
- **AND** no active ruleset requires its check
- **WHEN** governance posture is verified
- **THEN** the report MUST mark bundle enforcement as advisory/not enforced
- **AND** MUST identify the missing admin configuration
