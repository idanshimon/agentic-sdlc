"""Telemetry aggregation queries against Cosmos.

Powers the /api/telemetry/* endpoints (Decision Ledger feed, cost+latency dashboard,
ambiguity class drift). All reads are best-effort: a Cosmos hiccup returns an empty
payload rather than 500'ing the dashboard.

Data sources:
  * `decision-ledger` container — every Resolver decision (human + autopilot), partitioned
    by team_id. Schema: apps/orchestrator/models.py::LedgerEntry.
  * `pipeline-runs` container — RunState snapshots, partitioned by run_id. Carries
    cards (with blast_radius_cost_usd, ambiguity_class), decisions, total_cost_usd,
    total_tokens, gate_wall_clock_seconds, autopilot_decisions, created_at.

FALLBACK NOTE (documented per design): the original spec called for App Insights /
Log Analytics queries to break cost down by stage with per-call USD granularity
(emitted via telemetry.record_tokens). We instead aggregate from `pipeline-runs`
because (a) azure-monitor-query SDK is not in the orchestrator image, (b) the cost
column is only persisted in OTel custom metrics, not retrievable per-stage via the
metrics API without re-emitting as customEvents. Trade-off: per-stage cost is a
proportional split of run.total_cost_usd across stages observed in run.events,
not a true per-call sum. Totals + per-run timeseries are exact.
"""
from __future__ import annotations
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from .ledger import Ledger
from .models import INVARIANT_CLASSES

_logger = logging.getLogger("orchestrator.telemetry_queries")

# Relative cost weights per stage — used to apportion run.total_cost_usd across
# the stages that fired during a run. Derived from observed token usage profiles
# in stages.py (codegen + architect are the heavy LLM calls; review_scan/deliver
# barely touch the LLM). Sums to 1.0.
_STAGE_WEIGHTS: dict[str, float] = {
    "ingest": 0.03,
    "assessor": 0.18,
    "architect": 0.30,
    "test_plan": 0.12,
    "codegen": 0.32,
    "review_scan": 0.05,
}
_KNOWN_STAGES = list(_STAGE_WEIGHTS.keys())


def parse_window(window: str) -> timedelta:
    """24h / 7d / 30d → timedelta. Defaults to 24h on garbage input."""
    w = (window or "24h").lower().strip()
    if w == "24h":
        return timedelta(hours=24)
    if w == "7d":
        return timedelta(days=7)
    if w == "30d":
        return timedelta(days=30)
    return timedelta(hours=24)


# ────────────────────────────────────────────────────────────────────────────
# Decision Ledger feed
# ────────────────────────────────────────────────────────────────────────────
async def query_decisions(
    ledger: Ledger,
    *,
    team_id: Optional[str] = None,
    kind: Optional[str] = None,
    since_iso: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """Recent ledger entries, newest-first, filtered server-side.

    Empty list on any Cosmos error — the UI shows an empty-state, not a broken page.
    """
    limit = max(1, min(int(limit or 50), 500))
    clauses = ["1=1"]
    params: list[dict[str, Any]] = []
    if team_id:
        clauses.append("c.team_id=@t")
        params.append({"name": "@t", "value": team_id})
    if kind:
        kinds = [k.strip() for k in kind.split(",") if k.strip()]
        if len(kinds) == 1:
            clauses.append("c.decision_kind=@k")
            params.append({"name": "@k", "value": kinds[0]})
        elif kinds:
            placeholders = ",".join(f"@k{i}" for i in range(len(kinds)))
            clauses.append(f"c.decision_kind IN ({placeholders})")
            for i, k in enumerate(kinds):
                params.append({"name": f"@k{i}", "value": k})
    if since_iso:
        clauses.append("c.created_at>=@s")
        params.append({"name": "@s", "value": since_iso})
    # Cosmos cross-partition ORDER BY needs composite index — sort client-side.
    query = (
        f"SELECT TOP {limit} * FROM c WHERE {' AND '.join(clauses)}"
    )
    out: list[dict] = []
    try:
        kwargs: dict[str, Any] = {"query": query, "parameters": params}
        if team_id:
            kwargs["partition_key"] = team_id
        async for item in ledger._ledger.query_items(**kwargs):  # noqa: SLF001
            # Strip Cosmos internals to keep the payload UI-clean.
            clean = {k: v for k, v in item.items() if not k.startswith("_")}
            out.append(clean)
        # Sort newest-first client-side.
        out.sort(key=lambda d: d.get("created_at") or "", reverse=True)
    except Exception as exc:
        _logger.warning("Decision Ledger query failed (returning empty): %s", exc)
        return []
    return out


# ────────────────────────────────────────────────────────────────────────────
# Cost + latency dashboard
# ────────────────────────────────────────────────────────────────────────────
async def query_cost(
    ledger: Ledger,
    *,
    window: str = "24h",
    team_id: Optional[str] = None,
) -> dict:
    """Aggregate cost + latency across pipeline-runs in the time window."""
    delta = parse_window(window)
    since_dt = datetime.now(timezone.utc) - delta
    since_iso = since_dt.isoformat()

    clauses = ["c.created_at>=@s"]
    params: list[dict[str, Any]] = [{"name": "@s", "value": since_iso}]
    if team_id:
        clauses.append("c.team_id=@t")
        params.append({"name": "@t", "value": team_id})
    query = f"SELECT * FROM c WHERE {' AND '.join(clauses)}"

    runs: list[dict] = []
    try:
        async for item in ledger._runs.query_items(  # noqa: SLF001
            query=query, parameters=params,
        ):
            runs.append(item)
    except Exception as exc:
        _logger.warning("Cost query (pipeline-runs) failed: %s", exc)

    return _aggregate_cost(runs, since_dt, delta)


def _aggregate_cost(runs: list[dict], since_dt: datetime, delta: timedelta) -> dict:
    """Pure aggregation — easy to unit-test."""
    total_runs = len(runs)
    total_cost = 0.0
    total_tokens = 0
    total_decisions = 0
    human_decisions = 0
    autopilot_decisions = 0
    gate_wall = 0.0
    gate_wall_n = 0
    cost_by_stage: dict[str, float] = defaultdict(float)

    # Per-run datapoints for the line chart.
    points: list[dict[str, Any]] = []

    for run in runs:
        cost = float(run.get("total_cost_usd") or 0.0)
        toks = int(run.get("total_tokens") or 0)
        total_cost += cost
        total_tokens += toks

        decisions = run.get("decisions") or []
        auto_ids = set(run.get("autopilot_decisions") or [])
        for d in decisions:
            total_decisions += 1
            cs = d.get("confidence_source")
            cid = d.get("card_id")
            if cs == "autopilot" or (cid and cid in auto_ids):
                autopilot_decisions += 1
            else:
                human_decisions += 1

        gws = run.get("gate_wall_clock_seconds")
        if gws is not None:
            gate_wall += float(gws)
            gate_wall_n += 1

        # Per-stage cost split: which stages completed in this run?
        observed_stages = set()
        for ev in run.get("events", []) or []:
            stg = ev.get("stage")
            if stg in _STAGE_WEIGHTS and ev.get("status") == "completed":
                observed_stages.add(stg)
        if not observed_stages:
            observed_stages = set(_KNOWN_STAGES)
        weight_sum = sum(_STAGE_WEIGHTS[s] for s in observed_stages)
        if weight_sum > 0 and cost > 0:
            for s in observed_stages:
                cost_by_stage[s] += cost * (_STAGE_WEIGHTS[s] / weight_sum)

        ts_raw = run.get("created_at") or ""
        points.append({"ts": ts_raw, "usd": round(cost, 6), "run_id": run.get("run_id")})

    points.sort(key=lambda p: p["ts"])

    # Ensure all known stages appear in the breakdown (zero if absent).
    full_stage_costs = {s: round(cost_by_stage.get(s, 0.0), 6) for s in _KNOWN_STAGES}

    cpd = (total_cost / total_decisions) if total_decisions else 0.0
    mean_gate = (gate_wall / gate_wall_n) if gate_wall_n else 0.0
    mean_tok = (total_tokens / total_runs) if total_runs else 0.0

    return {
        "window": f"{int(delta.total_seconds()/3600)}h",
        "since": since_dt.isoformat(),
        "total_runs": total_runs,
        "total_decisions": total_decisions,
        "human_decisions": human_decisions,
        "autopilot_decisions": autopilot_decisions,
        "total_cost_usd": round(total_cost, 6),
        "total_tokens": total_tokens,
        "cost_per_decision_usd": round(cpd, 6),
        "mean_gate_wall_clock_seconds": round(mean_gate, 3),
        "mean_tokens_per_run": round(mean_tok, 1),
        "cost_by_stage": full_stage_costs,
        "cost_per_run_timeseries": points,
    }


# ────────────────────────────────────────────────────────────────────────────
# Ambiguity class drift
# ────────────────────────────────────────────────────────────────────────────
async def query_classes(
    ledger: Ledger,
    *,
    window: str = "7d",
    team_id: Optional[str] = None,
) -> dict:
    """Per-class counts, autopilot acceptance rate, blast radius, trend arrow."""
    delta = parse_window(window)
    now = datetime.now(timezone.utc)
    cur_since = now - delta
    prev_since = now - 2 * delta

    runs = await _runs_in_window(ledger, since=prev_since, team_id=team_id)
    cur_runs = [r for r in runs if (r.get("created_at") or "") >= cur_since.isoformat()]
    prev_runs = [r for r in runs if (r.get("created_at") or "") < cur_since.isoformat()]

    cur_stats = _per_class_stats(cur_runs)
    prev_counts = {k: v["count"] for k, v in _per_class_stats(prev_runs).items()}

    # Negative-precedent counts from the ledger (status='demoted' is the closest
    # signal — there's no 'negative_precedent' status in models.LedgerStatus).
    negs = await _negative_precedents(ledger, team_id=team_id, since_iso=cur_since.isoformat())

    total = sum(s["count"] for s in cur_stats.values()) or 1
    out_classes: list[dict[str, Any]] = []
    for klass, st in cur_stats.items():
        prev = prev_counts.get(klass, 0)
        cur = st["count"]
        if prev == 0 and cur > 0:
            trend = "up"
        elif cur == 0 and prev > 0:
            trend = "down"
        elif prev == 0 and cur == 0:
            trend = "flat"
        else:
            delta_ratio = (cur - prev) / max(prev, 1)
            trend = "up" if delta_ratio > 0.15 else "down" if delta_ratio < -0.15 else "flat"
        accept = st["autopilot_accepts"]
        autopilot_total = st["autopilot_total"]
        rate = (accept / autopilot_total) if autopilot_total else 0.0
        out_classes.append({
            "ambiguity_class": klass,
            "count": cur,
            "pct_of_total": round(100.0 * cur / total, 2),
            "autopilot_acceptance_rate": round(rate, 4),
            "mean_blast_radius_cost_usd": round(st["mean_blast"], 2),
            "negative_precedent_count": negs.get(klass, 0),
            "trend": trend,
            "is_invariant": klass in INVARIANT_CLASSES,
        })
    out_classes.sort(key=lambda c: c["count"], reverse=True)
    return {
        "window": f"{int(delta.total_seconds()/3600)}h",
        "since": cur_since.isoformat(),
        "total_decisions": sum(s["count"] for s in cur_stats.values()),
        "classes": out_classes,
    }


async def _runs_in_window(
    ledger: Ledger, *, since: datetime, team_id: Optional[str],
) -> list[dict]:
    clauses = ["c.created_at>=@s"]
    params: list[dict[str, Any]] = [{"name": "@s", "value": since.isoformat()}]
    if team_id:
        clauses.append("c.team_id=@t")
        params.append({"name": "@t", "value": team_id})
    query = f"SELECT * FROM c WHERE {' AND '.join(clauses)}"
    out: list[dict] = []
    try:
        async for item in ledger._runs.query_items(  # noqa: SLF001
            query=query, parameters=params,
        ):
            out.append(item)
    except Exception as exc:
        _logger.warning("classes/_runs_in_window failed: %s", exc)
    return out


def _per_class_stats(runs: list[dict]) -> dict[str, dict[str, Any]]:
    """Group cards/decisions by ambiguity_class across the given runs."""
    by: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "blast_sum": 0.0, "blast_n": 0,
                 "autopilot_total": 0, "autopilot_accepts": 0, "mean_blast": 0.0}
    )
    for run in runs:
        cards = run.get("cards") or []
        card_by_id = {c.get("card_id"): c for c in cards if c.get("card_id")}
        auto_ids = set(run.get("autopilot_decisions") or [])
        decisions = run.get("decisions") or []
        for d in decisions:
            cid = d.get("card_id")
            if not cid:
                continue
            card = card_by_id.get(cid)
            klass = (card or {}).get("ambiguity_class") or "other"
            slot = by[klass]
            slot["count"] += 1
            blast = float((card or {}).get("blast_radius_cost_usd") or 0.0)
            if blast > 0:
                slot["blast_sum"] += blast
                slot["blast_n"] += 1
            if d.get("confidence_source") == "autopilot" or cid in auto_ids:
                slot["autopilot_total"] += 1
                if d.get("decision_kind") == "accept":
                    slot["autopilot_accepts"] += 1
    for s in by.values():
        s["mean_blast"] = (s["blast_sum"] / s["blast_n"]) if s["blast_n"] else 0.0
    return by


# ────────────────────────────────────────────────────────────────────────────
# Runs index (recent runs list for /runs page)
# ────────────────────────────────────────────────────────────────────────────
async def query_recent_runs(
    ledger: Ledger,
    *,
    team_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """Recent pipeline-runs summaries, ORDER BY updated_at DESC.

    Returns project-shaped summary dicts (no full events/cards payload) suitable
    for the runs index page. Empty list on Cosmos error.
    """
    limit = max(1, min(int(limit or 50), 200))
    clauses = ["1=1"]
    params: list[dict[str, Any]] = []
    if team_id:
        clauses.append("c.team_id=@t")
        params.append({"name": "@t", "value": team_id})
    if status:
        statuses = [s.strip() for s in status.split(",") if s.strip()]
        if len(statuses) == 1:
            clauses.append("c.status=@st")
            params.append({"name": "@st", "value": statuses[0]})
        elif statuses:
            placeholders = ",".join(f"@st{i}" for i in range(len(statuses)))
            clauses.append(f"c.status IN ({placeholders})")
            for i, s in enumerate(statuses):
                params.append({"name": f"@st{i}", "value": s})
    # Cosmos requires TOP to be a literal int, not parameterized.
    # ORDER BY removed: cross-partition ORDER BY needs a composite index.
    # SELECT * to avoid projection issues on missing fields. Sort + slim client-side.
    query = (
        f"SELECT TOP {limit} * FROM c WHERE {' AND '.join(clauses)}"
    )
    out: list[dict] = []
    try:
        async for item in ledger._runs.query_items(  # noqa: SLF001
            query=query, parameters=params,
        ):
            # Project to summary fields client-side.
            summary = {
                "run_id": item.get("run_id"),
                "team_id": item.get("team_id"),
                "status": item.get("status"),
                "current_stage": item.get("current_stage"),
                "mode": item.get("mode"),
                "total_cost_usd": item.get("total_cost_usd"),
                "total_tokens": item.get("total_tokens"),
                "gate_wall_clock_seconds": item.get("gate_wall_clock_seconds"),
                "created_at": item.get("created_at"),
                "updated_at": item.get("updated_at"),
                "decisions_count": len(item.get("decisions") or []),
            }
            out.append(summary)
        # Sort newest-first client-side (Cosmos ORDER BY cross-partition needs index).
        out.sort(key=lambda r: r.get("updated_at") or r.get("created_at") or "", reverse=True)
    except Exception as exc:
        _logger.warning("query_recent_runs failed (returning empty): %s :: query=%r params=%r", exc, query, params)
        return []
    return out


async def _negative_precedents(
    ledger: Ledger, *, team_id: Optional[str], since_iso: str,
) -> dict[str, int]:
    """Count `demoted` entries per class (proxy for 'negative precedent' signal)."""
    clauses = ["c.status=@d", "c.created_at>=@s"]
    params: list[dict[str, Any]] = [
        {"name": "@d", "value": "demoted"},
        {"name": "@s", "value": since_iso},
    ]
    if team_id:
        clauses.append("c.team_id=@t")
        params.append({"name": "@t", "value": team_id})
    query = f"SELECT c.ambiguity_class FROM c WHERE {' AND '.join(clauses)}"
    out: dict[str, int] = defaultdict(int)
    try:
        kwargs: dict[str, Any] = {"query": query, "parameters": params}
        if team_id:
            kwargs["partition_key"] = team_id
        async for item in ledger._ledger.query_items(**kwargs):  # noqa: SLF001
            klass = item.get("ambiguity_class") or "other"
            out[klass] += 1
    except Exception as exc:
        _logger.warning("negative_precedents query failed: %s", exc)
    return dict(out)
