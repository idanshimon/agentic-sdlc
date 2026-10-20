## ADDED Requirements

### Requirement: DM-01 Typed judgment contract
The decision router MUST identify question/schema/options, evidence references, model/provider version, response and abstention/error state for bounded model judgments; it must not invent model explanations or calibrated correctness.

#### Scenario: DM-01-01
- **WHEN** A typed model returns scores without a rationale
- **THEN** the record preserves those scores and any separately generated explanation is attributed to its own producer

#### Scenario: DM-01-02
- **WHEN** No supported model route is configured
- **THEN** the task uses an explicitly supported alternative or becomes unsupported, without hidden inference

### Requirement: DM-02 Authority separate from model output
The system MUST derive permission from authenticated identity, applicable policy, target and independent evidence rather than decision-model probability, generated confidence or recalled instructions.

#### Scenario: DM-02-01
- **WHEN** The model confidently recommends a policy-prohibited production action
- **THEN** authorization refuses the action regardless of model score

#### Scenario: DM-02-02
- **WHEN** A structured authoritative fact resolves the question
- **THEN** the system uses the fact without requiring a redundant model judgment

### Requirement: DM-03 Recognition and discovery distinction
The design MUST support known-category recognition separately from optional budgeted open-ended investigation; unknown findings remain investigable without being presented as verified harm.

#### Scenario: DM-03-01
- **WHEN** An investigation identifies a concern outside every current failure category
- **THEN** the concern can be recorded with evidence and proposed significance without forcing a known label

#### Scenario: DM-03-02
- **WHEN** The discovery module is disabled
- **THEN** no discovery schedule or inference starts and known-failure repair remains usable

### Requirement: DM-04 Independent routing evaluation
The router MUST qualify candidate rules and model routes on held-out comparable SDLC cases with errors, abstention, false permission, latency, coverage and cost reported separately; a candidate must not be its sole outcome judge.

#### Scenario: DM-04-01
- **WHEN** A model has a confidently wrong high-risk recommendation
- **THEN** aggregate success cannot hide the unsafe case and its action authority remains policy-controlled

#### Scenario: DM-04-02
- **WHEN** A provider arm was not executed
- **THEN** the comparison marks it not measured rather than assigning zero quality

