# Spec delta: adopt-github-native-execution-substrate / agent-remediation

> **Capability:** `agent-remediation` (NEW)
>
> This capability answers a question the rest of this change leaves open. The deployment spec
> establishes that a run **ends** at a gate and a new run resumes on approval. It does not say
> what the agent *produces* at that moment, nor how agent-authored work is kept distinguishable
> from human-authored work in the repository.
>
> Without an answer, a migrated stage has two bad options: commit agent output directly into the
> human's branch (destroying provenance and making the human the apparent author of agent work),
> or emit it as an artifact that no reviewer sees. Neither is acceptable in a regulated SDLC where
> the auditable question is *who decided this, and who wrote this*.

## ADDED Requirements

### Requirement: Agent remediation MUST materialize as a separate stacked pull request

Agent remediation for a failed governed gate MUST be delivered as a separate pull request stacked
on the triggering pull request's branch, and the agent MUST NOT push commits to the branch of a
pull request opened by a human actor.

The stacked pull request's base MUST be the triggering pull request's head branch, so that the
human's diff and the agent's diff remain two independently reviewable units, and so that the
authorship recorded by the SCM is truthful for both.

This is the structural expression of the same principle the ledger enforces for decisions: an
agent action is attributable, isolated, and independently reviewable. A commit silently added to a
human's branch is the code-plane equivalent of an unledgered decision.

#### Scenario: a failed gate produces a stacked companion pull request

- **GIVEN** a pull request opened by an actor with `actor.kind: human`
- **AND** a governed gate on that pull request evaluates to failed
- **WHEN** the remediation agent produces changes that satisfy the gate
- **THEN** the changes MUST be delivered as a new pull request
- **AND** that pull request's base branch MUST be the triggering pull request's head branch
- **AND** the triggering pull request's head branch MUST have no new commits authored by the agent

#### Scenario: the agent does not write to a human branch

- **GIVEN** a remediation agent holds changes for a human-opened pull request
- **WHEN** the delivery step executes
- **THEN** no push to the human pull request's head branch MUST occur
- **AND** an attempt to do so MUST fail closed and record the refusal

#### Scenario: agent-opened pull requests are stackable on each other

- **GIVEN** a stacked remediation pull request that itself fails a second governed gate
- **WHEN** a further remediation is produced
- **THEN** it MUST stack on the remediation pull request's head branch
- **AND** the resulting chain MUST remain a linear stack with one reviewable diff per actor action

### Requirement: A remediation pull request MUST carry its complete evidence chain

A remediation pull request body MUST identify what caused it to exist. It MUST record:

- the identifier of the triggering pull request,
- the gate that failed, by name,
- the workflow run URL of the failing gate evaluation,
- the `LedgerEntry` identifier for the decision that authorized the remediation,
- the standards bundle citations in `[<dept>/<version>/<rule-id>]` form for the rules evaluated.

A reviewer opening the remediation pull request MUST be able to reach the failing evidence without
prior knowledge of the run, and an auditor reading the ledger MUST be able to reach the pull
request. The linkage MUST be bidirectional.

Provenance that exists only as tribal knowledge is not provenance.

#### Scenario: the remediation body is a complete evidence chain

- **GIVEN** a remediation pull request created by a failed gate
- **WHEN** its body is read
- **THEN** it MUST reference the triggering pull request identifier
- **AND** it MUST name the failed gate
- **AND** it MUST link the workflow run URL of the failing evaluation
- **AND** it MUST cite the evaluated rules as `[<dept>/<version>/<rule-id>]`

#### Scenario: the ledger reaches the pull request and the pull request reaches the ledger

- **GIVEN** a remediation pull request has been created
- **WHEN** the corresponding `LedgerEntry` is read
- **THEN** `gh_audit_xref` MUST identify the remediation pull request
- **AND** the remediation pull request body MUST identify that `LedgerEntry`

#### Scenario: an evidence chain with a missing link is rejected

- **GIVEN** a remediation whose failing workflow run URL cannot be resolved
- **WHEN** delivery is attempted
- **THEN** delivery MUST fail closed
- **AND** the failure MUST be recorded with `gate_reason: verification_failed`

### Requirement: An agent MUST NOT satisfy the human-review requirement on its own remediation

A remediation pull request MUST require review by an actor with `actor.kind: human` who is not the
authoring agent principal. An agent principal's approval MUST NOT count toward the required
review on a pull request authored by an agent principal.

Where the remediation targets a decision whose `ambiguity_class` is in `INVARIANT_CLASSES`, the
approval set MUST additionally satisfy the quorum policy declared in
`standards-bundles/<dept>/<version>/reviewers.yaml`.

An agent that can open a pull request, approve it, and merge it has closed its own loop, and the
governed pipeline has become an unreviewed one.

#### Scenario: an agent approval does not satisfy required review

- **GIVEN** a remediation pull request authored by an agent principal
- **WHEN** the same or another agent principal approves it
- **THEN** the required human review MUST remain unsatisfied
- **AND** the pull request MUST NOT be mergeable

#### Scenario: an invariant-class remediation requires quorum

- **GIVEN** a remediation for a decision whose `ambiguity_class` is `phi-classification`
- **AND** the bundle's `reviewers.yaml` declares two required approvers
- **WHEN** one human approval is recorded
- **THEN** the pull request MUST NOT be mergeable
- **AND** the shortfall MUST be attributable to the quorum policy, not to a generic failure

### Requirement: Governed gates MUST re-evaluate the triggering pull request after remediation lands

Gates on a triggering pull request MUST re-evaluate automatically when a remediation pull request
merges into that pull request's head branch.

A gate whose only path to green is a human remembering to press a button is not an enforcement
surface; it is a convention. The re-evaluation MUST be observable as a state transition on the
triggering pull request.

#### Scenario: the triggering pull request unblocks automatically

- **GIVEN** a triggering pull request failing a governed gate
- **AND** a stacked remediation pull request that satisfies that gate
- **WHEN** the remediation merges into the triggering head branch
- **THEN** the gate on the triggering pull request MUST re-evaluate without manual action
- **AND** the resulting evaluation MUST be recorded as a `runtime` ledger entry

#### Scenario: re-evaluation that still fails does not silently pass

- **GIVEN** a remediation that merges but does not satisfy the gate
- **WHEN** the gate re-evaluates
- **THEN** the triggering pull request MUST remain blocked
- **AND** a further remediation MUST stack rather than amend the existing remediation

### Requirement: Gate policy MUST NOT be modifiable by the pull request it evaluates

The policy definition a governed gate evaluates MUST be resolved from a source that the evaluated
pull request cannot modify within the same evaluation.

Where a gate workflow runs with elevated context on untrusted pull request content, the policy and
its evaluation logic MUST be read from the base revision or from a centrally governed location,
never from the pull request's own head revision.

A gate an author can edit in the same change it is gating provides no assurance.

#### Scenario: a pull request cannot weaken its own gate

- **GIVEN** a pull request whose diff modifies the gate policy definition
- **WHEN** the governed gate evaluates that pull request
- **THEN** the evaluation MUST use the base revision's policy
- **AND** the attempted policy modification MUST itself be gated as a standards change

#### Scenario: policy resolution failure is fail-closed

- **GIVEN** a governed gate whose policy definition cannot be loaded
- **WHEN** the gate evaluates
- **THEN** the gate MUST fail closed
- **AND** the outcome MUST be recorded with `gate_reason: verification_failed`
- **AND** the gate MUST NOT report success

### Requirement: Remediation MUST be bounded by the run budget

Remediation MUST NOT recurse without limit. A declared maximum remediation depth MUST bound the
length of a stack originating from a single triggering pull request.

Exhaustion MUST halt and open a gate with `gate_reason: budget_exceeded`, surfacing an agent that
cannot satisfy a gate as an explicit governance event rather than as an unbounded sequence of
pull requests.

#### Scenario: remediation depth is bounded

- **GIVEN** a declared maximum remediation depth of two
- **AND** a stack that has already produced two remediation pull requests
- **WHEN** a third remediation would be produced
- **THEN** it MUST NOT be created
- **AND** a gate MUST open with `gate_reason: budget_exceeded`
- **AND** the halt MUST reference the triggering pull request

## MODIFIED Requirements

### Requirement: The ledger MUST record the pull request lineage of a remediation

`gh_audit_xref` MUST, for a remediation decision, identify both the triggering pull request and
the remediation pull request, and MUST record the remediation's depth within its stack.

This extends the existing `gh_audit_xref` population at delivery. Recording only the created pull
request loses the causal link, and the causal link is the audit artifact.

#### Scenario: lineage is reconstructable from the ledger alone

- **GIVEN** a completed remediation at depth one
- **WHEN** its `LedgerEntry` is read from the durable store
- **THEN** `gh_audit_xref` MUST identify the triggering pull request
- **AND** it MUST identify the remediation pull request
- **AND** it MUST record the remediation depth
- **AND** the full stack MUST be reconstructable without reading the repository
