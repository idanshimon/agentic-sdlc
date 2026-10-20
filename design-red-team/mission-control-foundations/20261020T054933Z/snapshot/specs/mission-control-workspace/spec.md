## ADDED Requirements

### Requirement: MC-01 Attention before chronology
The workspace MUST rank actionable blocked, failed and stalled work using observed state, scope, ownership and age; every item must expose its source, consequence and supported next action.

#### Scenario: MC-01-01
- **WHEN** An older human-blocked item competes with recent completed runs
- **THEN** the blocked item is visible in the attention queue and opens the correctly scoped record

#### Scenario: MC-01-02
- **WHEN** The upstream source cannot be read
- **THEN** the workspace reports unavailable or stale coverage rather than an empty healthy queue

### Requirement: MC-02 Shared decision workbench
The workspace MUST show observed evidence, recommendation, presented alternatives, applicable policy, target, authorized actor, downstream consequences and verification status in one linked workbench without inventing missing phases.

#### Scenario: MC-02-01
- **WHEN** A task has an approved proposal but no executed command
- **THEN** the workbench shows approval separately from execution and does not claim the change was applied

### Requirement: MC-03 Safe command interaction
The workspace MUST distinguish inspect, request repair, retry checks, approve, pause dispatch and request cancellation; consequential commands require explicit intent, expected version and server authorization.

#### Scenario: MC-03-01
- **WHEN** Two operators submit a conflicting action against one version
- **THEN** at most one compatible transition is accepted and the other receives an actionable conflict

#### Scenario: MC-03-02
- **WHEN** A user selects a graph node or completes a tour
- **THEN** no approval, repository write or paid inference is initiated

### Requirement: MC-04 Accessible accountable operation
The workspace MUST provide scoped URL state, keyboard and touch access, a list alternative to graphs, honest empty/loading/error states and durable status after navigation or reconnect.

#### Scenario: MC-04-01
- **WHEN** A running action survives a transient observation failure
- **THEN** the UI reconnects without duplicate execution and reconciles the observed terminal status

#### Scenario: MC-04-02
- **WHEN** A user changes a repo identifier in a URL
- **THEN** the server cannot widen the authenticated readable scope

