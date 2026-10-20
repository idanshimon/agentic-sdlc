## ADDED Requirements

### Requirement: MO-01 Scoped memory and precedent
The system MUST distinguish investigation context, decision history, eligible precedent and outcome observations; recall must respect tenant/repository/data scope and never override policy.

#### Scenario: MO-01-01
- **WHEN** A recalled note asks the agent to bypass a protected review
- **THEN** the note remains untrusted context and no additional authority is granted

#### Scenario: MO-01-02
- **WHEN** Cross-run memory is disabled
- **THEN** no cross-run memory is injected but required action receipts remain available

### Requirement: MO-02 Observed outcomes and honest metrics
The system MUST distinguish human agreement, executed checks, deployment, original-task recovery, reversal and unknown coverage; it must not equate any one dimension with overall correctness.

#### Scenario: MO-02-01
- **WHEN** A patch merges but no deployment or retest is observed
- **THEN** merge is recorded and deployed resolution remains unverified

#### Scenario: MO-02-02
- **WHEN** Billing or verification telemetry is absent
- **THEN** the UI reports not measured with coverage rather than zero cost or a perfect result

### Requirement: MO-03 Governed learning and promotion
The system MUST treat permission expansion and canonical policy changes as versioned authorized changes supported by independently sourced, scope-compatible evidence and reversible rollout.

#### Scenario: MO-03-01
- **WHEN** A model writes its own success summaries repeatedly
- **THEN** the summaries do not create independent graduation samples or change its permissions

#### Scenario: MO-03-02
- **WHEN** A policy version changes the meaning of an old precedent
- **THEN** compatibility is re-evaluated and the original record is preserved

### Requirement: MO-04 Retention and portability
The system MUST provide policy-defined retention, scoped redaction/access revocation and export of decision/evidence references without leaking secrets or rewriting audit history to improve a score.

#### Scenario: MO-04-01
- **WHEN** A raw evidence object expires under policy
- **THEN** the record retains a truthful expired-reference state rather than fabricating readable evidence

#### Scenario: MO-04-02
- **WHEN** A repo disconnects
- **THEN** permitted audit export and pending-work disposition remain available without persisting usable repository credentials

### Requirement: MO-05 Learning is governed improvement
Learning MUST preserve independently supported knowledge and comparable precedent and may propose regression tests, runbooks or instruction/policy updates through their applicable review paths; routine learning must not imply weight retraining or self-issued permissions.

#### Scenario: MO-05-01
- **WHEN** A repair is reverted after an initial success observation
- **THEN** the later adverse outcome remains visible and affected precedent eligibility is re-evaluated

#### Scenario: MO-05-02
- **WHEN** A candidate lesson suggests changing a canonical instruction or policy
- **THEN** the system stages a versioned reviewable change rather than modifying its own authority silently



