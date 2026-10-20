## ADDED Requirements

### Requirement: AX-01 Target before authority
The system MUST resolve target identity, environment and applicable risk scope before autonomy evaluation and must reject unsafe precedent transfer across incompatible targets or policy versions.

#### Scenario: AX-01-01
- **WHEN** A sandbox precedent is offered for a production-affecting action
- **THEN** the system refuses reuse unless an explicit compatibility policy and required evidence permit it

#### Scenario: AX-01-02
- **WHEN** A target is unknown at authorization time
- **THEN** the action cannot obtain production-affecting permissions

### Requirement: AX-02 Bounded transition envelopes
The system MUST enforce action-specific permission, identity, tool/data/egress scope, attempt/time/concurrency and supported spend limits; capability activation alone must not grant authority.

#### Scenario: AX-02-01
- **WHEN** A repair exhausts its attempt or time budget
- **THEN** new repair dispatch stops and an attributed escalation records the reason

#### Scenario: AX-02-02
- **WHEN** The provider cannot support a claimed hard spend limit
- **THEN** the control is marked unsupported or advisory and cannot be presented as an enforced ceiling

### Requirement: AX-03 Durable command lifecycle
The system MUST persist intent before dispatch, require idempotency and expected-state preconditions, reconcile ambiguous outcomes and keep partially linked remediation non-mergeable.

#### Scenario: AX-03-01
- **WHEN** The ledger intent is saved but external PR creation fails
- **THEN** the task remains pending or failed with evidence and reconciliation does not invent a PR

#### Scenario: AX-03-02
- **WHEN** GitHub contains a PR whose decision linkage cannot be verified
- **THEN** the remediation is quarantined until the records agree

### Requirement: AX-04 Revocation cancellation and recovery
The system MUST stop new dispatch after authorized revocation, track cancellation acknowledgements separately from requests and require scoped authorization for rollback or compensating actions.

#### Scenario: AX-04-01
- **WHEN** An operator stops dispatch while an external action is running
- **THEN** no new action starts and the in-flight action remains tracked until its actual disposition is known

#### Scenario: AX-04-02
- **WHEN** A workflow has no cancellation or rollback support
- **THEN** the UI states that limitation and does not claim cancellation or restored service

### Requirement: AX-05 Protect the evaluation path
The system MUST classify changes to standards, workflows, verifiers, collectors, publishers, pins and ownership as governance-sensitive and enforce independent authorization appropriate to the selected policy.

#### Scenario: AX-05-01
- **WHEN** An agent repairs a failure by removing a gate step
- **THEN** the change cannot gain ordinary low-risk admission by claiming the rule file was untouched

