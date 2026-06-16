# Tasks: add-multi-persona-prompt-library

## 1 — YAML storage + initial migration

- [ ] 1.1 Create `prompts/` directory at monorepo root
- [ ] 1.2 Author `prompts/global/<stage>/v1.yaml` for all 6 stages, content identical to current dataclass strings (ingest, assessor, architect, test_plan, codegen, review_scan)
- [ ] 1.3 Add `prompts/` to `.dockerignore` whitelist for orchestrator + ledger-mcp images
- [ ] 1.4 Add `COPY prompts ./prompts` to `apps/orchestrator/Dockerfile.repo-root`
- [ ] 1.5 Pytest regression: assert YAML template equals the original `INGEST_PROMPT` / `ASSESSOR_PROMPT` etc. byte-for-byte (no whitespace drift on migration)

## 2 — Backend resolver

- [ ] 2.1 Pydantic model `PromptFile` in `apps/orchestrator/prompts_loader.py` matching the schema in proposal.md
- [ ] 2.2 `load_prompts(root: Path) → PromptCatalog` — scans `prompts/**.yaml`, validates each file, returns a typed catalog
- [ ] 2.3 `PromptCatalog.resolve(stage, model, team, run_overrides) → (template, chain)` — implements inheritance walk
- [ ] 2.4 `chain` is `list[ResolutionStep]` where each step has `scope, owner_persona, prompt_id, version, git_sha, matched: bool`
- [ ] 2.5 `prompt_library.py` becomes a thin shim — `get_prompt(stage, model)` calls `resolve(stage, model, team=None, run_overrides={})` and returns the legacy dict shape
- [ ] 2.6 Pytest: 8 unit tests covering inheritance, fallback, audit chain shape, model variant lookup, unknown stage error, malformed YAML rejected at load time
- [ ] 2.7 Pytest fixture seeds a 3-level prompt tree (global → persona → team) and asserts resolve returns the team variant with chain=[team, persona, global]

## 3 — Ledger integration

- [ ] 3.1 Extend `apps/orchestrator/models.py::LedgerEntry` with `prompt_resolution_path: list[dict] | None = None`
- [ ] 3.2 Update `apps/orchestrator/_pipeline_stages.py` resolver helper to capture the chain and pass it to `ledger.write_decision`
- [ ] 3.3 Pytest: stage_assessor produces a ledger entry with `prompt_resolution_path` populated
- [ ] 3.4 Extend `apps/decision-ledger-mcp/src/schema.ts::RuntimeEntrySchema` with `prompt_resolution_path: z.array(z.record(z.unknown())).optional()`
- [ ] 3.5 Vitest: write a runtime entry with chain, read it back, assert it round-trips

## 4 — UI: catalog browse (read-only first cut)

- [ ] 4.1 Replace `apps/ledger-insights-ui/src/app/prompts/page.tsx` with a tree browse: scope → persona → stage → prompt
- [ ] 4.2 Each row shows current version, owner persona badge, last updated date, "view" button
- [ ] 4.3 Click prompt → `/prompts/[scope]/[persona]/[stage]/[promptId]/page.tsx` (NEW dynamic route)
- [ ] 4.4 Prompt detail page: full YAML rendered (read-only), version dropdown loads any historical version
- [ ] 4.5 Tabs: Template / Metadata / Inheritance Graph / Usage (which runs used this version)
- [ ] 4.6 NEW API route `/api/prompts/[id]/route.ts` — GET returns current + all versions; reads from `/app/prompts` at request time

## 5 — UI: inheritance graph

- [ ] 5.1 NEW component `apps/ledger-insights-ui/src/components/domain/prompt-inheritance-graph.tsx`
- [ ] 5.2 Renders the chain visually for any team+stage: global node → persona node → team node, with the matched node highlighted
- [ ] 5.3 Clicking any node loads that prompt YAML inline (no navigation)

## 6 — Persona-aware sidebar in /prompts

- [ ] 6.1 Top-of-page persona filter dropdown
- [ ] 6.2 Selecting a persona dims prompts not owned by that persona, helps the operator see "my surface"

## 7 — Verification

- [ ] 7.1 `openspec validate add-multi-persona-prompt-library --strict` → Valid
- [ ] 7.2 Ship orchestrator + ledger-mcp + UI images via ACR
- [ ] 7.3 Submit a fresh run with the live submit path
- [ ] 7.4 Confirm the resulting run's ledger entries each carry `prompt_resolution_path` showing the global chain (no team or persona overrides yet)
- [ ] 7.5 Confirm `/prompts` UI shows all 6 migrated prompts with read-only browse

## 8 — Out of scope for this change (filed separately)

- Editor + GitHub PR opening — filed as `add-prompt-editor-github-pr-flow`
- Hot reload — Phase 2 follow-on
- Auth/RBAC on who can author — Phase 8
- Per-team prompt files in `prompts/team/cardiology/...` — wait until a customer asks for it; the schema supports it but seeding speculatively violates YAGNI

## Definition of done

A `/prompts` browse shows 6 prompts in the global scope. Each has a stable
`prompt_id`, immutable `v1` version, owner persona badge. Each new run's
ledger entries pin the prompt_id + version + git_sha they used. Resolving
a future "what prompt did the 2026-06-17 run use" question is a 2-click
lookup, not a git archaeology dig.
