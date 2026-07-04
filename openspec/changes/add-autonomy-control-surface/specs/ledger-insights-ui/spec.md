# Spec delta: ledger-insights-ui — Autonomy Control surface

## ADDED Requirements

### Requirement: Autonomy page derives all metrics from the shared ledger entries

The Autonomy page MUST compute every displayed number from the same `useDecisions()` entries list the Decisions page reads, with no separate API rollup. This guarantees the teaching-loop counts, per-class ladder, and split can never disagree with the Decisions table.

#### Scenario: Numbers match the Decisions page

- **GIVEN** the ledger holds a set of stage decisions for the current team
- **WHEN** the operator opens `/autonomy` and `/decisions`
- **THEN** the agent/human split on both pages is computed from the same entries
- **AND** the Autonomy page issues no additional decision-aggregation endpoint call beyond the shared `useDecisions()` query

#### Scenario: Empty ledger renders a guiding empty state

- **GIVEN** the ledger has zero stage decisions
- **WHEN** the operator opens `/autonomy`
- **THEN** the ladder area shows an empty state inviting the operator to run the pipeline and resolve a gate
- **AND** the page does not error or render NaN metrics

### Requirement: The teaching loop visualizes human-taught precedent reused by the agent

The teaching-loop hero MUST render the counts produced by `buildLineageIndex()` — human-taught precedents and the later autopilot decisions that reused them — and MUST state the autonomy-earned denominator explicitly. This makes "how the agent improves" a first-class, auditable story rather than an implied one.

#### Scenario: Loop shows a closed teaching cycle

- **GIVEN** a human swap set a precedent for an ambiguity bucket
- **AND** a later hybrid run auto-resolved the same bucket from that precedent
- **WHEN** the operator opens `/autonomy`
- **THEN** the hero shows a non-zero Taught count and a non-zero Agent-reuses count
- **AND** the autonomy-earned figure states the count of auto-resolved decisions over the total decision count

#### Scenario: Autonomy-earned percentage is honest about its base

- **GIVEN** the hero displays an autonomy-earned percentage
- **WHEN** the operator reads the supporting subtitle
- **THEN** the subtitle names the numerator (reused decisions) and the denominator (total decisions)

### Requirement: Every ambiguity class is placed on a four-rung autonomy ladder

The ladder MUST place each ambiguity class on exactly one rung of `floor → learning → trusted → autonomous`, derived from its precedent count and autonomy percentage. This gives the operator a per-class view of where trust has and has not been earned.

#### Scenario: A learning class with reuse climbs off the first rung

- **GIVEN** a non-floor class has at least one human-taught precedent and one autopilot reuse
- **WHEN** the ladder renders that class
- **THEN** the class sits on the trusted or autonomous rung rather than learning
- **AND** its autonomous-percentage metric is greater than zero

#### Scenario: A class with no precedent and no autopilot stays at learning

- **GIVEN** a non-floor class has only human decisions and no precedent
- **WHEN** the ladder renders that class
- **THEN** the class sits on the learning rung

### Requirement: Floor classes are pinned and never shown as auto-resolvable

The Autonomy page MUST pin every floor class to rung zero and render it as locked human-only, regardless of how many decisions it accumulates. PHI and auth classes can never appear to have earned autonomy.

#### Scenario: PHI and auth render locked at the floor

- **GIVEN** the floor set contains `phi-classification` and `auth-policy`
- **WHEN** the ladder renders those classes
- **THEN** each shows a lock indicator and the human-only floor rung
- **AND** each shows a zero-percent autonomous metric even if it has many human decisions

### Requirement: The locked floor is read from the live orchestrator config

The Autonomy page MUST obtain the floor set from the `/api/config/hard-gate-classes` proxy rather than a UI constant, so the locked classes always reflect the orchestrator's live `HARD_GATE_CLASSES`. The proxy MUST fail safe to the default floor so the page still renders when the orchestrator is unreachable.

#### Scenario: Floor reflects an orchestrator-extended hard-gate set

- **GIVEN** the orchestrator reports a hard-gate set beyond the two defaults
- **WHEN** the page fetches the floor
- **THEN** the additional class renders locked in both the ladder and the envelope

#### Scenario: Orchestrator unreachable falls back to the default floor

- **GIVEN** the orchestrator config endpoint is unreachable
- **WHEN** the proxy responds
- **THEN** it returns the default floor `auth-policy` and `phi-classification`
- **AND** the page renders those as locked without erroring

### Requirement: The envelope is presented as governed, not a UI toggle

The envelope panel MUST state that changing the floor is a standards-change proposal requiring reviewer approval, and MUST NOT expose a control that relaxes a floor class from the UI. The page tells the true governance posture: the floor is changed through review, not switched.

#### Scenario: No UI affordance relaxes a floor class

- **GIVEN** the operator views the envelope panel
- **WHEN** the operator looks for a way to make a floor class auto-resolvable
- **THEN** no toggle or button that relaxes a floor class is present
- **AND** the panel states that changing the floor requires a standards-change proposal
