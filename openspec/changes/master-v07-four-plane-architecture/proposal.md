# Proposal: v0.7 four-plane governed agentic SDLC

> **Status:** DRAFT — open for review
> **Authors:** Idan Shimon
> **Date:** 2026-06-05
> **Capabilities touched:** pipeline, ledger, standards-bundles, pipeline-doctor, agent-hq-integration, telemetry, deployment
> **Supersedes:** v0.6.x architecture (single-orchestrator + ADO-only delivery)

## Why this exists

v0.6 of `agentic-sdlc-reference` proved the core premise: **governance is the
differentiator, not codegen quality.** A Decision Ledger captured every pipeline
stage decision; HITL gates intercepted ambiguity classes; cost-per-decision
replaced cost-per-token guesswork.

Two limits became visible during the HCA Nashville workshop (May 27-28, 2026):

1. **Coverage gap.** The Ledger only saw orchestrator pipeline runs. ~80% of an
   organization's agentic activity (engineer IDE sessions, coding-agent issue→PR
   flows, reviewer Copilot Code Review runs) was invisible to it. Compliance
   audit on 20% of the surface, blind on the rest.
2. **Standards rigidity.** Department rules (Architect, Security, Privacy,
   FinOps) lived as scattered prompts and APIM policies. Changing a rule meant
   editing code. There was no place where "Architect proposes a relaxed PHI
   rule" could be reviewed by Security + Privacy + Legal as a committee, with
   blast-radius classification, canary rollout, and a `meta` ledger entry.

v0.7 closes both gaps with a four-plane architecture:

```
Plane 1 — STANDARDS    Per-department versioned policy bundles, committee-reviewed
Plane 2 — PIPELINE     9-stage governed pipeline (heavy lane); GH delivery (no more ADO)
Plane 3 — LEDGER       The audit/governance spine, two entry types, exposed 3 ways
Plane 4 — AGENT HQ     Coding-agent + IDE + chat-bridge runtime lanes, ledger-covered
```

Plus one cross-plane component: **Pipeline Doctor** — a Foundry agent that reads
the ledger continuously, auto-fixes within bounded envelopes, and proposes
standards changes via PR for everything else.

## Goals (concrete, testable)

1. **Cover 100% of agentic activity** in the Decision Ledger via three writers:
   orchestrator (pipeline lane), Agent HQ (coding-agent + IDE lanes), and
   manual API (human override). All three reach the same Cosmos container.

2. **Make standards changes a first-class governed flow.** Each department
   ships a `standards-bundles/<dept>/v<n.n.n>/` directory; changes go through
   PR + blast-radius routing + committee review + canary rollout, recorded as
   `meta` ledger entries.

3. **Replace ADO-as-target with GitHub-as-target** for the Deliver stage. PR
   creation, branch policy, and reviewer assignment all happen in
   `idanshimon/agentic-sdlc-target` (or the customer's GH org). HCA-style
   ADO targets remain supported via a `deliver_provider` config flag, but GH
   is the default.

4. **Keep what works.** Foundry agents, prompt library (42 variants × 6 stages
   × 7 providers), VNET private endpoints, MI-only data-plane auth, /telemetry
   dashboard. Nothing about v0.6's verified-working substrate gets discarded.

5. **Honest demo, end-to-end.** A live deployed demo at v0.7 URLs, exercising
   all four planes — including a real `meta` ledger entry showing a standards
   change going through committee review.

## Non-goals

- Not building a ServiceNow / UiPath integration. Out of scope for v0.7.
- Not building a custom Mission Control. GitHub's Mission Control is the runtime
  view; our `/telemetry` is the governance complement.
- Not solving the GHE.com Data Residency limitation (Coding Agent isn't supported
  there). Documented as a deferred constraint, not solved by us.
- Not training models. Provider routing only.

## High-level architecture

```
                      STANDARDS-CHANGE LOOP                       LEDGER FAN-OUT
                      (meta-pipeline)                             (cross-runtime)
                              │                                          │
       ┌──────────────────────┼──────────────────────┐                   │
       │                      │                      │                   │
       │   PLANE 1 — STANDARDS BUNDLES               │                   │
       │   ───────────────────────────               │                   │
       │   architect/v0.1.0/          PR review →    │                   │
       │   security/v0.1.0/           ADR draft →    │                   │
       │   privacy/v0.1.0/            committee  →   │                   │
       │   finops/v0.1.0/             canary     →   │                   │
       │                              meta entry │   │                   │
       └──────────────────────┬──────────────────┘   │                   │
                              │ pinned via PINS.yaml │                   │
                              ▼                      ▼                   ▼

PLANE 2 — PIPELINE                       PLANE 4 — AGENT HQ RUNTIME LANES
─────────────────────────────────       ──────────────────────────────────
Orchestrator (heavy lane)                Agent HQ + IDE + chat bridges
                                         (medium + light lanes)
PRD → ingest → assessor → resolver*      Issue → coding-agent → PR
       → architect → design-review →     IDE  → Copilot session → diff
       → test-plan → codegen →           Chat → Slack/Teams/Linear/Boards
       → review-scan → deliver(GH PR)
                                         Hooks: SessionStart, UserPromptSubmit,
* HITL gate via Plan Mode or chat        PreToolUse (BLOCK), PostToolUse, SessionEnd
                              │                                  │
                              │ runtime ledger entries           │ runtime ledger entries
                              ▼                                  ▼

           ┌──────────────────────────────────────────────────────┐
           │ PLANE 3 — DECISION LEDGER (Cosmos, team-partitioned) │
           │                                                      │
           │   entry_type: runtime | meta                         │
           │   exposed via: REST API · MCP server · hook payload  │
           │                                                      │
           └────────────┬───────────────────────────┬─────────────┘
                        │                           │
                        ▼                           ▼
                 /telemetry UI               PIPELINE DOCTOR
                 (Ledger Insights)           (drift / cost / quality)
                                                    │
                                                    ├─ AUTO-FIX (bounded envelope)
                                                    │  → runtime entry
                                                    │
                                                    └─ PROPOSE-CHANGE (PR)
                                                       → standards-change loop
                                                       → meta entry on merge
```

## What gets ported from v0.6 vs built fresh

### Ported (selectively, with refactor)
- `apps/orchestrator/` — keep stages, providers, prompt library; swap deliver target
- `apps/orchestrator/ledger.py` → `packages/ledger-core/` (extracted as shared library)
- `apps/orchestrator/prompt_library.py` — verbatim
- `apps/resolver-ui/` → renamed to `apps/ledger-insights-ui/`, drop HITL gate panel,
  keep /telemetry + /runs as Ledger Insights views
- OpenSpec proposals (the strict-valid ones): `add-prompt-library`,
  `add-telemetry-dashboard`, `add-vnet-private-endpoints`

### Built fresh
- `packages/ledger-core/` (extract + extend with `entry_type`, A365 attribution)
- `apps/decision-ledger-mcp/` (new — Node TS MCP server)
- `apps/pipeline-doctor/` (new — Foundry agent + Container Job)
- `.github/agents/` (new — 6 custom agent files)
- `.github/skills/` (new — 4-6 skills folders)
- `.github/hooks/` (new — 5 hook bundles + scripts)
- `standards-bundles/` (new — schema + reference bundles for security, finops)
- `apps/orchestrator/stages/deliver_github.py` (new — replaces ADO deliver)

### Discarded
- ADO-only deliver path. GH is default; ADO becomes opt-in via config flag.
- Standalone resolver HITL gate UI — Plan Mode + chat bridges replace it.

## Cross-plane invariants

1. **Every decision writes a ledger entry.** No silent edits, no untracked tool calls.
   Hooks enforce this for IDE; orchestrator stages enforce it via `Ledger.write_entry`;
   coding-agent flows enforce it via the SubagentStop hook.

2. **Every standards change is committee-reviewed.** Pipeline Doctor cannot
   directly change rules. Auto-fix is bounded by per-bundle envelopes
   (`envelope.yaml`) declared in each bundle directory.

3. **PHI rules can never be auto-relaxed.** The `privacy` bundle's envelope
   explicitly excludes any rule tagged `phi: true`. Pipeline Doctor's auto-fix
   on a PHI rule is blocked at envelope-check time, not at committee time.

4. **Bundle versions are pinned per-team.** `standards-bundles/PINS.yaml` carries
   `<team_id>: <bundle_version>` pairs. Canary rollouts ship a new version to
   5% of teams for 7 days before opening it to all.

## Decision: bundle storage location

Bundles live IN this repo for v0.7 (`standards-bundles/<dept>/v<n.n.n>/`). For
production deployment, each department publishes its bundle as an independent
repo (`<org>/standards-architect`, etc.) with its own CODEOWNERS roster.
Pipeline reads from a registry endpoint that resolves PINS.yaml against those
repos. v0.7 demo uses local-files-as-registry; production guidance is documented
in `docs/STANDARDS-BUNDLES-DEPLOYMENT.md`.

## Decision: A365 attribution mechanism

Two-step attribution:

1. Every custom agent in `.github/agents/` registers as an A365 tenant agent
   identity at deployment time (one-time bootstrap script:
   `deploy/scripts/register-a365-agents.sh`). Each agent gets a stable
   `agent_principal_id`.

2. Ledger entries carry `actor.id = agent_principal_id` for agent actions and
   `actor.id = m365_upn` for human actions. A fan-out worker reads new ledger
   entries and emits Microsoft Graph audit events keyed on these IDs, so A365's
   admin pane sees the full decision-level signal without polling our Cosmos.

The fan-out worker is best-effort: if Graph emission fails, the ledger entry
still persists. Compliance reads our ledger directly as the source of truth;
A365 view is the secondary, ergonomic surface.

## Risks and rollback

| Risk | Mitigation | Rollback |
|---|---|---|
| Copilot SDK is technical preview (Jan 2026), API shape may change | Pin SDK version in `package.json`, isolate SDK calls behind `apps/decision-ledger-mcp/src/copilot-sdk-client.ts` | Replace SDK calls with REST direct against `api.github.com/agents/...` |
| GH audit log → Graph fan-out endpoint shape uncertain | Build fan-out worker as Container Job with retry + DLQ; ledger writes are independent | Disable fan-out, fall back to direct ledger query in A365 PowerShell |
| Pipeline Doctor auto-fix produces incorrect change | Strict envelope schema, dry-run mode default, undo endpoint already exists | Toggle `pipeline-doctor.auto_fix.enabled = false` in config; revert via undo |
| Bundle canary rollout regresses prod team | Health-check during canary period (ledger watch for spike in rejections / cost / drift); auto-revert at 7-day mark if metrics regress | Manually re-pin team to prior version via PR on PINS.yaml |
| GH PR target unavailable / private | `deliver_provider: ado` config flag preserves v0.6 path | Switch flag, redeploy orchestrator |

## Test targets

- `apps/orchestrator/tests/` — port 95 existing + add 20 for GH deliver, A365 attribution
- `apps/pipeline-doctor/tests/` — net new, target 25 cases (envelope validation, drift detection, change-proposal authoring)
- `apps/decision-ledger-mcp/tests/` — net new, target 15 cases (tool routing, MCP protocol compliance, auth)
- `packages/ledger-core/tests/` — net new, target 30 cases (entry validation, runtime/meta separation, schema compatibility)
- `tests/e2e/` — new top-level dir, target 5 scenarios:
  1. PRD upload → 9 stages → GH PR with decisions.md
  2. GH issue → coding-agent → PR with hook-fired ledger entries
  3. IDE Copilot session → PreToolUse blocks PHI write → ledger captures decision
  4. Pipeline Doctor auto-fix on autopilot threshold (within envelope)
  5. Pipeline Doctor proposes standards change → PR opens with ADR

## Verification (definition of done)

- [ ] All four planes have at least one OpenSpec proposal in strict-valid state
- [ ] All four planes have at least one passing E2E test in `tests/e2e/`
- [ ] Live URLs respond 200 for orchestrator, ledger-insights-ui, ledger-mcp, pipeline-doctor
- [ ] One real PR was created on `idanshimon/agentic-sdlc-target` via the deliver stage
- [ ] One real `meta` ledger entry exists from a standards-change merge
- [ ] One real auto-fix from Pipeline Doctor exists in the ledger (within bounded envelope)
- [ ] `docs/explainer.html` shows the four-plane architecture (animated, dark theme)
- [ ] `docs/demo-script.md` is pipeline-centric, click-by-click, no name-anchored speakers
