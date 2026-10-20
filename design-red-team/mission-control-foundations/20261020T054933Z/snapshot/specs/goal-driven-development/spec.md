## ADDED Requirements

### Requirement: GD-01 Approved eligible work selection
The development controller MUST select only approved backlog tasks whose dependencies, priority, target authority, concurrency lease and budgets permit execution; it must not invent new product goals to stay busy.

#### Scenario: GD-01-01
- **WHEN** Approved work is exhausted
- **THEN** the controller waits or reports milestone completion and puts new suggestions in a separate proposed backlog

#### Scenario: GD-01-02
- **WHEN** A task depends on an unresolved product decision
- **THEN** the task is blocked and a concrete question is surfaced rather than a guessed implementation

### Requirement: GD-02 Requirement-to-acceptance development loop
Each autonomous development task MUST link approved requirements and acceptance criteria to investigation, meaningful decisions, implementation PR, independent checks/review, permitted release and observed acceptance outcome.

#### Scenario: GD-02-01
- **WHEN** A task opens a PR without executed required tests
- **THEN** the task is not complete

#### Scenario: GD-02-02
- **WHEN** An author changes protected acceptance checks to make its patch pass
- **THEN** the change is routed through independent applicable governance rather than accepted as ordinary repair

### Requirement: GD-03 Durable bounded continuation
The controller MUST reload durable task/config/evidence state before continuation, prevent duplicate active work and stop or escalate on uncertainty, repeated failure, unavailable capacity or exhausted limits.

#### Scenario: GD-03-01
- **WHEN** An execution worker restarts or a dispatch is repeated
- **THEN** one current task attempt is reconciled without duplicate consequential action

#### Scenario: GD-03-02
- **WHEN** A task repeatedly fails within its configured repair ceiling
- **THEN** the controller stops new attempts and records a human-actionable blocker

### Requirement: GD-04 Product change and milestone control
The system MUST version approved goals and acceptance changes, invalidate incompatible work assumptions and keep feature suggestions, product approval and operational repair as distinct authorities.

#### Scenario: GD-04-01
- **WHEN** A human changes the approved requirement during implementation
- **THEN** the running work is revalidated against the new version before release

#### Scenario: GD-04-02
- **WHEN** An incident repair agent proposes an unrelated feature
- **THEN** the feature remains a proposal and cannot inherit incident-remediation authority

