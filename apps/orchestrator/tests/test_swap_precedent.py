"""Task 4 — operator swap at the resolver gate is precedent-shaped (teaching loop).

When an operator writes their own resolution (decision_kind="swap" +
resolution_text), the ledger entry MUST carry the card's slot_value_hash +
ambiguity_class and the operator's verbatim text, and MUST be precedent-eligible
(no runtime_kind that would exclude it from findPrecedent's candidate query).
That is what makes findPrecedent quote the operator's wording back on the next
run in the same ambiguity bucket.

This test pins the shape against a fake ledger so it runs without Cosmos.

Run: PYTHONPATH=. .venv/bin/python -m pytest apps/orchestrator/tests/test_swap_precedent.py -v
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from apps.orchestrator import main as orchestrator_main
from apps.orchestrator.main import app, _runs
from apps.orchestrator.models import (
    AmbiguityCard, ResolutionOption, RunState, RunStatus, Stage,
)


class _FakeLedger:
    """Captures write_decision calls so we can assert the entry shape."""
    def __init__(self):
        self.entries = []

    async def write_decision(self, entry):
        self.entries.append(entry)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def fake_ledger(monkeypatch):
    fl = _FakeLedger()
    monkeypatch.setattr(orchestrator_main, "_ledger", fl)
    return fl


@pytest.fixture
def seeded_run():
    rec = ResolutionOption(
        label="rec", resolution="Recommended text.",
        rationale="why", downstream_impact="impact", recommended=True,
    )
    card = AmbiguityCard(
        card_id="swap-card", title="t", detail="d",
        ambiguity_class="data-retention", slot_value_hash="slot-hash-xyz",
        options=[rec],
    )
    run = RunState(
        team_id="cardiology", run_id="run-swap", prd_blob_url="x",
        status=RunStatus.AWAITING_GATE, current_stage=Stage.RESOLVER, cards=[card],
    )
    _runs[run.run_id] = run
    yield run
    _runs.pop(run.run_id, None)


def test_swap_entry_is_precedent_shaped(client, seeded_run, fake_ledger):
    """A swap with custom text writes a ledger entry carrying the card's
    slot_value_hash + ambiguity_class + the operator's verbatim text, and is
    precedent-eligible (no excluding runtime_kind)."""
    custom = "Retain 90 days; this team's compliance officer signed off (policy CO-2026-14)."
    resp = client.post(
        f"/api/runs/{seeded_run.run_id}/approve",
        json={
            "card_id": "swap-card",
            "decision_kind": "swap",
            "resolution_text": custom,
            "approval_path": "individual",
            "actor": "operator@dashboard",
        },
    )
    assert resp.status_code == 200, resp.text

    assert len(fake_ledger.entries) == 1
    e = fake_ledger.entries[0]
    # carries the operator's verbatim text
    assert e.resolution_text == custom
    # same slot_value_hash as the card → findPrecedent matches the bucket
    assert e.slot_value_hash == "slot-hash-xyz"
    assert e.ambiguity_class == "data-retention"
    # recorded as a swap, authored by the operator
    assert e.decision_kind == "swap"
    assert e.created_by == "operator@dashboard"
    # precedent-eligible: runtime_kind unset OR "stage_decision" (NOT a
    # teaching-signal kind that findPrecedent's candidate filter excludes)
    rk = getattr(e, "runtime_kind", None)
    assert rk in (None, "stage_decision"), f"swap entry has excluding runtime_kind={rk!r}"


def test_swap_resolution_text_is_verbatim_not_canned(client, seeded_run, fake_ledger):
    """The persisted text is the operator's, NOT the recommended option's."""
    custom = "Totally different from the recommendation."
    resp = client.post(
        f"/api/runs/{seeded_run.run_id}/approve",
        json={
            "card_id": "swap-card", "decision_kind": "swap",
            "resolution_text": custom, "approval_path": "individual",
            "actor": "operator@dashboard",
        },
    )
    assert resp.status_code == 200, resp.text
    e = fake_ledger.entries[0]
    assert e.resolution_text == custom
    assert e.resolution_text != "Recommended text."
