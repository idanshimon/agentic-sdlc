"""Phase 0 regression test: /api/runs/{id}/approve must not 500.

Caught during live-pipeline Phase 0 verification (2026-06-16): the orchestrator's
LedgerEntry model had no `entry_type` field, but ledger-core's CosmosLedger
.write_entry() reads `entry.entry_type` as the first thing it does. Every
per-card approve call raised AttributeError, returning 500 to the client.

This regression-tests the contract at the model level so the next drift
between orchestrator and ledger-core is caught at unit-test time, not
discovered in prod by a human clicking a broken button.
"""
from __future__ import annotations

import pytest

from orchestrator.models import LedgerEntry


def test_ledger_entry_has_entry_type_field():
    """LedgerEntry MUST expose `entry_type` because ledger-core reads it.

    Without this field, write_entry() raises AttributeError on the very
    first line — `if entry.entry_type == "runtime"`. The 500 the UI sees
    comes from this exact mismatch.
    """
    e = LedgerEntry(
        team_id="team-cardiology",
        run_id="r1",
        card_id="c1",
        ambiguity_class="phi-classification",
        decision_kind="accept",
    )
    # AttributeError here means the orchestrator-vs-ledger-core schema
    # drift is back. The default value MUST be "runtime" — that's what
    # ledger-core's invariant guard branches on.
    assert e.entry_type == "runtime"


def test_ledger_entry_serializes_entry_type():
    """model_dump must include entry_type so Cosmos document has it.

    The cosmos write path is `doc = entry.model_dump(...); upsert_item(doc)`.
    If entry_type isn't in the dumped dict, future readers (find_invariant
    in cosmos.py, ledger.query in ledger-mcp) won't find it and will
    silently treat the entry as missing.
    """
    e = LedgerEntry(
        team_id="team-cardiology",
        run_id="r1",
        card_id="c1",
        ambiguity_class="phi-classification",
        decision_kind="accept",
    )
    dumped = e.model_dump(mode="json", exclude_none=False)
    assert dumped["entry_type"] == "runtime"


def test_ledger_entry_entry_type_is_overridable():
    """If we ever need to write a non-runtime entry from orchestrator
    (we don't today; teaching signals go through ledger-mcp), the field
    must be settable. Document the surface, don't lock it.
    """
    e = LedgerEntry(
        team_id="team-cardiology",
        run_id="r1",
        card_id="c1",
        ambiguity_class="phi-classification",
        decision_kind="accept",
        entry_type="meta",
    )
    assert e.entry_type == "meta"
