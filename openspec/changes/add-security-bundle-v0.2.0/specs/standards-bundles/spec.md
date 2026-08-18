# standards-bundles — security v0.2.0 control coverage

## ADDED Requirements

### Requirement: A rule requiring an external mechanism MUST declare its status

A rule that cannot be evaluated by the deterministic pattern matcher MUST set
`requires_mechanism: true` and MUST carry a `mechanism_status` that reflects
reality.

Several v0.2.0 rules (supply-chain scanning, identity scope, retention) have no
regex form — there is no pattern for "this dependency has a CVE". Such a rule is
inert until an external mechanism exists. Declaring that inertness is what stops
the bundle from claiming a control it does not have; a rule marked
`implemented` whose workflow does not exist is indistinguishable, from the
ledger's point of view, from a control that works.

#### Scenario: A rule with no pattern declares its mechanism

- **GIVEN** a rule that cannot be expressed as a source pattern
- **WHEN** it is added to the bundle
- **THEN** it MUST set `requires_mechanism: true`
- **AND** it MUST name the enforcing surface under `enforcement`

#### Scenario: Mechanism status reflects the actual state

- **GIVEN** a rule with `requires_mechanism: true`
- **WHEN** its enforcing workflow does not exist in the repository
- **THEN** `mechanism_status` MUST NOT be `implemented`

### Requirement: SUPPLY-001 MUST block a merge on critical or high findings

The supply-chain gate MUST fail the build when the scanned SBOM contains any
finding at or above `high` severity, and MUST report the finding count by
severity.

An SBOM that is generated and archived but never acted upon is evidence of
process, not of security. SBOM-001 requires the artifact to exist; this
requirement makes it consequential.

#### Scenario: High-severity findings block

- **GIVEN** a scanned SBOM containing one or more findings at `high` or `critical`
- **WHEN** the supply-chain workflow runs
- **THEN** the job MUST exit non-zero
- **AND** the output MUST cite `[security/v0.2.0/SUPPLY-001]` with the count by severity

#### Scenario: Findings below the threshold do not block

- **GIVEN** a scanned SBOM whose highest finding is `medium`
- **WHEN** the supply-chain workflow runs
- **THEN** the job MUST pass
- **AND** the remaining findings MUST still be reported rather than suppressed

#### Scenario: The scan result is published as evidence

- **GIVEN** a completed supply-chain scan
- **WHEN** the workflow finishes
- **THEN** its SARIF MUST be uploaded to code scanning so the findings the gate
  reasoned over are reviewable
- **AND** every result MUST carry a non-empty `artifactLocation.uri`, so the
  evidence is attributable to a file rather than silently dropped

### Requirement: A BLOCK rule without an enforcement surface MUST NOT be counted as enforcing

Every rule at `severity: BLOCK` MUST name the surface that enforces it, either a
source pattern the deterministic matcher can evaluate or an external mechanism
declared under `enforcement`. A rule with neither MUST NOT be reported as an
active CI control.

A BLOCK rule with no enforcement surface is a claim without a control. This is
the failure mode the bundle exists to prevent: the rule text reads as
enforcement, the ledger records it as enforcement, and nothing evaluates it.

**Verified current behaviour (2026-08-18):** `_is_ci_eligible` in
`scripts/enforce_bundles.py` returns `False` when a BLOCK rule has no `pattern`,
so such a rule is silently excluded from the selected CI rule set — a probe
bundle carrying one BLOCK rule with no pattern and no enforcement block loaded
without error and yielded `[]` selected rules. The rule is therefore not
enforced, and is also not announced as unenforced.

This requirement deliberately specifies **exclusion, not load failure**. Making
it a hard load error was considered and rejected for now: `requires_mechanism`
rules legitimately have no pattern, so a naive "BLOCK implies pattern" check
would reject the supply-chain and retention rules that are correctly declared as
externally enforced. Tightening this into a load-time error requires
distinguishing "no pattern and no declared mechanism" from "no pattern because a
mechanism is declared", which is its own change.

#### Scenario: A BLOCK rule with no enforcement surface is not selected

- **GIVEN** a rule at `severity: BLOCK`
- **AND** it declares neither a `pattern` nor an `enforcement` mechanism
- **WHEN** CI rules are selected from the bundle
- **THEN** the rule MUST NOT appear in the selected set
- **AND** it MUST NOT be reported anywhere as an enforcing control

#### Scenario: A BLOCK rule with a declared external mechanism remains valid

- **GIVEN** a rule at `severity: BLOCK` with no `pattern`
- **AND** `requires_mechanism: true` with a named `enforcement` surface
- **WHEN** the bundle is loaded
- **THEN** the load MUST succeed
- **AND** the rule's enforcement is the responsibility of that named surface
