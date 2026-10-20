## ADDED Requirements

### Requirement: GV-01 One evidence projection
Graph and list views MUST share stable identities, authorized scope and source-grounded lifecycle data; relationships must expose provenance, freshness and known versus inferred status.

#### Scenario: GV-01-01
- **WHEN** A list and graph select the same task
- **THEN** both expose the same decision/status and exact source references

#### Scenario: GV-01-02
- **WHEN** Architecture is authored or inferred rather than observed live
- **THEN** the view labels its source and does not present it as verified deployed topology

### Requirement: GV-02 Archify and live graph boundary
The product MUST use pinned Content Creator/Archify output for optional authored explanations while keeping live operational projections and command authorization in first-party application code.

#### Scenario: GV-02-01
- **WHEN** A generated mission-control showcase has a local Approve interaction
- **THEN** it is not wired to repository authority and its synthetic data is not imported as telemetry

#### Scenario: GV-02-02
- **WHEN** The renderer is absent or authored graphs are disabled
- **THEN** the operational queue and decision workbench remain usable without a renderer runtime dependency

### Requirement: GV-03 Exploration interaction and render proof
Interactive graphs MUST provide explanation on selection, explicit semantic descent with Back/breadcrumbs, scoped deep links, readable relationships, keyboard/touch access and reduced-motion behavior.

#### Scenario: GV-03-01
- **WHEN** A user single-clicks a component
- **THEN** the explanation changes without an unexpected camera jump or action dispatch

#### Scenario: GV-03-02
- **WHEN** A release contains multiple graph views
- **THEN** each view and theme is rendered and exercised at its delivery size with label/arrow containment and source assertions

### Requirement: GV-04 Presentation isolation
Embedded artifacts MUST use sandbox/CSP and strict origin/message validation; they must receive no repository credentials and cannot issue privileged actions through selection or presentation messages.

#### Scenario: GV-04-01
- **WHEN** An iframe sends an approval-shaped postMessage
- **THEN** the host rejects it and no action is authorized

#### Scenario: GV-04-02
- **WHEN** A valid selection message names an out-of-scope record
- **THEN** server scope remains authoritative and the record is not disclosed

