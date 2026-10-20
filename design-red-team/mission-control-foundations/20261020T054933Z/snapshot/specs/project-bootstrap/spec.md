## ADDED Requirements

### Requirement: PB-01 Approved project intent
Bootstrap MUST convert a project request into reviewed goals/non-goals, intended users, acceptance criteria, milestones, target/data constraints, owner, selected profile and action authority before unattended development starts.

#### Scenario: PB-01-01
- **WHEN** The user asks to build an application but omits a consequential product or data decision
- **THEN** bootstrap asks or stages an explicit assumption and does not silently decide it

#### Scenario: PB-01-02
- **WHEN** A narrow diagnosis-only profile is chosen
- **THEN** its declared scope is retained and no unattended feature development or production release is enabled

### Requirement: PB-02 Three connected foundations
Bootstrap MUST generate or adapt the application/specs, continued-development loop and enabled operational-repair loop as linked versioned artifacts while preserving existing handwritten code/instructions and approved CI.

#### Scenario: PB-02-01
- **WHEN** A new project enables development and operational repair
- **THEN** the staged plan includes backlog, tests, build/review/deploy workflows, monitoring, runbooks and decision/evidence links rather than just agent Markdown

#### Scenario: PB-02-02
- **WHEN** An existing application is onboarded
- **THEN** its working pipeline is retained unless an explicit reviewed replacement is selected

### Requirement: PB-03 Resource and permission plan
Bootstrap MUST separate shared foundation services, per-application resources and optional modules with provider/placement, identity, permissions, ownership, data/network/retention, cost category, readiness and exit actions before authorized apply.

#### Scenario: PB-03-01
- **WHEN** A Simple profile disables Doctor, custom models and authored graphs
- **THEN** those service/resource dependencies are absent and the supported minimum receipt/dispatch path is explicit

#### Scenario: PB-03-02
- **WHEN** The selected application lacks a preview target or monitoring identity
- **THEN** the plan names the missing prerequisite without inventing access or provisioning resources silently

### Requirement: PB-04 Executed scope-specific readiness
Bootstrap MUST report staged, applying, probing, ready, blocked and degraded distinctly and bind readiness to actual executed evidence for the selected scope; full-lifecycle readiness requires CI/review, preview deployment, acceptance check and external health proof.

#### Scenario: PB-04-01
- **WHEN** Files are generated but CI has never run
- **THEN** bootstrap remains staged or probing and cannot report full-lifecycle ready

#### Scenario: PB-04-02
- **WHEN** Application deployment succeeds but enabled monitoring has no signal-to-incident proof
- **THEN** operational repair readiness remains unproven

#### Scenario: PB-04-03
- **WHEN** All selected full-lifecycle probes pass
- **THEN** the report links exact runs/builds/probes/config versions and lists disabled or unproven modules separately

### Requirement: PB-05 Durable setup and handoff
Bootstrap MUST preserve setup progress across restart, reconcile ambiguous external creation and hand off ownership, operating instructions, limits and recovery/exit steps without retaining usable secrets in generated artifacts.

#### Scenario: PB-05-01
- **WHEN** Setup restarts after a repository or preview was created
- **THEN** reconciliation reuses the observed target rather than blindly creating duplicates

#### Scenario: PB-05-02
- **WHEN** Bootstrap completes for the selected scope
- **THEN** the user sees what agents will do next, what needs approval and where to stop or disconnect them

