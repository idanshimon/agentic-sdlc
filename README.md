# Agentic SDLC v0.7 — Reference Design

[![status](https://img.shields.io/badge/status-v0.7--rc1-orange)](#)
[![tests](https://img.shields.io/badge/tests-pending-lightgrey)](#)
[![openspec](https://img.shields.io/badge/openspec-strict--valid-blue)](#)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A reference design for **governed agentic software development**: every AI-agent
decision is auditable, every standards change is committee-approved, and every
runtime — orchestrator pipeline, GitHub Coding Agent, IDE Copilot — feeds the
same Decision Ledger.

> v0.7 succeeds [v0.6.x](https://github.com/idanshimon/agentic-sdlc-reference).
> The v0.6 line proved governance is the differentiator. v0.7 makes it cover
> **all** agentic activity, not just
> the orchestrator's pipeline runs, and adds a committee-reviewed **standards
> bundle** plane so departments (Architect, Security, Privacy, FinOps) own
> their rules as versioned PRs, not tribal knowledge.

## Audience

Architects and engineering leaders evaluating agentic SDLC adoption at scale.
The design assumes:

- Most engineers do **not** live in VS Code. They work in Slack/Teams/Linear/Jira/Boards.
- Some engineers **do** live in VS Code and want IDE Copilot.
- Both populations need governance, attribution, and audit — without slowing them down.
- Compliance teams need a single audit surface, not three.

## The four planes

```
        STANDARDS BUNDLES                                   AGENT HQ RUNTIME
        (per-department,                                    (medium + light lanes)
         versioned, committee-reviewed)
                                                            • Coding Agent (issue → PR)
        architect/v0.1.0/                                   • IDE Copilot (VS Code)
        security/v0.1.0/                                    • Chat bridges (Slack/Teams/Linear/Boards)
        privacy/v0.1.0/                                     
        finops/v0.1.0/                                      Hooks: SessionStart, UserPromptSubmit,
                          ↓ pinned per team                  PreToolUse (BLOCK), PostToolUse, SessionEnd
                          ↓
        ┌─────────────────────────────────────────────────────────────────┐
        │                                                                 │
        │  PIPELINE (heavy lane — orchestrator)                           │
        │                                                                 │
        │  PRD → ingest → assessor → resolver* → architect → design →     │
        │       test-plan → codegen → review-scan → deliver (GitHub PR)   │
        │                                                                 │
        │  * HITL gate via Plan Mode or chat bridges                      │
        │                                                                 │
        └────────────────────────────┬────────────────────────────────────┘
                                     │
                                     │ all three lanes write to:
                                     ▼
        ┌─────────────────────────────────────────────────────────────────┐
        │  DECISION LEDGER (Cosmos, team-partitioned, two entry types)    │
        │  • entry_type: runtime  — pipeline runs, IDE sessions, agent PRs│
        │  • entry_type: meta     — standards-change merges               │
        │  Exposed: REST API · MCP server · hook payload I/O              │
        └────────────┬────────────────────────────────┬───────────────────┘
                     │                                │
                     ▼                                ▼
              /telemetry UI                    PIPELINE DOCTOR
              (Ledger Insights:                (Foundry agent)
               drift, cost, class)             • drift detection
                                               • bounded auto-fix
                                               • change-proposal PRs
```

### Config is editable, governed by PR (v0.7.22)

The Standards Bundles and Agent HQ surfaces are not just viewers. Operators edit
agents (`.github/agents/`), standards bundles (`standards-bundles/`), and the
prompt library (`prompts/`) directly in Ledger Insights; every save opens a
**governed pull request** against the file the pipeline reads. Nothing mutates
running behaviour in place — bundles are PR-only by design so a standards change
always goes through committee review. The agent→bundle subscription drives data:
each decision is stamped with the deciding agent's `bundle_refs`. The deliver
stage opens a **real GitHub PR** with the run's artifacts (or an honest "PR not
opened" — never a fabricated URL).

## Production hardening references

- [Architecture](docs/ARCHITECTURE.md)
- [Authentication](docs/AUTHENTICATION.md)
- [Security model](SECURITY.md)
- [Deployment](docs/DEPLOYMENT.md)
- [Run recovery](docs/RUN-RECOVERY.md)
- [GitHub enforcement](docs/GITHUB-ENFORCEMENT.md)
- [Generated API reference](docs/API.md)

## Repository layout

```
agentic-sdlc/
├── AGENTS.md                          ← repo-wide guardrails, every agent reads
├── README.md                          ← (this file)
├── LICENSE                            ← MIT
│
├── apps/
│   ├── orchestrator/                  ← 9-stage pipeline (FastAPI, Python 3.11)
│   ├── ledger-insights-ui/            ← /telemetry + /runs (Next.js 14)
│   ├── decision-ledger-mcp/           ← MCP server (Node TS) for cross-runtime ledger access
│   └── pipeline-doctor/               ← drift detection + auto-fix + change-proposal authoring
│
├── packages/
│   └── ledger-core/                   ← shared ledger library (used by orchestrator + doctor)
│
├── .github/
│   ├── copilot-instructions.md        ← Copilot-specific conventions
│   ├── instructions/                  ← path-scoped instructions (applyTo: ...)
│   ├── agents/                        ← Custom Agent files (assessor, architect, codegen, ...)
│   ├── skills/                        ← Agent Skills (PRD decomposition, PHI classification, ...)
│   └── hooks/                         ← Lifecycle hooks (session-start, pre-tool-use, ...)
│
├── standards-bundles/                 ← per-department versioned policy bundles
│   ├── PINS.yaml                      ← team → bundle-version map
│   ├── architect/v0.1.0/{rules,envelope,reviewers,README}.{yaml,md}
│   ├── security/v0.1.0/...
│   ├── privacy/v0.1.0/...
│   └── finops/v0.1.0/...
│
├── openspec/
│   ├── config.yaml                    ← strict-validation rules
│   ├── specs/                         ← capability specs (canonical truth)
│   └── changes/                       ← active proposals (each: proposal.md + tasks.md + spec deltas)
│
├── samples/
│   ├── prds/                          ← synthetic PRDs (PHI obviously fake)
│   └── policies/                      ← example bundle policies
│
├── infra/
│   └── main.bicep                     ← Azure RG + CAE + Cosmos + ACR + LAW
│
├── deploy/
│   └── scripts/                       ← register-a365-agents, deploy-orchestrator, smoke-test
│
└── docs/
    ├── ARCHITECTURE.md                ← full Mermaid diagrams
    ├── explainer.html                 ← single-file dark-theme explainer (offline-capable)
    ├── demo-script.md                 ← pipeline-centric click-by-click walkthrough
    ├── STANDARDS-BUNDLES-DEPLOYMENT.md
    ├── A365-INTEGRATION.md
    ├── HIPAA-SELF-HOSTED-RUNNER.md
    ├── PROVIDERS.md
    └── SELF-DEPLOY.md
```

## Quick start (three paths)

### 1. Try it live (zero setup)

URLs populated post-deploy. See `docs/demo-script.md` for the walkthrough.

### 2. Run locally

```bash
# Orchestrator
cd apps/orchestrator
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Ledger Insights UI
cd apps/ledger-insights-ui
npm install
npm run dev      # localhost:3000

# Decision Ledger MCP server
cd apps/decision-ledger-mcp
npm install
npm run build && npm run start    # stdio MCP server

# Pipeline Doctor (one-shot)
cd apps/pipeline-doctor
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pipeline_doctor --mode dry-run
```

### 3. Self-deploy to your Azure tenant

See `docs/SELF-DEPLOY.md`. Single Bicep + Container Apps env, MI for data-plane,
private endpoints to Cosmos and Storage. ~25 minutes from `az group create`
to working endpoints.

## Honest disclaimers

These are deliberately stated up-front because hand-waving them undermines trust:

- **Copilot SDK is technical preview** (Jan 2026). API shape may change. We pin SDK version
  and isolate SDK calls behind a thin client; replacement path is documented.
- **Coding Agent on GHE.com Data Residency is not yet supported** by GitHub
  (`gh.com/community/discussions/167952`). EU/data-sovereignty customers are limited to
  the orchestrator pipeline lane until GitHub closes that gap.
- **Pipeline Doctor auto-fix is bounded by per-bundle envelopes.** It cannot relax PHI rules,
  ever. It cannot exceed the envelope on any rule. Everything else is a PR.
- **Per-stage cost is apportioned, not measured per-call.** True per-call cost attribution
  requires App Insights SDK wired into every provider client; Phase 2 work.
- **Decision Ledger fan-out to A365 / Microsoft Graph audit events** is best-effort.
  If Graph emission fails, the ledger entry still persists. Compliance reads our ledger
  directly as the source of truth.
- **`accuracy_score` is not yet populated.** The field exists on every ledger entry
  and is `0.0` on all of them — nothing has computed it. Replay scoring
  (`apps/orchestrator/replay.py`) reports such entries as `UNSCORED` and excludes
  them from rates rather than counting them as agreements.
- **`slot_value_hash` is class-level, not slot-level.** Despite the name and the
  original `team + class + slot` intent, every distinct value maps 1:1 onto an
  ambiguity class on real data. Precedent and replay therefore key on `card_id`,
  which is the identity of a single decision question. Anything bucketing on
  `slot_value_hash` is grouping a whole class, not a chain.
- **A BLOCK rule is only as real as its mechanism.** `SBOM-001` shipped in
  `security/v0.1.0` as a BLOCK rule with no scanner behind it — the review stage
  reported `findings: 0` because nothing was ever scanned. `security/v0.2.0` adds
  `requires_mechanism` so a rule must declare its enforcement path, and
  `.github/workflows/supply-chain-scan.yml` supplies one. A missing or unreadable
  scan report fails the build; it is never treated as a pass.

## Onboarding and daily operation

**[docs/onboarding-and-operation.md](docs/onboarding-and-operation.md)** is the
end-to-end walkthrough: how an organization gets from nothing to a governed
agent factory (identity spine → department bundles → team pins → PRD → pipeline
→ the loop closing), and what an operator actually does with the dashboard each
day. It includes the three-queue daily loop, how to read a failed run correctly,
and the honest limits to state before a demo rather than after.

## Measuring autonomy honestly

**Autonomy earned** (the share of decisions resolved without a human) measures how
much the agent was *allowed* to do. It is not evidence that it should have been.
A system whose autonomy rate climbs while its error rate climbs looks like success
on every chart in this repository.

The number that grounds it is the **disagreement rate**: when the agent resolved a
decision alone, how often did it diverge from a human ruling on the same question?

```bash
python3 -m pytest apps/orchestrator/tests/test_replay.py
```

Replay pairs each human ruling with autopilot decisions on the same `card_id` and
reports a per-class verdict — `AUTONOMY EARNED`, `AUTONOMY DEFENSIBLE`,
`REVOKE AUTONOMY`, `INVARIANT — HUMAN ALWAYS`, `INSUFFICIENT`, or `UNSCORED`.

Three properties are load-bearing:

1. **It refuses to report on thin evidence.** Below the sample floor the rate is
   null and the verdict is `INSUFFICIENT` — never a flattering `0.0%` from n=2.
2. **Thresholds are governance, not constants.** `ReplayPolicy.from_bundle()`
   reads the same `defaults:` shape finops already uses for `AUTOPILOT-THRESHOLD-*`,
   so teams on different pinned versions are judged by their own standards and a
   threshold change is a bundle change with a canary, not a code deploy. Any rule
   marked `phi_locked: true` becomes an autonomy invariant automatically, so
   enforcement and scoring invariants cannot drift apart.
3. **It never writes to the ledger.** Scoring is a read-only projection.
   Fabricating rows to populate a metric would corrupt the audit substrate this
   system exists to protect.

Replay is also the fastest honest path to a calibrated baseline: instead of waiting
for precedent to accumulate, it scores against outcomes that already happened.
Spec: `openspec/changes/add-replay-disagreement-metric/`.

## Status

v0.7-rc1 is under active build. See `openspec/changes/` for the open proposals
and their tasks lists. Live demo URLs and verification status are tracked at
the bottom of `docs/demo-script.md` and updated on every successful deploy.

## License

MIT — see [LICENSE](LICENSE). Reference architecture by Idan Shimon. Free to fork,
adapt, and deploy in your own environment.
