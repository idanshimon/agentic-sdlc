from apps.orchestrator.review_dispatch import (
    ReviewLoopDispatch, ReviewLoopRegistry, identity_for,
)


def test_same_repo_pr_sha_has_same_loop_identity():
    dispatch = ReviewLoopDispatch(
        repo="owner/repo", pr_number=7, head_sha="a" * 40,
    )
    assert identity_for(dispatch).loop_id == identity_for(dispatch).loop_id


def test_new_head_sha_creates_new_loop_identity():
    first = identity_for(ReviewLoopDispatch(repo="owner/repo", pr_number=7, head_sha="a" * 40))
    second = identity_for(ReviewLoopDispatch(repo="owner/repo", pr_number=7, head_sha="b" * 40))
    assert first.loop_id != second.loop_id


def test_registry_is_replay_safe():
    registry = ReviewLoopRegistry()
    identity = identity_for(ReviewLoopDispatch(repo="owner/repo", pr_number=7, head_sha="a" * 40))
    first, created = registry.get_or_create(identity, "github-actions")
    second, created_again = registry.get_or_create(identity, "other")
    assert created is True
    assert created_again is False
    assert second == first
    assert second["actor"] == "github-actions"


def test_dispatch_endpoint_requires_workload_and_is_idempotent(monkeypatch):
    from fastapi.testclient import TestClient
    from apps.orchestrator.main import app
    from apps.orchestrator.github_pr_snapshot import PullRequestSnapshot
    from apps.orchestrator.github_outcomes import PublishedOutcome
    from unittest.mock import AsyncMock

    monkeypatch.setenv("AUTH_MODE", "trusted_headers")
    monkeypatch.setenv("GH_TOKEN", "test-token")
    monkeypatch.setattr(
        "apps.orchestrator.main.fetch_pr_snapshot",
        AsyncMock(return_value=PullRequestSnapshot("owner/repo", 7, "a" * 40, {"src/main.py": "ok"})),
    )
    monkeypatch.setattr(
        "apps.orchestrator.main.publish_review_outcome",
        AsyncMock(return_value=PublishedOutcome(10, "check", 20, "comment")),
    )
    client = TestClient(app)
    sha = "a" * 40
    headers = {
        "x-auth-subject": "github-actions",
        "x-auth-kind": "workload",
        "x-auth-roles": "github_workload",
        "x-auth-teams": "",
        "idempotency-key": f"owner/repo:7:{sha}",
    }
    payload = {"repo": "owner/repo", "pr_number": 7, "head_sha": sha}
    first = client.post("/api/review-loops", headers=headers, json=payload)
    second = client.post("/api/review-loops", headers=headers, json=payload)
    assert first.status_code == 202, first.text
    assert second.status_code == 202, second.text
    assert first.json()["loop_id"] == second.json()["loop_id"]
    assert first.json()["created"] is True
    assert second.json()["created"] is False
    assert first.json()["disposition"] == "ADVISORY"
    assert first.json()["head_sha"] == sha
    assert first.json()["ledger_hops"][0]["loop_id"] == first.json()["loop_id"]
    assert first.json()["check_url"] == "check"

    denied = client.post(
        "/api/review-loops",
        headers={**headers, "x-auth-roles": "operator"}, json=payload,
    )
    assert denied.status_code == 403
