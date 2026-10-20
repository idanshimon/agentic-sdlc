## ADDED Requirements

### Requirement: GH-01 Scoped connection and capability inventory
The connector MUST discover the actual installation, selected repositories, permissions, policy limits and supported agent features before enabling actions; it must not silently broaden installation access.

#### Scenario: GH-01-01
- **WHEN** The installation can read PRs but cannot dispatch an agent
- **THEN** read-only evidence remains available and dispatch is disabled with its exact missing capability

#### Scenario: GH-01-02
- **WHEN** An installation is revoked
- **THEN** new commands are denied and in-flight work is reconciled without exposing credentials

### Requirement: GH-02 Verified event and evidence ingestion
The connector MUST authenticate event delivery, deduplicate stable event identities, preserve source/freshness/commit references and support backfill or polling reconciliation for missing or reordered events.

#### Scenario: GH-02-01
- **WHEN** A PR update event is repeated and a later check event arrives first
- **THEN** one coherent current projection results without duplicate repair commands

#### Scenario: GH-02-02
- **WHEN** The API returns rate limiting or permission denial
- **THEN** the system uses bounded retry where appropriate and exposes degraded coverage, never an empty success

### Requirement: GH-03 Authorized external commands
The connector MUST execute external writes only from a current authorized action record, reconcile the exact target afterward and distinguish requested, accepted, observed and failed outcomes.

#### Scenario: GH-03-01
- **WHEN** A create-PR response is lost after GitHub accepted the request
- **THEN** reconciliation identifies the existing PR before another creation is attempted

#### Scenario: GH-03-02
- **WHEN** A forged report contains instructions to merge
- **THEN** the report remains untrusted evidence and cannot create merge authority

### Requirement: GH-04 Actual admission enforcement
The integration MUST verify required checks, trusted publishing identity, bypass posture and stale-evidence behavior at the governed ref before describing admission as enforced.

#### Scenario: GH-04-01
- **WHEN** A workflow file exists but no required check is configured
- **THEN** the installation is reported as advisory rather than enforced

#### Scenario: GH-04-02
- **WHEN** A new head or policy version replaces the approved state
- **THEN** the previous authorization cannot admit the new state

