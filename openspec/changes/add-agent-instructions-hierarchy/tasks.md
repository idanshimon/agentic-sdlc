# Tasks — add agent-instructions hierarchy

## Spec authoring

- [ ] `openspec/changes/add-agent-instructions-hierarchy/specs/agent-instructions/spec-delta.md` — capability spec
- [ ] Run `openspec validate add-agent-instructions-hierarchy --strict`

## Path-scoped instructions

- [ ] `.github/instructions/README.md` — applyTo semantics + runtime support matrix
- [ ] `.github/instructions/python.instructions.md` — applyTo `**/*.py`, Python conventions
- [ ] `.github/instructions/typescript.instructions.md` — applyTo `**/*.ts`, TS conventions
- [ ] `.github/instructions/bicep.instructions.md` — applyTo `infra/**/*.bicep`, Bicep + secret rules

## Frontmatter schema

- [ ] `.github/agents/agent-frontmatter.schema.json` — JSON Schema, required + optional fields
- [ ] `scripts/validate-agent-frontmatter.py` — validator, exits non-zero on any failure
- [ ] `.github/workflows/validate-agent-frontmatter.yml` — CI hook, runs on PR
- [ ] Backfill: re-validate all 6 existing `.github/agents/*.agent.md` against schema

## AGENTS.md fix

- [ ] Update precedence table to add "loaded by" column
- [ ] Add worked example: Architect editing `apps/orchestrator/main.py`
- [ ] Reference `.github/instructions/` as live, not aspirational

## Copilot instructions split

- [ ] Move Python rules from `.github/copilot-instructions.md` → `.github/instructions/python.instructions.md`
- [ ] Move TypeScript rules from `.github/copilot-instructions.md` → `.github/instructions/typescript.instructions.md`
- [ ] Leave commit-message + Plan Mode rules in `.github/copilot-instructions.md` (they're language-agnostic)
- [ ] Add "see also" footer linking to `.github/instructions/`

## SessionStart bundle injection

- [ ] `.github/hooks/scripts/session-start.sh` — read agent file's `bundle_subscriptions:`, fetch bundles via `ledger.get_bundle` MCP tool, inject as session context
- [ ] `.github/hooks/scripts/session-start.ps1` — PowerShell parity
- [ ] Update `.github/hooks/session-start.json` to declare 5s timeout + fail-open

## Tests

- [ ] `tests/test_agent_frontmatter_validator.py::test_required_fields_present`
- [ ] `tests/test_agent_frontmatter_validator.py::test_missing_field_rejected`
- [ ] `tests/test_agent_frontmatter_validator.py::test_unknown_tool_flagged`
- [ ] `tests/test_agent_frontmatter_validator.py::test_bundle_dept_must_exist`
- [ ] `tests/test_agent_frontmatter_validator.py::test_model_in_prompt_library_allowlist`
- [ ] `tests/test_agent_frontmatter_validator.py::test_filename_matches_name_field`
- [ ] `tests/test_agent_frontmatter_validator.py::test_ledger_writes_entry_type_valid`
- [ ] `tests/test_agent_frontmatter_validator.py::test_all_six_existing_agents_pass`

## Verification (definition of done)

- [ ] `openspec validate add-agent-instructions-hierarchy --strict` passes
- [ ] `scripts/validate-agent-frontmatter.py` passes against all `.github/agents/*.agent.md`
- [ ] `.github/instructions/` directory exists with 3 path-scoped files
- [ ] AGENTS.md "loaded by" column accurately maps each level → runtime
- [ ] CI workflow blocks PRs that introduce malformed agent frontmatter
- [ ] Worked-example session in AGENTS.md confirmed by manual VS Code + Copilot test
