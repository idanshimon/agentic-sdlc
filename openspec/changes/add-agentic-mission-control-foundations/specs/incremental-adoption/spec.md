## ADDED Requirements

### Requirement: IA-01 Existing pipeline assessment
Adoption MUST inventory actual CI/CD, repository controls, identity, tests, integration health and owner requirements and produce KEEP/SWAP/ADD/OUT with native/bridged/unavailable/unverified capabilities.

#### Scenario: IA-01-01
- **WHEN** A team has a working pipeline and asks for diagnosis only
- **THEN** bootstrap retains that pipeline and grants no repair, merge or deployment authority

### Requirement: IA-02 One complete repair proof
The initial write-enabled proof MUST connect a real reproducible failure to diagnosis, fix PR, independent checks/review, bounded follow-up, human merge and original-task test-target verification.

#### Scenario: IA-02-01
- **WHEN** The happy-path PR is created but tests were not run
- **THEN** the proof is incomplete and cannot be labeled resolved

#### Scenario: IA-02-02
- **WHEN** A duplicated event or changed commit is injected
- **THEN** the proof demonstrates deduplication or stale-authorization refusal rather than only a happy-path graph

### Requirement: IA-03 Graduation by action and target
Adoption MUST advance authority only for explicitly approved action/target classes with required evidence, revocation and rollback readiness; a successful demonstration alone grants no permission.

#### Scenario: IA-03-01
- **WHEN** Low-risk docs repairs qualify for automatic admission
- **THEN** database and production runbook authority remain independently restricted

### Requirement: IA-04 Cost ownership and exit
Adoption MUST name operational owners, supported deployment footprint, usage/coverage limits, recovery/export paths and an exit plan that retires duplicate responsibilities only after equivalent proof.

#### Scenario: IA-04-01
- **WHEN** An adopter disables the foundation
- **THEN** owned schedules/credentials are identified for reviewed retirement and existing CI/admission remains intact

#### Scenario: IA-04-02
- **WHEN** An optional service is not installed
- **THEN** its absence is explicit and no undocumented dependency blocks the minimal profile

