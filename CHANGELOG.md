# Changelog

All notable changes to the v0.7 reference design.

## [0.7.21] — 2026-06-20 — graduated-autonomy tier-2 (hard-gate) + operator agency + self-heal MVP

Two threads shipped this session. (1) The **self-heal cowork MVP** — a pluggable,
config-selectable brain + executor (both GitHub-Copilot and Azure-native paths,
no lock-in) with a decision-independent safety kernel; the 3-entry heal chain
(proposed → decided → executed) persists to Cosmos and was verified live. (2) The
**3-tier graduated-autonomy model** completed at the resolver gate: operators can
now accept / swap / write-their-own resolutions with immediate on-page feedback,
and PHI/auth classes are hard-gated — server-refused (409) from any bulk
soft-approve. Plus two teaching-loop bug fixes and a decisions-page readability
pass.

### Added — Self-heal cowork MVP (openspec: `add-self-heal-cowork`)

- `apps/orchestrator/heal.py` — `HealSession`/`HealProposal`/`HealDecision`/`HealExecution` (heal_id ties the chain) + `validate_heal_action()` safety kernel: PHI/auth → ESCALATE, deny → BLOCK, else ALLOW_WITH_APPROVAL (nothing auto-applies)
- `apps/orchestrator/heal_runtime.py` — pluggable `HealBrain` + `HealExecutor` protocols, config-selected via `HEAL_BRAIN` / `HEAL_EXECUTOR` (azure | github | stub). GitHubExecutor (gh→PR), AzureExecutor (real rerun + honest code-PR gap), Stub (works offline). Brain and executor independently swappable — **both paths kept, configurable, no lock-in**
- `POST /api/runs/{id}/heal`, `GET /api/heal/{id}`, `POST /api/heal/{id}/approve` — human-invoked only; approve hard-refuses BLOCK/ESCALATE even when approved=true
- `LedgerEntry.heal_id` — ties the `heal_proposed → heal_decided → heal_executed` chain; verified persisting to Cosmos live
- `HEAL_ACTIONS_ENABLED` master flag (false → read-only). 15 kernel tests + 9 loop tests
- Fixed: orchestrator was writing heal entries against the wrong `LedgerEntry` model (missing card_id/ambiguity_class/decision_kind) — added heal fields + defaults so the chain persists

### Added — Graduated-autonomy tier-2 + operator agency (openspec: `add-graduated-autonomy-tier2`)

- **Tier-2 hard-gate (server-enforced):** `HARD_GATE_CLASSES` (config.py) defaults to `INVARIANT_CLASSES`; env extends but can never shrink the PHI/auth floor. `/approve` returns **409** on `approval_path: "bulk"` for a hard-gated card — a curl cannot rubber-stamp PHI. `GateDecision.approval_path`, `AmbiguityCard.is_hard_gated` (stamped at assessor time), `GET /api/config/hard-gate-classes`. Verified live: bulk→409, individual→200. 8 tests
- **Operator agency (resolver-gate.tsx):** "Use this" now visibly locks the card to a "Decided — change" row + "N of M decided" counter (fixes the "toast but nothing changes" bug); edit-recommendation + write-your-own textarea → `decision_kind: swap` + verbatim text, with a PHI soft-warn; "Approve all" skips hard-gated + decided cards and shows the remaining-count; 🔒 EXPLICIT DECISION REQUIRED badge on hard-gated cards. 9 logic tests
- Completes the **3-tier model**: Tier 0 autopilot (refuses invariants) · Tier 1 soft-approve (now skips hard-gated) · Tier 2 hard-gate (individual, attributed, on the record)

### Fixed — Teaching loop (now PROVEN end-to-end, live 2026-06-21)

The operator teaching loop (swap a resolution on run A → autopilot auto-resolves
the same ambiguity on run B) is closed and proven live. It took THREE stacked fixes:

- **Unstable slot key:** `slot_value_hash` was `_hash(title + detail)` (LLM prose, varies run-to-run) → precedent never matched across runs. New `_slot_key(class, prd_section)` keys on stable semantic identity. Verified: same PRD → same hash across runs. 6 tests
- **`SELECT TOP 1` hygiene:** `find_precedent` dropped `SELECT TOP 1 … ORDER BY` for `SELECT *` + take-first-in-Python. Correct hygiene — but NOT the actual killer (the loop still failed after it). 5 query-shape tests
- **THE real killer — cross-model null deserialization throw:** the orchestrator's `LedgerEntry` gained optional heal fields `decision`/`rationale` (`Optional[str]=None`), so every swap serialized them as JSON null. `find_precedent` reads the row → `from_legacy_v06_dict` → `ledger_core.LedgerEntry`, which requires non-null strings → ValidationError → swallowed by `find_precedent`'s except → returned None. Every operator swap was silently unreadable as precedent. Fixed in `from_legacy_v06_dict` (drop null `decision`/`rationale`, treat null as absent). Same bug-class as the heal-chain persistence bug — two competing `LedgerEntry` models with different field contracts. +1 regression test pinning the exact null shape
- **Proven live:** team `teachFINAL-017155`, run A `495892ab` (operator swaps sla-binding) → run B `c24c6794` auto-resolved that exact card (`autopilot_decisions=1`) while PHI stayed hard-gated. The full graduated-autonomy story in one run: agent auto-resolves what a human taught it; PHI never auto-resolves regardless

### Fixed — Decisions-page readability

- Teaching-signal rows read as "thumbs_up on <uuid>" → `teachingSignalSummary()` renders plain-English title+detail per kind ("Marked 'helpful' — operator@demo …", "Flagged as wrong — Reason: …", "Autopilot paused for '<class>'")
- Removed the dead `↳ refers to <uuid>` line and the dead `<Link href="/prompts">` wrappers (catalog isn't deep-linkable) → informational text

### Infra / ops

- **Cosmos `publicNetworkAccess` auto-reverts to Disabled** — root-caused to Microsoft Defender for Cloud (`ASC DataProtection` policy set), not a fluke. Documented; the durable fix is `add-cosmos-private-endpoint-v07` (VNET + private endpoint). Writes during a Disabled window are silently lost (failure-tolerant ledger writes)
- Deploys: `orchestrator:teaching-loop-v18` (rev 0000018), `ledger-insights-ui:4838231` (rev 0000024)
- Commits: `498b7dc` `518576a` `2e5f549` `0071b56` `7550dfa` `2a20e72` `97bcc45` `4838231` `ca56916`

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
