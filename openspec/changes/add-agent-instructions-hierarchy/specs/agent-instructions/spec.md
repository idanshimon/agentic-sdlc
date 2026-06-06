# Spec delta — capability: agent-instructions

## ADDED Requirements

### Requirement: Standards hierarchy precedence

The repository MUST load agent context in five precedence layers, with bundles overriding all earlier layers when pinned. Layers, in order, are:

1. `AGENTS.md` (repo root)
2. `.github/copilot-instructions.md`
3. `.github/instructions/*.instructions.md` (only when `applyTo:` glob matches the touched file)
4. `.github/agents/<name>.agent.md` (only when that custom agent is invoked)
5. `standards-bundles/<dept>/v<n.n.n>/rules.yaml` (injected by the SessionStart hook from the agent's `bundle_subscriptions:`)

On direct conflict between layers 1–4, the lower-numbered layer wins. Layer 5 (bundles) MUST override layers 1–4 for the specific rules a bundle declares.

#### Scenario: Architect agent edits a Python file

- **GIVEN** a contributor opens `apps/orchestrator/main.py` in VS Code with the `architect` Custom Agent active
- **WHEN** the session starts
- **THEN** the loaded context contains, in order: `AGENTS.md`, `.github/copilot-instructions.md`, `.github/instructions/python.instructions.md`, `.github/agents/architect.agent.md`, the architect bundle, and the security bundle

#### Scenario: Bundle pin overrides a copilot-instructions rule

- **GIVEN** `.github/copilot-instructions.md` says "prefer SQLAlchemy"
- **AND** `standards-bundles/architect/v0.1.0/rules.yaml` rule `STORAGE-001` mandates "Cosmos DB only for ledger-adjacent stores"
- **WHEN** an Architect agent picks the storage backend for a ledger-adjacent service
- **THEN** the agent MUST follow the bundle rule, not the copilot-instructions preference

### Requirement: Path-scoped instruction files MUST validate `applyTo:` globs

Every `.github/instructions/*.instructions.md` file MUST declare its scope with a YAML frontmatter `applyTo:` field whose value is a repo-relative POSIX glob. Files without `applyTo:` MUST be treated as deprecated (always-loaded, equivalent to `copilot-instructions.md`); CI MUST emit a warning when one is added.

#### Scenario: Python instructions match a Python file

- **GIVEN** `.github/instructions/python.instructions.md` declares `applyTo: "**/*.py"`
- **WHEN** a session opens `apps/orchestrator/main.py`
- **THEN** the file's body MUST be loaded into the session context

#### Scenario: Bicep instructions do not match a Python file

- **GIVEN** `.github/instructions/bicep.instructions.md` declares `applyTo: "infra/**/*.bicep"`
- **WHEN** a session opens `apps/orchestrator/main.py`
- **THEN** the bicep instructions MUST NOT be loaded

### Requirement: Custom Agent frontmatter MUST validate against the schema

Every `.github/agents/*.agent.md` file MUST have YAML frontmatter validating against `.github/agents/agent-frontmatter.schema.json`. Required fields are `name`, `description`, `tools`, `preferred_models`, `bundle_subscriptions`, and `ledger_writes`. CI MUST run `scripts/validate-agent-frontmatter.py` on every PR touching `.github/agents/` and MUST block merge on validation failure.

#### Scenario: Validator passes a well-formed agent file

- **GIVEN** `.github/agents/architect.agent.md` declares all required fields with valid values
- **WHEN** `scripts/validate-agent-frontmatter.py` runs
- **THEN** the validator MUST exit with status 0 and emit no errors

#### Scenario: Validator rejects a missing required field

- **GIVEN** a new `.github/agents/security.agent.md` is added without a `ledger_writes` field
- **WHEN** the PR-validation CI workflow runs
- **THEN** the validator MUST exit with non-zero status and the workflow MUST block merge

#### Scenario: Validator rejects a bundle subscription that does not exist

- **GIVEN** an agent file declares `bundle_subscriptions: [unicorn]` but no `standards-bundles/unicorn/` directory exists
- **WHEN** the validator runs
- **THEN** the validator MUST report `bundle dept 'unicorn' not found under standards-bundles/`

#### Scenario: Validator rejects a tool name not exposed by the MCP server

- **GIVEN** an agent file declares `tools: [ledger.delete_universe]` but the MCP server exposes no such tool
- **WHEN** the validator runs
- **THEN** the validator MUST report `tool 'ledger.delete_universe' is not exposed by apps/decision-ledger-mcp`

### Requirement: SessionStart hook MUST inject subscribed bundles

`.github/hooks/scripts/session-start.sh` and `.github/hooks/scripts/session-start.ps1` MUST read the active Custom Agent file's `bundle_subscriptions:`, fetch each subscribed bundle via the `ledger.get_bundle` MCP tool at the version pinned in `standards-bundles/PINS.yaml`, and inject the rules portion of each bundle into the session context as a system message prefixed with `[bundle: <dept>/<version>]`. The hook MUST honor a 5-second timeout. On MCP unreachable, missing bundle dept, or hook timeout, the hook MUST fail-open (the session continues without bundle context).

#### Scenario: Architect session loads architect and security bundles

- **GIVEN** `.github/agents/architect.agent.md` declares `bundle_subscriptions: [architect, security]`
- **AND** `standards-bundles/PINS.yaml` pins architect to `v0.1.0` and security to `v0.1.0`
- **WHEN** a SessionStart event fires
- **THEN** the hook MUST call `ledger.get_bundle(dept="architect", version="v0.1.0")` and `ledger.get_bundle(dept="security", version="v0.1.0")` and inject both rule bodies into the session context

#### Scenario: MCP unavailable — session continues without bundles

- **GIVEN** the Decision Ledger MCP server returns HTTP 503 for `ledger.get_bundle`
- **WHEN** SessionStart fires
- **THEN** the hook MUST log a warning, fail-open, and let the session continue WITHOUT bundle context
- **AND** the local PHI-guard regex in `.github/hooks/scripts/pre-tool-use.sh` MUST remain active so PHI rules are still enforced offline

#### Scenario: Hook exceeds the 5-second timeout

- **GIVEN** the MCP server takes 8 seconds to respond
- **WHEN** SessionStart fires
- **THEN** the hook MUST be killed at 5 seconds, fail-open, and let the session continue

### Requirement: AGENTS.md MUST keep the precedence table accurate

`AGENTS.md` MUST contain the precedence table (with the "Loaded by" column), the persona inventory matching `.github/agents/*.agent.md`, the "Hard rules — NEVER" and "Hard rules — ALWAYS" sections, and at least one worked example showing what context loads for a common file path. The file MUST be ≤ 200 lines; longer rules MUST move to bundles.

#### Scenario: Persona inventory drifts from the agent files

- **GIVEN** a new `.github/agents/observer.agent.md` file is added in a PR
- **AND** the PR does not update the persona table in `AGENTS.md`
- **WHEN** CI runs
- **THEN** a CI check MUST flag the drift and block merge

#### Scenario: AGENTS.md exceeds the size budget

- **GIVEN** a PR grows `AGENTS.md` to 240 lines by inlining a 60-line rule list
- **WHEN** the size-check CI step runs
- **THEN** the step MUST fail with a message pointing the author at moving the rule list into the appropriate `standards-bundles/<dept>/v<n.n.n>/rules.yaml`

## MODIFIED Requirements

### Requirement: `.github/copilot-instructions.md` content scope

`.github/copilot-instructions.md` MUST contain only language-agnostic rules: commit-message format, Plan Mode trigger conditions, and OpenSpec workflow guidance. Per-language conventions MUST live in `.github/instructions/<lang>.instructions.md` with appropriate `applyTo:` globs. The file MUST link to `.github/instructions/` so contributors can find language-specific rules.

#### Scenario: Python convention is added

- **WHEN** a contributor wants to add a new Python convention (e.g. "use `match` over `if/elif` chains for ≥4 branches")
- **THEN** the convention MUST be added to `.github/instructions/python.instructions.md`, NOT to `.github/copilot-instructions.md`

#### Scenario: Plan Mode trigger is updated

- **WHEN** a contributor updates the Plan Mode trigger threshold
- **THEN** the change MUST land in `.github/copilot-instructions.md` because it is language-agnostic
