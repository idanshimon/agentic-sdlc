# Spec delta: add-graduated-autonomy-tier2 / resolver-gate

## ADDED Requirements

### Requirement: Hard-gated ambiguity classes MUST NOT be bulk/soft-approved

The system MUST reject any attempt to approve a hard-gated card via the bulk
("Approve all recommended") path. A hard-gated card MUST be decided
individually, with an explicit per-card operator action, on the record. The
hard-gate set defaults to `INVARIANT_CLASSES` (phi-classification, auth-policy)
and MAY be extended via the `HARD_GATE_CLASSES` env, but PHI and auth are an
immovable floor that the env can never remove. Enforcement MUST be server-side
and independent of the UI — a client that bypasses the UI filter MUST still be
refused.

#### Scenario: bulk approve on a PHI card is rejected server-side

- **GIVEN** a run paused at the resolver gate with a `phi-classification` card
- **WHEN** a client POSTs `/api/runs/{id}/approve` with `approval_path: "bulk"` for that card
- **THEN** the server MUST respond 409
- **AND** the response MUST explain the card is hard-gated and must be decided individually
- **AND** no decision MUST be persisted for that card

#### Scenario: individual approve on the same PHI card is allowed

- **GIVEN** the same run and PHI card
- **WHEN** a client POSTs `/api/runs/{id}/approve` with `approval_path: "individual"` for that card
- **THEN** the server MUST respond 200
- **AND** the decision MUST be persisted to the ledger under the operator's identity

#### Scenario: the env can extend but never shrink the hard-gate floor

- **GIVEN** `HARD_GATE_CLASSES="sla-binding"` is set
- **WHEN** the hard-gate set is resolved
- **THEN** it MUST contain `sla-binding`
- **AND** it MUST still contain `phi-classification` and `auth-policy`

### Requirement: Per-card decisions MUST give immediate on-page feedback

The system MUST reflect a per-card decision (accept, swap, or write-your-own) in
the gate UI immediately, without requiring a page reload. A decided card MUST be
visually distinct from an undecided one, and the operator MUST be able to see how
many cards remain to be decided.

#### Scenario: "Use this" locks the card and advances the counter

- **GIVEN** a resolver gate with 3 undecided gating cards
- **WHEN** the operator clicks "Use this" on a card's recommended option
- **THEN** that card MUST render a "Decided" state showing the chosen label
- **AND** a "1 of 3 decided" counter MUST be visible
- **AND** the card's option buttons MUST collapse to the decided summary with a "change" affordance

### Requirement: Operators MUST be able to edit a recommendation or write their own resolution

The resolver gate MUST let an operator submit a free-form resolution for a card
(editing the recommended text or writing entirely new text), recorded as a
`swap` decision. The submitted text MUST be persisted verbatim and MUST be
shaped as precedent so it can be matched on a later run for the same ambiguity.

#### Scenario: a written resolution is recorded as a precedent-shaped swap

- **GIVEN** a resolver gate card of class `data-retention` with slot_value_hash `H`
- **WHEN** the operator types a custom resolution and clicks "Use my version"
- **THEN** the server MUST persist a runtime ledger entry with `decision_kind: "swap"`, the verbatim text, `ambiguity_class: "data-retention"`, and `slot_value_hash: H`
- **AND** that entry MUST be precedent-eligible (no excluding runtime_kind)

### Requirement: Precedent matching MUST be stable across runs for the same ambiguity

The precedent key (`slot_value_hash`) MUST be derived from the stable semantic
identity of an ambiguity — its class and the PRD section it came from — NOT from
LLM-generated prose that varies run-to-run. `findPrecedent` MUST return a
matching precedent when one exists, and MUST NOT silently drop it due to a query
construction quirk.

#### Scenario: the same PRD produces the same slot key across runs

- **GIVEN** the same PRD is submitted twice
- **WHEN** the assessor produces a card of class `sla-binding` from the same PRD section in each run
- **THEN** both cards MUST carry the same `slot_value_hash`

#### Scenario: findPrecedent returns an existing matching precedent

- **GIVEN** a runtime ledger entry exists for (team `T`, class `K`, slot `S`, entry_type `runtime`)
- **WHEN** `findPrecedent(T, K, S)` is called
- **THEN** it MUST return that entry (or the most recent when several match)
- **AND** it MUST NOT return null while a matching row exists
