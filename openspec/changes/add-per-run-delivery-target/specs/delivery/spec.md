# Delivery target

## ADDED Requirements

### Requirement: Delivery target MUST be declared configuration, not an implicit attribute

The orchestrator MUST declare `github_default_target_repo` in its configuration
model. Resolution MUST NOT depend on an attribute that may be absent at runtime.

A missing target is a configuration error the operator can fix, and it MUST
surface at run creation — before expensive work is performed — not at the
deliver stage after codegen and review have already run.

#### Scenario: a team with no override falls back to the declared default

- **WHEN** a run is created for a team with no `delivery_overrides` entry
- **THEN** the target resolves to the declared `github_default_target_repo`
- **AND** the run proceeds normally

#### Scenario: no target resolves anywhere

- **WHEN** a run is created for a team with no override and no configured default
- **THEN** run creation fails with an error naming the team, the resolution order
  attempted, and the configuration key to set
- **AND** no pipeline stage executes
- **AND** the failure is NOT an `AttributeError` raised at the deliver stage

#### Scenario: a per-team override continues to win

- **WHEN** a team has `delivery_overrides[team].target_repo` set
- **THEN** that value is used in preference to the configured default

### Requirement: The delivery destination MUST be a queryable fact

The delivered ledger entry MUST carry `target_repo` as a typed field. Recording
it only inside the `rationale` prose string is insufficient: an auditor MUST be
able to answer "which runs delivered to repository X" by query rather than by
string-matching narrative text.

This mirrors the rule already enforced for bundle citations — a fact the system
knows MUST be recorded as a fact, not as a sentence.

#### Scenario: a delivered entry records its destination

- **WHEN** the deliver stage opens a pull request against a target repository
- **THEN** the delivered ledger entry carries `target_repo` as a typed field
- **AND** the value equals the repository the pull request was opened against

#### Scenario: delivery destination is queryable

- **WHEN** an auditor queries the ledger for entries with a given `target_repo`
- **THEN** every run delivered to that repository is returned
- **AND** no result depends on parsing the `rationale` string

#### Scenario: pre-existing entries remain valid

- **WHEN** a ledger entry written before this change is read
- **THEN** it parses successfully
- **AND** its delivery destination is reported as unknown
- **AND** it is NOT reported as an empty-string destination, which would be
  indistinguishable from a delivery that recorded no target

#### Scenario: the human-readable rationale is retained

- **WHEN** a delivered entry is written
- **THEN** `rationale` still describes the delivery in prose for a human reader
- **AND** the typed field is the authoritative source for queries
