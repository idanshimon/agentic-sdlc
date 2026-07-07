"""Compliance query — the acceptance query (Phase 5, add-configuration-plane).

THE HERO of the configuration-plane capability. Phases 1–4 exist to make ONE
query return complete, real, cross-surface rows:

    "Every AI decision on PHI-classified data in the last 30 days, the governing
     rule version, the deciding actor (human UPN or agent principal), and the cost"

Each row answers: WHAT was decided, WHY (the governing autonomy rule + the
bundle rule VERSION), WHO decided it (human UPN or agent principal), which MODEL,
and the COST — filterable by phi_class, date range, actor kind, and team.

Design:
  * `build_compliance_rows()` is PURE (ledger dicts in, flat rows out) so the
    acceptance test is deterministic with no Cosmos. It normalizes the actor
    (synthesizing from legacy created_by/confidence_source when the structured
    `actor` sub-doc is absent — same rule as ledger_core.from_legacy_v06_dict)
    and applies the filters.
  * `query_compliance()` is thin Cosmos glue: pull entries (team-partitioned when
    a team is given, else cross-partition), then hand off to the pure builder.
  * Cross-surface by construction: rows come from the single decision-ledger
    container, which already holds pipeline stage decisions, autopilot decisions,
    human gates, IDE/agent-hq session entries, and model-policy refusals. There
    is NO surface-specific branch — a new producing surface that writes the same
    schema shows up automatically (openspec scenario "cross-surface capable").
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

_logger = logging.getLogger("orchestrator.compliance_query")


def _parse_ts(ts: str) -> Optional[datetime]:
    """Parse an ISO timestamp to an aware datetime, tolerating both the Python
    '...+00:00' and the JS '...Z' suffixes. Returns None on empty/garbage so a
    bad timestamp sorts last / filters out rather than crashing the audit query.
    Comparing parsed datetimes (not raw strings) is essential: lexicographic
    comparison of mixed +00:00 / Z suffixes mis-filters and mis-orders rows
    (Copilot review compliance_query.py:113)."""
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _norm_actor(entry: dict) -> tuple[str, str]:
    """Return (actor_kind, actor_id). Prefer the structured `actor` sub-doc;
    fall back to legacy created_by + confidence_source (autopilot => agent)."""
    actor = entry.get("actor")
    if isinstance(actor, dict) and actor.get("id"):
        return str(actor.get("kind") or "human"), str(actor["id"])
    created_by = entry.get("created_by") or ""
    conf = entry.get("confidence_source")
    kind = "agent" if conf == "autopilot" or created_by.endswith("@agent") else "human"
    return kind, str(created_by)


def _row(entry: dict) -> dict:
    """Flatten a ledger entry into a compliance row (the audit-facing shape)."""
    actor_kind, actor_id = _norm_actor(entry)
    return {
        "id": entry.get("id"),
        "created_at": entry.get("created_at") or "",
        "team_id": entry.get("team_id"),
        "run_id": entry.get("run_id"),
        "agent_session_id": entry.get("agent_session_id"),
        "stage": entry.get("stage"),
        # WHAT
        "decision": entry.get("decision") or entry.get("resolution_text") or "",
        "ambiguity_class": entry.get("ambiguity_class"),
        "decision_kind": entry.get("decision_kind"),
        # WHY — governing autonomy rule + bundle rule version(s)
        "autonomy_ref": entry.get("autonomy_ref") or "",
        "bundle_refs": list(entry.get("bundle_refs") or []),
        # WHO
        "actor_kind": actor_kind,
        "actor_id": actor_id,
        # model + cost + PHI class. cost_usd stays None when absent so a legacy
        # entry with no cost attribution is flagged INCOMPLETE rather than being
        # silently defaulted to $0.00 and marked complete (Copilot review :70).
        "model_used": entry.get("model_used"),
        "cost_usd": entry.get("cost_usd", None),
        "phi_class": entry.get("phi_class") or "none",
    }


def _is_complete(row: dict) -> bool:
    """A row is 'complete' when every audit column the acceptance query promises
    is present + non-null: governing rule version, actor identity, model, cost."""
    return bool(
        row.get("bundle_refs")
        and row.get("actor_id")
        and row.get("actor_kind") in ("human", "agent")
        and row.get("model_used")
        and row.get("cost_usd") is not None
    )


def build_compliance_rows(
    entries: list[dict],
    *,
    phi_class: Optional[str] = None,
    since_iso: Optional[str] = None,
    until_iso: Optional[str] = None,
    actor_kind: Optional[str] = None,
    team_id: Optional[str] = None,
) -> list[dict]:
    """Pure builder: normalize + filter ledger dicts into compliance rows,
    sorted newest-first. All filters are AND-combined; None = no filter.

    Timestamps are compared as parsed datetimes (not raw strings) so mixed
    '+00:00' / 'Z' suffixes across surfaces filter and order correctly
    (Copilot review compliance_query.py:113)."""
    since_dt = _parse_ts(since_iso) if since_iso else None
    until_dt = _parse_ts(until_iso) if until_iso else None
    rows: list[dict] = []
    for e in entries:
        row = _row(e)
        if phi_class and row["phi_class"] != phi_class:
            continue
        row_dt = _parse_ts(row["created_at"])
        if since_dt is not None and (row_dt is None or row_dt < since_dt):
            continue
        if until_dt is not None and (row_dt is None or row_dt > until_dt):
            continue
        if actor_kind and row["actor_kind"] != actor_kind:
            continue
        if team_id and row["team_id"] != team_id:
            continue
        row["complete"] = _is_complete(row)
        rows.append(row)
    # Newest-first by parsed datetime; unparseable timestamps sort last.
    _EPOCH = datetime.min.replace(tzinfo=timezone.utc)
    rows.sort(key=lambda r: _parse_ts(r["created_at"]) or _EPOCH, reverse=True)
    return rows


def completeness_summary(rows: list[dict]) -> dict:
    """Audit banner: how many rows are fully attributed vs missing a field.
    A non-zero `incomplete` is itself a compliance finding (a decision the
    system could not fully explain), surfaced honestly rather than hidden."""
    total = len(rows)
    complete = sum(1 for r in rows if r.get("complete", _is_complete(r)))
    return {
        "total": total,
        "complete": complete,
        "incomplete": total - complete,
        "complete_pct": round(100.0 * complete / total, 1) if total else 100.0,
    }


async def query_compliance(
    ledger: Any,
    *,
    phi_class: Optional[str] = None,
    since_iso: Optional[str] = None,
    until_iso: Optional[str] = None,
    actor_kind: Optional[str] = None,
    team_id: Optional[str] = None,
    limit: int = 500,
) -> dict:
    """Cosmos-backed compliance query. Pulls decision-ledger entries (team-
    partitioned when team_id is given, else cross-partition), then builds rows
    via the pure builder. Best-effort: a Cosmos error returns an empty,
    honestly-labelled payload rather than 500'ing the audit surface.

    Returns {rows, summary, filters} — the exact shape the compliance UI renders.
    """
    limit = max(1, min(int(limit or 500), 2000))
    clauses = ["1=1"]
    params: list[dict[str, Any]] = []
    if team_id:
        clauses.append("c.team_id=@t")
        params.append({"name": "@t", "value": team_id})
    if phi_class:
        clauses.append("c.phi_class=@p")
        params.append({"name": "@p", "value": phi_class})
    if since_iso:
        clauses.append("c.created_at>=@s")
        params.append({"name": "@s", "value": since_iso})
    if until_iso:
        clauses.append("c.created_at<=@u")
        params.append({"name": "@u", "value": until_iso})
    # ORDER BY created_at DESC so TOP N returns the MOST RECENT N decisions, not
    # an arbitrary subset (Copilot review compliance_query.py:162). Without it,
    # Cosmos gives no ordering guarantee and a capped 30d window could silently
    # drop the newest rows. build_compliance_rows re-sorts as a safety net, but
    # the DB-side ordering is what makes `limit` correct. Single-partition reads
    # (team_id given) order cheaply; cross-partition uses the created_at index.
    query = (
        f"SELECT TOP {limit} * FROM c WHERE {' AND '.join(clauses)} "
        f"ORDER BY c.created_at DESC"
    )

    entries: list[dict] = []
    try:
        kwargs: dict[str, Any] = {"query": query, "parameters": params}
        if team_id:
            kwargs["partition_key"] = team_id
        else:
            kwargs["enable_cross_partition_query"] = True
        async for item in ledger._ledger.query_items(**kwargs):  # noqa: SLF001
            entries.append({k: v for k, v in item.items() if not k.startswith("_")})
    except Exception as exc:
        _logger.warning("compliance query failed (returning empty): %s", exc)

    # actor_kind is applied in the pure builder (it's a derived field).
    rows = build_compliance_rows(
        entries, phi_class=phi_class, since_iso=since_iso, until_iso=until_iso,
        actor_kind=actor_kind, team_id=team_id,
    )
    return {
        "rows": rows,
        "summary": completeness_summary(rows),
        "filters": {
            "phi_class": phi_class, "since": since_iso, "until": until_iso,
            "actor_kind": actor_kind, "team_id": team_id,
        },
    }
