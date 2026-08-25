# Capability: replay scoring (disagreement metric)

## ADDED Requirements

### Requirement: Replay MUST NOT write to the decision ledger

Replay is a read-only projection over existing entries. Scoring MUST NOT create,
modify, or delete ledger rows.

#### Scenario: scoring leaves the substrate untouched
- **WHEN** a replay is scored over a set of ledger entries
- **THEN** those entries MUST be byte-identical afterwards, and no write tool is invoked

#### Scenario: an unpopulated accuracy_score is not backfilled
- **WHEN** entries carry `accuracy_score: 0.0` because nothing ever computed it
- **THEN** replay MUST report them as `UNSCORED` and MUST NOT write a score back to the ledger

### Requirement: The metric MUST refuse to report on insufficient evidence

The metric MUST report no rate when the sample count is below the configured
minimum, rather than computing one from too few samples.

A rate computed from too few samples is not a weak signal, it is a false one.

#### Scenario: below the sample floor
- **WHEN** a class has fewer scored samples than the policy minimum
- **THEN** the reported rate MUST be null and the verdict MUST be `INSUFFICIENT`

#### Scenario: unknown outcomes are excluded, never assumed to agree
- **WHEN** a case has no known proposal or was never scored
- **THEN** it MUST NOT increment agreements, and the class MUST report `UNSCORED` when no case was scored

#### Scenario: comparison does not fuzzy-match into agreement
- **WHEN** a proposal differs from the human ruling by more than whitespace or case
- **THEN** it MUST be counted as a disagreement

### Requirement: Autonomy thresholds MUST come from the pinned bundle

Thresholds are governance. They MUST NOT be hardcoded in application code.

#### Scenario: policy is derived from bundle rules
- **WHEN** a bundle supplies `REPLAY-MIN-SAMPLES` or `REPLAY-CEILING-*` rules with a `defaults:` block
- **THEN** replay MUST use those values in place of built-in fallbacks

#### Scenario: per-class ceiling overrides the global ceiling
- **WHEN** a rule declares a `disagreement_ceiling` for a specific `ambiguity_class`
- **THEN** that class MUST be judged by its own ceiling and other classes by the global one

#### Scenario: malformed policy values fall back rather than crash
- **WHEN** a bundle supplies a non-numeric threshold
- **THEN** replay MUST retain the conservative built-in default and continue

#### Scenario: unconfigured systems under-grant autonomy
- **WHEN** no policy is supplied at all
- **THEN** the built-in fallbacks MUST be at least as strict as `min_samples: 5` and `disagreement_ceiling: 0.10`

### Requirement: Invariant classes MUST never earn autonomy

Invariant classes MUST never earn autonomy.

#### Scenario: a perfect score does not unlock an invariant
- **WHEN** a class in the invariant set scores zero disagreements over any number of samples
- **THEN** the verdict MUST be `INVARIANT — HUMAN ALWAYS`, never `AUTONOMY EARNED`

#### Scenario: enforcement invariants and scoring invariants cannot drift
- **WHEN** a bundle rule carries `phi_locked: true` with an `ambiguity_class`
- **THEN** that class MUST automatically be treated as an autonomy invariant with no separate declaration

### Requirement: Unsupervised failures MUST be isolated from gated ones

Unsupervised failures MUST be isolated from gated ones.

A wrong suggestion caught by a human is the system working as designed.

#### Scenario: gated disagreements do not count against autopilot
- **WHEN** a decision diverged from the human ruling but was gated rather than autopiloted
- **THEN** it MUST increment the overall disagreement count but MUST NOT increment autopilot disagreements

### Requirement: Precedent identity MUST key on `card_id`

Precedent identity MUST key on `card_id`.

#### Scenario: entries sharing a class-level hash are not treated as the same question
- **WHEN** two decisions share a `slot_value_hash` but have different `card_id` values
- **THEN** they MUST NOT be compared against one another as precedent and reuse

#### Scenario: a card with no human ruling yields no ground truth
- **WHEN** a card contains only autopilot decisions
- **THEN** it MUST produce no replay cases rather than treating an agent decision as truth