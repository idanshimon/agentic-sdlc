# Changelog

All notable changes to the v0.7 reference design.

## [0.7.20] — 2026-06-16 — operator-grade pipeline workflow + multi-persona prompt library

Two openspec changes shipped end-to-end in a single session (20 commits, 4 service
deploys). The pipeline now genuinely runs in production posture: real LLM calls,
real Cosmos persistence, real operator UX, real audit chain visible on every
decision.

### Added — Multi-persona prompt library (openspec: `add-multi-persona-prompt-library`)

- `prompts/global/<stage>/v1.yaml` × 7 — YAML-backed prompts replace dataclass strings; persona-owned (pm / architect / qa / sre / seceng); versioned in git with frontmatter (`prompt_id`, `version`, `status`, `scope`, `owner_persona`, `git_sha`, `template`, etc.)
- `apps/orchestrator/prompt_library_v2.py` — `PromptCatalog` + `resolve(stage, model, team)` with inheritance walk (run → team → persona → global); fail-fast on missing prompts or malformed YAML
- `LedgerEntry.prompt_resolution_path` — every decision in Cosmos pins the full chain that produced it; visible at `/api/runs/{id}/ledger`
- `/api/prompts/catalog` + `/api/prompts/{prompt_id}` orchestrator endpoints — surface the catalog with template metadata
- `/prompts` page rewritten — live catalog browse with KPI strip, persona+stage+scope filters, sortable table, drawer with full template + version history, "Edit + open PR" deep-link to GitHub web editor
- `<PromptChainBadge>` component — three render variants (inline / card / full); appears on every DecisionCard + drilldown
- 5 of 6 stages wired (assessor, architect, test_plan, codegen-impl, codegen-tests); ingest + review_scan defer (f-string-assembled prompts)
- 15 unit tests for the resolver + 3 for chain pinning + 5 for catalog endpoints

### Added — Operator-grade pipeline workflow (openspec: `ship-operator-grade-pipeline-workflow`)

- Per-event Cosmos persistence in `_push(run_id, ev)` — pod restarts (revision rollover, OOM, scale-to-zero) no longer leave zombie runs at the ingest snapshot. Failure-tolerant: log + continue.
- `POST /api/admin/runs/{id}/mark_failed` — one-off cleanup endpoint for pre-fix zombies (8/8 cleaned successfully)
- `POST /api/runs/{id}/finalize` — explicit gate close for resolver after per-card approves
- `GET /api/runs/{id}/ledger` — run-scoped ledger read proxy bypassing per-token RBAC
- `<ResolverGate>` rewritten — per-card approve loop + finalize, per-card "Use this" buttons for option override
- `<DesignReviewGate>` — Gate 2 operator surface with Approve / Reject + collapsible architecture preview
- `useRunStream` — SSE event invalidates React Query + dedup by `(stage, status, ts)` + auto-reconnect on revision-swap drops
- Sticky "needs your attention" banner on `/runs/{id}` when paused at any gate, with smooth-scroll Jump-to-gate
- `<ArtifactView>` rewritten — line numbers, Copy + Download buttons, light syntax color, collapse-to-200-lines
- `/api/economics` Next.js route — aggregates ledger entries via `lib/economics` pure functions; populates the previously-empty `/economics` page with real KPIs
- `/decisions` team filter — completes multi-team UX (`/runs/new` + `/runs` already had it)

### Fixed
- `LedgerEntry.entry_type` schema drift with ledger-core — per-card `/approve` returned HTTP 500 with AttributeError. Default `entry_type: str = "runtime"` + 3 regression tests.
- Resolver gate parsing: UI expected `(assessor, awaiting_gate)` but orchestrator emits `(resolver, gate_open)` — matcher accepts both shapes
- Resolver gate approve shape mismatch: UI sent `{decision, rationale}` but backend requires `GateDecision` pydantic shape — rewrote to per-card loop
- DesignReviewGate 409: orchestrator's audit-safety guard rejected gate-level approves with synthetic card_id — extended is-gate-level detection to accept `decision.gate != "resolver"`
- Sample PRD 500s on `/samples/<file>.md` — Next.js standalone static-file bug; worked around with `/api/samples/[file]/route.ts` server-side `fs.readFile`
- Event timestamps rendered "Invalid Date" — `eventTimeLabel(ev)` reads `ev.ts ?? ev.timestamp` for defense-in-depth

### Tests
- 137/137 orchestrator tests pass (was 105 at session start; +32 across all phases)
- 5 new test files: `test_approve_entry_type_drift.py`, `test_prompt_library_v2.py`, `test_prompt_chain_in_ledger.py`, `test_run_ledger_endpoint.py`, `test_prompt_catalog_endpoints.py`, `test_design_review_approve.py`
- UI `pnpm tsc --noEmit` clean throughout

### Deployed (all four services green)
- `ca-orchestrator--0000010` = `orchestrator:zombie-cleanup-v11`
- `ca-ledger-ui--0000022` = `ledger-insights-ui:phase7-8-economics-team-v14`
- `ca-ledger-mcp--0000003` = `decision-ledger-mcp:bundles-baked-v1`
- `ca-sbm-cardiology-alerts--0000001` = pipeline-emitted FastAPI

### Openspec status (strict-validated this session)
- ✅ `add-multi-persona-prompt-library` — tasks marked 100% complete
- ✅ `ship-operator-grade-pipeline-workflow` (new, retroactive) — tasks marked 100% complete
- ⬜ `add-cosmos-private-endpoint-v07` (durable Cosmos firewall fix; deferred)
- ⬜ `add-pipeline-doctor`, `add-standards-bundles`, `add-agent-hq-integration`, etc. (broader v0.7 ambitions; tracked separately)

### Known follow-ons
- Per-event-save debounce (correctness wins over cost today; production-scale should batch 6x)
- RBAC on admin endpoints (`/api/admin/runs/{id}/mark_failed` is one-off; v1.0 needs proper team-scoped admin)
- Hot-reload prompts (every change is still a versioned image tag; auditable; deferred)
- `ingest` and `review_scan` stage wirings (f-string-assembled prompts that defer until refactored to stage-keyed templates)

## [0.7.0-rc1] — 2026-06-05 — initial v0.7 scaffold

The four-plane architecture cut from v0.6 lessons.

### Added
- Repo skeleton at `~/projects/msft/agentic-sdlc/` (clean break from `cust/hca/agentic-sdlc`)
- `AGENTS.md` repo-wide guardrails
- `.github/copilot-instructions.md`
- OpenSpec config with strict-validation rules
- Master proposal `openspec/changes/master-v07-four-plane-architecture/`
- README.md with audience callout, four-plane diagram, layout map, honest disclaimers
- MIT LICENSE

### Background
v0.6 (HCA Nashville workshop reference, line `0.6.7` `bfae9d9`) proved that
**governance is the differentiator**: Decision Ledger as audit spine, HITL
gates at ambiguity classes, cost-per-decision dashboards. The two limits that
drove v0.7:

1. Ledger only saw orchestrator pipeline runs (~20% of agentic activity).
2. Department standards lived as scattered prompts and APIM policies; rule
   changes meant code changes; no committee process.

v0.7 closes both via Agent HQ ledger coverage + standards-bundles plane +
Pipeline Doctor.

### Ported from v0.6 (selectively)
- Orchestrator app (FastAPI, 9 stages, providers, prompt library)
- Ledger module (extracted to `packages/ledger-core/`, schema extended)
- Resolver UI → renamed `ledger-insights-ui` (HITL gate panel removed)
- OpenSpec proposals: prompt-library, telemetry-dashboard, vnet-private-endpoints

### Discarded from v0.6
- ADO-only deliver path (GH default; ADO opt-in via `deliver_provider` flag)
- Standalone HITL gate UI (Plan Mode + chat bridges replace it)
