"""Phase 5 hardening — Cosmos query shape for the compliance read.

Cross-partition ORDER BY in Cosmos requires a composite index that isn't
guaranteed to exist; the rest of this codebase (query_recent_runs,
query_decisions) deliberately omits cross-partition ORDER BY and sorts
client-side. The compliance query must follow the same rule or it can throw at
runtime against live Cosmos when no team_id (single partition) is supplied.

_build_compliance_cosmos_query is the pure, testable seam for that decision.
"""
from __future__ import annotations

from apps.orchestrator import compliance_query as cq


def test_single_partition_query_orders_db_side():
    # team_id given -> single partition -> ORDER BY is safe + cheap
    q = cq._build_compliance_cosmos_query(["c.team_id=@t"], limit=100, single_partition=True)
    assert "ORDER BY c.created_at DESC" in q
    assert q.startswith("SELECT TOP 100 *")


def test_cross_partition_query_omits_order_by():
    # no team_id -> cross partition -> NO ORDER BY (would need a composite index
    # and can throw). Ordering is done client-side in build_compliance_rows.
    q = cq._build_compliance_cosmos_query(["1=1"], limit=100, single_partition=False)
    assert "ORDER BY" not in q
    assert q.startswith("SELECT TOP 100 *")


def test_query_includes_all_clauses():
    q = cq._build_compliance_cosmos_query(
        ["c.team_id=@t", "c.phi_class=@p"], limit=50, single_partition=True,
    )
    assert "c.team_id=@t AND c.phi_class=@p" in q
