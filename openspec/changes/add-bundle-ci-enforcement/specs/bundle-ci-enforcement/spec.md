# Spec delta: add-bundle-ci-enforcement / bundle-ci-enforcement

## ADDED Requirements

### Requirement: Bundle rules MUST be enforceable on a GitHub-native CI surface independent of the orchestrator

The system MUST provide a standalone enforcer that applies `severity: BLOCK` bundle rules to a pull request's changed files and runs with no orchestrator import, no Cosmos access, and no LLM call. The enforcer MUST load rules directly from `standards-bundles/**` and depend only on the Python standard library plus a YAML parser.

#### Scenario: enforcer runs with zero orchestrator dependencies

- **GIVEN** the enforcer script `scripts/enforce_bundles.py`
- **WHEN** it is imported and executed against a set of changed files
- **THEN** it MUST NOT import any `apps.orchestrator` module
- **AND** it MUST NOT open a Cosmos connection or call an LLM provider
- **AND** it MUST read the rules from `standards-bundles/**` on disk

#### Scenario: enforcer flags a diff that violates a BLOCK rule

- **GIVEN** a security bundle rule with `severity: BLOCK`, a `pattern`, and `ci_checks: true`
- **AND** a changed file whose content matches that pattern
- **WHEN** the enforcer runs over the changed file
- **THEN** it MUST exit non-zero
- **AND** it MUST print the violation as `file:line [<dept>/v<version>/<rule-id>] <title>`

### Requirement: The enforcement surface MUST be a declared per-rule property

The bundle rule schema MUST support an optional `enforcement.ci_checks` boolean (default `false`) that opts a rule into the CI lane, consistent with the existing `pipeline_stages` and `ide_hooks` enforcement keys. A rule MUST run in the CI lane only when its `severity` is `BLOCK`, it declares a `pattern`, and either its `enforcement.ci_checks` is `true` or its bundle sets `ci_checks_default: true`.

#### Scenario: a BLOCK rule without ci_checks opt-in is not run in CI

- **GIVEN** a BLOCK rule with a `pattern` but `enforcement.ci_checks` unset and its bundle's `ci_checks_default` unset or false
- **WHEN** the enforcer selects rules for the CI lane
- **THEN** that rule MUST NOT be applied by the CI enforcer
- **AND** the rule's enforcement on `pipeline_stages` and `ide_hooks` MUST be unchanged

#### Scenario: a bundle-level default opts all its BLOCK rules into CI

- **GIVEN** a bundle whose metadata sets `ci_checks_default: true`
- **WHEN** the enforcer selects rules for that bundle
- **THEN** every rule in that bundle with `severity: BLOCK` and a `pattern` MUST be applied by the CI enforcer

### Requirement: The CI enforcer MUST fail closed on any bundle load or parse error

The enforcer MUST exit non-zero when a required bundle directory is missing, a `rules.yaml` fails to parse, a `PINS.yaml` pin is unresolvable, or a selected rule cannot be read. The enforcer MUST NOT treat a load or parse failure as an empty rule set that passes.

#### Scenario: malformed bundle fails the check rather than passing empty

- **GIVEN** a `standards-bundles/security/v0.1.0/rules.yaml` that is not valid YAML
- **WHEN** the enforcer attempts to load rules
- **THEN** it MUST exit non-zero with a diagnostic naming the unparseable file
- **AND** it MUST NOT report success on an empty rule set

#### Scenario: unresolvable pin fails the check

- **GIVEN** a `--team` whose `PINS.yaml` entry points at a `<dept>/<version>/` directory that does not exist
- **WHEN** the enforcer resolves bundle versions
- **THEN** it MUST exit non-zero with an "unresolvable pin" diagnostic

### Requirement: The CI enforcer MUST resolve bundle versions through PINS the same way the orchestrator does

The enforcer MUST resolve which bundle version to enforce by reading `standards-bundles/PINS.yaml` for the supplied team identifier, falling back to `defaults` when the team is unlisted, so the CI lane enforces the same bundle version a team's pipeline enforces. The team identifier MUST be a workflow input defaulting to `defaults`.

#### Scenario: pinned team enforces its pinned version

- **GIVEN** `PINS.yaml` pins `team-cardiology` to `security/v0.1.0`
- **WHEN** the enforcer runs with `--team team-cardiology`
- **THEN** it MUST load rules from `standards-bundles/security/v0.1.0/`

#### Scenario: unlisted team falls back to defaults

- **GIVEN** a team identifier absent from `PINS.yaml` `teams`
- **WHEN** the enforcer runs with that team identifier
- **THEN** it MUST resolve every department to the `defaults` version

### Requirement: A GitHub Actions workflow MUST run the enforcer on pull requests over the changed files

The system MUST provide a workflow at `.github/workflows/bundle-enforce.yml` that triggers on `pull_request`, computes the files changed against the base branch, runs `scripts/enforce_bundles.py` over exactly those files, and fails the check when the enforcer exits non-zero. The workflow MUST NOT require any repository secret to run.

#### Scenario: a PR that adds a violating file fails the workflow check

- **GIVEN** a pull request whose diff adds a file matching a CI-enabled BLOCK rule
- **WHEN** the `bundle-enforce` workflow runs
- **THEN** the check MUST report failure
- **AND** the failing log MUST cite the `<dept>/v<version>/<rule-id>` that matched

#### Scenario: the workflow runs without secrets

- **GIVEN** the `bundle-enforce` workflow
- **WHEN** it executes on a pull request
- **THEN** it MUST complete using only the checked-out repository and a YAML parser
- **AND** it MUST NOT reference a Cosmos connection string or a data-plane secret

### Requirement: The workflow MUST become a merge gate only when configured as a required status check

The workflow MUST report its result as an ordinary check by default, and MUST block merges only after an administrator adds it to the branch's required-status-check set under branch protection. The change's documentation MUST state that adding the workflow does not itself gate merges and MUST give the explicit step that makes it required.

#### Scenario: workflow reports but does not gate until required

- **GIVEN** a repository that has added `bundle-enforce.yml` but has not added it to branch protection required checks
- **WHEN** a pull request fails the enforcer
- **THEN** the check MUST show as failed on the pull request
- **AND** the merge button MUST NOT be blocked by this check until it is marked required

#### Scenario: documentation gives the required-check step

- **WHEN** a reader opens `docs/CI-ENFORCEMENT.md`
- **THEN** it MUST state that the workflow is advisory until made a required status check
- **AND** it MUST give the branch-protection step that marks `bundle-enforce` required

### Requirement: The CI enforcer MUST emit a machine-readable result artifact without writing to the ledger

The enforcer MUST write a `bundle-enforce-result.json` artifact carrying the pull-request reference, a pass or fail status, and the list of violations with their `<dept>/v<version>/<rule-id>` citations, and MUST NOT write to the Decision Ledger directly. The CI job MUST hold no ledger credential.

#### Scenario: result artifact captures cited violations

- **GIVEN** an enforcer run that finds two violations on a pull request
- **WHEN** the run completes
- **THEN** it MUST write `bundle-enforce-result.json` with `pass: false` and two `violations[]` entries each carrying a bundle citation and `file:line`
- **AND** it MUST NOT open a ledger connection

#### Scenario: a clean run records a passing artifact

- **GIVEN** an enforcer run over a diff that matches no CI-enabled BLOCK rule
- **WHEN** the run completes
- **THEN** it MUST exit zero
- **AND** it MUST write `bundle-enforce-result.json` with `pass: true` and an empty `violations[]`

### Requirement: The CI lane MUST NOT weaken the orchestrator and IDE PHI enforcement floor

The CI lane MUST be additive to the existing `pipeline_stages` and `ide_hooks` enforcement of `phi: true` rules and MUST NOT be treated as permitting any relaxation of the autonomous-review-loop PHI escalation floor. A PHI rule enforced in CI MUST also remain enforced on its previously declared surfaces.

#### Scenario: adding a PHI rule to the CI lane keeps its other surfaces

- **GIVEN** a `phi: true` BLOCK rule enforced on `pipeline_stages` and `ide_hooks`
- **WHEN** the rule additionally sets `enforcement.ci_checks: true`
- **THEN** the rule MUST continue to be enforced on `pipeline_stages` and `ide_hooks`
- **AND** the autonomous-review-loop `tier_floor_phi` escalation MUST remain authoritative for the merge decision

#### Scenario: a green CI check does not authorize a PHI auto-merge

- **GIVEN** a pull request that passes the CI enforcer but carries a blocker citing a `phi: true` rule from the orchestrator review
- **WHEN** merge is considered
- **THEN** the PHI floor MUST still force escalation regardless of the green CI check
