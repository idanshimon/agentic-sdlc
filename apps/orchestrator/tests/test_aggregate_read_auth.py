"""Read-only aggregate endpoints cannot cross team boundaries."""
from fastapi.testclient import TestClient
from apps.orchestrator.main import app


def h(team):
    return {"x-auth-subject":"reader","x-auth-kind":"human","x-auth-roles":"operator","x-auth-teams":team}


def test_runs_and_telemetry_reject_other_team(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "trusted_headers")
    client = TestClient(app)
    assert client.get("/api/runs?team_id=team-b", headers=h("team-a")).status_code == 403
    assert client.get("/api/telemetry/decisions?team_id=team-b", headers=h("team-a")).status_code == 403
    assert client.get("/api/compliance/decisions?team_id=team-b", headers=h("team-a")).status_code == 403


def test_non_public_read_requires_identity(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "trusted_headers")
    assert TestClient(app).get("/api/runs").status_code == 401
