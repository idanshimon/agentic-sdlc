# Spec delta: add-multi-persona-prompt-library / prompt-library

## ADDED Requirements

### Requirement: Prompts MUST be stored as versioned YAML files in git

Every prompt MUST live in a YAML file under `prompts/{scope}/{persona}/{stage}/v{version}.yaml`. Every prompt file MUST carry frontmatter: `prompt_id`, `version`, `status` (draft|published|superseded), `scope` (global|persona|team), `owner_persona`, `stage`, `model_compat_notes`, `effective_from`, `superseded_by`, `git_sha`, `authored_by`, `reason`, and `template`.

`prompt_id` MUST be stable across versions of the same logical prompt. `version` MUST follow semver and MUST be immutable once `status: published`.

#### Scenario: a global prompt file loads with full metadata

- **GIVEN** the file `prompts/global/assessor/v1.yaml` exists with valid frontmatter
- **WHEN** the orchestrator's `prompts_loader.load_prompts(Path("prompts"))` is called at startup
- **THEN** the returned `PromptCatalog` MUST contain an entry keyed by `("global", "assessor-global", "v1")`
- **AND** the entry's `template` MUST equal the file's `template` field byte-for-byte
- **AND** the entry's `git_sha` MUST equal the file's `git_sha` field

#### Scenario: a malformed prompt file aborts startup

- **GIVEN** the file `prompts/global/assessor/v1.yaml` is missing the required `owner_persona` field
- **WHEN** the loader scans the directory
- **THEN** the loader MUST raise `PromptValidationError` with the file path and the missing field
- **AND** the orchestrator MUST refuse to start (fail-fast on invalid prompt state)

### Requirement: Resolver MUST walk inheritance from most-specific to global

The orchestrator MUST resolve prompts via inheritance: run-overrides → team → persona → global. The resolver MUST return both the template and the full chain of scopes it considered, marking the matched scope.

#### Scenario: team override beats global

- **GIVEN** `prompts/global/assessor/v1.yaml` exists with template "GLOBAL ASSESSOR"
- **AND** `prompts/team/cardiology/assessor/v1.yaml` exists with template "CARDIOLOGY ASSESSOR"
- **WHEN** the resolver is called with `(stage="assessor", model="claude-sonnet-4-6", team="cardiology")`
- **THEN** the returned template MUST equal "CARDIOLOGY ASSESSOR"
- **AND** the chain MUST be `[{scope:team, matched:true}, {scope:persona, matched:false}, {scope:global, matched:false}]`

#### Scenario: missing team override falls through to global

- **GIVEN** `prompts/global/assessor/v1.yaml` exists
- **AND** no `prompts/team/finance/assessor/...` file exists
- **WHEN** the resolver is called with `(stage="assessor", model="claude-sonnet-4-6", team="finance")`
- **THEN** the returned template MUST equal the global file's template
- **AND** the chain MUST be `[{scope:team, matched:false}, {scope:persona, matched:false}, {scope:global, matched:true}]`

### Requirement: Every stage_decision ledger entry MUST pin the prompt resolution chain

Every `LedgerEntry` with `runtime_kind="stage_decision"` MUST carry `prompt_resolution_path` — a list of scope-step records (scope, owner_persona, prompt_id, version, git_sha, matched). This MUST be written by the orchestrator stage helper at the moment of decision, not derived post-hoc.

#### Scenario: assessor stage writes a ledger entry with chain

- **GIVEN** the resolver was called with `(stage="assessor", model="claude-sonnet-4-6", team="cardiology")` and returned chain `[team:matched, persona:no, global:no]`
- **WHEN** the assessor produces a decision and the stage helper writes it to the ledger
- **THEN** the resulting `LedgerEntry` MUST have `prompt_resolution_path` equal to the resolver's returned chain
- **AND** the matched scope's `git_sha` MUST be the git commit hash of the prompt file used

### Requirement: Legacy ledger entries without chain MUST render gracefully

Ledger entries written before this change have no `prompt_resolution_path`. The UI MUST render "chain unavailable (pre-v2)" for these entries without throwing.

#### Scenario: UI renders legacy entry without crashing

- **GIVEN** a ledger entry with `prompt_resolution_path: None`
- **WHEN** the `/decisions/<id>` page renders the Prompt Chain tab
- **THEN** the tab MUST display the literal text "chain unavailable (pre-v2)" with a tooltip explaining when the field was introduced
- **AND** the page MUST NOT throw a runtime error

### Requirement: PromptCatalog MUST be queryable by persona

The catalog API MUST expose `get_prompts_owned_by(persona: str) → list[PromptFile]` so the UI can render persona-specific views.

#### Scenario: filtering by persona returns the right slice

- **GIVEN** prompts/global has 6 prompts owned by 5 personas (pm: ingest+assessor; architect: architect; qa: test_plan; sre: codegen; seceng: review_scan)
- **WHEN** `catalog.get_prompts_owned_by("pm")` is called
- **THEN** the returned list MUST contain exactly 2 prompts (ingest, assessor) and no others

### Requirement: PromptCatalog MUST be queryable by stage

The catalog API MUST expose `get_versions(stage: str, scope: str = "global") → list[PromptFile]` returning all versions of a given stage's prompt in registration order, newest first.

#### Scenario: listing assessor versions returns the version history

- **GIVEN** `prompts/global/assessor/v1.yaml` and `prompts/global/assessor/v2.yaml` both exist
- **WHEN** `catalog.get_versions("assessor", "global")` is called
- **THEN** the returned list MUST be `[v2_file, v1_file]` (newest first)
- **AND** each entry MUST be a fully validated `PromptFile`

### Requirement: prompts/ MUST ship inside the orchestrator image

The orchestrator Docker image MUST include `prompts/` at `/app/prompts/`. The loader MUST read from this path at startup.

#### Scenario: image rebuild after merge picks up new prompt

- **GIVEN** `prompts/global/assessor/v2.yaml` is committed and merged to main
- **WHEN** the ACR build of the orchestrator runs and the new image is deployed
- **THEN** `/app/prompts/global/assessor/v2.yaml` MUST exist inside the running container
- **AND** the next run's resolver MUST be able to return v2 if it's the most-recent published version

### Requirement: a `published` prompt MUST be immutable

Once a prompt file is committed with `status: published`, its template MUST NOT be modified. Subsequent changes MUST create a new version with `status: draft` first, then a publish PR that updates it to `status: published` and sets `superseded_by` on the previous version.

#### Scenario: editing a published prompt is rejected at PR time

- **GIVEN** `prompts/global/assessor/v1.yaml` exists with `status: published`
- **WHEN** a PR proposes modifying the `template` field of that file
- **THEN** the GitHub Action MUST fail the PR check with "published prompts are immutable — create v2 instead"
