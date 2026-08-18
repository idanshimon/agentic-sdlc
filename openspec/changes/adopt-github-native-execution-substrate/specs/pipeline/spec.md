# Spec delta: adopt-github-native-execution-substrate / pipeline

## ADDED Requirements

### Requirement: A run-scoped artifact store MUST carry inter-stage data

The pipeline MUST provide a run-scoped store for data passed between stages. Stages MUST write
named entries and read them by name rather than threading all intermediate data through the
stage payload.

Appends MUST be safe under concurrent writers so that parallel stage work can accumulate into one
named entry. The store MUST be scoped to a single run and MUST NOT persist beyond it; durable
knowledge belongs in the Decision Ledger.

#### Scenario: a stage hands off data through the store

- **GIVEN** the architect stage produces an architecture artifact
- **WHEN** the codegen stage begins
- **THEN** codegen MUST read the artifact from the run-scoped store by name
- **AND** the stage payload MUST NOT be required to carry the artifact body

#### Scenario: a large handoff no longer truncates

- **GIVEN** a stage output exceeding the prior stage-payload size limit
- **WHEN** the run proceeds to the next stage
- **THEN** the downstream stage MUST receive the complete output
- **AND** the run MUST NOT record a truncated payload

#### Scenario: concurrent appends do not lose data

- **GIVEN** two concurrent writers appending findings to one named entry
- **WHEN** both complete
- **THEN** the entry MUST contain the findings from both writers

#### Scenario: the store does not outlive the run

- **GIVEN** a completed run
- **WHEN** a subsequent run for the same team begins
- **THEN** the new run MUST NOT read the prior run's store entries

### Requirement: The pipeline MUST compute an accuracy signal for ledger decisions

`accuracy_score` MUST have a compute site. A scheduled retrospective MUST evaluate completed runs
and update the accuracy signal for the decisions it examines.

A schema field that is never populated MUST NOT be presented as a learning capability. This
requirement exists because `accuracy_score` is currently `0.0` on every live entry.

#### Scenario: the retrospective populates the accuracy signal

- **GIVEN** a set of completed runs eligible for retrospective
- **WHEN** the scheduled retrospective executes
- **THEN** at least one examined decision MUST have a non-zero `accuracy_score`
- **AND** the retrospective run that produced it MUST be identifiable from the record

#### Scenario: runs are sampled without recency bias

- **GIVEN** a window of completed runs since the last retrospective
- **WHEN** the retrospective selects runs to examine
- **THEN** selection MUST be randomised across the window
- **AND** MUST NOT be limited to the most recent runs

### Requirement: Durable lessons MUST earn promotion before influencing a run

A pattern observed in a single run MUST be recorded as tentative and MUST NOT be injected into any
agent prompt.

A tentative lesson MUST be promoted only when the same pattern recurs at the same stage on a
separate run. Contradicted lessons MUST be retired with a recorded reason.

#### Scenario: a single observation is not injected

- **GIVEN** a pattern observed in exactly one run
- **WHEN** a subsequent run executes the same stage
- **THEN** the tentative lesson MUST NOT appear in the agent's prompt

#### Scenario: recurrence at the same stage promotes the lesson

- **GIVEN** a tentative lesson from a run at the assessor stage
- **WHEN** the same pattern is observed at the assessor stage on a different run
- **THEN** the lesson MUST be promoted to active
- **AND** it MUST become eligible for injection

#### Scenario: recurrence at a different stage does not promote

- **GIVEN** a tentative lesson recorded at the assessor stage
- **WHEN** a similar pattern is observed at the codegen stage
- **THEN** the assessor lesson MUST remain tentative

#### Scenario: a contradicted lesson is retired with a reason

- **GIVEN** an active lesson contradicted by new evidence
- **WHEN** the retrospective processes that evidence
- **THEN** the lesson MUST be retired
- **AND** the retirement reason MUST be recorded

### Requirement: Lesson weighting MUST be asymmetric and MUST decay

A lesson observed to mislead MUST lose more weight than a helpful observation gains. A lesson
presented to an agent but not used MUST decay. Lessons below the archival floor MUST be archived
rather than injected.

A misleading lesson is more costly than a missing one, and the weighting MUST reflect that.

#### Scenario: a harmful outcome costs more than a helpful one gains

- **GIVEN** a lesson at a given weight
- **WHEN** it contributes to one helpful outcome and one harmful outcome
- **THEN** its resulting weight MUST be lower than its starting weight

#### Scenario: an unused lesson decays out

- **GIVEN** a lesson repeatedly presented but never used
- **WHEN** successive retrospectives run
- **THEN** its weight MUST decrease
- **AND** once below the archival floor it MUST NOT be injected

### Requirement: Durable lessons MUST be org-scoped ledger entries under existing governance

A promoted lesson MUST be written as a ledger entry keyed by `(ambiguity_class, slot_value_hash)`
— the key `find_precedent` already uses — so lessons apply across runs, stages, and teams within
the team partition.

Lessons MUST be append-only, attributed, and subject to the same PHI rules as any other write. A
lesson MUST NOT contain raw PHI.

#### Scenario: a lesson is reusable beyond its originating run

- **GIVEN** a promoted lesson for a given ambiguity class and slot value hash
- **WHEN** a different run encounters the same class and slot value hash
- **THEN** the lesson MUST be retrievable for that run

#### Scenario: a lesson containing PHI is blocked

- **GIVEN** a candidate lesson whose content would contain raw PHI
- **WHEN** the retrospective attempts to write it
- **THEN** the write MUST be blocked
- **AND** the block MUST be recorded

#### Scenario: promotion of an invariant-class lesson requires endorsement

- **GIVEN** a lesson whose ambiguity class is in `INVARIANT_CLASSES`
- **WHEN** it becomes eligible for promotion
- **THEN** it MUST require human endorsement before first injection
