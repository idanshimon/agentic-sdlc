"""Phase 5 compliance endpoint test — GET /api/compliance/decisions.

Thin glue over compliance_query.query_compliance. With _ledger disabled in the
test env, the endpoint returns an empty-but-well-formed payload (rows/summary/
filters) — never a 500. Filter params are accepted and echoed back.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from apps.orchestrator.main import app

client = TestClient(app)


def test_compliance_endpoint_returns_shaped_payload_when_ledger_disabled():
    r = client.get("/api/compliance/decisions")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "rows" in body and isinstance(body["rows"], list)
    assert "summary" in body
    assert set(body["summary"]) >= {"total", "complete", "incomplete", "complete_pct"}
    assert "filters" in body


def test_compliance_endpoint_echoes_filters():
    r = client.get(
        "/api/compliance/decisions",
        params={"phi_class": "high", "actor_kind": "human", "team_id": "cardiology",
                "window": "30d"},
    )
    assert r.status_code == 200, r.text
    f = r.json()["filters"]
    assert f["phi_class"] == "high"
    assert f["actor_kind"] == "human"
    assert f["team_id"] == "cardiology"
    # a window shortcut resolves to a concrete since timestamp
    assert f["since"] is not None
