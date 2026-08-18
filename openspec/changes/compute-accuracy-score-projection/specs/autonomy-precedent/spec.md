# autonomy-precedent — read-time accuracy projection

## MODIFIED Requirements

### Requirement: Precedent accuracy MUST be computed at read time

The system MUST derive `accuracy_score` on a precedent entry from the recorded
agreement history for that entry's `(team_id, ambiguity_class)` group at the
moment the precedent is read, and MUST NOT persist the derived value to the
decision ledger.

The projection MUST reuse the existing replay scorer so that the autonomy gate
and the operator-facing replay report cannot disagree about the same history.

#### Scenario: History of full agreement yields a granting score

- **GIVEN** an ambiguity class with at least `min_samples` scored autopilot
  decisions, all matching the human ruling on the same card
- **WHEN** a precedent for that class is read
- **THEN** its `accuracy_score` is `1.0`
- **AND** a rule with `mode: autopilot_above_threshold` and a threshold at or
  below `1.0` grants autonomy

#### Scenario: Mixed history yields the true agreement rate

- **GIVEN** an ambiguity class with `min_samples` or more scored cases of which
  some disagree with the human ruling
- **WHEN** a precedent for that class is read
- **THEN** its `accuracy_score` equals agreements divided by scored cases
- **AND** the value MUST NOT be rounded upward or otherwise adjusted in the
  direction that favours granting autonomy

#### Scenario: Insufficient evidence gates

- **GIVEN** an ambiguity class with fewer than `min_samples` scored cases
- **WHEN** a precedent for that class is read
- **THEN** its `accuracy_score` is `0.0`
- **AND** the card is gated to a human rather than autopiloted

#### Scenario: Unscored history is not treated as agreement

- **GIVEN** historical entries for a class that carry no human ruling and are
  therefore unscored
- **WHEN** the projection is computed
- **THEN** those entries are excluded from the denominator
- **AND** they MUST NOT be counted as agreements

#### Scenario: An invariant class never grants autonomy

- **GIVEN** an ambiguity class marked invariant by the governing bundle
- **AND** a perfect agreement history for that class
- **WHEN** the autonomy decision is made
- **THEN** the card is gated regardless of the computed score

#### Scenario: A failed projection gates

- **GIVEN** the projection cannot be computed, for example because the history
  query fails
- **WHEN** a precedent is read
- **THEN** the resulting `accuracy_score` is `0.0` and the card is gated
- **AND** the failure is logged rather than silently swallowed

#### Scenario: The ledger is not modified

- **GIVEN** any precedent read that computes a projection
- **WHEN** the read completes
- **THEN** no decision-ledger entry is created, updated, or deleted as a result
