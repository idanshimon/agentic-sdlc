# Spec delta: integrations-plane

## ADDED Requirements

### Requirement: The integrations registry is opt-in and fails safe when absent

The orchestrator MUST load an authorable `integrations.yaml` describing the external
systems this instance is wired to, using the configuration-plane loader posture: an
explicit env path first, then deploy locations, and NEVER the repository's `.example`
template. When no registry is present the instance MUST remain fully operational in
bootstrap mode, with every integration surface reporting `unconfigured`.

#### Scenario: No registry present leaves pipeline behaviour unchanged

- **GIVEN** no `integrations.yaml` exists at any candidate path
- **WHEN** the orchestrator starts and a run is submitted
- **THEN** the run executes exactly as it would without this capability
- **AND** `GET /api/integrations` returns an empty registry with `loaded: false`

#### Scenario: The repository template is never auto-discovered

- **GIVEN** the repository contains `config/integrations.yaml.example`
- **WHEN** the loader computes its candidate paths
- **THEN** the `.example` template is not among them
- **AND** a load from a scratch working directory reports the registry as not loaded

#### Scenario: A malformed registry degrades loudly rather than half-applying

- **GIVEN** `integrations.yaml` is present but structurally invalid
- **WHEN** the loader runs
- **THEN** the registry reports as not loaded with an error reason
- **AND** no partially parsed integration is exposed as configured

### Requirement: Integration credentials are referenced, never stored or returned

An integration entry MUST name its credential by environment/secret reference only. The
registry MUST NOT contain credential material, and no API response MUST ever include a
token, key, or connection string.

#### Scenario: Credential presence is reported without disclosure

- **GIVEN** an integration declares `token_env: DELIVER_GH_TOKEN`
- **AND** that environment variable holds a value
- **WHEN** an operator reads `GET /api/integrations`
- **THEN** the entry reports `credential_present: true`
- **AND** the response body contains no substring of the credential value

#### Scenario: A credential embedded in the registry is refused

- **GIVEN** an `integrations.yaml` entry carries an inline `token` value
- **WHEN** the loader validates the registry
- **THEN** the entry is refused with a validation error naming the offending field
- **AND** the refusal is logged without echoing the value

### Requirement: Integration status is honest about what was actually verified

Each integration MUST report a status of `unconfigured`, `configured`, `verified`, or
`failing`. `verified` MUST only be reachable through an actual successful read-only probe.
A probe that cannot be executed MUST NOT produce `verified`.

#### Scenario: Declared but unprobed is configured, not verified

- **GIVEN** an integration is fully declared with a present credential
- **AND** no reachability probe has been run
- **WHEN** the operator reads its status
- **THEN** the status is `configured`
- **AND** the response states that reachability has not been verified

#### Scenario: A failed probe surfaces the failure

- **GIVEN** an integration whose endpoint rejects the probe
- **WHEN** the operator runs `POST /api/integrations/{id}/test`
- **THEN** the integration status becomes `failing` with a reason
- **AND** the reason does not include credential material

#### Scenario: A probe that cannot run returns unknown

- **GIVEN** an integration whose provider has no implemented probe
- **WHEN** the operator runs its test
- **THEN** the result is `unknown` with an explanation
- **AND** the stored status is not upgraded to `verified`

### Requirement: A run may carry planning work-item provenance

The run intake MUST accept optional `source_system` and `source_ref` fields identifying
the planning work item (idea, epic, story, or task) the PRD came from. When supplied, the
orchestrator MUST normalize them into a work-item reference on the run and stamp that
reference onto every ledger entry the run writes, so the audit chain extends one hop
upstream of the pipeline.

#### Scenario: Provenance flows from intake to every ledger entry

- **GIVEN** a run is submitted with a planning system and a work-item reference
- **WHEN** the pipeline writes stage decisions to the ledger
- **THEN** each entry carries the same work-item reference
- **AND** an operator can retrieve every decision caused by that work item

#### Scenario: Provenance is optional and non-blocking

- **GIVEN** a run is submitted with no provenance fields
- **WHEN** the pipeline runs
- **THEN** the run completes normally
- **AND** its ledger entries carry a null work-item reference

#### Scenario: Unverified provenance is recorded as a claim

- **GIVEN** a run declares a work item in a planning system that is not configured
- **WHEN** the reference is recorded
- **THEN** it is marked as `claimed` rather than `verified`
- **AND** the surface never presents an unfetched reference as validated

#### Scenario: An unresolvable reference does not fail the run

- **GIVEN** a configured planning integration that cannot resolve the supplied reference
- **WHEN** the run is submitted
- **THEN** the run proceeds with the reference marked unverified and a recorded reason
- **AND** the pipeline does not fail on planning-system unavailability

### Requirement: Planning-tracker integrations are provider-pluggable behind one record shape

The planning-tracker integration MUST expose a single normalized work-item shape — stable
id, item type, title, body usable as PRD input, and a URL — so that adding a provider does
not change any consumer of the shape.

#### Scenario: A new provider requires no consumer change

- **GIVEN** a planning-tracker provider is added to the registry
- **WHEN** a work item is resolved through it
- **THEN** it is returned in the same normalized shape as every other provider
- **AND** the ledger, run model, and settings surface are unmodified by the addition

#### Scenario: An unknown provider is refused at load

- **GIVEN** a registry entry names a planning provider the instance does not implement
- **WHEN** the registry loads
- **THEN** the entry is refused with a validation error naming the unknown provider
- **AND** other well-formed entries still load

### Requirement: This capability performs no writes to external planning systems

The integrations plane MUST be read-only toward planning systems in this capability. No
work item may be created, modified, transitioned, or closed.

#### Scenario: No write path exists

- **GIVEN** an operator inspects the planning-tracker integration surface
- **WHEN** they enumerate the available actions
- **THEN** only read and reachability-probe actions are offered
- **AND** no endpoint accepts a work-item mutation

### Requirement: An aggregated settings read composes existing configuration without a new source of truth

`GET /api/config/settings` MUST return the instance's enterprise posture by composing the
already-loaded configuration objects — organization model, autonomy matrix, model policy,
standards pins, hard-gate floor, repo autonomy — plus the integrations registry. Each
section MUST declare whether it is in bootstrap or activated state, and whether it is
editable through the API or governed by pull request only.

#### Scenario: Every section declares its activation state

- **GIVEN** some configuration objects are activated and others are not
- **WHEN** an operator reads the aggregated settings
- **THEN** each section reports `bootstrap` or `activated`
- **AND** each section reports whether it is editable via the API or governed by PR

#### Scenario: The aggregate never disagrees with the individual reads

- **GIVEN** an operator reads the aggregated settings and the individual configuration endpoints
- **WHEN** the values are compared
- **THEN** they are derived from the same loaded objects and agree

#### Scenario: One unavailable section does not fail the whole read

- **GIVEN** one configuration section raises while loading
- **WHEN** the aggregated read runs
- **THEN** the remaining sections are returned
- **AND** the failing section is reported with an error status rather than omitted silently

### Requirement: Governance controls are read-only on the settings surface

The hard-gate class floor, PHI-locked bundle rules, and invariant ambiguity classes MUST
be presented as read-only on every settings surface, with an explicit statement that
changing them requires a standards-change pull request.

#### Scenario: The floor cannot be relaxed from settings

- **GIVEN** an operator views the governance section
- **WHEN** they attempt to modify a hard-gate class or a PHI-locked rule
- **THEN** no API path accepts the modification
- **AND** the surface states that the change requires a standards-change pull request
