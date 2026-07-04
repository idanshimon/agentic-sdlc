# Spec delta: ledger — admin lifecycle endpoints + honest attribution

## ADDED Requirements

### Requirement: Admin run deletion removes only the run doc and preserves audit

The orchestrator MUST expose an admin endpoint that hard-deletes a single run document from the pipeline-runs container while leaving that run's decision-ledger entries intact. Run cleanup must never destroy the decision audit trail.

#### Scenario: Delete a run, keep its decisions

- **GIVEN** a run exists in the pipeline-runs container with decision-ledger entries under its team partition
- **WHEN** an operator calls DELETE on the admin run endpoint for that run id
- **THEN** the run doc is removed and a subsequent read of that run returns not-found
- **AND** the decision-ledger entries the run wrote remain queryable

#### Scenario: Delete drops in-memory handles idempotently

- **GIVEN** a run may or may not still be held in the orchestrator's in-memory maps
- **WHEN** the admin run delete executes
- **THEN** the in-memory run, queue, gate, and PRD-cache handles for that run id are cleared
- **AND** the call succeeds whether or not those handles were present

### Requirement: Admin ledger clear is scoped to a single team partition

The orchestrator MUST expose an admin endpoint that deletes all decision-ledger entries for one team partition and MUST NOT delete entries belonging to any other team. The endpoint reports how many entries were found and deleted.

#### Scenario: Clear one team without touching another

- **GIVEN** decision entries exist for team A and team B
- **WHEN** an operator calls DELETE on the admin ledger endpoint for team A
- **THEN** team A's entries are removed and the response reports the found and deleted counts
- **AND** team B's entries remain intact

### Requirement: Gate approval records the caller's confidence source

The approve handler MUST write the caller-supplied confidence_source onto the decision-ledger entry so an agent (autopilot) decision made through the resolver gate is attributed as agent, not human. When the field is omitted the entry MUST default to human.

#### Scenario: Autopilot decision through the gate is attributed to the agent

- **GIVEN** a gate approval is submitted with confidence_source set to autopilot
- **WHEN** the approve handler writes the ledger entry
- **THEN** the persisted entry carries confidence_source autopilot
- **AND** downstream reads classify it as an agent decision

#### Scenario: Omitted confidence source defaults to human

- **GIVEN** a gate approval is submitted without a confidence_source field
- **WHEN** the approve handler writes the ledger entry
- **THEN** the persisted entry carries confidence_source human

### Requirement: The Decisions UI derives actor kind from confidence source

The Decisions surface MUST classify each entry's actor kind from confidence_source when no structured actor object is present, in both the row table and the autonomy-split summary. Human and agent decisions must be counted and iconed correctly rather than defaulting every entry to agent.

#### Scenario: Split tile counts human and agent from confidence source

- **GIVEN** the ledger returns entries with confidence_source values but no structured actor object
- **WHEN** the autonomy-split tile computes its counts
- **THEN** entries with confidence_source autopilot count as agent and the rest count as human
- **AND** the tile shows non-zero percentages when both kinds are present

#### Scenario: A human decision renders a human icon

- **GIVEN** a decision row whose confidence_source is human
- **WHEN** the row renders its actor
- **THEN** it shows the human actor treatment, not the agent bot treatment
