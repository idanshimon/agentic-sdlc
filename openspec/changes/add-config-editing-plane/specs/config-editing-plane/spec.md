## ADDED Requirements

### Requirement: Agent bundle subscriptions drive ledger bundle_refs

The pipeline MUST stamp each decision's `bundle_refs` with the deciding agent's declared `bundle_subscriptions`, resolved from `.github/agents/<agent>.agent.md` and validated against the real `standards-bundles/<dept>` directories.

#### Scenario: architect decision carries its bundles
- **WHEN** the architect agent records a decision and architect.agent.md declares `bundle_subscriptions: [architect, security]`
- **THEN** the ledger entry's `bundle_refs` MUST contain `architect` and `security`

#### Scenario: invalid subscription is dropped
- **WHEN** an agent file declares a subscription that is not a real bundle directory (e.g. a prose line `all (read-only)`)
- **THEN** that value MUST be excluded from `bundle_refs` rather than stamped as a bogus ref

#### Scenario: both write sites stamp bundle_refs
- **WHEN** a decision is recorded via either the autopilot path or the per-card approve path
- **THEN** `bundle_refs` MUST be populated from the deciding stage's agent in both cases

### Requirement: Config edits open a governed pull request

The config editing plane MUST persist agent, bundle, and prompt edits by opening a pull request against the file the pipeline reads, never by mutating running behaviour in place.

#### Scenario: agent edit opens a PR
- **WHEN** an operator saves an edit to an agent via `POST /api/config/agents/save`
- **THEN** the server MUST open a pull request that writes `.github/agents/<name>.agent.md` and return the PR URL

#### Scenario: prompt edit opens a draft-version PR
- **WHEN** an operator saves a prompt edit via `POST /api/config/prompts/save`
- **THEN** the server MUST open a pull request writing `prompts/<scope>/<stage>/v<N+1>.yaml` with `status: draft`

#### Scenario: edit does not change running behaviour before merge
- **WHEN** a config PR is opened but not yet merged
- **THEN** the pipeline MUST continue to use the currently published config until the PR merges

### Requirement: Bundle edits are PR-only

The bundle editor MUST be PR-only and MUST NOT support live application, because live-editing the compliance standards would bypass committee review.

#### Scenario: bundle save opens a PR
- **WHEN** an operator saves a bundle edit via `POST /api/config/bundles/save`
- **THEN** the server MUST open a pull request and MUST NOT apply the change to the running standard

#### Scenario: reload excludes bundles
- **WHEN** `POST /api/config/reload` is called
- **THEN** only agent and prompt caches MAY be refreshed and bundle rules MUST NOT be hot-reloaded

### Requirement: Config write path is confined to an allowlist

The config write path MUST refuse any target outside the allowlisted roots `.github/agents`, `standards-bundles`, and `prompts`, including absolute paths and `..` escapes.

#### Scenario: path escape is refused
- **WHEN** a save request resolves to a path outside the allowlisted roots (absolute path or `..` traversal)
- **THEN** the server MUST refuse the write and return an error without opening a PR

#### Scenario: allowlisted path is accepted
- **WHEN** a save request targets a path under `.github/agents`, `standards-bundles`, or `prompts`
- **THEN** the server MUST proceed to open the PR

### Requirement: Config write-back never fabricates a result

The config write path MUST return an honest error when it cannot open a real PR (no token configured, or any non-2xx GitHub response) and MUST NOT fabricate a PR URL or report a fake success.

#### Scenario: missing token degrades honestly
- **WHEN** a save is attempted and no GitHub token is configured
- **THEN** the endpoint MUST return a 422 and the UI MUST show "Saved locally — PR not opened" with no PR URL

#### Scenario: missing binary does not 500
- **WHEN** an underlying call raises `FileNotFoundError` (e.g. a missing binary in the container)
- **THEN** the write MUST surface as a clean `ConfigWriteError` (422), never an unhandled 500

### Requirement: Config write-back uses the GitHub REST API

The config write-back MUST use the GitHub REST API over HTTPS rather than shelling `git`/`gh`, because the deployed orchestrator is a stateless container with no git working tree.

#### Scenario: write works without a git clone
- **WHEN** a config save runs inside the deployed container that has no `.git`, `git`, or `gh`
- **THEN** the PR MUST still be opened via REST calls authenticated by the token
