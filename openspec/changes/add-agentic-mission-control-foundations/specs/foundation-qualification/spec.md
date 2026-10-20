## ADDED Requirements

### Requirement: FQ-01 Foundation test ownership and layers
The foundation MUST maintain executable tests for its own configuration resolver, bootstrap generation, identity/authorization, receipt persistence/concurrency, event/command adapters, lifecycle projectors and operator UI, separate from generated application tests.

#### Scenario: FQ-01-01
- **WHEN** Application tests pass but foundation authorization or receipt tests fail
- **THEN** the foundation release is blocked; application success cannot substitute for foundation qualification

#### Scenario: FQ-01-02
- **WHEN** A connector or receipt backend is replaced
- **THEN** the replacement runs the same applicable contract/conformance suite before activation

### Requirement: FQ-02 Profile acceptance and failure matrix
Foundation acceptance MUST exercise supported profiles and module combinations, including the minimum topology with optional services absent, plus stale evidence, duplicate events, restart, conflicting commands, missing permissions, revocation and budget exhaustion.

#### Scenario: FQ-02-01
- **WHEN** Simple is tested only by hiding enterprise pages while optional workers still run
- **THEN** the minimal-profile acceptance criterion fails

#### Scenario: FQ-02-02
- **WHEN** No runtime test ran for an enabled command path
- **THEN** that path remains unqualified even if OpenSpec validation and documentation checks pass

### Requirement: FQ-03 Independent acceptance authority
The foundation MUST assign an authorized owner to acceptance criteria and authoritative evaluation artifacts, version/protect those artifacts before they establish completion and require applicable independent review for their creation or change; generated tests alone are not their own approval.

#### Scenario: FQ-03-01
- **WHEN** An implementing agent generates an acceptance test that merely asserts HTTP success
- **THEN** the test cannot alone establish product correctness without validated coverage of the approved behavior

#### Scenario: FQ-03-02
- **WHEN** An agent adds a useful regression in its implementation PR
- **THEN** the regression may count after independent validation under the selected policy; agent authorship alone does not disqualify it

#### Scenario: FQ-03-03
- **WHEN** An acceptance artifact is changed to conceal an implementation defect
- **THEN** the change requires its own authorized acceptance review and prior evidence is revalidated

### Requirement: FQ-04 Evidence bound release qualification
Qualification MUST bind foundation/app test results to the relevant source, artifact, spec, config/profile, policy and test versions and preserve failed, skipped, unavailable and unexecuted states; release and deployment outcomes must remain distinct.

#### Scenario: FQ-04-01
- **WHEN** A previously green test run refers to another spec revision or delivered artifact
- **THEN** it cannot qualify the current incompatible change

#### Scenario: FQ-04-02
- **WHEN** A required acceptance scenario is skipped or no tests are discovered
- **THEN** the release is not qualified by a green aggregate

#### Scenario: FQ-04-03
- **WHEN** An acceptance report is written by the implementation agent without independent execution evidence
- **THEN** the report is treated as a claim rather than a passing result

