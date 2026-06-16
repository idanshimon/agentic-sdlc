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
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from .decisions_md import write_decisions_md
from .ledger import InvariantWriteBlocked, Ledger
from .models import (
    GateDecision, INVARIANT_CLASSES, LedgerEntry, RunMode, RunState, RunStatus,
    Stage, StageEvent,
)
from .stages import (
    stage_architect, stage_assessor, stage_codegen, stage_deliver,
    stage_ingest, stage_review_scan, stage_test_plan,
)
from .prompt_library import build_catalog_view, get_prompt, UnknownStageError
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _ledger
    init_telemetry()
    _ledger = Ledger()
    yield
    if _ledger:
        await _ledger.close()


app = FastAPI(title="Agentic SDLC Orchestrator", version="0.1.0", lifespan=lifespan)

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


# ---------- helpers -----------------------------------------------------------
async def _push(run_id: str, ev: StageEvent | None) -> None:
    q = _queues.get(run_id)
    if q is not None:
        await q.put(ev)


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
    for card in run.cards:
        if not card.is_gating:
            continue
        if card.card_id in run.autopilot_decisions or card.card_id in run.autopilot_overrides:
            continue
        # Invariant override — always gates.
        if card.ambiguity_class in INVARIANT_CLASSES:
            run.autopilot_overrides.append(card.card_id)
            continue
        # HYBRID: gate when no precedent exists.
        if run.mode == RunMode.HYBRID:
            if _ledger is None:
                continue  # no ledger → can't verify precedent → gate
            precedent = await _ledger.find_precedent(
                run.team_id, card.ambiguity_class, card.slot_value_hash,
            )
            if not precedent:
                continue
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
        _logger.exception("Pipeline crashed: %s", exc)
        run.status = RunStatus.FAILED
        await _push(run_id, StageEvent(
            run_id=run_id, stage=run.current_stage, status="failed", message=str(exc),
        ))
    finally:
        if _ledger:
            await _ledger.save_run(run)
        await _push(run_id, None)  # sentinel: stream complete


async def _open_gate(run: RunState, stage: Stage) -> None:
    """Block until a gate decision arrives, recording human-attention wall-clock."""
    run.status = RunStatus.AWAITING_GATE
    ev = asyncio.Event()
    _gate_events[run.run_id] = ev
    _gate_started[run.run_id] = time.monotonic()
    with span(f"gate.{stage}"):
        await ev.wait()
    elapsed = time.monotonic() - _gate_started.pop(run.run_id, time.monotonic())
    run.gate_wall_clock_seconds += elapsed
    record_gate_wall_clock(stage.value, elapsed)
    run.status = RunStatus.RUNNING


def _release_gate(run_id: str) -> None:
    ev = _gate_events.pop(run_id, None)
    if ev:
        ev.set()


# ---------- routes ------------------------------------------------------------
@app.get("/healthz")
async def healthz() -> dict:
    """Liveness probe (no external deps touched)."""
    return {"status": "ok", "runs_in_memory": len(_runs)}


@app.post("/api/run")
async def create_run(
    prd: UploadFile = File(...),
    team_id: str = Form("cardiology"),
    mode: str = Form("manual"),
    stage_providers: str = Form(""),
) -> dict:
    """Accept a PRD upload and kick off the 9-stage pipeline (design.md §2).

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

    run = RunState(
        team_id=team_id, prd_blob_url=f"inline://{prd.filename}", mode=run_mode,
        stage_provider_overrides=overrides,
    )
    _runs[run.run_id] = run
    _queues[run.run_id] = asyncio.Queue()
    _prd_cache[run.run_id] = raw  # cache so /rerun can reuse without re-upload
    if _ledger:
        await _ledger.save_run(run)
    asyncio.create_task(_drive(run.run_id, raw))
    return {"run_id": run.run_id, "stream_url": f"/api/runs/{run.run_id}/stream"}


@app.post("/api/runs/{run_id}/rerun")
async def rerun(run_id: str, body: dict | None = None) -> dict:
    """Start a fresh run with the same PRD + team_id as `run_id`, optionally
    in a different mode. The original run is left untouched for A/B comparison.

    Body (optional JSON): {"mode": "manual" | "autopilot" | "hybrid"}
    If mode is omitted, INVERTS the original: manual -> autopilot, otherwise -> manual.

    Returns the new run_id. The old run remains in _runs (audit chain preserved).
    """
    src = _runs.get(run_id)
    if src is None:
        raise HTTPException(404, "source run not found")
    raw = _prd_cache.get(run_id)
    if raw is None:
        raise HTTPException(409, "source PRD not in cache (server restarted); please resubmit")

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
    )
    _runs[new_run.run_id] = new_run
    _queues[new_run.run_id] = asyncio.Queue()
    _prd_cache[new_run.run_id] = raw
    if _ledger:
        await _ledger.save_run(new_run)
    asyncio.create_task(_drive(new_run.run_id, raw))
    return {
        "run_id": new_run.run_id,
        "source_run_id": run_id,
        "mode": target_mode.value,
        "team_id": src.team_id,
        "stream_url": f"/api/runs/{new_run.run_id}/stream",
    }


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str) -> RunState:
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
                # The persisted doc is a RunState.model_dump() shape — re-hydrate.
                return RunState.model_validate(doc)
            except Exception as exc:
                _logger.warning("Failed to re-hydrate Cosmos run doc %s: %s", run_id, exc)
                # Last-resort: return the raw dict so the UI doesn't crash with 500.
                # FastAPI will serialize this; consumers using RunState fields will
                # still see the right keys because Cosmos stores model_dump output.
                return doc  # type: ignore[return-value]
    raise HTTPException(404, "run not found")


@app.get("/api/runs/{run_id}/ledger")
async def get_run_ledger(run_id: str) -> dict:
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


@app.post("/api/runs/{run_id}/pause")
async def pause_run(run_id: str) -> dict:
    """Flip run to MANUAL mode mid-flight. Pipeline does not interrupt the
    currently-executing stage, but the NEXT gate boundary respects the new
    mode (i.e. opens a human gate instead of auto-advancing).

    Pair with /resume to flip back to autopilot/hybrid.
    """
    run = _runs.get(run_id)
    if run is None:
        raise HTTPException(404, "run not found")
    previous_mode = run.mode
    run.previous_mode = previous_mode  # remember for /resume
    run.mode = RunMode.MANUAL
    return {"ok": True, "previous_mode": previous_mode.value, "current_mode": "manual"}


@app.post("/api/runs/{run_id}/resume")
async def resume_run(run_id: str, body: dict | None = None) -> dict:
    """Flip a paused run back to its pre-pause mode (autopilot/hybrid).

    Body (optional): {"mode": "autopilot" | "hybrid" | "manual"} — explicit override.
    If omitted, restores `run.previous_mode` if set, else defaults to AUTOPILOT.
    """
    run = _runs.get(run_id)
    if run is None:
        raise HTTPException(404, "run not found")

    requested = (body or {}).get("mode")
    if requested:
        try:
            target_mode = RunMode(requested.lower())
        except ValueError:
            raise HTTPException(400, f"invalid mode: {requested!r}")
    else:
        target_mode = run.previous_mode or RunMode.AUTOPILOT

    previous_mode = run.mode
    run.mode = target_mode
    run.previous_mode = None  # consumed
    return {"ok": True, "previous_mode": previous_mode.value, "current_mode": target_mode.value}


@app.get("/api/runs/{run_id}/stream")
async def stream_run(run_id: str) -> EventSourceResponse:
    """SSE stream of StageEvents — UI listens here for live pipeline progress."""
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


@app.post("/api/runs/{run_id}/approve")
async def approve(run_id: str, decision: GateDecision) -> dict:
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

    # Guard: reject per-card decisions after the resolver gate has closed.
    # Without this, a card accepted seconds after /finalize lands in
    # run.decisions AFTER stage_architect has snapshotted run.decisions for
    # its LLM prompt — so the ledger says "decided" but the architecture text
    # was generated without it. Silent ledger/architecture drift (verified
    # 2026-05-25 in prod logs for run ff03847f: /approve 200 fired 5s after
    # /finalize, architect LLM returned 18s later from the older snapshot).
    # Gate-level approvals (decision.card_id is None) bypass this check —
    # they release whatever gate is currently open (e.g. design_review).
    if decision.card_id and (
        run.status != RunStatus.AWAITING_GATE
        or run.current_stage != Stage.RESOLVER
    ):
        raise HTTPException(
            409,
            "resolver gate is closed; cannot accept per-card decisions. "
            "Use /rerun to start a new run if the decision needs to take effect.",
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
            entry = LedgerEntry(
                team_id=run.team_id, run_id=run.run_id, card_id=card.card_id,
                ambiguity_class=card.ambiguity_class, slot_value_hash=card.slot_value_hash,
                resolution_text=final_text,
                decision_kind=decision.decision_kind, created_by=decision.actor,
                # Phase 2.6: same as the autopilot path — the assessor's
                # resolved prompt chain is the audit trail for which prompt
                # produced the ambiguity card the operator just decided on.
                prompt_resolution_path=run.prompt_chain_by_stage.get("assessor"),
            )
            try:
                await _ledger.write_decision(entry)
            except InvariantWriteBlocked as exc:
                raise HTTPException(409, f"invariant write-block: {exc}")
    # one approval call closes the gate for the demo (UIs can batch cards client-side)
    # NOTE: For Resolver (Gate 1), the UI MUST call /finalize after the last card
    # to release the gate. Non-Resolver gates (e.g. design_review) still auto-release
    # because they are whole-stage approvals with no per-card cycle.
    if decision.gate and decision.gate != "resolver":
        _release_gate(run_id)
    return {"ok": True, "decisions_count": len(run.decisions), "resolution_text": final_text}


@app.post("/api/runs/{run_id}/finalize")
async def finalize_gate(run_id: str, body: dict | None = None) -> dict:
    """Close the open Resolver gate explicitly after the human reviews all decisions.

    Validates that every gating card has a recorded decision before releasing.
    This is the 'final approval' step (UX: humans want a moment of confirmation
    before downstream stages auto-run).
    """
    run = _runs.get(run_id)
    if run is None:
        raise HTTPException(404, "run not found")

    gating_card_ids = {c.card_id for c in run.cards if c.is_gating}
    resolved_card_ids = {d.card_id for d in run.decisions if d.card_id}
    unresolved = gating_card_ids - resolved_card_ids
    if unresolved:
        raise HTTPException(
            400,
            f"{len(unresolved)} gating card(s) still unresolved; "
            f"resolve all before finalize",
        )
    _release_gate(run_id)
    return {
        "ok": True,
        "gate_closed": True,
        "decisions_count": len(run.decisions),
        "next_stage": "architect",
    }


@app.post("/api/runs/{run_id}/undo")
async def undo_decision(run_id: str, body: dict) -> dict:
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


@app.post("/api/runs/{run_id}/reject")
async def reject(run_id: str, decision: GateDecision) -> dict:
    """Reject-with-note — one-keystroke default per design.md §3."""
    run = _runs.get(run_id)
    if run is None:
        raise HTTPException(404, "run not found")
    decision.decision_kind = "reject"
    run.decisions.append(decision)
    if decision.card_id and _ledger:
        card = next((c for c in run.cards if c.card_id == decision.card_id), None)
        if card:
            await _ledger.write_decision(LedgerEntry(
                team_id=run.team_id, run_id=run.run_id, card_id=card.card_id,
                ambiguity_class=card.ambiguity_class, slot_value_hash=card.slot_value_hash,
                resolution_text=decision.resolution_text or "(reject)",
                decision_kind="reject", created_by=decision.actor,
            ))
    _release_gate(run_id)
    return {"ok": True}


@app.post("/api/runs/{run_id}/demote")
async def demote(run_id: str, precedent_id: str, actor: str = "demo-user@hca") -> dict:
    """Synchronous demote — invalidates caches; back-trace report is async (§4).

    Read-modify-write (preserves ambiguity_class / slot_value_hash / resolution_text)
    against the run's actual team partition.
    """
    if _ledger is None:
        raise HTTPException(503, "ledger unavailable")
    run = _runs.get(run_id)
    if run is None:
        raise HTTPException(404, "unknown run")
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
@app.get("/api/telemetry/decisions")
async def telemetry_decisions(
    team_id: str | None = None,
    kind: str | None = None,
    since: str | None = None,
    limit: int = 50,
) -> dict:
    """Recent Decision Ledger entries, newest-first. See models.LedgerEntry."""
    if _ledger is None:
        return {"items": [], "count": 0}
    items = await query_decisions(
        _ledger, team_id=team_id, kind=kind, since_iso=since, limit=limit,
    )
    return {"items": items, "count": len(items)}


@app.get("/api/telemetry/cost")
async def telemetry_cost(window: str = "24h", team_id: str | None = None) -> dict:
    """Cost + latency rollup across pipeline-runs in the window."""
    if _ledger is None:
        return {
            "window": window, "total_runs": 0, "total_decisions": 0,
            "human_decisions": 0, "autopilot_decisions": 0, "total_cost_usd": 0.0,
            "cost_per_decision_usd": 0.0, "mean_gate_wall_clock_seconds": 0.0,
            "mean_tokens_per_run": 0.0, "cost_by_stage": {}, "cost_per_run_timeseries": [],
        }
    return await query_cost(_ledger, window=window, team_id=team_id)


@app.get("/api/telemetry/classes")
async def telemetry_classes(window: str = "7d", team_id: str | None = None) -> dict:
    """Ambiguity-class drift signal: counts, acceptance, blast, trend arrows."""
    if _ledger is None:
        return {"window": window, "total_decisions": 0, "classes": []}
    return await query_classes(_ledger, window=window, team_id=team_id)


# ---------- runs index endpoint ----------------------------------------------
@app.get("/api/runs")
async def list_runs(
    team_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> dict:
    """Recent pipeline-runs summaries, newest-first by updated_at.

    Powers the /runs index page. Best-effort: returns empty list on Cosmos error
    rather than 500'ing the dashboard. Supports team_id and status filters
    (status accepts comma-separated values, e.g. status=running,awaiting_gate).
    """
    if _ledger is None:
        return {"items": [], "count": 0}
    items = await query_recent_runs(
        _ledger, team_id=team_id, status=status, limit=limit,
    )
    return {"items": items, "count": len(items)}


# ---------- prompt-library endpoints -----------------------------------------
@app.get("/api/prompt-library")
async def prompt_library_catalog() -> dict:
    """Per-stage prompt variants by model — the registry the APIM circuit
    breaker consults to pick a compat prompt after a provider failover.

    Phase 1 answer to Kapil's workshop ask (2026-05-27): surface what the
    orchestrator already knows (stages.py system prompts) as a first-class
    catalog. UI at /prompt-library renders this table.
    """
    return build_catalog_view()


@app.get("/api/prompt-library/{stage}")
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
