"""FastAPI orchestrator — entry point.

Implements design.md §2 pipeline graph as a stateful, SSE-streamed workflow with
human gates (Resolver §3, Design Review §2) that pause execution until a POST
arrives on /approve, /reject, or /demote.

Routes:
  POST   /api/run                          — create run from PRD upload
  GET    /api/runs/{run_id}                — fetch run state
  GET    /api/runs/{run_id}/stream         — Server-Sent Events stream
  POST   /api/runs/{run_id}/approve        — resolve a card or close a gate
  POST   /api/runs/{run_id}/reject         — reject a card (one-keystroke default)
  POST   /api/runs/{run_id}/demote         — demote a precedent (design.md §4)
  GET    /healthz                          — liveness
"""
from __future__ import annotations
import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from .auth import (
    AuthConfigurationError, Principal, authorize_mutation, principal_from_request,
    require_team, validate_auth_configuration,
)
from .commands import begin_command, cas_command, finish_command
from .decision_outbox import enqueue_decision, flush_decision_outbox
from .decisions_md import write_decisions_md
from .execution_store import ExecutionInputStore
from .heal import (
    HealDecision, HealProposal, HealTrigger, HealValidationOutcome,
    assert_human_invoked, validate_heal_action,
)
from .heal_runtime import get_brain, get_executor
from . import heal_runtime as _heal_rt
from . import config as _config
from .ledger import InvariantWriteBlocked, Ledger
from .models import (
    GateDecision, INVARIANT_CLASSES, LedgerEntry, RunMode, RunState, RunStatus,
    Stage, StageEvent,
)
from .agent_bundles import bundles_for_stage
from .stages import (
    stage_architect, stage_assessor, stage_codegen, stage_deliver,
    stage_ingest, stage_review_scan, stage_test_plan,
)
from ._pipeline_stages import ModelPolicyRefusal
from .prompt_library import build_catalog_view, get_prompt, UnknownStageError
from .recovery import PIPELINE_ORDER, checkpoint
from .recovery_worker import recover_nonterminal_runs
from .leases import LeaseConflict, maintain_lease, release_lease
from .review_dispatch import (
    ReviewLoopDispatch, ReviewLoopRegistry, identity_for,
)
from .github_pr_snapshot import SnapshotError, fetch_pr_snapshot
from .github_outcomes import publish_review_outcome
from .review_loop import run_review_loop
from .review_verdict import build_review_verdict
from .telemetry import init_telemetry, record_gate_wall_clock, span
from .telemetry_queries import query_classes, query_cost, query_decisions, query_recent_runs
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
_logger = logging.getLogger("orchestrator.main")

# In-process run registry. For multi-replica, swap to Cosmos as source of truth;
# the SSE bus would need Service Bus / Redis pub-sub. Demo runs single replica.
_runs: dict[str, RunState] = {}
_queues: dict[str, asyncio.Queue[StageEvent | None]] = {}
_gate_events: dict[str, asyncio.Event] = {}
_gate_started: dict[str, float] = {}
_prd_cache: dict[str, str] = {}  # raw PRD text per run — enables rerun without re-upload
_ledger: Ledger | None = None
_input_store: ExecutionInputStore | None = None
_review_loop_registry = ReviewLoopRegistry()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _ledger, _input_store
    validate_auth_configuration()
    init_telemetry()
    _ledger = Ledger()
    _input_store = ExecutionInputStore()

    async def resume_recovered(run: RunState, plan) -> None:
        _runs[run.run_id] = run
        _queues.setdefault(run.run_id, asyncio.Queue())
        if plan.action == "await_gate":
            # Recreate the local wake-up surface, then continue from the boundary
            # after the durable gate command resolves it.
            gate_event = _gate_events.setdefault(run.run_id, asyncio.Event())

            async def continue_after_recovered_gate() -> None:
                await gate_event.wait()
                run.pending_gate = None
                run.status = RunStatus.RUNNING
                checkpoint(run, plan.stage, "completed")
                next_stage = {
                    Stage.RESOLVER: Stage.ARCHITECT,
                    Stage.DESIGN_REVIEW: Stage.TEST_PLAN,
                }.get(plan.stage)
                if next_stage is None:
                    run.status = RunStatus.FAILED
                    await _push(run.run_id, StageEvent(
                        run_id=run.run_id, stage=plan.stage or run.current_stage,
                        status="failed", message="Recovered gate has no safe continuation boundary",
                    ))
                    return
                if _input_store is None or not run.input_ref or not run.input_sha256:
                    run.status = RunStatus.FAILED
                    return
                raw = (await _input_store.get(run.input_ref, run.input_sha256)).decode("utf-8")
                asyncio.create_task(_drive_from_stage(run.run_id, raw, next_stage))

            asyncio.create_task(continue_after_recovered_gate())
            return
        if _input_store is None or not run.input_ref or not run.input_sha256:
            _logger.error("Cannot resume %s: durable input unavailable", run.run_id)
            return
        raw = (await _input_store.get(run.input_ref, run.input_sha256)).decode("utf-8")
        _prd_cache[run.run_id] = raw
        if plan.stage not in {Stage.ARCHITECT, Stage.TEST_PLAN, Stage.CODEGEN, Stage.REVIEW_SCAN, Stage.DELIVER}:
            _logger.error("Cannot safely resume %s from unsupported boundary %s", run.run_id, plan.stage)
            return
        asyncio.create_task(_drive_from_stage(run.run_id, raw, plan.stage))

    try:
        summary = await recover_nonterminal_runs(
            _ledger, owner=os.getenv("HOSTNAME", "orchestrator-local"),
            resume=resume_recovered,
        )
        _logger.info("Startup recovery scan: %s", summary)
    except Exception as exc:
        _logger.warning("Startup recovery scan failed safely: %s", exc)
    yield
    if _ledger:
        await _ledger.close()


# ── OpenAPI metadata ─────────────────────────────────────────────────────────
# Single source of truth for the product version. Bump here on release; the
# badge in README + the /docs + /redoc pages all read this.
API_VERSION = os.environ.get("API_VERSION", "0.7.0")

API_DESCRIPTION = """\
The **Agentic SDLC Orchestrator** turns a Product Requirements Document into a
delivered pull request through a governed, human-gated agent pipeline.

**Pipeline:** Ingest → Assessor → *Resolver gate (human)* → Architect →
*Design-review gate* → Test-plan → Codegen → Review/Scan → Deliver.

Every meaningful decision is written to an append-only **decision ledger** with
its bundle citations, model, and cost. Hard-gated classes (PHI, auth) can never
be auto-resolved — they require an explicit, attributed human decision.

### Conventions
- **Streaming:** `GET /api/runs/{id}/stream` is a Server-Sent-Events stream of
  stage transitions. Everything else is plain JSON.
- **Auth:** gateway-fronted; the API trusts its ingress. CORS origins are
  env-driven (`CORS_ALLOWED_ORIGINS`).
- **Errors:** standard HTTP status codes with a `{ "detail": "..." }` body.
- **Interactive docs:** this page (`/docs`), ReDoc at `/redoc`, raw schema at
  `/openapi.json`.
"""

# Tag groups so /docs renders as a sectioned, navigable explorer instead of a
# flat list of 30+ operations. `x-displayName` + ordering are honored by ReDoc.
OPENAPI_TAGS = [
    {"name": "Runs", "description": "Create runs from a PRD, fetch state, stream progress, and control the run lifecycle (pause / resume / rerun / undo)."},
    {"name": "Gates & Decisions", "description": "Resolve ambiguity cards and release human gates: approve, reject, demote, finalize. Hard-gated (PHI/auth) classes require explicit individual decisions."},
    {"name": "Decision Ledger", "description": "Append-only audit trail of every agent + human decision, with bundle citations, model, and cost."},
    {"name": "Review Loop", "description": "Autonomous review→remediate→re-review loop controls and the Tier-B human merge touch-point."},
    {"name": "Self-Heal", "description": "Pipeline-doctor heal proposals and their human approval."},
    {"name": "Telemetry", "description": "Cost, latency, and decision-class analytics for dashboards."},
    {"name": "Configuration", "description": "Read + governed-PR write-back for agents, bundles, prompts, autonomy tiers, and hard-gate posture."},
    {"name": "Prompt Library", "description": "The versioned prompt catalog each stage resolves against."},
    {"name": "System", "description": "Liveness, health, and administrative maintenance."},
]


app = FastAPI(
    title="Agentic SDLC Orchestrator",
    version=API_VERSION,
    summary="Governed, human-gated agentic software-delivery pipeline API.",
    description=API_DESCRIPTION,
    openapi_tags=OPENAPI_TAGS,
    contact={
        "name": "Agentic SDLC",
        "url": "https://github.com/idanshimon/agentic-sdlc",
    },
    license_info={"name": "MIT", "url": "https://opensource.org/licenses/MIT"},
    lifespan=lifespan,
)

# CORS — allow Resolver UI + localhost dev to call the API + open SSE stream.
# Allowlist is env-driven so VNET migrations / new ingress FQDNs don't require
# a code change. CORS_ALLOWED_ORIGINS is a comma-separated list.
import os as _os
_default_origins = [
    "https://ca-resolver-ui-vnet.redbay-8e91f1bf.eastus.azurecontainerapps.io",
    "https://ca-resolver-ui.calmbay-c2786d2a.eastus.azurecontainerapps.io",
    "http://localhost:3000",
    "http://localhost:3001",
]
_env_origins = [o.strip() for o in _os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_env_origins or _default_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.middleware("http")
async def api_auth_boundary(request: Request, call_next):
    """Authenticate every non-public API request; mutations also get coarse RBAC."""
    public = {"/api/health", "/health", "/openapi.json", "/docs", "/redoc"}
    if request.url.path.startswith("/api/") and request.url.path not in public and request.method not in {"OPTIONS"}:
        try:
            principal = principal_from_request(request)
            if request.method not in {"GET", "HEAD"}:
                authorize_mutation(principal, request.url.path)
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        request.state.principal = principal
    return await call_next(request)


def _principal(request: Request) -> Principal:
    principal = getattr(request.state, "principal", None)
    if principal is None:
        principal = principal_from_request(request)
    return principal


def _authorize_run(request: Request, run: RunState) -> Principal:
    principal = _principal(request)
    require_team(principal, run.team_id)
    return principal


# ---------- helpers -----------------------------------------------------------
async def _push(run_id: str, ev: StageEvent | None) -> None:
    """Push an event to any open SSE subscriber AND durably persist the
    run to Cosmos so pod restarts don't zombie the run.

    Phase 6.1 fix (2026-06-16): previously save_run() only fired in the
    finally block of _drive, so any pod death mid-stage (revision
    rollover, OOM, network blip, scale-to-zero, ACR redeploy) left the
    Cosmos doc stuck at the ingest-time snapshot: status=running,
    events=[], decisions=[]. The /runs table then displayed 8 zombie
    rows all showing "running · 0 decisions · $0.0000" for hours after
    they had actually progressed through gates and decisions in-memory.

    Caught operator-side via screenshot: 8 of 13 rows showed "running"
    with no progress even though backend curl proved they were past the
    assessor stage. Verified via cross-check of /api/runs vs
    /api/runs/<id> showing list_status="running" / truth_events=0 for
    every revision-rollover survivor.

    Persist on every event so the durable view always matches in-memory
    state to within one stage transition. Cost: one extra Cosmos write
    per event (~30 events per run). At demo scale that's ~$0.001/run
    extra; at production scale we'd batch or debounce, but for now
    correctness wins over cost.
    """
    q = _queues.get(run_id)
    if q is not None:
        await q.put(ev)
    # Skip the durable write for the stream-complete sentinel — _drive's
    # own finally block has the final save and we don't want a double-write.
    if ev is not None and _ledger is not None:
        run = _runs.get(run_id)
        if run is not None:
            try:
                await _ledger.save_run_cas(run)
            except Exception as exc:
                _logger.warning(
                    "Per-event Cosmos save_run failed for %s on event "
                    "(%s, %s): %s",
                    run_id, ev.stage, ev.status, exc,
                )


async def _run_autopilot(run: RunState) -> None:
    """Auto-resolve non-invariant gating cards per run.mode (design.md §3).

    Rules:
      * Invariant-class cards (PHI / auth-policy) ALWAYS gate — added to
        autopilot_overrides.
      * HYBRID: only auto-resolve when ledger precedent exists for
        (team, class, slot_hash); otherwise leave the card to gate.
      * AUTOPILOT: auto-accept the recommended option on every non-invariant card.
      * All auto-decisions are tagged confidence_source='autopilot' and MUST
        NOT count toward ledger promotion math (handled in ledger.write_decision).
    """
    if run.mode not in (RunMode.AUTOPILOT, RunMode.HYBRID):
        return
    from .autonomy import AUTONOMY_MATRIX, autonomy_ref
    for card in run.cards:
        if not card.is_gating:
            continue
        if card.card_id in run.autopilot_decisions or card.card_id in run.autopilot_overrides:
            continue
        # Invariant override — always gates. (Belt: the matrix also returns
        # 'gate' for invariants, but this stays as the primary hard-lock so the
        # guarantee holds even if autonomy config is absent or bypassed.)
        if card.ambiguity_class in INVARIANT_CLASSES:
            run.autopilot_overrides.append(card.card_id)
            continue

        # Phase 2 — autonomy matrix (config-plane). When authored, it decides
        # per (team, class) whether to gate / autopilot-always / autopilot-above-
        # threshold, overriding the mode-driven default below. When unloaded,
        # rule is None and we preserve the exact pre-Phase-2 behaviour. We also
        # capture WHY (autonomy_ref) so the decision records why it was
        # autopiloted vs gated — the audit answer the compliance query reads.
        rule = AUTONOMY_MATRIX.rule_for(run.team_id, card.ambiguity_class)
        decision_ref = ""
        if rule is not None:
            if rule.mode == "gate":
                run.autopilot_overrides.append(card.card_id)
                continue
            if rule.mode == "autopilot_above_threshold":
                # Gate unless ledger precedent meets the configured confidence.
                if _ledger is None:
                    run.autopilot_overrides.append(card.card_id)
                    continue
                precedent = await _ledger.find_precedent(
                    run.team_id, card.ambiguity_class, card.slot_value_hash,
                )
                score = getattr(precedent, "accuracy_score", 0.0) if precedent else 0.0
                if not precedent or score < rule.threshold:
                    run.autopilot_overrides.append(card.card_id)
                    continue
                decision_ref = autonomy_ref(
                    run.team_id, card.ambiguity_class,
                    reason=f"precedent{score:g}>=t{rule.threshold:g}",
                )
            else:  # autopilot_always
                decision_ref = autonomy_ref(
                    run.team_id, card.ambiguity_class, reason="autopilot-always",
                )
        else:
            # HYBRID: gate when no precedent exists (legacy mode-driven path).
            if run.mode == RunMode.HYBRID:
                if _ledger is None:
                    continue  # no ledger → can't verify precedent → gate
                precedent = await _ledger.find_precedent(
                    run.team_id, card.ambiguity_class, card.slot_value_hash,
                )
                if not precedent:
                    continue
                decision_ref = autonomy_ref(
                    run.team_id, card.ambiguity_class, reason="hybrid-precedent",
                )
            else:  # pure AUTOPILOT mode, no matrix rule
                decision_ref = autonomy_ref(
                    run.team_id, card.ambiguity_class, reason="autopilot-mode",
                )
        # Pick the recommended option (or first option if none flagged).
        if not card.options:
            run.autopilot_overrides.append(card.card_id)
            continue
        recommended = next((o for o in card.options if o.recommended), card.options[0])
        idx = card.options.index(recommended)
        auto_decision = GateDecision(
            card_id=card.card_id,
            decision_kind="accept",
            resolution_text=recommended.resolution,
            option_index=idx,
            actor=f"autopilot:{run.team_id}",
            confidence_source="autopilot",
        )
        run.decisions.append(auto_decision)
        run.autopilot_decisions.append(card.card_id)
        if _ledger:
            entry = LedgerEntry(
                team_id=run.team_id, run_id=run.run_id, card_id=card.card_id,
                ambiguity_class=card.ambiguity_class,
                slot_value_hash=card.slot_value_hash,
                resolution_text=recommended.resolution,
                decision_kind="accept",
                created_by=auto_decision.actor,
                confidence_source="autopilot",
                # Wire (2026-06-21): stamp the bundles the deciding agent
                # subscribes to. Ambiguity cards come out of the assessor stage,
                # so the assessor's bundle subscriptions (security, privacy)
                # govern this decision. Makes the agent→bundle relationship a
                # queryable fact on the decision, not display-only card metadata.
                bundle_refs=bundles_for_stage("assessor"),
                # Config-plane Phase 2: WHY this card was auto-resolved (the
                # autonomy rule + reason), so the decision is self-explaining in
                # the compliance query. Computed per-branch above.
                autonomy_ref=decision_ref,
                # Phase 2.6: pin the prompt chain that produced this
                # auto-decision. Cards come out of the assessor stage,
                # so the assessor's chain is the right one to capture.
                # Empty dict for runs that pre-date Phase 2 wiring (legacy
                # entries render "chain unavailable (pre-v2)" in the UI).
                prompt_resolution_path=run.prompt_chain_by_stage.get("assessor"),
            )
            try:
                await _ledger.write_decision(entry)
            except InvariantWriteBlocked:
                # Should not happen — invariants already filtered above, but
                # if the ledger blocks anyway, force the card to gate.
                run.autopilot_decisions.remove(card.card_id)
                run.decisions.remove(auto_decision)
                run.autopilot_overrides.append(card.card_id)


def _generators_from_stage(run: RunState, prd_text: str, start: Stage):
    """Build downstream generators without replaying completed boundaries."""
    ordered = [
        (Stage.ARCHITECT, lambda: stage_architect(run)),
        (Stage.TEST_PLAN, lambda: stage_test_plan(run, prd_text=prd_text)),
        (Stage.CODEGEN, lambda: stage_codegen(run)),
        (Stage.REVIEW_SCAN, lambda: stage_review_scan(run)),
        (Stage.DELIVER, lambda: stage_deliver(run)),
    ]
    start_index = next((i for i, (stage, _) in enumerate(ordered) if stage == start), None)
    if start_index is None:
        raise ValueError(f"stage-specific continuation unsupported for {start.value}")
    return [(stage, factory()) for stage, factory in ordered[start_index:]]


async def _drive_from_stage(run_id: str, prd_text: str, start: Stage) -> None:
    """Continue only stage boundaries safe to replay from durable artifacts."""
    run = _runs[run_id]
    owner = os.getenv("HOSTNAME", "orchestrator-local")
    lease_stop = asyncio.Event()
    lease_lost = asyncio.Event()
    lease_task = (
        asyncio.create_task(maintain_lease(
            _ledger, run_id=run_id, owner=owner, stop=lease_stop, lost=lease_lost,
        )) if _ledger and run.lease_owner == owner else None
    )
    try:
        for _, generator in _generators_from_stage(run, prd_text, start):
            if lease_lost.is_set():
                raise LeaseConflict("recovery lease lost; stopping stage execution")
            async for ev in generator:
                if lease_lost.is_set():
                    raise LeaseConflict("recovery lease lost; stopping stage execution")
                await _push(run_id, ev)
                if ev.status == "completed":
                    checkpoint(run, ev.stage, "completed")
                if ev.status == "failed":
                    run.status = RunStatus.FAILED
                    return
        run.status = RunStatus.COMPLETED
        url = await write_decisions_md(run)
        await _push(run_id, StageEvent(
            run_id=run_id, stage=Stage.DELIVER, status="completed",
            message=f"decisions.md written: {url}", payload={"decisions_md_url": url},
        ))
    except Exception as exc:
        _logger.exception("Recovered pipeline crashed: %s", exc)
        run.status = RunStatus.FAILED
        await _push(run_id, StageEvent(
            run_id=run_id, stage=run.current_stage, status="failed", message=str(exc),
        ))
    finally:
        lease_stop.set()
        if lease_task:
            await lease_task
        try:
            if run.lease_owner == owner:
                release_lease(run, owner)
        except Exception as exc:
            _logger.warning("Recovery lease release failed for %s: %s", run_id, exc)
        if _ledger:
            await _ledger.save_run_cas(run)
        await _push(run_id, None)


async def _drive(run_id: str, prd_text: str) -> None:
    """Background task: walks the pipeline graph, pausing at gates."""
    run = _runs[run_id]
    try:
        async for ev in stage_ingest(run, prd_text):
            await _push(run_id, ev)
            if ev.status == "gate_open":
                await _open_gate(run, ev.stage)

        async for ev in stage_assessor(run, prd_text):
            await _push(run_id, ev)
            if ev.status == "gate_open":
                # Autopilot intercept — runs after Assessor, before the gate opens.
                if run.mode in (RunMode.AUTOPILOT, RunMode.HYBRID):
                    await _run_autopilot(run)
                    await _push(run_id, StageEvent(
                        run_id=run_id, stage=Stage.RESOLVER, status="progress",
                        message=(
                            f"Autopilot auto-resolved {len(run.autopilot_decisions)} "
                            f"card(s); {len(run.autopilot_overrides)} require human review"
                        ),
                        payload={
                            "autopilot_decisions": list(run.autopilot_decisions),
                            "autopilot_overrides": list(run.autopilot_overrides),
                            "mode": run.mode.value,
                        },
                    ))
                    if not run.autopilot_overrides:
                        # Nothing needs human attention — show the summary briefly,
                        # then skip opening the gate at all (design.md §3 "show the work").
                        await asyncio.sleep(3.0)
                        continue
                await _open_gate(run, ev.stage)

        async for ev in stage_architect(run):
            await _push(run_id, ev)
            if ev.status == "gate_open":
                await _open_gate(run, ev.stage)

        for gen in (
            stage_test_plan(run, prd_text=prd_text), stage_codegen(run),
            stage_review_scan(run), stage_deliver(run),
        ):
            async for ev in gen:
                await _push(run_id, ev)
                if ev.status == "completed":
                    checkpoint(run, ev.stage, "completed")
                if ev.status == "failed":
                    run.status = RunStatus.FAILED
                    return

        run.status = RunStatus.COMPLETED
        url = await write_decisions_md(run)
        await _push(run_id, StageEvent(
            run_id=run_id, stage=Stage.DELIVER, status="completed",
            message=f"decisions.md written: {url}", payload={"decisions_md_url": url},
        ))
    except ModelPolicyRefusal as refusal:
        # Phase 4 (add-configuration-plane): a config/models.yaml refusal is a
        # GOVERNED failure, not a crash — audit it. Write a ledger entry citing
        # the model-policy rule (autonomy_ref=rule_ref) so the compliance query
        # can explain WHY the run failed, then fail the run with an honest event.
        _logger.warning("Model policy refused a stage: %s", refusal)
        run.status = RunStatus.FAILED
        await _write_model_refusal_entry(run, refusal)
        await _push(run_id, StageEvent(
            run_id=run_id, stage=run.current_stage, status="failed",
            message=str(refusal),
            payload={"model_policy_rule": refusal.rule_ref,
                     "refused_model": refusal.model, "stage": refusal.stage},
        ))
    except Exception as exc:
        _logger.exception("Pipeline crashed: %s", exc)
        run.status = RunStatus.FAILED
        await _push(run_id, StageEvent(
            run_id=run_id, stage=run.current_stage, status="failed", message=str(exc),
        ))
    finally:
        if _ledger:
            await _ledger.save_run_cas(run)
        await _push(run_id, None)  # sentinel: stream complete


async def _write_model_refusal_entry(run: RunState, refusal: ModelPolicyRefusal) -> None:
    """Persist a ledger entry for a model-policy refusal, citing the governing
    rule in `autonomy_ref` (the same queryable audit field the autopilot/gate
    paths use). Safe no-op when the ledger is disabled (tests / bootstrap)."""
    if _ledger is None:
        return
    try:
        await _ledger.write_decision(LedgerEntry(
            team_id=run.team_id, run_id=run.run_id,
            ambiguity_class="other",
            resolution_text=(
                f"model policy refused {refusal.model!r} at stage "
                f"{refusal.stage!r}: {refusal.reason}"
            ),
            decision_kind="reject", created_by="model-policy@config-plane",
            confidence_source="autopilot",
            stage=refusal.stage,
            # cite the governing model-policy rule — the audit answer the
            # compliance query reads (same field the autonomy paths stamp).
            autonomy_ref=refusal.rule_ref,
        ))
    except Exception as exc:  # pragma: no cover - defensive; never mask the failure
        _logger.warning("could not write model-refusal ledger entry: %s", exc)


async def _open_gate(run: RunState, stage: Stage) -> None:
    """Block until a gate decision arrives, recording human-attention wall-clock."""
    run.status = RunStatus.AWAITING_GATE
    checkpoint(run, stage, "awaiting_gate")
    run.pending_gate = {
        "gate_id": f"{run.run_id}:{stage.value}:{run.checkpoint_version}",
        "stage": stage.value,
        "version": run.checkpoint_version,
        "status": "open",
    }
    # Persist the durable gate before registering/waiting on the local wake-up.
    if _ledger:
        await _ledger.save_run_cas(run)
    ev = asyncio.Event()
    _gate_events[run.run_id] = ev
    # An approval may have committed between persistence and local registration.
    if run.pending_gate and run.pending_gate.get("status") == "resolved":
        ev.set()
    _gate_started[run.run_id] = time.monotonic()
    with span(f"gate.{stage}"):
        await ev.wait()
    elapsed = time.monotonic() - _gate_started.pop(run.run_id, time.monotonic())
    run.gate_wall_clock_seconds += elapsed
    record_gate_wall_clock(stage.value, elapsed)
    run.pending_gate = None
    run.status = RunStatus.RUNNING
    checkpoint(run, stage, "completed")


def _release_gate(run_id: str) -> None:
    run = _runs.get(run_id)
    if run is not None and run.pending_gate:
        run.pending_gate["status"] = "resolved"
        run.run_version += 1
    ev = _gate_events.pop(run_id, None)
    if ev:
        ev.set()


# ---------- routes ------------------------------------------------------------
@app.get("/healthz", tags=["System"])
async def healthz() -> dict:
    """Liveness probe (no external deps touched)."""
    return {"status": "ok", "runs_in_memory": len(_runs)}


@app.get("/api/config/hard-gate-classes", tags=["Configuration"])
async def get_hard_gate_classes() -> dict:
    """Tier-2 governance posture: which ambiguity classes can never be
    auto-resolved or bulk/soft-approved (each requires an explicit, attributed,
    individual human decision). PHI + auth are an immovable floor; the set may
    be extended via the HARD_GATE_CLASSES env (never shrunk). Read-only — the
    Settings/Governance UI renders this; changing the posture is a
    standards-change PR.
    """
    return {
        "hard_gate_classes": sorted(_config.HARD_GATE_CLASSES),
        "floor": sorted(INVARIANT_CLASSES),
        "explainer": (
            "These classes can never be auto-resolved (tier-0) or bulk/soft-"
            "approved (tier-1) — each requires an explicit, attributed human "
            "decision (tier-2). PHI and auth are an immovable floor. Changing "
            "this set is a standards-change PR."
        ),
    }


@app.get("/api/config/repo-autonomy", tags=["Configuration"])
async def get_repo_autonomy() -> dict:
    """Per-repo autonomy posture for the autonomous review loop.

    Which repos have been graduated to autonomous merge (Tier A), autonomous
    review + human merge (Tier B), or advisory only (Tier C — the default for
    every repo not listed). A repo with a recent PHI/deny blocker can never hold
    Tier A (graduation must be earned). Read-only — changing a tier is a config
    edit (governed PR); PHI/auth/deny always force runtime escalation regardless.
    """
    from . import repo_autonomy as _ra
    return _ra.REPO_AUTONOMY.posture_summary()


class ReviewLoopMergeBody(BaseModel):
    loop_id: str
    expected_head_sha: str = Field(pattern=r"^[0-9a-fA-F]{40}$")
    merge_method: str = "merge"


@app.get("/api/review-loops", tags=["Review Loop"])
async def list_review_loops(request: Request, limit: int = 100) -> dict:
    principal = _principal(request)
    if not principal.has_any_role("operator", "release_manager", "standards_reviewer"):
        raise HTTPException(403, "principal is not authorized to read review loops")
    if _ledger:
        records = await _ledger.list_review_loops(min(max(limit, 1), 200))
    else:
        records = list(_review_loop_registry._items.values())[-limit:]
    clean = [{k: v for k, v in record.items() if not k.startswith("_")} for record in records]
    return {"items": clean, "count": len(clean)}


@app.post("/api/review-loops", tags=["Review Loop"], status_code=202)
async def dispatch_review_loop(body: ReviewLoopDispatch, request: Request) -> dict:
    """Accept an authenticated GitHub workload dispatch for an exact PR head.

    The deterministic loop identity makes workflow retries safe. Snapshot fetch,
    review execution, and GitHub outcome publishing are subsequent workers.
    """
    principal = _principal(request)
    identity = identity_for(body)
    supplied_key = request.headers.get("idempotency-key", "")
    expected_key = f"{body.repo}:{body.pr_number}:{body.head_sha}"
    if supplied_key != expected_key:
        raise HTTPException(409, "review-loop idempotency key must bind repo, PR, and head SHA")
    record, created = _review_loop_registry.get_or_create(identity, principal.subject)
    if _ledger:
        durable = await _ledger.get_review_loop(identity.loop_id)
        if durable:
            record.clear()
            record.update({k: v for k, v in durable.items() if not k.startswith("_")})
            created = False
        elif created:
            persisted = await _ledger.create_review_loop_strict(record)
            record["_etag"] = persisted.get("_etag")
    if created:
        token = os.getenv("DELIVER_GH_TOKEN") or os.getenv("GH_TOKEN") or ""
        if not token:
            record["disposition"] = "FAILED"
            record["reason"] = "GitHub token is not configured"
            raise HTTPException(503, record["reason"])
        import httpx
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                snapshot = await fetch_pr_snapshot(
                    repo=body.repo, pr_number=body.pr_number,
                    expected_head_sha=body.head_sha, token=token, client=client,
                )
            record["snapshot_files"] = sorted(snapshot.files)
            record["snapshot_file_count"] = len(snapshot.files)
            record["disposition"] = "SNAPSHOT_READY"

            from . import repo_autonomy as _ra
            tier = _ra.REPO_AUTONOMY.tier_for(body.repo)

            async def review(files: dict):
                return build_review_verdict(files, team="defaults")

            async def remediate(verdict, files: dict):
                # Fail-safe bounded behavior: no model remediator is wired for
                # external PRs yet, so preserve bytes and let the attempt bound
                # escalate rather than inventing a fix.
                return dict(files)

            async def merge(repo: str):
                result = await merge_pull_request(
                    repo=repo, pr_number=body.pr_number, token=token,
                    expected_head_sha=body.head_sha,
                )
                if not result.merged:
                    raise RuntimeError(result.reason)
                return f"https://github.com/{repo}/pull/{body.pr_number}"

            loop_result = await run_review_loop(
                repo=body.repo, tier=tier, code_files=snapshot.files,
                review=review, remediate=remediate, do_merge=merge,
            )
            disposition = {
                "converged": "MERGED",
                "awaiting_human_merge": "PASSED_AWAITING_MERGE",
                "escalated": "ESCALATED",
                "advisory": "ADVISORY",
            }[loop_result.outcome]
            assurance = {
                "deterministic_policy": "pass" if disposition in {"MERGED", "PASSED_AWAITING_MERGE", "ADVISORY"} else "fail",
                "build_tests": "not_run",
                "dependency_security": "not_run",
                "semantic_review": "pass" if disposition in {"MERGED", "PASSED_AWAITING_MERGE"} else "unknown",
                "mandatory_human": "not_run" if tier in {"A", "B"} else "unknown",
            }
            record.update({
                "tier": tier,
                "attempt": max(1, loop_result.attempts + 1),
                "disposition": disposition,
                "merged": loop_result.merged,
                "assurance": assurance,
                "ledger_hops": [
                    {
                        **hop,
                        "loop_id": identity.loop_id,
                        "repo": identity.repo,
                        "pr_number": identity.pr_number,
                        "head_sha": identity.head_sha,
                        "tier": tier,
                        "disposition": disposition,
                        **assurance,
                    }
                    for hop in loop_result.ledger_hops
                ],
            })
            async with httpx.AsyncClient(timeout=30.0) as client:
                published = await publish_review_outcome(
                    client=client, repo=body.repo, pr_number=body.pr_number,
                    head_sha=body.head_sha, token=token, disposition=disposition,
                    summary=f"{disposition}; attempts={loop_result.attempts}",
                )
            record.update({
                "check_id": published.check_id, "check_url": published.check_url,
                "comment_id": published.comment_id, "comment_url": published.comment_url,
            })
            if _ledger:
                etag = record.pop("_etag", None)
                if not etag:
                    durable = await _ledger.get_review_loop(identity.loop_id)
                    etag = (durable or {}).get("_etag")
                if not etag:
                    raise HTTPException(503, "review-loop durable version unavailable")
                persisted = await _ledger.save_review_loop_strict(record, expected_etag=etag)
                record["_etag"] = persisted.get("_etag")
        except SnapshotError as exc:
            record["disposition"] = "FAILED"
            record["reason"] = str(exc)
            raise HTTPException(409, str(exc)) from exc
    return {**record, "created": created}


# Imported at module level so tests can monkeypatch main.merge_pull_request.
from .merge_pr import merge_pull_request  # noqa: E402


@app.post("/api/review-loops/merge", tags=["Review Loop"])
async def review_loop_merge(body: ReviewLoopMergeBody, request: Request) -> dict:
    """The Tier-B human merge touch-point.

    Tier B = the loop reviews to PASS autonomously, but a human clicks merge —
    this endpoint is that click. Enforces the tier server-side: refuses on
    Tier-C / unlisted repos (no autonomous merge surface there; the loop only
    comments). Tier-A repos merge inside the loop, so this endpoint is the B path.
    A blocked merge returns merged=false + escalate (honest), never a fake success.
    """
    from . import repo_autonomy as _ra
    record = _review_loop_registry._items.get(body.loop_id)
    if _ledger:
        durable = await _ledger.get_review_loop(body.loop_id)
        if durable:
            record = {k: v for k, v in durable.items() if not k.startswith("_")}
            record["_etag"] = durable.get("_etag")
            _review_loop_registry._items[body.loop_id] = record
    if not record:
        raise HTTPException(404, "review loop not found")
    if record.get("disposition") != "PASSED_AWAITING_MERGE":
        raise HTTPException(409, "loop is not in PASSED_AWAITING_MERGE state")
    if record.get("head_sha") != body.expected_head_sha.lower():
        raise HTTPException(409, "stale_head_sha")
    tier = _ra.REPO_AUTONOMY.tier_for(record["repo"])
    if tier != "B":
        raise HTTPException(409, "human merge endpoint is restricted to Tier B")
    token = os.getenv("DELIVER_GH_TOKEN") or os.getenv("GH_TOKEN") or ""
    # Re-read exact head before irreversible merge.
    import httpx
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            await fetch_pr_snapshot(
                repo=record["repo"], pr_number=record["pr_number"],
                expected_head_sha=body.expected_head_sha, token=token, client=client,
            )
    except SnapshotError as exc:
        raise HTTPException(409, str(exc)) from exc
    result = await merge_pull_request(
        repo=record["repo"], pr_number=record["pr_number"], token=token,
        merge_method=body.merge_method, expected_head_sha=body.expected_head_sha,
    )
    if result.merged:
        record["disposition"] = "MERGED"
        record["merge_sha"] = result.sha
        if _ledger:
            etag = record.pop("_etag", None)
            if not etag:
                raise HTTPException(503, "review-loop durable version unavailable")
            persisted = await _ledger.save_review_loop_strict(record, expected_etag=etag)
            record["_etag"] = persisted.get("_etag")
    return {
        "loop_id": body.loop_id,
        "merged": result.merged,
        "sha": result.sha,
        "escalate": result.escalate,
        "reason": result.reason,
        "tier": tier,
        "disposition": record["disposition"],
    }


# ── Editing plane (#3): governed PR write-back ────────────────────────────────
# The Agents / Bundles / Prompts editors save real config files the pipeline
# reads. Per the four-plane governance model, an edit opens a PR (committee /
# CODEOWNERS review) rather than silently mutating running behaviour. All three
# call the shared config_writer core, which confines writes to the config roots.

class _ConfigSaveBase(BaseModel):
    content: str
    commit_message: str
    pr_title: Optional[str] = None
    pr_body: str = ""


class AgentSaveBody(_ConfigSaveBase):
    name: str  # agent name → .github/agents/<name>.agent.md


class BundleSaveBody(_ConfigSaveBase):
    dept: str          # security | privacy | architect | finops
    version: str       # e.g. v0.1.0
    file: str = "rules.yaml"  # rules.yaml | envelope.yaml | reviewers.yaml


class PromptSaveBody(_ConfigSaveBase):
    scope: str         # global | persona | team
    stage: str         # assessor | architect | test_plan | codegen | review_scan
    version: str       # vN (the editor picks the next version)
    persona: Optional[str] = None  # required for persona/team scope


def _safe_seg(s: str) -> str:
    """Reject path-segment injection (slashes, dots) in user-supplied ids."""
    if not s or "/" in s or "\\" in s or ".." in s:
        raise HTTPException(400, f"invalid identifier: {s!r}")
    return s


async def _do_config_save(rel_path: str, body: _ConfigSaveBase, labels: list[str]) -> dict:
    from .config_writer import write_config_pr, ConfigWriteError
    try:
        result = await write_config_pr(
            rel_path=rel_path,
            content=body.content,
            commit_message=body.commit_message,
            pr_title=body.pr_title or body.commit_message,
            pr_body=body.pr_body,
            labels=labels,
        )
    except ConfigWriteError as exc:
        raise HTTPException(422, f"config write failed: {exc}") from exc
    return {
        "ok": result.ok,
        "pr_url": result.pr_url,
        "branch": result.branch,
        "path": result.path,
        "dry_run": result.dry_run,
        "message": result.message,
    }


@app.post("/api/config/agents/save", tags=["Configuration"])
async def save_agent(body: AgentSaveBody) -> dict:
    """Edit a custom agent (.github/agents/<name>.agent.md) → opens a PR.

    Prompts/agents may additionally hot-reload via /api/config/reload so a demo
    sees the effect before merge; the PR remains the durable source of truth.
    """
    name = _safe_seg(body.name)
    return await _do_config_save(
        f".github/agents/{name}.agent.md", body,
        labels=["config-edit", "agent", f"agent/{name}"],
    )


@app.post("/api/config/bundles/save", tags=["Configuration"])
async def save_bundle(body: BundleSaveBody) -> dict:
    """Edit a standards bundle file → opens a PR. PR-ONLY (no live apply):
    live-editing the compliance standards would bypass committee review, which
    is the entire governance story. The bundle takes effect only after merge.

    Phase 3 governance teeth (add-configuration-plane): before opening the PR,
    a rules.yaml edit to an EXISTING bundle is validated — a diff that would
    delete, unlock, de-classify, or downgrade a `phi_locked` rule is REFUSED
    (HTTP 409) before any PR is created. PHI controls can only be strengthened.
    This mirrors the autonomy invariant hard-lock: even a well-formed edit
    cannot quietly relax a PHI rule. New bundle versions (no existing file) and
    non-rules files (envelope/reviewers) skip this check.
    """
    dept = _safe_seg(body.dept)
    version = _safe_seg(body.version)
    file = _safe_seg(body.file)
    if file == "rules.yaml":
        _validate_bundle_rules_edit(dept, version, body.content)
    return await _do_config_save(
        f"standards-bundles/{dept}/{version}/{file}", body,
        labels=["config-edit", "standards-change", f"dept/{dept}"],
    )


def _validate_bundle_rules_edit(dept: str, version: str, proposed_content: str) -> None:
    """Refuse a rules.yaml edit that weakens a phi_locked rule. No-op when the
    bundle version is new (nothing to protect) or the proposed YAML is malformed
    (the PR flow / CI surfaces the parse error; we don't 500 the editor here)."""
    from .bundle_rules import (
        Bundle,
        PhiLockViolation,
        load_bundle,
        load_bundle_from_text,
    )

    try:
        existing = load_bundle(dept, version)
    except FileNotFoundError:
        return  # brand-new bundle version — no existing rule to protect
    except Exception as exc:  # pragma: no cover - defensive
        _logger.warning("bundle-edit validation: could not load existing %s/%s: %s",
                        dept, version, exc)
        return
    try:
        proposed = load_bundle_from_text(proposed_content)
    except Exception as exc:
        # Malformed proposed YAML — let the PR/CI catch it rather than block here,
        # UNLESS it drops PHI rules by being unparseable. Treat as empty to be safe.
        _logger.info("bundle-edit validation: proposed YAML unparseable (%s); "
                     "treating as rule-less for lock check", exc)
        proposed = Bundle(dept=dept, version=version)
    try:
        from .bundle_rules import validate_bundle_edit
        validate_bundle_edit(existing, proposed)
    except PhiLockViolation as exc:
        raise HTTPException(409, str(exc)) from exc


@app.post("/api/config/prompts/save", tags=["Configuration"])
async def save_prompt(body: PromptSaveBody) -> dict:
    """Save a new prompt version (prompts/<scope>/<persona>/<stage>/v<N>.yaml)
    → opens a PR. The editor picks the next version; the YAML carries
    status/superseded_by so the catalog resolves the right one."""
    scope = _safe_seg(body.scope)
    stage = _safe_seg(body.stage)
    version = _safe_seg(body.version)
    if scope == "global":
        rel = f"prompts/global/{stage}/{version}.yaml"
    else:
        if not body.persona:
            raise HTTPException(400, f"persona required for scope={scope!r}")
        persona = _safe_seg(body.persona)
        rel = f"prompts/{scope}/{persona}/{stage}/{version}.yaml"
    return await _do_config_save(
        rel, body, labels=["config-edit", "prompt", f"stage/{stage}"],
    )


@app.get("/api/config/pins")
async def get_pins() -> dict:
    """Bundle-version pin matrix for the config UI (Phase 3, config-plane).

    Returns {defaults, teams, available} from standards-bundles/PINS.yaml plus
    the on-disk bundle versions per department, so the UI can render the
    team→version matrix and offer a valid pin dropdown. Read-only — changing a
    pin goes through the governed bundles PR flow, same as any standards change.
    """
    from .pins import read_pins
    return read_pins()


@app.post("/api/config/reload", tags=["Configuration"])
async def reload_config() -> dict:
    """Hot-reload the running orchestrator's agent-bundle + prompt caches so an
    edit takes effect in THIS session without redeploy. Prompts/agents only —
    bundles are PR-only. The durable source of truth is still the merged PR."""
    from .agent_bundles import reload_agent_bundles
    reload_agent_bundles()
    reloaded = ["agent_bundles"]
    try:
        from .prompt_library_v2 import reload_prompt_catalog  # type: ignore
        reload_prompt_catalog()
        reloaded.append("prompt_catalog")
    except Exception:
        pass  # prompt catalog reload is best-effort
    return {"ok": True, "reloaded": reloaded}


@app.post("/api/run", tags=["Runs"])
async def create_run(
    request: Request,
    prd: UploadFile = File(...),
    team_id: str = Form(default_factory=lambda: os.environ.get("LEDGER_TEAM_ID", "team-demo")),
    mode: str = Form("manual"),
    stage_providers: str = Form(""),
) -> dict:
    """Accept a PRD upload and kick off the 9-stage pipeline (design.md §2).

    `team_id` is the Cosmos partition every decision for this run is written
    under. It defaults to the `LEDGER_TEAM_ID` env var (falling back to
    "team-demo"), which MUST match the team the dashboard's LEDGER_MCP_TOKEN is
    scoped to — otherwise the run's decisions land in a partition the dashboard
    token cannot read and the Decisions view appears empty (KI-1 Bug B). The
    previous hardcoded "cardiology" default caused exactly that divergence.

    `mode` is per-run autopilot opt-in: "manual" (default), "autopilot", or "hybrid".
    `stage_providers` is an optional JSON string mapping stage→{provider,model,via_apim}
    to override the default config for this run only. Example:
        {"architect": {"provider": "foundry-anthropic", "model": "claude-sonnet-4-6"}}
    """
    import json as _json
    raw = (await prd.read()).decode("utf-8", errors="replace")
    try:
        run_mode = RunMode(mode.lower())
    except ValueError:
        raise HTTPException(400, f"invalid mode: {mode!r} (use manual/autopilot/hybrid)")

    overrides: dict[str, dict] = {}
    if stage_providers:
        try:
            parsed = _json.loads(stage_providers)
        except _json.JSONDecodeError as exc:
            raise HTTPException(400, f"stage_providers must be valid JSON: {exc}")
        if not isinstance(parsed, dict):
            raise HTTPException(400, "stage_providers must be a JSON object")
        valid_stages = {"ingest", "assessor", "architect", "test_plan", "codegen", "review_scan"}
        for stage_key, val in parsed.items():
            if stage_key not in valid_stages:
                raise HTTPException(400, f"unknown stage: {stage_key!r}")
            if not isinstance(val, dict):
                raise HTTPException(400, f"stage_providers[{stage_key!r}] must be an object")
            overrides[stage_key] = {k: v for k, v in val.items() if k in ("provider", "model", "via_apim")}

    principal = _principal(request)
    require_team(principal, team_id)

    # Configuration plane (Phase 1): resolve team_id against the org model. Once a
    # customer has authored org.yaml, an unknown team is refused rather than
    # written as an anonymous ledger entry (openspec: add-configuration-plane).
    # With no org.yaml loaded (bootstrap/demo), resolution is permissive.
    from .org_model import ORG_MODEL, UnknownTeamError
    try:
        ORG_MODEL.resolve_team(team_id)
    except UnknownTeamError as exc:
        raise HTTPException(422, str(exc))

    run = RunState(
        team_id=team_id, prd_blob_url=f"inline://{prd.filename}", mode=run_mode,
        stage_provider_overrides=overrides,
    )
    # Production acknowledges only after input + initial run are durable. Tests
    # that intentionally omit infrastructure retain the explicit local path.
    if _input_store is not None:
        try:
            run.input_ref, run.input_sha256 = await _input_store.put(run.run_id, raw.encode("utf-8"))
            run.prd_blob_url = run.input_ref
        except Exception as exc:
            raise HTTPException(503, f"failed to persist run input: {exc}") from exc
    if _ledger:
        try:
            await _ledger.create_run_strict(run)
        except Exception as exc:
            raise HTTPException(503, f"failed to persist initial run: {exc}") from exc
    _runs[run.run_id] = run
    _queues[run.run_id] = asyncio.Queue()
    _prd_cache[run.run_id] = raw  # local optimization; durable ref is authoritative
    asyncio.create_task(_drive(run.run_id, raw))
    return {"run_id": run.run_id, "stream_url": f"/api/runs/{run.run_id}/stream"}


@app.post("/api/runs/{run_id}/rerun", tags=["Runs"])
async def rerun(run_id: str, request: Request, body: dict | None = None) -> dict:
    """Start a fresh run with the same PRD + team_id as `run_id`, optionally
    in a different mode. The original run is left untouched for A/B comparison.

    Body (optional JSON): {"mode": "manual" | "autopilot" | "hybrid"}
    If mode is omitted, INVERTS the original: manual -> autopilot, otherwise -> manual.

    Returns the new run_id. The old run remains in _runs (audit chain preserved).
    """
    src = _runs.get(run_id)
    if src is None:
        raise HTTPException(404, "source run not found")
    _authorize_run(request, src)
    raw = _prd_cache.get(run_id)
    if raw is None and _input_store is not None and src.input_ref and src.input_sha256:
        try:
            raw = (await _input_store.get(src.input_ref, src.input_sha256)).decode("utf-8")
        except Exception as exc:
            raise HTTPException(409, f"source PRD could not be restored: {exc}") from exc
    if raw is None:
        raise HTTPException(409, "source PRD is unavailable; please resubmit")

    # Determine target mode
    requested = (body or {}).get("mode")
    if requested:
        try:
            target_mode = RunMode(requested.lower())
        except ValueError:
            raise HTTPException(400, f"invalid mode: {requested!r}")
    else:
        # Invert: manual <-> autopilot. Hybrid -> manual.
        target_mode = RunMode.AUTOPILOT if src.mode == RunMode.MANUAL else RunMode.MANUAL

    new_run = RunState(
        team_id=src.team_id,
        prd_blob_url=src.prd_blob_url,
        mode=target_mode,
        input_ref=src.input_ref,
        input_sha256=src.input_sha256,
    )
    if _ledger:
        try:
            await _ledger.create_run_strict(new_run)
        except Exception as exc:
            raise HTTPException(503, f"failed to persist rerun: {exc}") from exc
    _runs[new_run.run_id] = new_run
    _queues[new_run.run_id] = asyncio.Queue()
    _prd_cache[new_run.run_id] = raw
    asyncio.create_task(_drive(new_run.run_id, raw))
    return {
        "run_id": new_run.run_id,
        "source_run_id": run_id,
        "mode": target_mode.value,
        "team_id": src.team_id,
        "stream_url": f"/api/runs/{new_run.run_id}/stream",
    }


@app.get("/api/runs/{run_id}", tags=["Runs"])
async def get_run(run_id: str, request: Request) -> RunState:
    """Return the run state. See design.md §2.

    Resolves in this order:
      1. In-memory _runs dict (live runs in this pod)
      2. Cosmos pipeline-runs container (durable; survives pod restart)

    The in-memory check covers the live-streaming case where /api/runs/{id}/stream
    is hot. The Cosmos fallback covers the long-tail case where an operator
    drills into a historical run from /runs after a deploy or scale event.
    """
    run = _runs.get(run_id)
    if run is not None:
        _authorize_run(request, run)
        return run
    # Cosmos fallback. Ledger client may be None in stub-only test runs.
    if _ledger is not None:
        try:
            doc = await _ledger.get_run(run_id)
        except Exception as exc:
            _logger.warning("Cosmos get_run failed for %s: %s", run_id, exc)
            doc = None
        if doc is not None:
            try:
                hydrated = RunState.model_validate(doc)
            except Exception as exc:
                _logger.warning("Failed to re-hydrate Cosmos run doc %s: %s", run_id, exc)
                raise HTTPException(500, "persisted run state is invalid") from exc
            _authorize_run(request, hydrated)
            return hydrated
    raise HTTPException(404, "run not found")


@app.get("/api/runs/{run_id}/ledger", tags=["Decision Ledger"])
async def get_run_ledger(run_id: str, request: Request) -> dict:
    """Return ledger entries written for this run.

    Cross-partition Cosmos query so the caller doesn't have to know which
    team_id the run was filed under. Useful for:
      - UI: render decision provenance on /runs/<id>
      - Phase 2.6 verification: confirm prompt_resolution_path is pinned
        on every decision the assessor / approver wrote
      - Audit: surface the full per-run decision history without going
        through ledger-mcp's per-token team-scoped auth

    Returns up to 100 entries ordered by created_at desc.
    """
    if _ledger is None:
        return {"entries": [], "run_id": run_id, "note": "ledger not configured"}

    # First fetch the run to learn its team_id (partition key).
    run = _runs.get(run_id)
    team_id: str | None = None
    if run is not None:
        team_id = run.team_id
    elif _ledger is not None:
        try:
            doc = await _ledger.get_run(run_id)
            if doc:
                team_id = doc.get("team_id")
        except Exception:
            pass

    if not team_id:
        raise HTTPException(404, "run not found and could not infer team_id")
    require_team(_principal(request), team_id)

    # Query the decision-ledger container for this team partition; filter to
    # entries for this run. Re-use the orchestrator's already-authenticated
    # CosmosLedger client via its underlying _ledger container handle.
    try:
        entries = []
        async for item in _ledger._ledger.query_items(  # type: ignore[attr-defined]
            query=(
                "SELECT * FROM c WHERE c.team_id = @team AND c.run_id = @run "
                "ORDER BY c.created_at DESC OFFSET 0 LIMIT 100"
            ),
            parameters=[
                {"name": "@team", "value": team_id},
                {"name": "@run",  "value": run_id},
            ],
            partition_key=team_id,
        ):
            entries.append(item)
        return {
            "run_id": run_id,
            "team_id": team_id,
            "count": len(entries),
            "entries": entries,
        }
    except Exception as exc:
        _logger.warning("Ledger read for run %s failed: %s", run_id, exc)
        raise HTTPException(500, f"ledger read failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Phase 3 — prompt catalog endpoints
#
# Surfaces the orchestrator's lazy-loaded PromptCatalog (Phase 2 work) to
# any caller — UI tree browse, version detail page, resolution preview.
# Read-only. Editing goes through a separate GitHub-PR flow (filed as
# openspec change add-prompt-editor-github-pr-flow).
# ---------------------------------------------------------------------------

@app.get("/api/prompts/catalog", tags=["Prompt Library"])
async def list_prompts() -> dict:
    """Return every prompt file in the catalog, grouped for UI tree browse.

    Shape:
      {
        loaded_from: "/app/prompts",
        count: 7,
        by_persona: {
          "pm":        [ {prompt_id, version, stage, scope, ...}, ... ],
          "architect": [ ... ],
          ...
        },
        by_stage: {
          "assessor":      [ ... ],
          ...
        },
        prompts: [  # flat list for table view
          { prompt_id, version, stage, scope, owner_persona, status,
            git_sha, authored_by, reason, effective_from, template_chars,
            template_first_line }
        ]
      }

    template_chars/template_first_line ship instead of the full template so
    list responses stay small (one ~50KB template would make this 50KB+
    each). Full body comes from /api/prompts/<id>.
    """
    from .prompt_library_v2 import PromptValidationError
    from ._pipeline_stages import get_prompt_catalog, _prompts_root
    try:
        catalog = get_prompt_catalog()
    except PromptValidationError as exc:
        raise HTTPException(500, f"catalog load failed: {exc}") from exc

    prompts = catalog._all  # safe — read-only view
    by_persona: dict[str, list] = {}
    by_stage: dict[str, list] = {}
    flat: list[dict] = []
    for p in prompts:
        first_line = p.template.splitlines()[0] if p.template else ""
        entry = {
            "prompt_id": p.prompt_id,
            "version": p.version,
            "stage": p.stage,
            "scope": p.scope,
            "owner_persona": p.owner_persona,
            "status": p.status,
            "git_sha": p.git_sha,
            "authored_by": p.authored_by,
            "reason": p.reason,
            "effective_from": p.effective_from,
            "superseded_by": p.superseded_by,
            "model_compat_notes": p.model_compat_notes,
            "template_chars": len(p.template),
            "template_first_line": first_line[:120],
        }
        flat.append(entry)
        by_persona.setdefault(p.owner_persona, []).append(entry)
        by_stage.setdefault(p.stage, []).append(entry)

    return {
        "loaded_from": str(_prompts_root()),
        "count": len(prompts),
        "by_persona": by_persona,
        "by_stage": by_stage,
        "prompts": flat,
    }


@app.get("/api/prompts/{prompt_id}", tags=["Prompt Library"])
async def get_prompt_detail(prompt_id: str, version: str | None = None) -> dict:
    """Return one prompt's full content + all versions.

    Query params:
      version: optional. If set, returns only that version. Otherwise
               returns the newest published version + all historical
               versions in the `versions` list.
    """
    from .prompt_library_v2 import PromptValidationError
    from ._pipeline_stages import get_prompt_catalog
    try:
        catalog = get_prompt_catalog()
    except PromptValidationError as exc:
        raise HTTPException(500, f"catalog load failed: {exc}") from exc

    matches = [p for p in catalog._all if p.prompt_id == prompt_id]
    if not matches:
        raise HTTPException(404, f"prompt_id={prompt_id!r} not found")

    matches.sort(key=lambda p: tuple(int(x) for x in p.version.lstrip("v").split(".")),
                 reverse=True)

    if version:
        match = next((p for p in matches if p.version == version), None)
        if not match:
            raise HTTPException(404, f"version={version!r} not found for prompt_id={prompt_id!r}")
        return {
            "prompt_id": match.prompt_id,
            "version": match.version,
            "stage": match.stage,
            "scope": match.scope,
            "owner_persona": match.owner_persona,
            "status": match.status,
            "git_sha": match.git_sha,
            "authored_by": match.authored_by,
            "reason": match.reason,
            "effective_from": match.effective_from,
            "superseded_by": match.superseded_by,
            "model_compat_notes": match.model_compat_notes,
            "template": match.template,
            "versions": [{"version": p.version, "status": p.status,
                          "effective_from": p.effective_from} for p in matches],
        }

    current = matches[0]
    return {
        "prompt_id": current.prompt_id,
        "version": current.version,
        "stage": current.stage,
        "scope": current.scope,
        "owner_persona": current.owner_persona,
        "status": current.status,
        "git_sha": current.git_sha,
        "authored_by": current.authored_by,
        "reason": current.reason,
        "effective_from": current.effective_from,
        "superseded_by": current.superseded_by,
        "model_compat_notes": current.model_compat_notes,
        "template": current.template,
        "versions": [{"version": p.version, "status": p.status,
                      "effective_from": p.effective_from} for p in matches],
    }


@app.post("/api/runs/{run_id}/pause", tags=["Runs"])
async def pause_run(run_id: str, request: Request) -> dict:
    """Flip run to MANUAL mode mid-flight. Pipeline does not interrupt the
    currently-executing stage, but the NEXT gate boundary respects the new
    mode (i.e. opens a human gate instead of auto-advancing).

    Pair with /resume to flip back to autopilot/hybrid.
    """
    run = _runs.get(run_id)
    if run is None:
        raise HTTPException(404, "run not found")
    principal = _authorize_run(request, run)
    payload = {"action": "pause"}
    record_key, replay = begin_command(
        run, request, principal, payload, expected_gate_version=None,
    )
    if replay is not None:
        return replay

    def mutate(authoritative: RunState) -> dict:
        previous = authoritative.mode
        authoritative.previous_mode = previous
        authoritative.mode = RunMode.MANUAL
        return {"ok": True, "previous_mode": previous.value, "current_mode": "manual"}

    if _ledger:
        result = await cas_command(
            _ledger, run_id, record_key=record_key, payload=payload, mutate=mutate,
        )
        run.previous_mode = run.mode
        run.mode = RunMode.MANUAL
        return result
    result = mutate(run)
    finish_command(run, record_key, payload, result)
    return result


@app.post("/api/runs/{run_id}/resume", tags=["Runs"])
async def resume_run(run_id: str, request: Request, body: dict | None = None) -> dict:
    """Flip a paused run back to its pre-pause mode (autopilot/hybrid).

    Body (optional): {"mode": "autopilot" | "hybrid" | "manual"} — explicit override.
    If omitted, restores `run.previous_mode` if set, else defaults to AUTOPILOT.
    """
    run = _runs.get(run_id)
    if run is None:
        raise HTTPException(404, "run not found")
    principal = _authorize_run(request, run)

    requested = (body or {}).get("mode")
    if requested:
        try:
            target_mode = RunMode(requested.lower())
        except ValueError:
            raise HTTPException(400, f"invalid mode: {requested!r}")
    else:
        target_mode = run.previous_mode or RunMode.AUTOPILOT

    payload = {"action": "resume", "mode": target_mode.value}
    record_key, replay = begin_command(
        run, request, principal, payload, expected_gate_version=None,
    )
    if replay is not None:
        return replay

    def mutate(authoritative: RunState) -> dict:
        previous = authoritative.mode
        authoritative.mode = target_mode
        authoritative.previous_mode = None
        return {"ok": True, "previous_mode": previous.value, "current_mode": target_mode.value}

    if _ledger:
        result = await cas_command(
            _ledger, run_id, record_key=record_key, payload=payload, mutate=mutate,
        )
        run.mode = target_mode
        run.previous_mode = None
        return result
    result = mutate(run)
    finish_command(run, record_key, payload, result)
    return result


@app.get("/api/runs/{run_id}/stream", tags=["Runs"])
async def stream_run(run_id: str, request: Request) -> EventSourceResponse:
    """SSE stream of StageEvents — UI listens here for live pipeline progress."""
    run = _runs.get(run_id)
    if run is None:
        raise HTTPException(404, "run not found")
    _authorize_run(request, run)
    if run_id not in _queues:
        raise HTTPException(404, "run not found")

    async def gen() -> AsyncIterator[dict]:
        q = _queues[run_id]
        while True:
            ev = await q.get()
            if ev is None:
                yield {"event": "done", "data": "[DONE]"}
                return
            yield {"event": ev.status, "data": ev.model_dump_json()}

    return EventSourceResponse(gen())


@app.post("/api/runs/{run_id}/approve", tags=["Gates & Decisions"])
async def approve(run_id: str, decision: GateDecision, request: Request) -> dict:
    """Record an Accept/Swap decision on the open gate (design.md §3).

    Resolution-text resolution rules:
    - If card_id present and option_index is given, use that option's resolution text
    - If card_id present and no option_index/text, use the card's recommended option
    - If resolution_text is explicitly passed, use that (swap / write-my-own)
    - For gate-level approvals (e.g. design_review), resolution_text just describes the gate
    """
    run = _runs.get(run_id)
    if run is None:
        raise HTTPException(404, "run not found")
    principal = _authorize_run(request, run)
    decision.actor = principal.subject
    command_payload = decision.model_dump(mode="json")
    record_key, replay = begin_command(
        run, request, principal, command_payload,
        expected_gate_version=decision.expected_gate_version,
    )
    if replay is not None:
        return replay

    # Guard: reject per-card decisions after the resolver gate has closed.
    # Without this, a card accepted seconds after /finalize lands in
    # run.decisions AFTER stage_architect has snapshotted run.decisions for
    # its LLM prompt — so the ledger says "decided" but the architecture text
    # was generated without it. Silent ledger/architecture drift (verified
    # 2026-05-25 in prod logs for run ff03847f: /approve 200 fired 5s after
    # /finalize, architect LLM returned 18s later from the older snapshot).
    # Gate-level approvals bypass this check — they release whatever gate
    # is currently open (e.g. design_review). Two ways a request can mark
    # itself as gate-level (so it skips the resolver-closed check):
    #
    #   1. card_id is None  — the canonical pattern (per-card decisions
    #      require a real card_id; design-review style approvals don't)
    #   2. decision.gate is set and != "resolver"  — operator-facing UIs
    #      may need to send a synthetic card_id to satisfy schema
    #      validation (Phase 4.1 DesignReviewGate did this initially) but
    #      explicitly tag the target gate. We accept that pattern too so
    #      the orchestrator and the UI converge on either contract.
    is_gate_level = (
        decision.card_id is None
        or (decision.gate and decision.gate != "resolver")
    )
    if not is_gate_level and (
        run.status != RunStatus.AWAITING_GATE
        or run.current_stage != Stage.RESOLVER
    ):
        raise HTTPException(
            409,
            "resolver gate is closed; cannot accept per-card decisions. "
            "Use /rerun to start a new run if the decision needs to take effect.",
        )

    # Tier-2 governance: hard-gated classes (PHI/auth by default) can NEVER be
    # bulk/soft-approved. The server enforces this independently of the UI —
    # a client cannot rubber-stamp a hard-gated card by sweeping it into an
    # "Approve all" batch. Only an explicit, individual decision is accepted.
    if decision.card_id:
        _card = next((c for c in run.cards if c.card_id == decision.card_id), None)
        if (
            _card is not None
            and _card.ambiguity_class in _config.HARD_GATE_CLASSES
            and decision.approval_path == "bulk"
        ):
            raise HTTPException(
                409,
                f"'{_card.ambiguity_class}' is hard-gated and cannot be bulk-approved; "
                f"this card must be decided individually with an explicit operator action.",
            )

    # Resolve the actual resolution_text from the chosen option
    final_text = decision.resolution_text
    if decision.card_id and not final_text:
        card = next((c for c in run.cards if c.card_id == decision.card_id), None)
        if card and card.options:
            if decision.option_index is not None and 0 <= decision.option_index < len(card.options):
                chosen = card.options[decision.option_index]
            else:
                chosen = next((o for o in card.options if o.recommended), card.options[0])
            final_text = chosen.resolution

    # Persist a fully-populated decision back to the run state
    persisted = GateDecision(
        card_id=decision.card_id,
        decision_kind=decision.decision_kind,
        resolution_text=final_text,
        option_index=decision.option_index,
        gate=decision.gate,
        actor=decision.actor,
    )
    run.decisions.append(persisted)
    if decision.card_id and _ledger:
        card = next((c for c in run.cards if c.card_id == decision.card_id), None)
        if card:
            from .autonomy import autonomy_ref as _autonomy_ref
            # Config-plane Phase 2: a human decided this card because its class
            # was gated (invariant hard-lock, matrix `gate`, or bootstrap default).
            # Record WHY it required a human — the same audit field the autopilot
            # path stamps, so every decision explains its gate/autopilot origin.
            gate_ref = _autonomy_ref(
                run.team_id, card.ambiguity_class, reason="human-gate",
            )
            entry = LedgerEntry(
                team_id=run.team_id, run_id=run.run_id, card_id=card.card_id,
                ambiguity_class=card.ambiguity_class, slot_value_hash=card.slot_value_hash,
                resolution_text=final_text,
                decision_kind=decision.decision_kind, created_by=decision.actor,
                # Wire (2026-06-21): same as the autopilot path — cards come from
                # the assessor, so stamp the assessor agent's bundle subscriptions
                # so a human decision is governed-attributed to the same bundles.
                bundle_refs=bundles_for_stage("assessor"),
                autonomy_ref=gate_ref,
                # Phase 2.6: same as the autopilot path — the assessor's
                # resolved prompt chain is the audit trail for which prompt
                # produced the ambiguity card the operator just decided on.
                prompt_resolution_path=run.prompt_chain_by_stage.get("assessor"),
            )
            enqueue_decision(run, entry)
            try:
                await flush_decision_outbox(run, _ledger)
            except InvariantWriteBlocked as exc:
                raise HTTPException(409, f"invariant write-block: {exc}")
            except Exception as exc:
                _logger.warning("Decision outbox remains pending for retry: %s", exc)
    # one approval call closes the gate for the demo (UIs can batch cards client-side)
    # NOTE: For Resolver (Gate 1), the UI MUST call /finalize after the last card
    # to release the gate. Non-Resolver gates (e.g. design_review) still auto-release
    # because they are whole-stage approvals with no per-card cycle.
    if decision.gate and decision.gate != "resolver" and decision.decision_kind != "reject":
        _release_gate(run_id)
    result = {
        "ok": True,
        "decisions_count": len(run.decisions),
        "resolution_text": final_text,
        "run_version": run.run_version + 1,
        "gate_version": int((run.pending_gate or {}).get("version", run.checkpoint_version)),
    }
    finish_command(run, record_key, command_payload, result)
    if _ledger:
        await _ledger.save_run_cas(run)
    return result


@app.post("/api/admin/runs/{run_id}/mark_failed", tags=["System"])
async def admin_mark_failed(run_id: str, request: Request, body: dict | None = None) -> dict:
    """Admin: force a run to status=failed durably in Cosmos.

    Phase 6.2 (2026-06-16): one-off cleanup for runs zombified by
    pod restarts before the per-event save_run fix landed. The /runs
    table showed 8 of these with "running · 0 dec · $0.0000" for hours.
    Marking them failed honestly clears the table.

    Body:
      { "reason": "..." }   optional cancellation reason recorded on the run

    Returns the updated run state.
    """
    body = body or {}
    reason = body.get("reason", "marked failed by admin cleanup")
    # Pull from Cosmos (may not be in-memory after restart)
    if _ledger is None:
        raise HTTPException(503, "ledger not configured")
    doc = await _ledger.get_run(run_id)
    if doc is None:
        raise HTTPException(404, "run not found in Cosmos")
    try:
        run = RunState.model_validate(doc)
    except Exception as exc:
        raise HTTPException(500, f"failed to re-hydrate run doc: {exc}") from exc
    run.status = RunStatus.FAILED
    # Bump updated_at so the /runs list re-sorts the cleaned run to reflect
    # the cleanup time, and so read-after-write verification can confirm the
    # write landed by comparing timestamps (not just trusting the 200).
    from datetime import datetime, timezone
    run.updated_at = datetime.now(timezone.utc).isoformat()
    # Append a synthetic event so the audit trail records the cleanup.
    run.events.append(StageEvent(
        run_id=run_id,
        stage=run.current_stage,
        status="failed",
        message=f"Admin cleanup: {reason}",
    ))
    await _ledger.save_run_cas(run)
    return {"ok": True, "run_id": run_id, "status": "failed", "reason": reason}


@app.post("/api/runs/{run_id}/finalize", tags=["Gates & Decisions"])
async def finalize_gate(run_id: str, request: Request, body: dict | None = None) -> dict:
    """Close the open Resolver gate explicitly after the human reviews all decisions.

    Validates that every gating card has a recorded decision before releasing.
    This is the 'final approval' step (UX: humans want a moment of confirmation
    before downstream stages auto-run).
    """
    run = _runs.get(run_id)
    if run is None:
        raise HTTPException(404, "run not found")
    _authorize_run(request, run)
    principal = _principal(request)
    body = body or {}
    expected_gate_version = body.get("expected_gate_version")
    command_payload = {"expected_gate_version": expected_gate_version}
    record_key, replay = begin_command(
        run, request, principal, command_payload,
        expected_gate_version=expected_gate_version,
    )
    if replay is not None:
        return replay

    def mutate(authoritative: RunState) -> dict:
        gating = {c.card_id for c in authoritative.cards if c.is_gating}
        resolved = {d.card_id for d in authoritative.decisions if d.card_id}
        remaining = gating - resolved
        if remaining:
            raise HTTPException(400, f"{len(remaining)} gating card(s) still unresolved; resolve all before finalize")
        if authoritative.pending_gate:
            authoritative.pending_gate["status"] = "resolved"
        return {
            "ok": True,
            "gate_closed": True,
            "decisions_count": len(authoritative.decisions),
            "next_stage": "architect",
            "run_version": authoritative.run_version + 1,
            "gate_version": int((authoritative.pending_gate or {}).get("version", authoritative.checkpoint_version)),
        }

    if _ledger:
        result = await cas_command(
            _ledger, run_id, record_key=record_key,
            payload=command_payload, mutate=mutate,
        )
        if run.pending_gate:
            run.pending_gate["status"] = "resolved"
        _release_gate(run_id)
        return result

    result = mutate(run)
    _release_gate(run_id)
    finish_command(run, record_key, command_payload, result)
    return result


# ========================================================================
# Self-heal cowork (add-self-heal-cowork) — gate/run-end triggered, both
# brain + executor are config-selected (azure | github | stub), no lock-in.
# ========================================================================
# In-memory heal-session store. heal_id -> {"proposal": HealProposal,
# "validation": HealValidationResult, "decision": HealDecision|None,
# "execution": HealExecution|None}. Mirrors the _runs dict pattern.
_heal_sessions: dict[str, dict] = {}


async def _write_heal_ledger(
    *, team_id: str, run_id: str, heal_id: str, runtime_kind: str,
    decision: str, rationale: str, actor_kind: str, actor_id: str,
    precedent_refs: list[str] | None = None, pr_url: str | None = None,
    stage: str | None = None,
) -> None:
    """Pin one link of the heal chain to the ledger. No-op if ledger absent.

    Uses the orchestrator's LedgerEntry with the heal fields (runtime_kind,
    heal_id, decision, rationale, actor_kind/id, pr_url, stage). card_id /
    ambiguity_class / decision_kind take benign defaults — heal entries are not
    card decisions.
    """
    if not _ledger:
        return
    try:
        await _ledger.write_decision(LedgerEntry(
            team_id=team_id, run_id=run_id, heal_id=heal_id,
            runtime_kind=runtime_kind,  # heal_proposed | heal_decided | heal_executed
            decision=decision, rationale=rationale,
            actor_kind=actor_kind, actor_id=actor_id,
            created_by=actor_id,
            precedent_refs=precedent_refs or [],
            pr_url=pr_url, stage=stage,
            resolution_text=decision,  # mirror into the legacy field for UI back-compat
        ))
    except Exception as exc:  # never crash the heal flow on a ledger blip
        _logger.warning("heal ledger write failed (heal_id=%s, kind=%s): %s",
                        heal_id, runtime_kind, exc)


@app.post("/api/runs/{run_id}/heal", tags=["Self-Heal"])
async def open_heal_session(run_id: str, request: Request, body: dict | None = None) -> dict:
    """Open a heal session for a run. HUMAN-INVOKED ONLY — at a gate
    (awaiting_gate) or at run end (completed/failed). Never a daemon.

    The brain diagnoses + proposes ONE action; the validator gates it; the
    proposal is returned for the human to approve. Nothing executes here.
    """
    if not _heal_rt.heal_settings.actions_enabled:
        raise HTTPException(403, "heal actions are disabled (HEAL_ACTIONS_ENABLED=false)")
    body = body or {}
    principal = _principal(request)
    run = _runs.get(run_id)
    # Allow healing Cosmos-resident terminal runs too (not just in-memory).
    run_summary: dict
    if run is not None:
        run_summary = {"status": run.status.value if hasattr(run.status, "value") else run.status,
                       "current_stage": getattr(run.current_stage, "value", run.current_stage),
                       "team_id": run.team_id}
        team_id = run.team_id
        require_team(principal, team_id)
    elif _ledger:
        doc = await _ledger.get_run(run_id)
        if not doc:
            raise HTTPException(404, "run not found")
        run_summary = {"status": doc.get("status"),
                       "current_stage": doc.get("current_stage"),
                       "team_id": doc.get("team_id")}
        team_id = doc.get("team_id", "unknown")
        require_team(principal, team_id)
    else:
        raise HTTPException(404, "run not found")

    # Determine the trigger from run status + enforce human-invoked-only.
    status = run_summary.get("status")
    trigger = HealTrigger.AT_GATE if status == "awaiting_gate" else HealTrigger.AT_RUN_END
    try:
        assert_human_invoked(trigger, status)
    except ValueError as exc:
        raise HTTPException(409, str(exc))

    # Brain diagnoses + proposes (config-selected: azure | github | stub).
    brain = get_brain()
    precedent: list[dict] = []  # TODO(slice-2): query prior heal_executed entries
    proposal = await brain.diagnose(
        run_id=run_id, team_id=team_id, trigger=trigger,
        run_summary=run_summary, precedent=precedent,
    )

    # Validate the proposed action through the safety kernel.
    validation = validate_heal_action(proposal.action)

    _heal_sessions[proposal.heal_id] = {
        "proposal": proposal, "validation": validation,
        "decision": None, "execution": None,
        "brain": brain.name,
    }

    # Pin heal_proposed to the ledger (agent actor).
    await _write_heal_ledger(
        team_id=team_id, run_id=run_id, heal_id=proposal.heal_id,
        runtime_kind="heal_proposed",
        decision=proposal.action.summary, rationale=proposal.diagnosis,
        actor_kind="agent", actor_id=f"heal-brain:{brain.name}",
        precedent_refs=proposal.precedent_refs, stage=proposal.action.stage,
    )

    return {
        "heal_id": proposal.heal_id,
        "trigger": trigger.value,
        "brain": brain.name,
        "diagnosis": proposal.diagnosis,
        "action": proposal.action.model_dump(),
        "validation": validation.model_dump(),
        "requires_human_approval": True,
        "can_execute": validation.outcome == HealValidationOutcome.ALLOW_WITH_APPROVAL,
    }


@app.get("/api/heal/{heal_id}", tags=["Self-Heal"])
async def get_heal_session(heal_id: str, request: Request) -> dict:
    """Fetch the current state of a heal session."""
    sess = _heal_sessions.get(heal_id)
    if not sess:
        raise HTTPException(404, "heal session not found")
    proposal: HealProposal = sess["proposal"]
    require_team(_principal(request), proposal.team_id)
    return {
        "heal_id": heal_id,
        "brain": sess.get("brain"),
        "diagnosis": proposal.diagnosis,
        "action": proposal.action.model_dump(),
        "validation": sess["validation"].model_dump(),
        "decision": sess["decision"].model_dump() if sess["decision"] else None,
        "execution": sess["execution"].model_dump() if sess["execution"] else None,
    }


@app.post("/api/heal/{heal_id}/approve", tags=["Self-Heal"])
async def approve_heal(heal_id: str, request: Request, body: dict | None = None) -> dict:
    """Human approves (or declines) the proposed heal. On approval, the
    config-selected executor lands the heal and the chain is pinned.

    Body: { "approver_id": "<m365 upn>", "approved": true, "note": "..." }
    """
    sess = _heal_sessions.get(heal_id)
    if not sess:
        raise HTTPException(404, "heal session not found")
    body = body or {}
    principal = _principal(request)
    approver_id = principal.subject
    approved = bool(body.get("approved", True))
    note = body.get("note", "")

    proposal: HealProposal = sess["proposal"]
    require_team(principal, proposal.team_id)
    validation = sess["validation"]

    # Hard safety: a BLOCK/ESCALATE outcome can never be executed, even if the
    # human clicks approve. This is the kernel boundary the spec mandates.
    if validation.outcome != HealValidationOutcome.ALLOW_WITH_APPROVAL and approved:
        raise HTTPException(
            403,
            f"heal cannot be executed: {validation.outcome.value} — {validation.reason}"
            + (f" (escalate via: {validation.escalation_path})" if validation.escalation_path else ""),
        )

    decision = HealDecision(heal_id=heal_id, approver_id=approver_id,
                            approved=approved, note=note)
    sess["decision"] = decision

    # Pin heal_decided (human actor).
    await _write_heal_ledger(
        team_id=proposal.team_id, run_id=proposal.run_id, heal_id=heal_id,
        runtime_kind="heal_decided",
        decision=f"{'approved' if approved else 'declined'} heal: {proposal.action.summary}",
        rationale=note or ("approved by operator" if approved else "declined by operator"),
        actor_kind="human", actor_id=approver_id,
        stage=proposal.action.stage,
    )

    if not approved:
        return {"heal_id": heal_id, "approved": False, "executed": False}

    # Execute via the config-selected executor (github | azure | stub).
    executor = get_executor()
    execution = await executor.execute(proposal)
    sess["execution"] = execution

    # Pin heal_executed (executor as agent actor) with the PR/re-run ref.
    await _write_heal_ledger(
        team_id=proposal.team_id, run_id=proposal.run_id, heal_id=heal_id,
        runtime_kind="heal_executed",
        decision=f"executed {proposal.action.action_type.value}: {execution.detail}",
        rationale=execution.detail,
        actor_kind="agent", actor_id=f"heal-executor:{executor.name}",
        pr_url=execution.result_ref or None, stage=proposal.action.stage,
    )

    return {
        "heal_id": heal_id,
        "approved": True,
        "executed": execution.success,
        "executor": executor.name,
        "result_ref": execution.result_ref,
        "detail": execution.detail,
    }


@app.post("/api/runs/{run_id}/undo", tags=["Runs"])
async def undo_decision(run_id: str, body: dict, request: Request) -> dict:
    """Undo a resolved decision on a Resolver card, re-opening it for re-decision.

    Only allowed while the run is paused on the Resolver gate — undoing after
    the architect (or any downstream stage) has already consumed the decision
    would corrupt subsequent stages. Returns 409 in that case.

    Behavior:
      * Remove ALL run.decisions entries matching card_id (both autopilot and
        any human override could coexist; cleanest is to nuke and let the
        human re-pick).
      * Untrack the card from autopilot_decisions / autopilot_overrides so
        the next pass treats it as a fresh open card.
      * Best-effort delete the ledger row.
      * Emit a Stage.RESOLVER progress event so the SSE-subscribed UI
        re-renders with the card back in the open state.
      * Do NOT release the gate.
    """
    run = _runs.get(run_id)
    if run is None:
        raise HTTPException(404, "run not found")
    _authorize_run(request, run)

    card_id = (body or {}).get("card_id")
    if not card_id:
        raise HTTPException(400, "card_id required")

    if not any(c.card_id == card_id for c in run.cards):
        raise HTTPException(404, f"card_id {card_id!r} not found on run")

    # Guard: undo only valid while paused on the Resolver gate. Once the gate
    # has released and downstream stages have consumed the decision, undo would
    # leave the run in an inconsistent state.
    if run.status != RunStatus.AWAITING_GATE or run.current_stage != Stage.RESOLVER:
        raise HTTPException(
            409,
            "undo only allowed while Resolver gate is open; "
            "current stage has already consumed the decision",
        )

    before = len(run.decisions)
    run.decisions = [d for d in run.decisions if d.card_id != card_id]
    removed = before - len(run.decisions)

    if card_id in run.autopilot_decisions:
        run.autopilot_decisions.remove(card_id)
    if card_id in run.autopilot_overrides:
        run.autopilot_overrides.remove(card_id)

    if _ledger:
        try:
            await _ledger.delete_decision(run.run_id, card_id)
        except Exception as exc:
            _logger.warning("Ledger delete_decision failed (continuing): %s", exc)

    await _push(run_id, StageEvent(
        run_id=run_id, stage=Stage.RESOLVER, status="progress",
        message=f"Undo on card {card_id}",
        payload={"undo_card_id": card_id, "removed_decisions": removed},
    ))

    return {"ok": True, "card_id": card_id, "decisions_count": len(run.decisions)}


@app.post("/api/runs/{run_id}/reject", tags=["Gates & Decisions"])
async def reject(run_id: str, decision: GateDecision, request: Request) -> dict:
    """Reject-with-note — one-keystroke default per design.md §3."""
    run = _runs.get(run_id)
    if run is None:
        raise HTTPException(404, "run not found")
    principal = _authorize_run(request, run)
    decision.actor = principal.subject
    decision.decision_kind = "reject"
    run.decisions.append(decision)
    if decision.card_id and _ledger:
        card = next((c for c in run.cards if c.card_id == decision.card_id), None)
        if card:
            from .autonomy import autonomy_ref as _autonomy_ref
            await _ledger.write_decision(LedgerEntry(
                team_id=run.team_id, run_id=run.run_id, card_id=card.card_id,
                ambiguity_class=card.ambiguity_class, slot_value_hash=card.slot_value_hash,
                resolution_text=decision.resolution_text or "(reject)",
                decision_kind="reject", created_by=decision.actor,
                # Config-plane Phase 2: a reject is still a human gate decision —
                # record WHY the card required a human (same audit field).
                autonomy_ref=_autonomy_ref(
                    run.team_id, card.ambiguity_class, reason="human-gate-reject",
                ),
            ))
    _release_gate(run_id)
    return {"ok": True}


@app.post("/api/runs/{run_id}/demote", tags=["Gates & Decisions"])
async def demote(run_id: str, precedent_id: str, request: Request) -> dict:
    """Synchronous demote — invalidates caches; back-trace report is async (§4).

    Read-modify-write (preserves ambiguity_class / slot_value_hash / resolution_text)
    against the run's actual team partition.
    """
    if _ledger is None:
        raise HTTPException(503, "ledger unavailable")
    run = _runs.get(run_id)
    if run is None:
        raise HTTPException(404, "unknown run")
    principal = _authorize_run(request, run)
    actor = principal.subject
    team_id = run.team_id  # use run's actual team, not a hardcoded literal
    try:
        # Read the existing item from the correct partition
        existing = await _ledger._ledger.read_item(  # noqa: SLF001
            item=precedent_id, partition_key=team_id,
        )
        existing["status"] = "demoted"
        existing["demoted_by"] = actor
        existing["demoted_at_run"] = run_id
        await _ledger._ledger.upsert_item(existing)  # noqa: SLF001
    except Exception as exc:
        _logger.warning("demote failed: %s", exc)
        return {"ok": False, "error": str(exc)}
    return {
        "ok": True,
        "team_id": team_id,
        "note": "back-trace report queued (async, 24h SLA per design.md §4)",
    }


# ---------- telemetry dashboard endpoints -------------------------------------
# Power the /telemetry page in resolver-ui. All three are read-only aggregations
# against Cosmos (decision-ledger + pipeline-runs). If the ledger client is
# unavailable (e.g. local dev with LEDGER_DISABLED=1), they return empty payloads
# rather than 503 — the UI shows "no data yet" instead of an error toast.
@app.get("/api/telemetry/decisions", tags=["Telemetry"])
async def telemetry_decisions(
    request: Request,
    team_id: str | None = None,
    kind: str | None = None,
    since: str | None = None,
    limit: int = 50,
) -> dict:
    """Recent Decision Ledger entries, newest-first. See models.LedgerEntry."""
    principal = _principal(request)
    scoped_team = team_id or (next(iter(principal.teams)) if len(principal.teams) == 1 else None)
    if scoped_team:
        require_team(principal, scoped_team)
    elif not principal.has_any_role("admin"):
        raise HTTPException(400, "team_id is required for multi-team telemetry")
    team_id = scoped_team
    if _ledger is None:
        return {"items": [], "count": 0}
    items = await query_decisions(
        _ledger, team_id=team_id, kind=kind, since_iso=since, limit=limit,
    )
    return {"items": items, "count": len(items)}


@app.get("/api/telemetry/cost", tags=["Telemetry"])
async def telemetry_cost(request: Request, window: str = "24h", team_id: str | None = None) -> dict:
    """Cost + latency rollup across pipeline-runs in the window."""
    principal = _principal(request)
    team_id = team_id or (next(iter(principal.teams)) if len(principal.teams) == 1 else None)
    if team_id: require_team(principal, team_id)
    elif not principal.has_any_role("admin"): raise HTTPException(400, "team_id is required")
    if _ledger is None:
        return {
            "window": window, "total_runs": 0, "total_decisions": 0,
            "human_decisions": 0, "autopilot_decisions": 0, "total_cost_usd": 0.0,
            "cost_per_decision_usd": 0.0, "mean_gate_wall_clock_seconds": 0.0,
            "mean_tokens_per_run": 0.0, "cost_by_stage": {}, "cost_per_run_timeseries": [],
        }
    return await query_cost(_ledger, window=window, team_id=team_id)


@app.get("/api/telemetry/classes", tags=["Telemetry"])
async def telemetry_classes(request: Request, window: str = "7d", team_id: str | None = None) -> dict:
    """Ambiguity-class drift signal: counts, acceptance, blast, trend arrows."""
    principal = _principal(request)
    team_id = team_id or (next(iter(principal.teams)) if len(principal.teams) == 1 else None)
    if team_id: require_team(principal, team_id)
    elif not principal.has_any_role("admin"): raise HTTPException(400, "team_id is required")
    if _ledger is None:
        return {"window": window, "total_decisions": 0, "classes": []}
    return await query_classes(_ledger, window=window, team_id=team_id)


# ---------- compliance query (THE acceptance query, config-plane Phase 5) ------
@app.get("/api/compliance/decisions")
async def compliance_decisions(
    request: Request,
    phi_class: str | None = None,
    actor_kind: str | None = None,
    team_id: str | None = None,
    window: str | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = 500,
) -> dict:
    """Unified compliance query (add-configuration-plane Phase 5 — the hero).

    Returns, per AI decision: WHAT was decided, WHY (governing autonomy rule +
    bundle rule VERSION), WHO (human UPN or agent principal), which MODEL, and
    the COST — filterable by phi_class, date range, actor kind, and team, across
    every decision-producing surface (one ledger container, no surface-specific
    branch). This is the capability's acceptance test:

        phi_class=high&window=30d  ->  complete, non-null rows.

    `window` (24h|7d|30d) is a shortcut that resolves to `since`; an explicit
    `since`/`until` (ISO) overrides it. Best-effort: empty payload on Cosmos
    error, never a 500.
    """
    from .compliance_query import completeness_summary, query_compliance
    from .telemetry_queries import parse_window
    principal = _principal(request)
    team_id = team_id or (next(iter(principal.teams)) if len(principal.teams) == 1 else None)
    if team_id: require_team(principal, team_id)
    elif not principal.has_any_role("admin"): raise HTTPException(400, "team_id is required")

    since_iso = since
    if since_iso is None and window:
        from datetime import datetime, timezone
        since_iso = (datetime.now(timezone.utc) - parse_window(window)).isoformat()

    if _ledger is None:
        return {
            "rows": [],
            "summary": completeness_summary([]),
            "filters": {
                "phi_class": phi_class, "since": since_iso, "until": until,
                "actor_kind": actor_kind, "team_id": team_id,
            },
        }
    return await query_compliance(
        _ledger, phi_class=phi_class, since_iso=since_iso, until_iso=until,
        actor_kind=actor_kind, team_id=team_id, limit=limit,
    )


# ---------- runs index endpoint ----------------------------------------------
@app.get("/api/runs", tags=["Runs"])
async def list_runs(
    request: Request,
    team_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> dict:
    """Recent pipeline-runs summaries, newest-first by updated_at.

    Powers the /runs index page. Best-effort: returns empty list on Cosmos error
    rather than 500'ing the dashboard. Supports team_id and status filters
    (status accepts comma-separated values, e.g. status=running,awaiting_gate).
    """
    principal = _principal(request)
    team_id = team_id or (next(iter(principal.teams)) if len(principal.teams) == 1 else None)
    if team_id: require_team(principal, team_id)
    elif not principal.has_any_role("admin"): raise HTTPException(400, "team_id is required")
    if _ledger is None:
        return {"items": [], "count": 0}
    items = await query_recent_runs(
        _ledger, team_id=team_id, status=status, limit=limit,
    )
    return {"items": items, "count": len(items)}


# ---------- prompt-library endpoints -----------------------------------------
@app.get("/api/prompt-library", tags=["Prompt Library"])
async def prompt_library_catalog() -> dict:
    """Per-stage prompt variants by model — the registry the APIM circuit
    breaker consults to pick a compat prompt after a provider failover.

    Phase 1 answer to Kapil's workshop ask (2026-05-27): surface what the
    orchestrator already knows (stages.py system prompts) as a first-class
    catalog. UI at /prompt-library renders this table.
    """
    return build_catalog_view()


@app.get("/api/prompt-library/{stage}", tags=["Prompt Library"])
async def prompt_library_lookup(
    stage: str,
    model: str | None = None,
    strict: bool = False,
) -> dict:
    """Look up the prompt variant for (stage, model). 404 on unknown stage.

    Returns the FULL template (not a preview). When ``strict=true`` the
    endpoint also 404s on an unknown model rather than falling back — used
    by the prompt-library viewer modal so the user never sees a substituted
    variant without realising it.
    """
    try:
        result = get_prompt(stage, model)
    except UnknownStageError:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown stage '{stage}'. Valid stages: ingest, assessor, "
                   f"architect, test_plan, codegen, review_scan.",
        )
    if strict and result.get("fallback"):
        raise HTTPException(
            status_code=404,
            detail=f"Unknown model '{model}' for stage '{stage}'.",
        )
    return result
