# Spec delta: adopt-github-native-execution-substrate / ledger

## ADDED Requirements

### Requirement: The ledger MUST persist the alternatives weighed, not only the selection

A `LedgerEntry` representing a resolved ambiguity card MUST carry `rejected_options`, an array of
every `ResolutionOption` presented to the decider that was not selected. Each element MUST retain
the option's `resolution` text and its rationale.

The selected option remains recorded via `resolution_text` and `option_index`. `rejected_options`
MUST be empty only when the card genuinely presented a single option.

This closes the audit question "why not the other option", which the current schema cannot answer.

#### Scenario: a multi-option card persists its rejected alternatives

- **GIVEN** an `AmbiguityCard` with three `ResolutionOption` entries
- **AND** an operator resolves it by selecting `option_index: 1`
- **WHEN** the orchestrator writes the resulting `LedgerEntry`
- **THEN** `resolution_text` MUST equal the text of option 1
- **AND** `rejected_options` MUST contain exactly the two unselected options
- **AND** each rejected option MUST retain its resolution text

#### Scenario: rejected alternatives survive a durable round trip

- **GIVEN** a `LedgerEntry` with two `rejected_options` has been written
- **WHEN** the entry is read back through the Cosmos-backed ledger client
- **THEN** `rejected_options` MUST be present and equal to what was written

#### Scenario: a single-option card is not falsified

- **GIVEN** an `AmbiguityCard` with exactly one `ResolutionOption`
- **WHEN** the decision is written
- **THEN** `rejected_options` MUST be an empty array
- **AND** the entry MUST NOT be treated as missing data by validation

### Requirement: Decision confidence MUST be recorded and MUST NOT be a gating authority

`decision_confidence` MUST be recorded as evidence on a decision entry and MUST NOT participate
in gate evaluation.

A `LedgerEntry` MAY carry `decision_confidence`, a float in `[0.0, 1.0]` expressing the agent's
confidence in a proposed resolution. No configuration value, environment
variable, or request field may make a sufficiently high confidence bypass a hard-gated ambiguity
class. Gating is determined by classification (`ambiguity_class` against `HARD_GATE_CLASSES`) and
by autonomy posture — never by confidence.

#### Scenario: confidence is recorded on an autopiloted decision

- **GIVEN** a decision the pipeline resolves on autopilot with model confidence 0.94
- **WHEN** the `LedgerEntry` is written
- **THEN** `decision_confidence` MUST equal 0.94
- **AND** `autonomy_ref` MUST still record why the decision was autopiloted

#### Scenario: maximum confidence does not clear an invariant class

- **GIVEN** an `AmbiguityCard` whose `ambiguity_class` is `phi-classification`
- **AND** a proposed resolution with `decision_confidence: 1.0`
- **WHEN** the pipeline evaluates whether the card may be auto-resolved
- **THEN** the card MUST remain gated
- **AND** a human decision MUST be required before the run proceeds

### Requirement: Every gate-opening entry MUST carry a typed gate reason

A `LedgerEntry` written when a gate opens MUST carry `gate_reason`, drawn from the closed set:
`invariant_class`, `autonomy_tier`, `low_precedent`, `budget_exceeded`, `verification_failed`,
`stalled`, `operator_requested`.

`gate_reason` is a typed, queryable classification. It complements `autonomy_ref`, which carries
the specific rule reference, and MUST NOT replace it.

#### Scenario: a PHI card gates with the invariant reason

- **GIVEN** a card whose `ambiguity_class` is `phi-classification`
- **WHEN** the resolver gate opens for that card
- **THEN** the entry's `gate_reason` MUST be `invariant_class`
- **AND** `autonomy_ref` MUST still be populated

#### Scenario: exhausting the run budget gates with a distinct reason

- **GIVEN** a run that reaches its configured maximum stage retries
- **WHEN** the run halts for human attention
- **THEN** `gate_reason` MUST be `budget_exceeded`
- **AND** the entry MUST NOT report an unclassified failure

#### Scenario: gate reason is queryable across runs

- **WHEN** the compliance query is filtered by `gate_reason = invariant_class`
- **THEN** the result MUST contain every invariant-gated decision for the team
- **AND** MUST exclude decisions gated for other reasons

### Requirement: Existing ledger entries MUST remain valid without the new fields

`rejected_options`, `decision_confidence`, and `gate_reason` MUST default to empty/null on
deserialization of entries written before this change. Historical entries MUST NOT be mutated to
populate them.

#### Scenario: a pre-existing entry deserializes

- **GIVEN** a persisted ledger entry written before this change
- **WHEN** it is read through the current `LedgerEntry` model
- **THEN** deserialization MUST succeed
- **AND** `rejected_options` MUST be an empty array
- **AND** `gate_reason` and `decision_confidence` MUST be null

## MODIFIED Requirements

### Requirement: Bundle citation MUST be complete and MUST NOT be hardcoded

Every stage that writes a decision entry MUST stamp `bundle_refs`. The literal
`bundle_refs=["architect/v0.1.0/SERVICE-CONTAINERIZED-001"]` currently present in the delivery
stage MUST be removed.

Where a specific rule was evaluated to reach the decision, `bundle_refs` MUST name that rule at
`[dept/version/rule-id]` precision. Where only the stage's subscription set is known, the entry
MUST record the subscription set and MUST NOT imply that a specific rule was evaluated.

#### Scenario: the hardcoded citation is gone

- **WHEN** the repository is searched for the literal rule ID `SERVICE-CONTAINERIZED-001` outside
  the standards bundles themselves
- **THEN** there MUST be no occurrence in stage implementation code

#### Scenario: every stage stamps bundle references

- **GIVEN** a completed run that executed all pipeline stages
- **WHEN** the run's ledger entries are read back
- **THEN** every stage-decision entry MUST have a non-empty `bundle_refs`

#### Scenario: subscription-set attribution is not overclaimed

- **GIVEN** a stage decision where no individual rule was evaluated
- **WHEN** the entry is written
- **THEN** `bundle_refs` MUST record the stage's subscription set
- **AND** the entry MUST be distinguishable from one citing a specifically evaluated rule
