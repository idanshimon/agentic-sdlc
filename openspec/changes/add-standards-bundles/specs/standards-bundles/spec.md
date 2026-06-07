## ADDED Requirements

### Requirement: Standards-bundles directory structure

The repository MUST contain a top-level `standards-bundles/` directory with per-department, versioned policy bundles. Each bundle SHALL live at `standards-bundles/<dept>/v<n.n.n>/` and contain `rules.yaml`, `envelope.yaml`, `reviewers.yaml`, and `README.md`. The v0.1.0 release MUST ship four departments: `architect`, `security`, `privacy`, `finops`.

#### Scenario: bundle directory layout
- **WHEN** an agent reads `standards-bundles/security/v0.1.0/`
- **THEN** the directory MUST contain exactly `rules.yaml`, `envelope.yaml`, `reviewers.yaml`, and `README.md`

#### Scenario: missing required department
- **WHEN** the orchestrator starts and `standards-bundles/privacy/` does not exist
- **THEN** startup MUST fail with `"required department privacy missing"`

### Requirement: rules.yaml schema

Every `rules.yaml` MUST contain a list of rules. Each rule MUST have: `id` (unique within the bundle), `title`, `phi` (boolean), `enforcement` (which surfaces enforce it), `pattern`, `severity` (one of BLOCK, WARN, LOG), `rationale`, and `test_cases`.

#### Scenario: duplicate rule id
- **WHEN** a `rules.yaml` contains two rules with the same `id`
- **THEN** the bundle validator SHALL fail with `"duplicate rule id"`

#### Scenario: missing severity
- **WHEN** a rule lacks `severity`
- **THEN** the validator SHALL reject the bundle

### Requirement: envelope.yaml allowed auto-fixes

Every `envelope.yaml` MUST declare `allowed_auto_fixes` (list of rule patterns + bounds + preconditions) and `forbidden` (list of rule patterns or properties that block auto-fix even when envelope bounds are met). Rules with `phi: true` MUST be auto-excluded from `allowed_auto_fixes` regardless of envelope content.

#### Scenario: PHI rule in allowed_auto_fixes
- **WHEN** an `envelope.yaml` lists a rule with `phi: true` under `allowed_auto_fixes`
- **THEN** the validator SHALL strip the entry and emit a `"phi rule cannot be auto-fixed"` warning

### Requirement: reviewers.yaml roster per blast class

Every `reviewers.yaml` MUST declare reviewer assignments per blast class (HIGH, MED, LOW, AUTO) with `required_approvers`, `must_include_roles`, and `can_include_roles`. A people→email map MUST also be provided. The HIGH blast class MUST have at least one entry in `must_include_roles`.

#### Scenario: HIGH blast class with no required roles
- **WHEN** a `reviewers.yaml` declares HIGH with empty `must_include_roles`
- **THEN** the validator script `scripts/validate-reviewer-roster.py` SHALL fail

### Requirement: PINS.yaml team-to-version mapping

`standards-bundles/PINS.yaml` MUST map every team_id to a specific bundle version per department. The orchestrator MUST refuse startup if any pin resolves to a non-existent `<dept>/<version>/` directory.

#### Scenario: orphaned pin
- **WHEN** PINS.yaml pins `team_a` to `architect/v0.2.0` but only `architect/v0.1.0/` exists
- **THEN** orchestrator startup MUST fail with `"unresolvable pin"`

### Requirement: Standards-change agent triggers on bundle PRs

A custom agent at `.github/agents/standards-change.agent.md` MUST be invoked when a PR opens against `standards-bundles/`. The agent SHALL classify the change's blast class, draft an ADR, assign reviewers per the relevant `reviewers.yaml`, and block merge until quorum is reached.

#### Scenario: bundle PR opens
- **WHEN** a PR modifying `standards-bundles/security/v0.1.0/rules.yaml` is opened
- **THEN** the standards-change agent MUST be invoked and post a blast-class classification + reviewer roster within 30 seconds

#### Scenario: merge before quorum
- **WHEN** a reviewer attempts to merge a HIGH-blast bundle PR with one approval and required_approvers=2
- **THEN** branch protection rules MUST block the merge

### Requirement: Meta ledger entries on bundle merge

When a PR against `standards-bundles/` merges, a `meta` ledger entry MUST be written automatically. The entry MUST carry `change_ticket_id`, `bundle_version_from`, `bundle_version_to`, `blast_class`, `reviewers`, and `pr_url`.

#### Scenario: bundle PR merges
- **WHEN** a `standards-bundles/architect/v0.1.0` → `v0.2.0` PR merges
- **THEN** a `meta` entry MUST be written within 5 seconds with `bundle_version_from = "v0.1.0"` and `bundle_version_to = "v0.2.0"`

### Requirement: Canary rollout for new bundle versions

New bundle versions MUST roll out to 5% of teams for 7 days before full rollout. Pipeline Doctor SHALL watch metrics during canary; if regression is detected, an auto-revert PR MUST be opened.

#### Scenario: canary regression detected
- **WHEN** Pipeline Doctor detects autopilot rejection rate climbing > 25% on canary teams during the 7-day window
- **THEN** an auto-revert PR MUST be opened against PINS.yaml and labeled `pipeline-doctor`, `canary-revert`
