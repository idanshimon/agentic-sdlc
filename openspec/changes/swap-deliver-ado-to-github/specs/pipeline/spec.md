## MODIFIED Requirements

### Requirement: Deliver stage provider dispatch

The pipeline's deliver stage MUST dispatch on `config.deliver_provider` to one of two implementations: `deliver_github` (default) or `deliver_ado` (opt-in, ported from v0.6). Both implementations SHALL share the same input/output contract: input is the completed run state + ledger entries + codegen output; output is a PR URL plus a `runtime` ledger entry of kind `delivered`.

#### Scenario: default GitHub delivery
- **WHEN** a run completes and `config.deliver_provider` is unset
- **THEN** `deliver_github` MUST execute and produce a GitHub PR URL

#### Scenario: opt-in ADO delivery
- **WHEN** a run completes and `config.deliver_provider = "ado"`
- **THEN** `deliver_ado` MUST execute and produce an ADO PR URL

#### Scenario: provider-agnostic output shape
- **WHEN** either implementation completes
- **THEN** the resulting ledger entry MUST have kind `delivered` and a populated PR URL field

### Requirement: Branch naming convention

The deliver stage MUST create branches with the pattern `agentic-sdlc/run-<run_id>` (changed from v0.6's `feature/<run_id>`) so that downstream queries can filter on `branch:agentic-sdlc/*` trivially.

#### Scenario: GitHub branch naming
- **WHEN** `deliver_github` opens a PR for run `abc-123`
- **THEN** the source branch MUST be named `agentic-sdlc/run-abc-123`

### Requirement: PR body renders decisions.md inline

The deliver stage MUST render the `decisions.md` content directly into the PR body (was attached file in v0.6 ADO path). The renderer (`decisions_md.py`) is ported verbatim from v0.6.

#### Scenario: PR body contains decisions
- **WHEN** a PR is opened
- **THEN** the PR body MUST contain the full `decisions.md` Markdown rendered as inline content

### Requirement: Reviewer assignment from bundles

The deliver stage MUST assign reviewers from `standards-bundles/<dept>/v<n>/reviewers.yaml` matching the run's bundle subscriptions. When multiple bundles apply, the union of required roles SHALL be assigned.

#### Scenario: single-bundle reviewer assignment
- **WHEN** a run subscribes only to `architect/v0.1.0`
- **THEN** the PR's reviewers MUST be the `must_include_roles` from `architect/v0.1.0/reviewers.yaml`

#### Scenario: multi-bundle reviewer assignment
- **WHEN** a run subscribes to both `architect/v0.1.0` and `security/v0.1.0`
- **THEN** the PR's reviewers MUST be the union of `must_include_roles` from both reviewer rosters

## ADDED Requirements

### Requirement: GitHub App auth boundary

The deliver-github implementation MUST authenticate via a GitHub App. PAT-based delivery SHALL NOT be supported. App credentials MUST be stored as Container App secrets and retrieved via Managed Identity + Key Vault. App installation is per-customer-org.

#### Scenario: missing installation_id
- **WHEN** the orchestrator starts and any team in config lacks `github_app.installation_id`
- **THEN** the orchestrator SHALL refuse to start and log the offending team_id

#### Scenario: PAT credential rejection
- **WHEN** the deliver_github implementation detects a PAT in its credential bundle
- **THEN** the deliver call MUST fail with `"PAT auth not supported; use GitHub App"`

### Requirement: gh_audit_xref ledger field on delivered entries

A `runtime` ledger entry of kind `delivered` produced by `deliver_github` MUST carry a `gh_audit_xref` field set to the GH audit session ID for the PR creation, enabling compliance to join the Decision Ledger to GH's `actor:Copilot` audit log.

#### Scenario: GitHub PR creates an audit entry
- **WHEN** `deliver_github` creates a PR via the GitHub App
- **THEN** the resulting `delivered` ledger entry MUST contain `gh_audit_xref` matching the GH audit session ID

### Requirement: Mixed-tenant delivery support

The deliver stage MUST support per-team provider overrides so that some teams within the same orchestrator deployment can use GitHub while others use ADO.

#### Scenario: per-team provider override
- **WHEN** `team_a` config sets `deliver_provider = "github"` and `team_b` config sets `deliver_provider = "ado"`
- **THEN** runs from each team MUST dispatch to their respective implementations
