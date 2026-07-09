"""Test the GET /api/config/repo-autonomy endpoint (PR-4)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from apps.orchestrator.main import app

client = TestClient(app)


def test_repo_autonomy_endpoint_returns_posture():
    resp = client.get("/api/config/repo-autonomy")
    assert resp.status_code == 200
    body = resp.json()
    assert "bootstrap" in body
    assert "default_tier" in body
    assert body["default_tier"] == "C"
    assert isinstance(body["repos"], list)


def test_repo_autonomy_endpoint_reflects_reloaded_policy(tmp_path, monkeypatch):
    from apps.orchestrator import repo_autonomy as ra
    cfg = tmp_path / "repo_autonomy.yaml"
    cfg.write_text("repos:\n  demo: {tier: B}\n", encoding="utf-8")
    ra.reload_repo_autonomy(path=str(cfg))
    try:
        resp = client.get("/api/config/repo-autonomy")
        body = resp.json()
        assert body["bootstrap"] is False
        repos = {r["repo"]: r for r in body["repos"]}
        assert repos["demo"]["tier"] == "B"
    finally:
        ra.reload_repo_autonomy(path="/nonexistent")  # restore bootstrap
