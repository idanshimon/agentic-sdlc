# Capability: stop conditions on ambiguity cards

## ADDED Requirements

### Requirement: A detectable stop condition MUST name its enforcing mechanism

A stop condition marked detectable MUST name the mechanism that evaluates it.

A stop condition that claims the pipeline can evaluate it, without naming what
performs that evaluation, asserts a control that does not exist. This mirrors
`requires_mechanism` on BLOCK-severity bundle rules.

#### Scenario: detectable condition declares a mechanism
- **WHEN** a stop condition is emitted with `detectable: true`
- **THEN** it MUST carry a non-empty `mechanism` naming the deterministic check that evaluates it
- **AND** a card carrying a `detectable: true` condition with an empty `mechanism` MUST be rejected at card-build time

#### Scenario: undetectable condition is labelled advisory
- **WHEN** a stop condition is emitted with `detectable: false`
- **THEN** it MUST be rendered as advisory in every UI surface that displays it
- **AND** it MUST NOT be counted as a control in any compliance or coverage view

#### Scenario: a model is not a mechanism
- **WHEN** a stop condition names an LLM judgement as its `mechanism`
- **THEN** the condition MUST be treated as `detectable: false`
- **AND** the pipeline MUST NOT report it as enforced

### Requirement: A breached stop condition MUST gate to a human

A breached stop condition MUST gate to a human.

Stop conditions narrow autonomy. They never widen it.

#### Scenario: breach overrides earned autonomy
- **WHEN** a card's stop condition is breached
- **AND** that card's ambiguity class has earned autopilot autonomy
- **THEN** the card MUST gate to a human regardless of earned autonomy
- **AND** the gate reason MUST cite the breached condition

#### Scenario: stop conditions cannot unlock an invariant
- **WHEN** a card belongs to an invariant class (e.g. `phi-classification`)
- **AND** its stop conditions are all satisfied
- **THEN** the card MUST still gate to a human
- **AND** satisfied conditions MUST NOT be treated as evidence for promotion

#### Scenario: a breach at a downstream stage fails that stage
- **WHEN** a detectable condition is breached by an artifact produced at architect or codegen
- **THEN** that stage MUST fail
- **AND** the failure message MUST cite the breached condition

### Requirement: Declared and evaluated conditions MUST be recorded distinctly

Declared and evaluated conditions MUST be recorded distinctly.

An unevaluated condition is not a passed condition. Conflating the two would let
an undetectable boundary read as a satisfied one.

#### Scenario: the ledger separates declared from evaluated
- **WHEN** a card with stop conditions is resolved
- **THEN** the ledger entry MUST record which conditions were declared and which were actually evaluated
- **AND** conditions that were not evaluated MUST NOT be recorded as satisfied

#### Scenario: absence of conditions is not compliance
- **WHEN** a card carries zero stop conditions
- **THEN** the card MUST NOT be reported as having satisfied its boundaries
- **AND** compliance views MUST distinguish "no conditions declared" from "all conditions satisfied"

### Requirement: Stop conditions MUST be additive to existing cards

Stop conditions MUST be additive to existing cards.

#### Scenario: cards without stop conditions keep working
- **WHEN** an existing card carries no `stop_conditions` field
- **THEN** it MUST resolve exactly as it did before this change
- **AND** no default condition may be synthesised on its behalf