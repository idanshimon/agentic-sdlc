# Proposal: add agent-instructions hierarchy

> **Status:** DRAFT
> **Capability:** agent-instructions
> **Related:** add-agent-hq-integration, master-v07-four-plane-architecture

## Why

`AGENTS.md` and `.github/copilot-instructions.md` were authored as part of the
Agent HQ integration but never normatively specified. The current state has
three problems:

1. **`AGENTS.md` claims a precedence chain it doesn't fully implement.** It
   lists four levels (AGENTS.md → copilot-instructions.md → `.github/instructions/*.instructions.md` → bundles)
   but the third level — path-scoped instruction files via `applyTo` — has no
   directory, no example file, no loader, no test.
2. **The Custom Agent frontmatter contract is implicit.** Each `.github/agents/*.agent.md`
   declares `tools:`, `bundle_subscriptions:`, `preferred_models:`, `ledger_writes:`,
   but no spec says which fields are required, what the value spaces are, or
   what fails when a field is missing or malformed.
3. **The `bundle_subscriptions:` injection mechanism is asserted but unowned.**
   `.github/agents/README.md` claims hooks at SessionStart read this list
   and inject the bundle rules; the hook spec doesn't mention it, the
   `session-start.sh` script doesn't implement it.

This proposal closes all three gaps so a fresh contributor (or a coding agent
opening this repo for the first time) can answer: "When my Copilot session
starts in this repo, what instructions get loaded, in what order, and where
does my agent file fit?"

## What changes

Three additions, one fix.

### 1. New normative spec: `agent-instructions` capability

A new capability declaring:

- The precedence chain (with explicit conflict resolution rules)
- Which runtime loads which file at which lifecycle event
- How AGENTS.md, `.github/copilot-instructions.md`, and `.github/instructions/*.instructions.md`
  compose
- The Custom Agent frontmatter schema (required + optional fields)
- The bundle-injection contract between Custom Agents and the SessionStart hook

### 2. Path-scoped instructions directory

Add `.github/instructions/` with:

- `README.md` — explains `applyTo:` glob semantics, when to write a path-scoped
  instruction vs. a bundle rule, and how SessionStart resolves them
- `python.instructions.md` — `applyTo: "**/*.py"` with the Python conventions
  currently in `.github/copilot-instructions.md`
- `typescript.instructions.md` — `applyTo: "**/*.ts"` with the TS conventions
- `bicep.instructions.md` — `applyTo: "infra/**/*.bicep"` with naming + secret rules

Splitting language conventions out of `copilot-instructions.md` means an
engineer working on Bicep doesn't burn context on Python ruff settings.

### 3. Custom Agent frontmatter schema

A versioned JSON Schema at `.github/agents/agent-frontmatter.schema.json`
that every `.agent.md` file validates against. Required fields:

| Field | Type | Notes |
|---|---|---|
| `name` | string | matches the filename stem |
| `description` | string | one-paragraph persona summary |
| `tools` | array<string> | MCP tool names + `file.read` / `file.write` / `terminal` |
| `preferred_models` | array<string> | ordered preference, first available wins |
| `bundle_subscriptions` | array<string> | dept names; bundles are pinned via `standards-bundles/PINS.yaml` |
| `ledger_writes` | array<object> | `{entry_type, kind, stage?}` tuples — declares what the agent CAN write |

Validation runs in CI via a new task in `scripts/validate-agent-frontmatter.py`.

### 4. Fix AGENTS.md precedence claim

Update AGENTS.md so the precedence list reflects what actually exists:

- Add a "loaded by" column (which runtime / hook reads each level)
- Add a worked example showing what context an Architect agent in VS Code
  sees when editing `apps/orchestrator/main.py` (AGENTS.md + copilot-instructions
  + python.instructions + architect.agent + architect bundle)
- Stop referencing `.github/instructions/*` as if it exists today; the
  reference becomes valid once this change is implemented

## Why this design

**Normative spec, not "documented as we found it".** AGENTS.md is a contract
between the repo and every agent that opens a session here. Contracts need
specs. The current state — "the file says what it says, hopefully runtimes
honor it" — is exactly the un-audited 80% the four-plane architecture exists
to eliminate.

**JSON Schema for frontmatter, not loose conventions.** Custom Agent files
get added by humans in PRs. Without machine-checkable schema, drift creeps in
(`bundles:` vs `bundle_subscriptions:`, `model:` vs `preferred_models:`).
A pre-merge validator prevents this with zero ongoing maintenance.

**Path-scoped instructions, not one giant copilot-instructions.** GitHub
Copilot's `.github/instructions/*.instructions.md` with `applyTo:` globs is
the Universe-2025 standard for path-scoped guidance. Using the GH-blessed
mechanism means the conventions survive Copilot config changes; rolling our
own loader means we re-invent it every six months.

## Risks and rollback

| Risk | Mitigation | Rollback |
|---|---|---|
| Splitting `copilot-instructions.md` into per-language files breaks discoverability | `copilot-instructions.md` keeps a "see also" pointing to `.github/instructions/` | Revert split commit; conventions return to single file |
| Frontmatter validator rejects existing agent files due to missing field | Authoring task includes a one-time backfill of existing `.agent.md` files | Mark validator non-blocking in CI until backfill lands |
| Bundle injection at SessionStart slows IDE startup | Hook has 5s timeout, fail-open; bundle YAML is small (<10KB per dept) | Disable bundle injection in `session-start.json` per-team |

## Honest limitations

- **Not all Copilot surfaces honor `.github/instructions/*` equally.** VS Code
  + Copilot Chat: yes. Copilot CLI: partial. Cloud agent: yes. We document the
  matrix in `.github/instructions/README.md` and treat AGENTS.md as the
  always-loaded fallback.
- **Frontmatter schema validation is pre-merge only.** A misformatted agent
  file pushed directly to `main` (e.g. via admin override) could still load
  malformed; SessionStart hook adds a soft-warn but does not refuse.

## Test targets

- Unit (validator): 8 cases — required field present, missing field rejected,
  unknown tool name flagged, bundle dept exists in `standards-bundles/`,
  model name matches `prompt_library` allowlist
- Integration: synthetic VS Code session opens `apps/orchestrator/main.py`,
  confirms AGENTS.md + copilot-instructions + python.instructions
  + architect.agent are all visible to the session
- E2E: `openspec validate add-agent-instructions-hierarchy --strict` passes;
  `scripts/validate-agent-frontmatter.py` passes against all 6 agent files
