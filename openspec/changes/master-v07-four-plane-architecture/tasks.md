# Tasks — master v0.7 four-plane architecture

Each task is bite-sized (2-5 min) and references file paths + verification.
Order matters: bootstrap → ports → planes → integration → deploy → demo.

## Phase 1 — Repo bootstrap (this commit) [DONE]

- [x] Create `~/projects/msft/agentic-sdlc/` with directory skeleton
- [x] `.gitignore`, `LICENSE` (MIT), `AGENTS.md`, `.github/copilot-instructions.md`
- [x] `openspec/config.yaml` with strict-validation
- [x] `openspec/changes/master-v07-four-plane-architecture/proposal.md` (this proposal)
- [ ] `openspec/changes/master-v07-four-plane-architecture/tasks.md` (this file)
- [ ] `README.md` (audience callout, layout map, four-plane diagram)
- [ ] `CHANGELOG.md` seeded with v0.7.0-dev

## Phase 2 — Per-plane OpenSpec proposals

- [ ] `openspec/changes/extend-ledger-runtime-meta-entries/` (proposal + tasks + spec deltas)
- [ ] `openspec/changes/add-pipeline-doctor/` (proposal + tasks + spec deltas)
- [ ] `openspec/changes/add-standards-bundles/` (proposal + tasks + spec deltas)
- [ ] `openspec/changes/add-agent-hq-integration/` (proposal + tasks + spec deltas)
- [ ] `openspec/changes/swap-deliver-ado-to-github/` (proposal + tasks + spec deltas)

## Phase 3 — Code port from v0.6 (selective)

- [ ] Port `apps/orchestrator/main.py` (FastAPI app)
- [ ] Port `apps/orchestrator/models.py` (Pydantic schemas)
- [ ] Port `apps/orchestrator/stages.py` (9-stage state machine)
- [ ] Port `apps/orchestrator/providers/` (foundry, aoai, anthropic_direct, databricks)
- [ ] Port `apps/orchestrator/prompt_library.py` verbatim
- [ ] Port `apps/orchestrator/telemetry.py`
- [ ] Port `apps/orchestrator/decisions_md.py`
- [ ] Extract `apps/orchestrator/ledger.py` → `packages/ledger-core/` (shared lib)
- [ ] Extend ledger schema with `entry_type`, `bundle_refs`, `gh_audit_xref`, `actor.id`
- [ ] Port relevant tests, port them green, add 20 for GH deliver + A365 attribution
- [ ] Port `apps/resolver-ui/` → `apps/ledger-insights-ui/`, drop HITL gate, keep /telemetry + /runs

## Phase 4 — New components

### Pipeline Doctor (`apps/pipeline-doctor/`)
- [ ] `models.py` — `DriftSignal`, `AutoFixProposal`, `ChangeProposal`, `EnvelopeCheck`
- [ ] `drift_detector.py` — class freq, cost-per-decision, autopilot rejection rate
- [ ] `envelope_validator.py` — load bundle envelope.yaml, validate proposed change
- [ ] `auto_fixer.py` — apply within envelope, write runtime ledger entry
- [ ] `change_proposer.py` — open PR on `standards-bundles/<dept>` with ADR
- [ ] `main.py` — entrypoint for cron / Container Job
- [ ] `tests/` — 25 cases minimum

### Decision Ledger MCP server (`apps/decision-ledger-mcp/`)
- [ ] `package.json` (Node 20, MCP SDK pinned)
- [ ] `tsconfig.json` strict mode
- [ ] `src/server.ts` — MCP server entrypoint
- [ ] `src/tools/{query,write,list-runtime,list-meta,find-precedent}.ts`
- [ ] `src/auth.ts` — bearer token to Cosmos
- [ ] `tests/` — 15 cases minimum

### Hook bundle (`.github/hooks/`)
- [ ] `session-start.json` (hook config) + `scripts/session-start.{sh,ps1}` (load AGENTS.md, query ledger for prior context)
- [ ] `pre-tool-use.json` + `scripts/pre-tool-use.{sh,ps1}` (PHI classifier — block on raw MRN)
- [ ] `post-tool-use.json` + `scripts/post-tool-use.{sh,ps1}` (write ledger entry)
- [ ] `user-prompt-submit.json` + `scripts/user-prompt-submit.{sh,ps1}` (capture intent)
- [ ] `session-end.json` + `scripts/session-end.{sh,ps1}` (write summary)

### Custom agents (`.github/agents/`)
- [ ] `assessor.agent.md`
- [ ] `architect.agent.md`
- [ ] `codegen.agent.md`
- [ ] `review-scan.agent.md`
- [ ] `pipeline-doctor.agent.md`
- [ ] `standards-change.agent.md`

### Standards bundles (`standards-bundles/`)
- [ ] `BUNDLE-SCHEMA.md` (the schema documentation)
- [ ] `PINS.yaml` (team → bundle-version mapping)
- [ ] `security/v0.1.0/{rules.yaml,envelope.yaml,reviewers.yaml,README.md}` (reference: PHI classifier rules)
- [ ] `architect/v0.1.0/{rules.yaml,envelope.yaml,reviewers.yaml,README.md}` (allowed stacks, app patterns)
- [ ] `privacy/v0.1.0/{rules.yaml,envelope.yaml,reviewers.yaml,README.md}` (HIPAA min-necessary, retention)
- [ ] `finops/v0.1.0/{rules.yaml,envelope.yaml,reviewers.yaml,README.md}` (per-team budget ceilings)

## Phase 5 — Azure deployment

- [ ] `az group create --name rg-agentic-sdlc-v07-eastus --location eastus`
- [ ] Deploy infra Bicep: `infra/main.bicep` (CAE + Cosmos + ACR + storage + LAW + AppInsights + MIs)
- [ ] Cosmos: DB `agentic-sdlc`, containers `decision-ledger` (PK `/team_id`), `pipeline-runs` (PK `/run_id`)
- [ ] Build + push images via `az acr build`:
  - `orchestrator:0.7.0-rc1`
  - `ledger-insights-ui:0.7.0-rc1`
  - `decision-ledger-mcp:0.7.0-rc1`
  - `pipeline-doctor:0.7.0-rc1`
- [ ] Deploy Container Apps (orchestrator, ledger-insights-ui, ledger-mcp, pipeline-doctor as Container Job)
- [ ] Verify all four URLs respond 200
- [ ] Smoke-test: PRD upload → run completes → GH PR opens

## Phase 6 — GitHub publication

- [ ] Create `idanshimon/agentic-sdlc` (private initially)
- [ ] Push initial commit (squashed Phase 1-4 work)
- [ ] Create `idanshimon/agentic-sdlc-target` (the PR target repo for demo)
- [ ] Wire orchestrator deliver stage to push to `agentic-sdlc-target`
- [ ] Test: trigger an end-to-end run, verify PR opens

## Phase 7 — Documentation

- [ ] `docs/ARCHITECTURE.md` — full Mermaid diagrams, four-plane breakdown
- [ ] `docs/explainer.html` — dark-theme single-file explainer (port template from v0.6, update content)
- [ ] `docs/demo-script.md` — pipeline-centric click-by-click walkthrough
- [ ] `docs/STANDARDS-BUNDLES-DEPLOYMENT.md` — per-dept-as-separate-repo guidance
- [ ] `docs/A365-INTEGRATION.md` — attribution mechanism, fan-out worker
- [ ] `docs/HIPAA-SELF-HOSTED-RUNNER.md` — Coding Agent in customer tenant
- [ ] `docs/PROVIDERS.md` — port from v0.6
- [ ] `docs/SELF-DEPLOY.md` — port from v0.6 + update for v0.7

## Phase 8 — End-to-end verification

- [ ] Trigger pipeline run with synthetic PRD → confirm 9 stages execute → GH PR opens
- [ ] Trigger Pipeline Doctor manually → confirm one auto-fix entry + one change-proposal PR
- [ ] Open a synthetic standards-change PR → confirm change-agent classifies + assigns reviewers
- [ ] Confirm ledger query via MCP server returns the entries from above flows
- [ ] Confirm `/telemetry` UI shows the entries

## Rollback plan

- Bundle a `deploy/scripts/rollback-to-v06.sh` that re-points DNS / config to v0.6 endpoints
- Keep v0.6 RG (`rg-agentic-sdlc-demo-eastus`) running through v0.7 demo period
- Document the swap in `docs/ROLLBACK.md`
