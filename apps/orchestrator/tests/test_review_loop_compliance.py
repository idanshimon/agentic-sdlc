"""Task 5.1 + completion gate: the 3 loop kinds flow through the generic ledger
query with NO loop-specific branch, and a converged loop is reconstructable from
the ledger alone via its reviewloop/... citations.

There is no dedicated compliance_query module in this repo; the generic
newest-first reader is telemetry_queries.query_decisions, which filters only on
team_id / decision_kind / created_at and returns any entry unmodified. That
genericity IS the "no loop-specific branch" property the spec requires.

Run:
    source .venv/bin/activate
    python -m pytest apps/orchestrator/tests/test_review_loop_compliance.py -q
"""
from __future__ import annotations

import asyncio
from typing import Any, Optional

from apps.orchestrator import telemetry_queries as tq


class _FakeCosmosLedger:
    """Minimal Ledger stand-in: query_items yields the seeded docs (post-WHERE
    is emulated loosely — we return everything and let the query's client-side
    sort run, which is what matters for the reconstruction assertion)."""

    def __init__(self, docs: list[dict]):
        self._docs = docs

    class _Inner:
        def __init__(self, docs):
            self._docs = docs

        async def query_items(self, *, query: str, parameters=None, **kwargs):
            for d in self._docs:
                yield d

    @property
    def _ledger(self):
        return _FakeCosmosLedger._Inner(self._docs)


def _loop_chain() -> list[dict]:
    """A converged Tier-A loop: one remediation, then a merge — the shape the
    controller writes (runtime_kind + autonomy_ref + created_at)."""
    return [
        {
            "id": "h1", "team_id": "t1", "entry_type": "runtime",
            "runtime_kind": "review_remediation",
            "autonomy_ref": "reviewloop/A/delivery/remediate@attempt=1",
            "decision": "remediation attempt 1", "created_at": "2026-07-08T10:00:00+00:00",
            "_cosmos_internal": "strip-me",
        },
        {
            "id": "h2", "team_id": "t1", "entry_type": "runtime",
            "runtime_kind": "loop_converged",
            "autonomy_ref": "reviewloop/A/delivery/merge@attempt=1",
            "decision": "auto-merged", "created_at": "2026-07-08T10:01:00+00:00",
        },
    ]


def _run(coro):
    return asyncio.run(coro)


def test_loop_kinds_flow_through_generic_query_no_special_branch():
    ledger = _FakeCosmosLedger(_loop_chain())
    rows = _run(tq.query_decisions(ledger, team_id="t1", limit=50))
    kinds = {r["runtime_kind"] for r in rows}
    assert kinds == {"review_remediation", "loop_converged"}
    # Cosmos internals stripped (generic cleaning, not loop-specific).
    assert all(not any(k.startswith("_") for k in r) for r in rows)


def test_converged_loop_reconstructable_from_citations_alone():
    ledger = _FakeCosmosLedger(_loop_chain())
    rows = _run(tq.query_decisions(ledger, team_id="t1", limit=50))
    refs = [r["autonomy_ref"] for r in rows]
    assert all(ref.startswith("reviewloop/A/delivery/") for ref in refs)
    # Exactly one remediation + one converged -> the auditor can rebuild the arc.
    remediations = [r for r in rows if r["runtime_kind"] == "review_remediation"]
    converged = [r for r in rows if r["runtime_kind"] == "loop_converged"]
    assert len(remediations) == 1
    assert len(converged) == 1
    # newest-first: merge is the terminal hop.
    assert rows[0]["runtime_kind"] == "loop_converged"


def test_escalated_loop_is_queryable_and_cites_reason():
    escalated = [{
        "id": "e1", "team_id": "t1", "entry_type": "runtime",
        "runtime_kind": "loop_escalated",
        "autonomy_ref": "reviewloop/A/delivery/escalate@attempt=3:max_attempts",
        "decision": "escalated: max_attempts", "created_at": "2026-07-08T11:00:00+00:00",
    }]
    ledger = _FakeCosmosLedger(escalated)
    rows = _run(tq.query_decisions(ledger, team_id="t1", limit=50))
    assert rows[0]["runtime_kind"] == "loop_escalated"
    assert ":max_attempts" in rows[0]["autonomy_ref"]
