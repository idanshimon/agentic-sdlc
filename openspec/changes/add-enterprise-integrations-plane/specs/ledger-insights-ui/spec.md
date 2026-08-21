# Spec delta: ledger-insights-ui — Enterprise Settings surface

## ADDED Requirements

### Requirement: The Settings surface renders the instance's enterprise posture in one place

The dashboard MUST provide a `/settings` surface that renders the aggregated enterprise
configuration — organization, integrations, autonomy, models, and governance — as tabbed
sections derived from the aggregated settings read.

#### Scenario: Every configuration section is reachable from one surface

- **GIVEN** an operator opens `/settings`
- **WHEN** the page renders
- **THEN** Organization, Integrations, Autonomy, Models, and Governance sections are each reachable
- **AND** each section shows whether it is in bootstrap or activated state

#### Scenario: Section selection is addressable

- **GIVEN** an operator selects a settings section
- **WHEN** the page state changes
- **THEN** the selected section is reflected in the URL so the view can be shared and restored

#### Scenario: The orchestrator being unreachable renders an error state, not an empty one

- **GIVEN** the orchestrator cannot be reached
- **WHEN** the settings page loads
- **THEN** an explicit error state is shown
- **AND** the page does not render an empty configuration that implies nothing is configured

### Requirement: The Integrations tab distinguishes declared from verified connections

The Integrations tab MUST render each external system with its provider, owning identity,
declared scopes, credential presence, and status, and MUST visually distinguish a merely
declared integration from one whose reachability was actually probed.

#### Scenario: Configured and verified are visually distinct

- **GIVEN** one integration is declared but never probed and another was probed successfully
- **WHEN** the operator views the Integrations tab
- **THEN** the two render with different status treatments
- **AND** the unprobed one is not presented as verified

#### Scenario: Testing an integration reports the real outcome

- **GIVEN** an operator triggers the reachability test for an integration
- **WHEN** the probe completes
- **THEN** the resulting status and its reason are rendered
- **AND** a failure is shown as a failure rather than being swallowed into an unchanged view

#### Scenario: No credential is ever rendered

- **GIVEN** an integration with a present credential
- **WHEN** its details are rendered or expanded
- **THEN** only credential presence and the reference name are shown
- **AND** no credential value appears anywhere in the surface

#### Scenario: An unconfigured registry guides the operator

- **GIVEN** no integrations registry is activated
- **WHEN** the operator opens the Integrations tab
- **THEN** a guiding empty state explains how to activate the registry
- **AND** the tab does not render as a broken or blank panel

### Requirement: The Governance tab presents immovable controls as locked

The Governance tab MUST render the hard-gate class floor, invariant ambiguity classes, and
PHI-locked bundle rules as read-only locked controls, with the statement that changing them
requires a standards-change pull request.

#### Scenario: Locked controls offer no edit affordance

- **GIVEN** an operator views the Governance tab
- **WHEN** they inspect the hard-gate floor and PHI-locked rules
- **THEN** the controls are rendered as locked with no edit affordance
- **AND** the governed-pull-request path is stated on the surface

### Requirement: A run's planning work item is visible in the run surface

When a run carries planning provenance, the run detail surface MUST display the source
system, the work-item reference, and whether that reference is claimed or verified, linking
out to the work item when a resolution template is configured.

#### Scenario: Provenance is shown with its verification state

- **GIVEN** a run submitted with a work-item reference
- **WHEN** an operator opens that run
- **THEN** the source system and reference are displayed
- **AND** the display states whether the reference is claimed or verified

#### Scenario: A run without provenance shows no provenance chrome

- **GIVEN** a run submitted without provenance
- **WHEN** an operator opens that run
- **THEN** no empty or placeholder provenance block is rendered
