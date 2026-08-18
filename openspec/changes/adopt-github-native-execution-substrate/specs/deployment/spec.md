# Spec delta: adopt-github-native-execution-substrate / deployment

## ADDED Requirements

### Requirement: Pipeline stages MUST execute as GitHub Actions workflow runs

Each pipeline stage MUST execute as a job in a workflow definition committed to the repository
under `.github/workflows/`. The definition MUST be a versioned repository file subject to
`CODEOWNERS` review.

User-private automation MUST NOT be the canonical workflow definition, because it is neither
versioned in Git nor reviewable.

#### Scenario: a stage runs on the GitHub substrate

- **GIVEN** a run is submitted for a team whose stages have migrated
- **WHEN** the pipeline reaches the `review_scan` stage
- **THEN** the stage MUST execute as a GitHub Actions workflow run
- **AND** the run's ledger entry MUST reference the workflow run identifier

#### Scenario: the workflow definition is governed

- **WHEN** a pull request modifies a pipeline workflow definition
- **THEN** `CODEOWNERS` MUST require review from the owning persona team
- **AND** the change MUST NOT be mergeable without that review

### Requirement: The substrate MUST authenticate to Azure by federated identity

Workflows that reach Azure data-plane resources MUST authenticate by OIDC federation. Long-lived
service-principal secrets MUST NOT be stored as repository or organization secrets for
data-plane auth.

#### Scenario: a migrated stage authenticates without a stored secret

- **GIVEN** a stage workflow that writes to the Decision Ledger
- **WHEN** the workflow authenticates to Azure
- **THEN** it MUST use a federated OIDC token
- **AND** the workflow definition MUST NOT reference a service-principal client secret

### Requirement: Human approval MUST route through an Environment gated by a control-plane verdict

A stage requiring human approval MUST be bound to a GitHub Environment with required reviewers.
That Environment MUST additionally be protected by a custom deployment protection rule that
requests a classification verdict from the control plane before the approval is offered.

The control plane MUST return the gating classification for the pending decision. GitHub MUST
NOT be the authority on whether a decision is hard-gated; it is the surface on which the
control plane's verdict is presented and recorded.

#### Scenario: the control plane supplies the gating verdict

- **GIVEN** a stage awaiting approval for a card classified `phi-classification`
- **WHEN** the deployment protection rule is evaluated
- **THEN** the control plane MUST be called for the verdict
- **AND** the verdict MUST report the decision as hard-gated
- **AND** the Environment MUST require an individual named approver

#### Scenario: the control plane is unreachable

- **GIVEN** the control plane cannot be reached when the protection rule is evaluated
- **WHEN** the rule resolves
- **THEN** the deployment MUST NOT be approved
- **AND** the failure MUST be recorded as a gate with `gate_reason: stalled`
- **AND** the system MUST fail closed

#### Scenario: a hard-gated decision cannot be bulk-approved through the GitHub path

- **GIVEN** a `phi-classification` card pending approval via the Environment
- **WHEN** an approval is submitted with `approval_path` of `bulk`
- **THEN** the control plane MUST reject it with HTTP 409
- **AND** the decision MUST remain unresolved
- **AND** the rejection MUST hold regardless of any recorded `decision_confidence`

### Requirement: Environment protection MUST be hardened against native bypass

Every Environment gating an invariant class MUST have administrator bypass disabled and
self-review prevented, and quorum MUST be enforced by the control plane.

GitHub enables **administrator bypass of environment protection rules by default**, and a native
environment requires only **one approval from up to six configured reviewers**. Neither default is
acceptable for an invariant-class gate.

Because GitHub cannot express an N-of-M named-approver quorum, any quorum requirement is applied
by the control plane before it returns an approving verdict — the Environment MUST NOT be treated
as the quorum authority.

The quorum policy already exists as data. `standards-bundles/<dept>/<version>/reviewers.yaml`
declares, per `blast_class`, a `required_approvers` count, `must_include_roles`, and
`can_include_roles` — for example the security bundle's `HIGH` class requires three approvers and
must include both `security_lead` and `privacy_dpo`. The control plane MUST evaluate the approval
set against that declared policy. GitHub's single approval MUST be treated as one contributing
signature, never as satisfaction of the quorum.

A gate is only as strong as its weakest bypass. The control plane, not the Environment, is the
authority on whether an approval is sufficient.

#### Scenario: administrator bypass is disabled on a gating environment

- **GIVEN** an Environment bound to a stage that gates invariant classes
- **WHEN** its protection configuration is audited
- **THEN** administrator bypass MUST be disabled
- **AND** self-review MUST be prevented

#### Scenario: a single approval does not satisfy a quorum requirement

- **GIVEN** a decision whose `blast_class` is `HIGH` under the security bundle
- **AND** `reviewers.yaml` requires three approvers including `security_lead` and `privacy_dpo`
- **AND** one reviewer has approved through the GitHub Environment
- **WHEN** the control plane is asked for its verdict
- **THEN** the verdict MUST remain unapproved
- **AND** the run MUST NOT proceed until the declared quorum and required roles are satisfied

#### Scenario: quorum is satisfied in count but missing a required role

- **GIVEN** a `HIGH` blast-class decision with three recorded approvers
- **AND** none of them holds the `privacy_dpo` role
- **WHEN** the control plane evaluates the approval set
- **THEN** the verdict MUST remain unapproved
- **AND** the missing required role MUST be reported

#### Scenario: an environment configuration drift is detected

- **WHEN** the governance scan runs against gating Environments
- **THEN** any Environment with administrator bypass re-enabled MUST fail the scan
- **AND** the finding MUST be reported as a governance regression

### Requirement: Agent execution MUST be write-isolated from its own outputs

The agent job MUST run without write permissions. Any write an agent proposes MUST be buffered as
an output artifact and materialized only by a separate, narrowly-scoped job.

A compromised or prompt-injected agent MUST NOT be able to authorize its own writes.

#### Scenario: the agent job holds no write permission

- **GIVEN** a stage workflow that executes an agent
- **WHEN** the workflow definition is inspected
- **THEN** the agent job's `permissions` MUST NOT include write scopes
- **AND** writes MUST be materialized in a separate job

#### Scenario: a proposed write is materialized under narrow scope

- **GIVEN** an agent that proposes a pull request comment
- **WHEN** the output is materialized
- **THEN** the materializing job MUST hold only the permission required for that output type

### Requirement: Agent network egress MUST be deny-by-default

Stage workflows executing agents MUST restrict outbound network access to an explicit allowlist.
An agent handling PHI-adjacent context MUST NOT have unrestricted egress.

#### Scenario: egress is restricted to an allowlist

- **GIVEN** a stage workflow executing an agent
- **WHEN** its network configuration is inspected
- **THEN** egress MUST be limited to an explicit allowlist
- **AND** unrestricted egress MUST NOT be configured

### Requirement: Audit records MUST be retained for the regulatory period in an external sink

Decision records MUST be retained in the control plane's durable store, and organization audit
events MUST be streamed to an external sink configured for write-once retention.

GitHub Actions log and artifact retention is bounded and configurable in days; it does not satisfy
a six-year retention obligation, so it cannot be the system of record.

Retention MUST meet the longest applicable obligation: six years for HIPAA documentation, and not
less than six months for AI-system logs under EU AI Act deployer obligations.

#### Scenario: decision records outlive Actions retention

- **GIVEN** a decision written during a run whose Actions logs have since expired
- **WHEN** the decision is queried from the ledger
- **THEN** the full decision record MUST still be retrievable
- **AND** it MUST retain its `bundle_refs`, `autonomy_ref`, and actor attribution

#### Scenario: audit events stream to a durable sink

- **WHEN** the enterprise audit configuration is inspected
- **THEN** audit log streaming MUST be enabled to an external sink
- **AND** the sink MUST be configured for write-once retention

### Requirement: Preview and research-stage dependencies MUST be pinned and declared

Every preview or research-stage dependency MUST be pinned to an explicit version and recorded in
a declared inventory naming its maturity and its fallback.

The agentic workflow toolchain is a research-stage project and several governance-relevant GitHub
features are in public preview.

A governance control MUST NOT depend on an unpinned preview feature without a declared fallback.

#### Scenario: the preview inventory exists and names fallbacks

- **WHEN** the substrate dependency inventory is read
- **THEN** each preview or research-stage dependency MUST be listed with its maturity
- **AND** each MUST name the fallback used if the feature becomes unavailable

#### Scenario: the toolchain is version-pinned

- **WHEN** a stage workflow references the agentic workflow toolchain
- **THEN** it MUST reference an explicit pinned version
- **AND** MUST NOT float to the latest release

### Requirement: Runs MUST declare an explicit budget and gate rather than fail opaquely

A run MUST carry a declared budget: maximum stage retries, maximum total run duration, and an
idle timeout. On exhaustion the run MUST halt and open a gate with `gate_reason: budget_exceeded`.

An exhausted budget MUST NOT surface as an unclassified timeout or a generic failure.

#### Scenario: exceeding maximum retries opens a classified gate

- **GIVEN** a run whose budget permits two stage retries
- **WHEN** a stage fails a third time
- **THEN** the run MUST halt
- **AND** a gate MUST open with `gate_reason: budget_exceeded`

#### Scenario: an idle run is halted rather than left running

- **GIVEN** a run that has produced no stage event within its idle timeout
- **WHEN** the timeout elapses
- **THEN** the run MUST halt with `gate_reason: stalled`

### Requirement: An operator MUST be able to halt an in-flight stage

The control plane MUST expose an operator halt for a running stage. The halt MUST be recorded as
a ledger entry attributed to the operator with `gate_reason: operator_requested`.

#### Scenario: an operator halts a running stage

- **GIVEN** a stage executing on the GitHub substrate
- **WHEN** an operator issues a halt for that run
- **THEN** the stage MUST stop
- **AND** a ledger entry MUST record the halting operator as `actor.kind: human`
- **AND** `gate_reason` MUST be `operator_requested`

### Requirement: Migration MUST be per-stage and reversible

Each stage MUST migrate behind an independent flag. The existing execution path MUST remain
functional until that stage's GitHub equivalent has been proven on a live run. Rollback MUST be
possible per stage without redeploying the control plane.

#### Scenario: a stage rolls back independently

- **GIVEN** `review_scan` has migrated and `codegen` has not
- **WHEN** the `review_scan` migration flag is disabled
- **THEN** `review_scan` MUST execute on the prior path
- **AND** other stages MUST be unaffected

#### Scenario: decommissioning requires proof for every stage

- **WHEN** decommissioning of the prior stage executor is proposed
- **THEN** every stage MUST have at least one completed live run on the GitHub substrate
- **AND** the evidence MUST be recorded per stage
