"""Task 3.2: POST /api/review-loops/merge — the Tier-B human merge touch-point.

Tier B = autonomous review to PASS, but a human clicks merge. This endpoint is
that click. It enforces the tier server-side: it refuses on Tier-C/unlisted (no
merge surface there) and refuses when the repo is not graduated. Tier-A repos
merge autonomously via the loop, so this human endpoint is specifically the B path.

Run:
    source .venv/bin/activate
    python -m pytest apps/orchestrator/tests/test_review_loop_merge_endpoint.py -q
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from apps.orchestrator import repo_autonomy as ra
from apps.orchestrator.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_policy():
    yield
    ra.reload_repo_autonomy(path="/nonexistent")  # restore bootstrap after each test


def _set_policy(tmp_path, body: str):
    p = tmp_path / "repo_autonomy.yaml"
    p.write_text(body, encoding="utf-8")
    ra.reload_repo_autonomy(path=str(p))


def test_tier_b_repo_allows_human_merge(tmp_path, monkeypatch):
    _set_policy(tmp_path, "repos:\n  reviewed: {tier: B}\n")

    called = {}

    async def fake_merge(*, repo, pr_number, token, **kw):
        called["repo"] = repo
        called["pr"] = pr_number
        from apps.orchestrator.merge_pr import MergeResult
        return MergeResult(merged=True, sha="deadbeef", reason="merged")

    monkeypatch.setattr("apps.orchestrator.main.merge_pull_request", fake_merge, raising=False)

    resp = client.post("/api/review-loops/merge",
                       json={"repo": "reviewed", "pr_number": 12})
    assert resp.status_code == 200
    body = resp.json()
    assert body["merged"] is True
    assert body["sha"] == "deadbeef"
    assert called["pr"] == 12


def test_tier_c_repo_refuses_merge(tmp_path):
    _set_policy(tmp_path, "repos:\n  advisory: {tier: C}\n")
    resp = client.post("/api/review-loops/merge",
                       json={"repo": "advisory", "pr_number": 1})
    assert resp.status_code == 409
    assert "advisory" in resp.json()["detail"].lower() or "tier c" in resp.json()["detail"].lower()


def test_unlisted_repo_refuses_merge(tmp_path):
    _set_policy(tmp_path, "repos:\n  known: {tier: B}\n")
    resp = client.post("/api/review-loops/merge",
                       json={"repo": "never-heard-of-it", "pr_number": 1})
    assert resp.status_code == 409


def test_merge_failure_surfaces_as_escalation(tmp_path, monkeypatch):
    _set_policy(tmp_path, "repos:\n  reviewed: {tier: B}\n")

    async def fake_merge(*, repo, pr_number, token, **kw):
        from apps.orchestrator.merge_pr import MergeResult
        return MergeResult(merged=False, escalate=True,
                           reason="blocked by branch protection")

    monkeypatch.setattr("apps.orchestrator.main.merge_pull_request", fake_merge, raising=False)
    resp = client.post("/api/review-loops/merge",
                       json={"repo": "reviewed", "pr_number": 7})
    # A blocked merge is a 200 with merged=false + escalate — the caller sees the
    # honest outcome, not a fake success and not a 500.
    assert resp.status_code == 200
    body = resp.json()
    assert body["merged"] is False
    assert body["escalate"] is True
