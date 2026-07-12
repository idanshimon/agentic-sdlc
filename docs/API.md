# API Reference — Agentic SDLC Orchestrator

**Version:** 0.7.0  
**Interactive docs:** `/docs` (Swagger UI) · `/redoc` (ReDoc) · `/openapi.json` (raw schema)

> Auto-generated from the live OpenAPI schema. Regenerate with `python scripts/gen_api_docs.py`.

The **Agentic SDLC Orchestrator** turns a Product Requirements Document into a
delivered pull request through a governed, human-gated agent pipeline.

**Pipeline:** Ingest → Assessor → *Resolver gate (human)* → Architect →
*Design-review gate* → Test-plan → Codegen → Review/Scan → Deliver.

Every meaningful decision is written to an append-only **decision ledger** with
its bundle citations, model, and cost. Hard-gated classes (PHI, auth) can never
be auto-resolved — they require an explicit, attributed human decision.

## Conventions

- **Streaming:** `GET /api/runs/{id}/stream` is a Server-Sent-Events stream of
  stage transitions. Everything else is plain JSON.
- **Auth:** gateway-fronted; the API trusts its ingress. CORS origins are
  env-driven (`CORS_ALLOWED_ORIGINS`).
- **Errors:** standard HTTP status codes with a `{ "detail": "..." }` body.
- **Interactive docs:** this page (`/docs`), ReDoc at `/redoc`, raw schema at
  `/openapi.json`.

## Endpoints

### Runs

_Create runs from a PRD, fetch state, stream progress, and control the run lifecycle (pause / resume / rerun / undo)._

| Method | Path | Summary |
|---|---|---|
| `POST` | `/api/run` | Create Run |
| `GET` | `/api/runs` | List Runs |
| `GET` | `/api/runs/{run_id}` | Get Run |
| `POST` | `/api/runs/{run_id}/pause` | Pause Run |
| `POST` | `/api/runs/{run_id}/rerun` | Rerun |
| `POST` | `/api/runs/{run_id}/resume` | Resume Run |
| `GET` | `/api/runs/{run_id}/stream` | Stream Run |
| `POST` | `/api/runs/{run_id}/undo` | Undo Decision |

### Gates & Decisions

_Resolve ambiguity cards and release human gates: approve, reject, demote, finalize. Hard-gated (PHI/auth) classes require explicit individual decisions._

| Method | Path | Summary |
|---|---|---|
| `POST` | `/api/runs/{run_id}/approve` | Approve |
| `POST` | `/api/runs/{run_id}/demote` | Demote |
| `POST` | `/api/runs/{run_id}/finalize` | Finalize Gate |
| `POST` | `/api/runs/{run_id}/reject` | Reject |

### Decision Ledger

_Append-only audit trail of every agent + human decision, with bundle citations, model, and cost._

| Method | Path | Summary |
|---|---|---|
| `GET` | `/api/runs/{run_id}/ledger` | Get Run Ledger |

### Review Loop

_Autonomous review→remediate→re-review loop controls and the Tier-B human merge touch-point._

| Method | Path | Summary |
|---|---|---|
| `POST` | `/api/review-loops` | Dispatch Review Loop |
| `POST` | `/api/review-loops/merge` | Review Loop Merge |

### Self-Heal

_Pipeline-doctor heal proposals and their human approval._

| Method | Path | Summary |
|---|---|---|
| `GET` | `/api/heal/{heal_id}` | Get Heal Session |
| `POST` | `/api/heal/{heal_id}/approve` | Approve Heal |
| `POST` | `/api/runs/{run_id}/heal` | Open Heal Session |

### Telemetry

_Cost, latency, and decision-class analytics for dashboards._

| Method | Path | Summary |
|---|---|---|
| `GET` | `/api/telemetry/classes` | Telemetry Classes |
| `GET` | `/api/telemetry/cost` | Telemetry Cost |
| `GET` | `/api/telemetry/decisions` | Telemetry Decisions |

### Configuration

_Read + governed-PR write-back for agents, bundles, prompts, autonomy tiers, and hard-gate posture._

| Method | Path | Summary |
|---|---|---|
| `POST` | `/api/config/agents/save` | Save Agent |
| `POST` | `/api/config/bundles/save` | Save Bundle |
| `GET` | `/api/config/hard-gate-classes` | Get Hard Gate Classes |
| `POST` | `/api/config/prompts/save` | Save Prompt |
| `POST` | `/api/config/reload` | Reload Config |
| `GET` | `/api/config/repo-autonomy` | Get Repo Autonomy |

### Prompt Library

_The versioned prompt catalog each stage resolves against._

| Method | Path | Summary |
|---|---|---|
| `GET` | `/api/prompt-library` | Prompt Library Catalog |
| `GET` | `/api/prompt-library/{stage}` | Prompt Library Lookup |
| `GET` | `/api/prompts/catalog` | List Prompts |
| `GET` | `/api/prompts/{prompt_id}` | Get Prompt Detail |

### System

_Liveness, health, and administrative maintenance._

| Method | Path | Summary |
|---|---|---|
| `POST` | `/api/admin/runs/{run_id}/mark_failed` | Admin Mark Failed |
| `GET` | `/healthz` | Healthz |

---
_33 endpoints across 9 groups._
