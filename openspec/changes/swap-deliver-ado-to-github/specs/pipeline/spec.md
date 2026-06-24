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

The deliver stage MUST create branches with the pattern `agentic/<run_id>` so that downstream queries can filter delivery branches on `agentic/*` trivially.

#### Scenario: GitHub branch naming
- **WHEN** `deliver_github` opens a PR for run `abc-123`
- **THEN** the source branch MUST be named `agentic/abc-123`

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

### Requirement: GitHub delivery auth

The deliver-github implementation MUST authenticate to GitHub using a token resolved from `DELIVER_GH_TOKEN` (falling back to `GH_TOKEN`), stored as a Container App secret. A repo-scoped PAT or fine-grained token with Contents + Pull-requests write is the shipped auth; GitHub App installation auth is planned future hardening, not yet implemented.

#### Scenario: token from environment
- **WHEN** the deliver stage runs and `DELIVER_GH_TOKEN` (or `GH_TOKEN`) is set as a container secret
- **THEN** the implementation MUST authenticate its GitHub REST calls with that token

#### Scenario: missing token degrades honestly
- **WHEN** the deliver stage runs and no delivery token is configured
- **THEN** the stage MUST emit an honest "PR not opened" event with a reason and MUST NOT fabricate a PR URL

### Requirement: Delivery never fabricates a PR URL

The deliver stage MUST emit a real PR URL only when a PR was actually opened, and MUST otherwise emit an honest not-delivered event carrying the reason — never a randomly-generated or placeholder URL.

#### Scenario: real delivery
- **WHEN** delivery is configured and the GitHub REST calls succeed
- **THEN** the `delivered` event MUST carry the real `pr_url` returned by GitHub and `delivery_status: delivered`

#### Scenario: not configured
- **WHEN** delivery is not configured (no target repo or no token)
- **THEN** the event MUST carry `delivery_status: not_delivered` and a `delivery_reason`, and MUST omit `pr_url`

#### Scenario: no demo fakes
- **WHEN** any run completes, including demo-mode runs
- **THEN** the deliver event MUST NOT contain a fabricated PR URL (no `Math.random()` PR number, no `dev.azure.com` placeholder)

### Requirement: Delivery target repo resolution and bootstrap

The deliver stage MUST resolve the delivery repo from `DELIVER_TARGET_REPO` when set, otherwise a convention default `<token-owner>/agentic-sdlc-delivery`, and MUST be able to create and initialize that repo when `DELIVER_AUTO_CREATE` is enabled.

#### Scenario: explicit target repo
- **WHEN** `DELIVER_TARGET_REPO` is set to `owner/repo`
- **THEN** the deliver stage MUST open the PR against `owner/repo`

#### Scenario: convention default
- **WHEN** `DELIVER_TARGET_REPO` is unset and a valid token resolves owner `idanshimon`
- **THEN** the deliver stage MUST target `idanshimon/agentic-sdlc-delivery`

#### Scenario: empty repo is bootstrapped
- **WHEN** the target repo exists but has no base branch (empty repo)
- **THEN** the deliver stage MUST seed an initial commit so the PR has a base to target

### Requirement: Delivery commits all run artifacts atomically

The deliver stage MUST push the run's generated artifacts (code, tests, architecture, decisions) to the run branch in a single commit via the GitHub Git Data API.

#### Scenario: artifacts in one commit
- **WHEN** a run delivers `src/main.py`, `tests/test_main.py`, `docs/architecture.md`, and `decisions.md`
- **THEN** all four files MUST appear in one commit on branch `agentic/<run-id>` referenced by the PR

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
