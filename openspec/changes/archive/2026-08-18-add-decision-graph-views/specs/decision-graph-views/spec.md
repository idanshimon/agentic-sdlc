# Spec delta: decision graph views

## ADDED Requirements

### Requirement: The ledger MUST offer graph lenses that read from the same ledger and never write

The Decision Ledger UI MUST provide read-only graph visualizations derived from
the same ledger query that backs the `/decisions` table. These views MUST NOT
write to the Decision Ledger, modify standards bundles, or mutate any run. They
are a reading layer, identical in write-posture to the in-UI AgentAssistant.

The existing `/decisions` table and activity feed MUST remain unchanged; the
graph views are additive routes.

#### Scenario: graph views perform no writes

- **GIVEN** an operator opens any decision graph view
- **WHEN** the view renders and the operator clicks nodes
- **THEN** no ledger write, bundle edit, or run mutation MAY occur
- **AND** the only navigation effect MAY be a drill-through to an existing record

#### Scenario: graph reads the same ledger as the table

- **GIVEN** the `/decisions` table shows N decisions for the authed team
- **WHEN** the operator opens the Decision Map
- **THEN** the map MUST be derived from the same ledger read
- **AND** MUST auto-refresh on the same polling interval as the table

### Requirement: Every graph node MUST drill through to its full audited record

Each node that represents a ledger entry MUST be clickable and MUST navigate to
that entry's full record at `/decisions#decision-<id>`, reusing the existing
drill-down anchor contract. A node that cannot reach its record is a defect.

#### Scenario: node click opens the record

- **GIVEN** a decision node in any graph view
- **WHEN** the operator clicks it
- **THEN** the app MUST navigate to `/decisions#decision-<entry_id>`
- **AND** the decisions surface MUST expand and scroll that entry into view

### Requirement: The learning loop MUST be visually distinct and rendered as a directed lineage

The system MUST render the `reuses` relationship — an autopilot decision
auto-resolved from a prior precedent (`precedent_refs` / `precedent_id`) — as a
directed edge distinct from structural edges (citation, run-grouping,
class-clustering). A dedicated lineage view MUST lay these edges out as a
deterministic left→right DAG so the human→agent teaching loop reads as a
timeline, with human-precedent roots on the left.

#### Scenario: reuse edge is distinguishable from structural edges

- **GIVEN** a decision that reused a precedent and another that merely cites a bundle
- **WHEN** both are rendered on the Decision Map
- **THEN** the reuse edge MUST be visually distinct (color/weight/animation) from the citation edge

#### Scenario: lineage reads left to right from a human root

- **GIVEN** a human precedent that two later autopilot decisions reused
- **WHEN** the operator opens the Precedent Lineage view
- **THEN** the human precedent MUST appear as a root on the left
- **AND** each reusing decision MUST appear to its right connected by a reuse edge

### Requirement: The Decision Map MUST stay legible under load

The cross-run map MUST provide controls that let the reader reduce the rendered
graph to answer a question rather than render an undifferentiated hairball. At
minimum it MUST support toggling edge families independently and focusing on
flagged decisions plus their immediate neighborhood. Layout MUST be
deterministic so an exported screenshot is reproducible for audit.

#### Scenario: operator focuses on flagged decisions

- **GIVEN** a map with many decisions of which one is flagged
- **WHEN** the operator enables the flag-focus control
- **THEN** the view MUST retain the flagged decision and its immediate neighbors
- **AND** MUST drop unrelated nodes from the render

#### Scenario: deterministic layout

- **GIVEN** the same set of ledger entries
- **WHEN** a graph view is rendered twice
- **THEN** node positions MUST be identical across renders
