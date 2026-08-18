# Tasks: add-multi-persona-prompt-library

> **Status: 100% shipped in v0.7.20** (2026-06-16). All sections 1-7 complete and verified live.
> Section 4 went beyond read-only first cut — full editor with GitHub PR opening shipped (originally
> scoped to follow-on change). See "Delta from original plan" at bottom.

## 1 — YAML storage + initial migration

- [x] 1.1 Create `prompts/` directory at monorepo root  *(commit acc5420)*
- [x] 1.2 Author `prompts/global/<stage>/v1.yaml` for all 6 stages  *(commit acc5420; AST-extracted, byte-correct UTF-8)*
- [x] 1.3 Add `prompts/` to `.dockerignore` whitelist for orchestrator + ledger-mcp images  *(commit 911dd79 — caught by build failure ch1a; `!prompts` rule)*
- [x] 1.4 Add `COPY prompts ./prompts` to `apps/orchestrator/Dockerfile.repo-root`  *(commit 911dd79)*
- [x] 1.5 Pytest regression: byte-exact YAML match  *(commit acc5420 + f83c343 — test evolved from matching legacy dataclass strings to matching production inline strings as stages migrated)*

## 2 — Backend resolver

- [x] 2.1 Pydantic model `PromptFile` in `apps/orchestrator/prompt_library_v2.py`  *(commit acc5420 — chose `prompt_library_v2.py` not `prompts_loader.py` to keep namespace alignment with legacy `prompt_library.py`)*
- [x] 2.2 `load_prompts(root: Path) → PromptCatalog`  *(commit acc5420)*
- [x] 2.3 `PromptCatalog.resolve(stage, model, team) → ResolveResult(template, chain)`  *(commit acc5420)*
- [x] 2.4 Chain shape: `list[{scope, owner_persona, prompt_id, version, git_sha, matched, reason}]`  *(commit acc5420)*
- [x] 2.5 Backward-compat shim — `prompt_library.py` legacy callers continue to work; new callers use `prompt_library_v2` directly via `get_prompt_catalog()` singleton  *(commit f83c343 + da051b2)*
- [x] 2.6 Pytest: 15 unit tests covering inheritance, fail-fast on misconfig, model variant, unknown stage, malformed YAML rejected  *(commit acc5420 — `test_prompt_library_v2.py` 15 cases)*
- [x] 2.7 Pytest fixture seeds 3-level tree (global → persona → team) and asserts resolve returns the team variant with chain ordered correctly  *(commit acc5420)*

## 3 — Ledger integration

- [x] 3.1 Extend `LedgerEntry.prompt_resolution_path: Optional[list[dict[str, Any]]] = None`  *(commit da051b2)*
- [x] 3.2 Wire 5 of 6 stages to `catalog.resolve()` + stash chain on `run.prompt_chain_by_stage[stage]`  *(commits f83c343 + da051b2 — assessor, architect, test_plan, codegen-impl, codegen-tests. ingest + review_scan defer because they assemble prompts from f-strings, not stage-keyed templates; out of scope of v1)*
- [x] 3.3 Pytest: 3 regression tests for chain pinning  *(commit 911dd79 — `test_prompt_chain_in_ledger.py`)*
- [x] 3.4 Both ledger writers (autopilot `_drive` + per-card `/approve`) pin chain into LedgerEntry  *(commit 911dd79)*
- [x] 3.5 Live verification: run `b3a73554` returned `prompt_resolution_path` populated with `[✓] scope=global · prompt_id=assessor-global · v=v1 · git_sha=MIGRATION_PROD_PROMPTS · owner=pm`  *(verified 2026-06-16)*

## 4 — UI: catalog browse (read-only first cut)

- [x] 4.1 Rewrote `/prompts` page from localStorage-seed-based to live catalog-backed  *(commit 09200d5)*
- [x] 4.2 KPI strip + sortable table + persona-colored badges + version pills + byte counts  *(commit 09200d5)*
- [x] 4.3 Click row → slide-out drawer with full template + frontmatter + all versions  *(commit 09200d5 — chose drawer over `/prompts/[scope]/[persona]/[stage]/[id]` dynamic route for faster UX, less routing overhead)*
- [x] 4.4 Version dropdown loads any historical version  *(commit 09200d5)*
- [x] 4.5 Inline template + frontmatter rendering in drawer (no separate tabs)  *(commit 09200d5 — drawer renders everything inline; tabs felt over-engineered for the 6-prompt-today reality)*
- [x] 4.6 NEW API routes `/api/prompts/catalog` + `/api/prompts/{prompt_id}` on orchestrator  *(commit 09200d5 — 5 unit tests in `test_prompt_catalog_endpoints.py`)*

## 5 — UI: inheritance graph

- [x] 5.1 NEW component `prompt-chain-badge.tsx` with 3 variants (inline / card / full)  *(commit 6bc3621)*
- [x] 5.2 Full variant renders the chain visually for any decision: team → persona → global, matched scope highlighted, rejection reasons inline  *(commit 6bc3621)*
- [x] 5.3 Renders on every DecisionCard + decision-table drilldown row, not just /prompts page  *(commit 6bc3621 — broader surface than originally planned)*

## 6 — Persona-aware filter in /prompts

- [x] 6.1 Persona / stage / scope filter pills on /prompts page  *(commit 09200d5)*
- [x] 6.2 Filter pills reduce visible rows; Clear filters resets all  *(commit 09200d5)*

## 7 — Verification

- [x] 7.1 `openspec validate add-multi-persona-prompt-library --strict` → Valid  *(verified at commit 43d233e; re-run after tasks update)*
- [x] 7.2 Ship orchestrator + UI images via ACR  *(orchestrator catalog-api-v8 + UI prompt-catalog-v8, deployed as ca-orchestrator--0000008 + ca-ledger-ui--0000016)*
- [x] 7.3 Submit fresh run via live submit path  *(verified runs: `b3a73554`, `404b4fc1`, `9c3836ed` among others)*
- [x] 7.4 Confirm ledger entries carry `prompt_resolution_path` showing global chain  *(verified 5/5 entries on run `404b4fc1` via `/api/runs/{id}/ledger`)*
- [x] 7.5 `/prompts` UI shows all 6 migrated prompts (+1 codegen-tests added as 7th when codegen was split) with read-only browse  *(verified live on ca-ledger-ui--0000022)*

## 8 — Out of scope for this change (DELTA from original)

The original "out of scope" list shrank during execution. Re-categorized:

- ~~Editor + GitHub PR opening — filed as `add-prompt-editor-github-pr-flow`~~ → **SHIPPED in this change** (commit 09200d5). "Edit + open PR" button on drawer deep-links to `https://github.com/idanshimon/agentic-sdlc/edit/main/prompts/<scope>/<stage>/<version>.yaml`. GitHub web editor + PR opening loop works without orchestrator-side PR API code — that's a future RBAC + change-control feature.
- Hot reload — still Phase 2 follow-on; current pattern is "every prompt change is a versioned image tag; auditable; rebuild required."
- Auth/RBAC on who can author — still Phase 8 / production posture (CODEOWNERS-only today).
- Per-team prompt files in `prompts/team/<team>/...` — still YAGNI; schema supports it but no team has needed override yet.

## Delta from original plan

What this change shipped beyond the original v1 scope:

1. **Edit + open PR flow in drawer** — originally deferred to a separate change, shipped as part of v1 because the GitHub web editor deep-link required zero backend work and made the whole loop demoable in one commit.
2. **Chain rendering on every decision card** (not just on /prompts) — Phase 5 closes the user-facing audit loop. Originally Phase 5 was scoped to /prompts page only; we surfaced the chain on /decisions instead because that's where operators ask "which prompt produced this?"
3. **5 stages wired** (assessor, architect, test_plan, codegen-impl, codegen-tests) — original plan didn't enumerate which stages; production audit found 5 of 6 stages had stage-keyed prompts ready to migrate; ingest + review_scan use f-string-assembled prompts that defer.
4. **fail-fast loader** with `PromptValidationError` instead of silent stub fallback — caught the `/app/prompts` deploy gap immediately on first deployment (run `40f34d2a` crashed with the exact error, which is the correct behavior — better to fail loud than silent-ship the wrong prompt).

## Definition of done — verified met 2026-06-16

A `/prompts` browse shows 7 prompts (6 stages + codegen-tests split) in the
global scope, each with a stable `prompt_id`, immutable `v1` version, owner
persona badge. Every new run's ledger entries pin the `prompt_id` + `version`
+ `git_sha` they used. Resolving "what prompt did run `404b4fc1` use" is a
1-click lookup on `/decisions` → expand → see chain badge with click-through
to /prompts catalog.

Operator can edit any prompt via the drawer's "Edit + open PR" button, which
opens the GitHub web editor with the YAML pre-loaded. Commit + PR + persona
reviewer (CODEOWNERS) approval + merge + ACR rebuild = new version shipped.
End-to-end loop verified clickable on live dashboard.
