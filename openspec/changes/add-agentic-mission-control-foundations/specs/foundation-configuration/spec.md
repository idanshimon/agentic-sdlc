## ADDED Requirements

### Requirement: FC-01 Composable profiles and independent controls
The foundation MUST support schema-versioned starter profiles and independent capability, authority, governance, model, budget and presentation settings rather than one maturity or security slider.

#### Scenario: FC-01-01
- **WHEN** A team selects Simple plus stricter security and observe-only authority
- **THEN** the effective plan preserves that valid combination without forcing a full enterprise deployment

#### Scenario: FC-01-02
- **WHEN** A profile label is selected
- **THEN** the UI shows actual resolved features and authority rather than implying certification or automatic permission promotion

### Requirement: FC-02 Deterministic effective configuration
The resolver MUST apply authenticated platform/organization constraints before repository/task overrides, fill unspecified defaults from versioned profiles and expose value provenance plus a resolved digest.

#### Scenario: FC-02-01
- **WHEN** A repo override attempts to disable an organization-required gate
- **THEN** validation refuses the conflict and names the governing policy

#### Scenario: FC-02-02
- **WHEN** A permitted repo setting tightens a budget
- **THEN** the tighter value is resolved consistently by UI, worker and server validation

### Requirement: FC-03 Dependency resolved activation
Every optional module MUST declare dependencies, conflicts, permission/resource needs and readiness probes; resolution must reject cycles, unsupported combinations and missing mandatory dependencies without auto-granting access.

#### Scenario: FC-03-01
- **WHEN** A module is enabled without a needed permission
- **THEN** its state is blocked or enabled-unconfigured and bootstrap proposes the missing prerequisite without granting it

#### Scenario: FC-03-02
- **WHEN** Doctor, typed models and authored graphs are disabled
- **THEN** the minimal foundation runs with those workers, model hosts and render services absent, not merely hidden

### Requirement: FC-04 Enforced threshold semantics
Configurable thresholds MUST declare units/ranges, ownership, evidence meaning and failure posture; unsupported enforcement must remain unavailable/advisory and model confidence cannot override hard policy.

#### Scenario: FC-04-01
- **WHEN** A user supplies an invalid negative attempt limit or unknown threshold key
- **THEN** validation rejects the configuration before apply

#### Scenario: FC-04-02
- **WHEN** A model confidence threshold is lowered
- **THEN** that changes only its permitted judgment routing and cannot bypass protected action authorization

### Requirement: FC-05 Reproducible instruction bootstrap
Bootstrap MUST inspect the existing repo, preview artifacts/permissions/resources, stage instructions and workflows from pinned templates/effective config, validate them and require authorized apply without clobbering handwritten content.

#### Scenario: FC-05-01
- **WHEN** The same inputs are bootstrapped twice
- **THEN** managed output is idempotent and existing handwritten instructions remain unchanged

#### Scenario: FC-05-02
- **WHEN** A generated artifact conflicts with an unmanaged file
- **THEN** bootstrap stops with a reviewable conflict instead of overwriting it

#### Scenario: FC-05-03
- **WHEN** A selected module is unavailable on the installation
- **THEN** generated instructions do not promise tools or authority that cannot execute

### Requirement: FC-06 Safe configuration change and deactivation
Configuration changes MUST follow applicable authorization, stamp digests on affected decisions/actions, invalidate incompatible prior authority and drain/reconcile or explicitly cancel work before deactivation is declared complete.

#### Scenario: FC-06-01
- **WHEN** A feature is disabled with an accepted command still running
- **THEN** new dispatch stops, the command is reconciled and the UI does not claim that hiding the feature cancelled it

#### Scenario: FC-06-02
- **WHEN** A user changes only visualization visibility
- **THEN** underlying admission controls remain unchanged

### Requirement: FC-07 Minimum accountable foundation
The minimal profile MUST retain scoped identity, durable consequential-action receipts, bounded execution and truthful status while allowing optional rich ledger hosting, analytics, custom models and governance overlays to be omitted.

#### Scenario: FC-07-01
- **WHEN** A simple adopter does not provision Cosmos or committee workflows
- **THEN** the supported minimal receipt backend records actions without requiring those services

#### Scenario: FC-07-02
- **WHEN** The current project has mandatory bundle requirements
- **THEN** a preset cannot silently remove them; any adaptation requires explicit owning-spec and policy approval

