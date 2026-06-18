# Spec delta: add-self-heal-cowork / self-heal-cowork

## ADDED Requirements

### Requirement: Heal sessions MUST be human-invoked at a gate or at end-of-run

A heal session MUST only be created in response to an explicit human action,
at one of exactly two trigger points: (a) while a run is paused at a gate
(resolver or design_review), or (b) when a run has reached a terminal state
(completed or failed). The system MUST NOT open a heal session on a schedule,
on a timer, or in response to a drift signal alone. Unattended drift
remediation is the separate `add-pipeline-doctor` capability.

#### Scenario: operator opens a heal session at end of a failed run

- **GIVEN** a run with status `failed` and red codegen-test artifacts
- **WHEN** the operator clicks "Review & heal" on the run-detail page
- **THEN** a heal session MUST be created scoped to that run_id
- **AND** the Cowork agent MUST begin a streaming diagnosis within the session
- **AND** no heal session MUST exist for that run before the operator's click

#### Scenario: no heal session is auto-created by a drift signal

- **GIVEN** the ledger contains a drift signal that would trigger the scheduled Pipeline Doctor
- **WHEN** no human has invoked a heal session
- **THEN** the system MUST NOT create a heal session
- **AND** the only automated consumer of that signal MUST be the scheduled `add-pipeline-doctor` job

### Requirement: Every heal action MUST require explicit per-action human approval

The system MUST require explicit per-action human approval before any
write-causing action executes within a heal session. This applies to any
action that writes to GitHub (a PR or commit), to the prompt library, to a
standards bundle, to an autopilot threshold, or to the pipeline run state.
Each such action MUST be presented to the human with its concrete effect (a
diff, a re-run plan, a PR preview) and MUST NOT execute until the human
explicitly approves that specific action. The read-only `AssistantPanel`
boundary is relaxed for heal sessions ONLY behind this per-action approval
gate.

#### Scenario: a code heal is shown as a diff before it lands

- **GIVEN** an active heal session where the Cowork agent proposes `assign_code_heal`
- **WHEN** the agent prepares the heal
- **THEN** the proposed change MUST be presented to the human before any PR is opened
- **AND** the GitHub coding agent MUST NOT be dispatched until the human approves
- **AND** if the human declines, no PR MUST be opened and the run MUST remain unchanged

#### Scenario: a re-run action requires approval even though it is idempotent

- **GIVEN** a heal session proposing `rerun_stage` for a failed stage
- **WHEN** the agent surfaces the proposal
- **THEN** the re-run MUST NOT start until the human approves it
- **AND** the approval MUST be recorded as a ledger entry before the stage re-runs

### Requirement: PHI-class and explicit-deny rules MUST never be auto-healed

The validator MUST reject any heal action that would modify a rule with
`phi: true` or an explicit-deny rule pattern, regardless of session state,
human approval, or envelope configuration. Such a heal MUST be converted into
an escalation for a human-authored standards change, and MUST never be applied
by the Cowork agent or the Executor.

#### Scenario: a PHI rule heal is blocked at the validator

- **GIVEN** a heal session where the Cowork agent's proposed heal would alter a rule carrying `phi: true`
- **WHEN** the heal is validated before presentation to the human
- **THEN** the validator MUST reject the heal as a forbidden action
- **AND** the session MUST surface an escalation path (human-authored standards change) instead
- **AND** no auto-apply path MUST exist for that heal even if the human clicks approve

### Requirement: Heal decisions MUST be pinned to the ledger as a typed decision class

The system MUST write every meaningful step of a heal session to the Decision
Ledger. This covers the agent's proposal, the human's decision, and the
executor's completion, each as an entry with the standard schema (actor,
rationale, cost, bundle_refs, precedent_refs) plus a heal-specific kind. The
chain MUST be reconstructable: which signal, who decided, what landed, and
where (the PR or re-run).

#### Scenario: a completed code heal pins the full chain

- **GIVEN** a heal session that proposed `assign_code_heal`, was approved by a human, and resulted in a PR opened by the GitHub coding agent
- **WHEN** the executor reports the PR back to the orchestrator
- **THEN** the ledger MUST contain a `heal_proposed` entry with `actor.kind = agent`
- **AND** a `heal_decided` entry with `actor.kind = human` and the approver's identity
- **AND** a `heal_executed` entry carrying the PR URL
- **AND** all three entries MUST share a common heal_id so the chain is queryable

### Requirement: Code heals MUST land as GitHub pull requests, not direct mutations

When a heal involves changing code, the Cowork agent MUST NOT edit repository
files directly. The heal MUST be dispatched to the GitHub Copilot coding agent
(the Executor) which opens a pull request on the repository. The PR MUST be
subject to the repository's existing CODEOWNERS, CI, and merge governance. The
Cowork agent's responsibility ends at recording the decided intent and the
resulting PR reference.

#### Scenario: a code heal produces a reviewable PR

- **GIVEN** an approved `assign_code_heal` action in a heal session
- **WHEN** the Executor performs the code surgery
- **THEN** the result MUST be a pull request on the repository, not a direct commit to a protected branch
- **AND** the PR MUST be subject to CODEOWNERS review and CI before merge
- **AND** the heal_executed ledger entry MUST reference the PR, not a merged commit
