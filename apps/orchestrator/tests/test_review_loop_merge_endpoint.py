"""Human merge is bound to a verified Tier-B loop and exact head SHA."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from apps.orchestrator import repo_autonomy as ra
from apps.orchestrator.github_pr_snapshot import PullRequestSnapshot
from apps.orchestrator.main import app, _review_loop_registry
from apps.orchestrator.merge_pr import MergeResult

client = TestClient(app)
SHA = "a" * 40


@pytest.fixture(autouse=True)
def reset(monkeypatch, tmp_path):
    path = tmp_path / "repo_autonomy.yaml"
    path.write_text("repos:\n  owner/repo: {tier: B}\n")
    ra.reload_repo_autonomy(path=str(path))
    _review_loop_registry._items.clear()
    monkeypatch.setenv("GH_TOKEN", "test-token")
    monkeypatch.setattr(
        "apps.orchestrator.main.fetch_pr_snapshot",
        AsyncMock(return_value=PullRequestSnapshot("owner/repo", 7, SHA, {"a.py": "ok"})),
    )
    yield
    ra.reload_repo_autonomy(path="/nonexistent")
    _review_loop_registry._items.clear()


def seed(disposition="PASSED_AWAITING_MERGE"):
    _review_loop_registry._items["loop-1"] = {
        "loop_id": "loop-1", "repo": "owner/repo", "pr_number": 7,
        "head_sha": SHA, "disposition": disposition,
    }


def test_verified_tier_b_loop_can_merge(monkeypatch):
    seed()
    monkeypatch.setattr(
        "apps.orchestrator.main.merge_pull_request",
        AsyncMock(return_value=MergeResult(merged=True, sha="deadbeef", reason="merged")),
    )
    response = client.post("/api/review-loops/merge", json={
        "loop_id": "loop-1", "expected_head_sha": SHA,
    })
    assert response.status_code == 200, response.text
    assert response.json()["disposition"] == "MERGED"


def test_nonpassing_loop_cannot_merge():
    seed("ESCALATED")
    response = client.post("/api/review-loops/merge", json={
        "loop_id": "loop-1", "expected_head_sha": SHA,
    })
    assert response.status_code == 409


def test_stale_expected_sha_cannot_merge():
    seed()
    response = client.post("/api/review-loops/merge", json={
        "loop_id": "loop-1", "expected_head_sha": "b" * 40,
    })
    assert response.status_code == 409
