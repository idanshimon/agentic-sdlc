## ADDED Requirements

### Requirement: OP-01 External incident evidence
Enabled operational repair MUST ingest authenticated redacted signals from monitoring independent of the watched application, correlate application/environment/deployed-version/symptom evidence and control duplicates, storms and recursive triggers.

#### Scenario: OP-01-01
- **WHEN** The application is unavailable and cannot report its own errors
- **THEN** an external health path can still identify the failure and route a bounded incident

#### Scenario: OP-01-02
- **WHEN** Many signals describe the same failure or an agent repair retriggers itself
- **THEN** incident correlation and configured budgets/concurrency prevent unbounded duplicate repairs

### Requirement: OP-02 Diagnosis before intervention
The operational loop MUST distinguish observed symptoms, suspected causes and verified facts and route code defects, configuration/runbook actions, dependency/capacity failures, flakes and unknowns through their respective authority and evidence needs.

#### Scenario: OP-02-01
- **WHEN** A downstream dependency is unavailable
- **THEN** the agent does not invent an application patch merely to produce a fix

#### Scenario: OP-02-02
- **WHEN** The failure cannot be reproduced and causal evidence is insufficient
- **THEN** the incident stays investigation-only or escalates without claiming confirmed diagnosis

### Requirement: OP-03 Policy-permitted automatic release
The operational loop MUST support proposed repair, qualifying autonomous release and human-required escalation as separate configured paths; merge/deploy requires exact-state independent checks and current action/target authority.

#### Scenario: OP-03-01
- **WHEN** A qualifying low-risk repair has explicit current automatic release authority and passes required gates
- **THEN** the loop may merge and deploy through the approved rollout path without demanding an unrelated blanket human step

#### Scenario: OP-03-02
- **WHEN** A repair touches authentication, schema or infrastructure outside its envelope
- **THEN** the corresponding human/governance path is required regardless of model confidence

#### Scenario: OP-03-03
- **WHEN** No production release permission is configured
- **THEN** the agent may prepare the permitted PR but cannot silently deploy it

### Requirement: OP-04 Original-symptom recovery proof
The loop MUST verify the original symptom and selected health criterion against the deployed build over the configured observation window; merge, deployment and recovered service remain separate states.

#### Scenario: OP-04-01
- **WHEN** A build deploys successfully but attachment uploads still fail
- **THEN** the incident remains unresolved and the agent does not record recovery

#### Scenario: OP-04-02
- **WHEN** Verification is unavailable or the observation window is incomplete
- **THEN** recovery is pending or unknown rather than passing

### Requirement: OP-05 Authorized recovery and learning handoff
The operational loop MUST use a tested scoped rollback/compensation or escalation path when remediation fails and hand off independent outcome references to governed knowledge/precedent evaluation.

#### Scenario: OP-05-01
- **WHEN** A canary worsens health
- **THEN** only authorized recovery actions execute and their actual effects are verified; otherwise a named owner is escalated

#### Scenario: OP-05-02
- **WHEN** A successful code repair is independently confirmed
- **THEN** the incident links its regression test, deployed result and candidate lesson without changing weights or permissions automatically

