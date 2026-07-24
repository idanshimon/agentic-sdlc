# Changelog

All notable changes to the v0.7 reference design.

## [0.10.0] — 2026-07-24 — real-LLM end-to-end, run-lifecycle stability, codegen governance

The pipeline now runs end-to-end on a real LLM in the v07 resource group and
opens real delivery PRs — and this release makes that path actually complete and
adoptable, not just reachable. Three themes, each a strict-validated OpenSpec
change.

### Added — wire real LLM providers (openspec: `wire-real-llm-providers`)

- Keyless Managed-Identity auth in `providers/aoai.py` (`DefaultAzureCredential`
  + Cognitive Services bearer token) — no API key required *(e291d6b)*.
- `REQUIRE_LIVE_PROVIDERS` flag: fail-closed on provider errors without the
  production auth lockdown, so a demo can run real models with `AUTH_MODE=disabled`
  *(e291d6b)*.
- Ledger query cap 200 → 2000; graph views fetch 1000 with an honest cap notice
  *(7581829)*. One-shot team backfill gated behind `ENABLE_TEAM_BACKFILL`
  *(1869783)*.
- Verified live: real GPT-4.1 producing multi-KB code at real cost across
  eligibility, vitals-streaming, and payer-contract (Neo4j) PRDs.

### Added — stabilize run lifecycle execution (openspec: `stabilize-run-lifecycle-execution`)

- Strong-referenced `_spawn` helper so pipeline driver tasks are not
  garbage-collected mid-run *(dccffc4)*.
- `_push` now persists orchestrator-emitted events into `run.events`, making
  driver failures + tracebacks observable via the API *(dc03b49, 16241ba)*.
- Recovery lease made CAS-race-resistant — survives the owner's own per-event
  writes, loses the lease only on a real ownership change; enables safe
  horizontal scale *(e172ac4, 94be94e, 3db1310)*.
- Approve/finalize rehydrate the run from Cosmos on cache-miss; gate release on a
  rehydrated run spawns a continuation; single-driver-per-segment gate flow
  *(a47c977, 160db7f, c01eb16, 9460029)*.
- Durable run doc trims oversized code payloads (live run keeps full artifacts)
  *(8e5528e)*.

### Added — harden codegen governance quality (openspec: `harden-codegen-governance-quality`)

- **Context-scoped PHI-001**: new declarative `context_pattern` +
  `safe_wrapper_pattern` bundle-rule fields, so the rule flags cleartext PHI
  *logging* without blocking legitimate domain field/param names; one matcher
  shared by the CI lane and the pipeline review *(17191bd, a13d4f5)*.
- **Static runnability gate**: review-scan now statically proves generated code
  parses and every name resolves (symtable-based, module + function scope), so
  unrunnable code (missing `import os`, `TestClient`, `time`) is a first-class
  BLOCK *(07b0155, 72e9f4b)*.
- **Delivered-layout prompts**: codegen delivers `src/main.py`, tests import
  `from main import app` (was a broken `from app import app`) — delivered suites
  are now collectable *(07b0155, 72e9f4b)*.
- PHI-safe codegen prompt so generated healthcare code redacts by construction
  *(b6cfca4)*.

### Fixed

- Silent codegen→review_scan run failures — root cause was `_push` never
  persisting driver events (hid the traceback), compounded by GC'd driver tasks
  and the lease CAS race. All three fixed.
- PHI-001 blocking 100% of legitimate healthcare code (blanket token match).
- Delivered test suites failing at collection (`ModuleNotFoundError: app`).
- Generated code shipping missing imports (now blocked by the runnability gate).

### Tests

- 440 orchestrator tests pass (was 427 at session start; +13).
- New test files: `test_phi001_context_scoped.py`, `test_static_runnability.py`,
  `test_lease_cas_race.py`.

### Deployed (all services green)

- `ca-orchestrator-vnet--0000040` (real AOAI, runnability gate, CAS-safe lease,
  min=1/max=3 with `ENABLE_RECOVERY_LEASE=1`).
- `ca-ledger-mcp-vnet--0000004`, `ca-ledger-ui-vnet--0000028` unchanged.

### Openspec status (strict-validated this session)

- ✅ `wire-real-llm-providers` — tasks 100% complete
- ✅ `stabilize-run-lifecycle-execution` — tasks 100% complete
- ✅ `harden-codegen-governance-quality` — tasks 100% complete

### Known follow-ons

- Generated code still emits Pydantic v1 idioms (`@validator`, `.dict()`,
  `Field(example=)`) — deprecation warnings, not failures; a prompt note would fix.
- Business-logic test quality varies (a delivered suite may have a slow-SLA or
  logic test that fails); the runnability gate guarantees the code *runs*, not
  that every generated contract test passes.
- Databricks-Claude routing for architect/codegen remains unimplemented.

## [0.9.0] — 2026-07-12 — decision graph views (Map / Lineage / Run Flow)

The `/decisions` table and activity feed read the record beautifully but cannot
answer three *structural* questions about the ledger as a whole: which standards
rule is doing the most work, whether the system is actually learning (autopilot
reusing human precedents), and how a single run flowed stage by stage. All three
answers were latent in fields the ledger already stores (`precedent_refs`,
`references_entry_id`, `bundle_refs`, `run_id`, `ambiguity_class`) but were never
visualized. Added **three read-only graph lenses** over the same ledger read,
additive to and non-destructive of the table/feed:

- **Decision Map** (`/decisions/graph`) — cross-run governance network. Bundles
  are hubs sized by citation count (the "which rule works hardest" answer at a
  glance); decisions cluster by ambiguity class; the learning-loop and teaching
  edges are visually distinct. Edge-family filter chips + a flag-focus control
  keep it legible instead of a hairball.
- **Precedent Lineage** (`/decisions/lineage`) — the learning loop as a
  deterministic left→right dagre DAG. Human precedents are roots on the left;
  each autopilot reuse hop moves right, so the human→agent teaching loop reads as
  a timeline. This is the headline view.
- **Run Flow** (`/decisions/runflow`) — one run's decisions laid out under their
  pipeline stage (or ambiguity bucket), for engineers debugging a run.

Every graph node click-throughs to `/decisions#decision-<id>` (the existing
drill-down anchor), all three auto-refresh on the same `useDecisions` poll, and
none of them write. Built on one shared, pure graph-builder engine
(`src/lib/graph/`) covered by 22 unit tests; layouts are deterministic so audit
screenshots reproduce. New deps: `@xyflow/react`, `@dagrejs/dagre`. Specified in
the `add-decision-graph-views` change.

## [0.8.0] — 2026-07-12 — legible Decisions surface for dev leaders

The `/decisions` page led with an internal lifecycle grid (raw entry GUIDs and
`proposed·missing / required·missing` phase chips) that non-specialist leaders
could not read, and it pushed the actually-useful clickable ledger table below
the fold. Replaced it with a **plain-language "What's been happening" activity
feed**: one human sentence per entry (who decided what, agent-on-autopilot vs. a
person, and when), a **learning-event count** that surfaces where humans taught
the system (feedback / flag / pause) or where autopilot reused a prior human
decision, and **click-through** on every row — activating a row deep-links to
`#decision-<id>` and expands + scrolls the full record (rationale, provenance,
model, cost, PHI, bundle citations, teaching signals) in the table below. The
feed derives only from ledger entries and never invents actors or outcomes.
Covered by `decision-activity.test.ts` (classifier + sentence builder) and the
`redesign-decision-lifecycle-control-plane` spec delta.

## [0.7.22] — 2026-06-23 — config editing plane + real delivery PRs (no more fakes)

Four threads shipped. (1) The **config editing plane** turned three display-only
surfaces into real editors: the agent→bundle relationship now drives data
(`bundle_refs` on every decision), and Agents / Bundles / Prompts each open a
**governed PR** on save instead of mutating live (bundles were read-only; the
agents editor was localStorage-only; prompts was a GitHub deeplink). (2) The
**deliver stage opens real GitHub PRs** — the old path emitted two `Math.random()`
URLs at a repo that doesn't exist (demo runs) or a fabricated `dev.azure.com`
fallback (real runs); both 404'd. Now it opens a real PR via the Git Data API or
emits an honest "PR not opened: <reason>" — never a fake. Proven live end-to-end:
a real autopilot run through every gate opened a real PR with all four artifacts.
(3) **Decision lineage visualization** surfaces the teaching-loop graph in the
decisions table. (4) The **Prompt Library** was redesigned from an admin table
into a pipeline-flow card grid (and fixed off-system design tokens that were the
real cause of its unpolished look).

### Added — Config editing plane (openspec: `add-config-editing-plane`)

- `apps/orchestrator/agent_bundles.py` — parses `.github/agents/*.agent.md`, validates declared `bundle_subscriptions` against real `standards-bundles/<dept>` dirs (strips inline comments, rejects prose like `all (read-only)`), exposes `bundles_for_stage()`. The relationship now **drives data**: `LedgerEntry.bundle_refs` is stamped at both decision write sites with the deciding agent's bundles. 9 tests
- `apps/orchestrator/config_writer.py` — shared governed PR write-back via the **GitHub REST API** (Contents + Pulls). Path allowlist (`.github/agents`, `standards-bundles`, `prompts`); absolute + `..` escapes refused server-side. 11 tests
- `POST /api/config/{agents,bundles,prompts}/save` → opens a PR, returns the URL. `POST /api/config/reload` → hot-reload agents/prompts only (bundles are **PR-only** — live-editing the compliance standard would bypass committee review). 8 endpoint tests
- **REST, not git/gh subprocess:** deploy verification proved the container is a bare file tree (`COPY`, no `.git`/`git`/`gh`) — the git-subprocess version returned `[Errno 2]`. REST needs only a token. Verified end-to-end: a real PR opened + closed via the REST path
- **Honest by default:** no token → clean 422 → UI shows "Saved locally — PR not opened". No code path fabricates a PR URL. `GH_TOKEN` wired as a Container App secret
- UI: `VersionedEditor.onPullRequest` hook (local save + PR, honest toasts); Agents editor → `saveAgentConfig` (was localStorage); Bundles "Edit rules" editor with a governance banner (was read-only); Prompt Library in-app editor → next-version draft (`vN+1`, status: draft) → PR

### Added — Real delivery PRs (openspec: `swap-deliver-ado-to-github`, reconciled)

- `apps/orchestrator/deliver_pr.py` — opens a real GitHub PR via the Git Data API (blobs → tree → commit → branch → PR), all run artifacts (`src/main.py`, `tests/test_main.py`, `docs/architecture.md`, `decisions.md`) in **one atomic commit** on branch `agentic/<run-id>`. 8 tests
- **Repeatable-demo features:** repo resolution (`DELIVER_TARGET_REPO`, else `<owner>/agentic-sdlc-delivery`), auto-create missing repo (`DELIVER_AUTO_CREATE`), self-bootstrap an empty repo (seed README so a fresh repo just works), delivery-specific `DELIVER_GH_TOKEN`. Idempotent: tolerates branch-exists (force-update) and PR-exists (returns existing)
- `scripts/reset_deliveries.py` — closes open `agentic/*` PRs + deletes their branches for a clean slate between demos (dry-run by default)
- **Proven live:** autopilot run `1de0f1a2` through resolver gate + design gate → opened `idanshimon/agentic-sdlc-delivery/pull/2` with all four artifacts. `delivery_status: delivered`
- **Spec reconciliation:** the change was a DRAFT specifying GitHub App auth + forbidding PATs. Shipped reality is PAT auth via REST. Spec updated honestly (token auth + the never-fabricate-a-URL guarantee + repo bootstrap); App auth / reviewer assignment / `gh_audit_xref` / per-team overrides remain unbuilt forward design

### Added — Decision lineage visualization

- The decisions table surfaces the teaching-loop graph: which human decisions taught precedent and which autopilot decisions reused it (`b01b760`)

### Changed — Prompt Library redesign + run-stream honesty

- `prompts/page.tsx` rebuilt as a pipeline-flow card grid (one card per stage, in run order) instead of an admin table; fixed off-system design tokens (`--surface-2`, `--text-primary`) that didn't exist and were the real cause of the unpolished render. Verified via CDP screenshot + vision QA on the live deploy
- Run event stream renders the deliver event honestly: a real "View pull request" link when `pr_url` is present, an amber "PR not opened — <reason>" when not — no raw fabricated-URL JSON dump

### Fixed — UI

- Sticky sidebar (nav no longer scrolls away when switching tabs); Cards-view search now filters (was showing "4 of 10" but rendering all)

### Infra / ops

- Deploys: `orchestrator:deliver-v22` (rev 0000026), `ledger-insights-ui:747e9a7` (rev 0000029). Secrets: `gh-config-token`, `deliver-gh-token`. Env: `DELIVER_TARGET_REPO`, `DELIVER_AUTO_CREATE=1`
- Commits: `a965e7a` `f7c31e4` `9ec6504` `aa7df86` `b01b760` `efe02e2` `3561efd` `15d45a6` `747e9a7` `1153577`

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
