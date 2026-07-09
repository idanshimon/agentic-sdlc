"""Tests for the net-new GitHub merge primitive (PR-4).

deliver_pr.py only OPENS PRs (swap-deliver-ado-to-github: "orchestrator never
merges"). The autonomous loop's Tier-A auto-merge needs a real
PUT /pulls/{n}/merge that is branch-protection-aware: a merge blocked by
required checks / reviews MUST escalate explicitly, never silent-no-op (which
would violate the never-silent-merge invariant).

Run:
    source .venv/bin/activate
    python -m pytest apps/orchestrator/tests/test_merge_pr.py -q
"""
from __future__ import annotations

import asyncio

import pytest

from apps.orchestrator import merge_pr as mp


class _FakeResponse:
    def __init__(self, status_code, json_data=None):
        self.status_code = status_code
        self._json = json_data or {}

    def json(self):
        return self._json


class _FakeClient:
    """Minimal stand-in for httpx.AsyncClient — records the PUT it received."""
    def __init__(self, response):
        self._response = response
        self.calls = []

    async def put(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self._response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


def _run(coro):
    return asyncio.run(coro)


def test_successful_merge_returns_merged_result():
    client = _FakeClient(_FakeResponse(200, {"merged": True, "sha": "abc123"}))
    result = _run(mp.merge_pull_request(
        repo="owner/delivery", pr_number=7, token="t", client=client))
    assert result.merged is True
    assert result.sha == "abc123"
    assert result.escalate is False
    # verify it hit the real merge endpoint
    url, _ = client.calls[0]
    assert url.endswith("/repos/owner/delivery/pulls/7/merge")


def test_branch_protection_block_405_escalates_not_silent():
    """405 Method Not Allowed = blocked by branch protection / not mergeable.
    MUST escalate, never report a silent success."""
    client = _FakeClient(_FakeResponse(405, {"message": "Required status check is expected."}))
    result = _run(mp.merge_pull_request(
        repo="owner/delivery", pr_number=7, token="t", client=client))
    assert result.merged is False
    assert result.escalate is True
    assert "branch protection" in result.reason.lower() or "not mergeable" in result.reason.lower()


def test_conflict_409_escalates():
    client = _FakeClient(_FakeResponse(409, {"message": "Head branch was modified. Review and try the merge again."}))
    result = _run(mp.merge_pull_request(
        repo="owner/delivery", pr_number=7, token="t", client=client))
    assert result.merged is False
    assert result.escalate is True


def test_no_token_refuses_rather_than_pretending():
    result = _run(mp.merge_pull_request(
        repo="owner/delivery", pr_number=7, token="", client=None))
    assert result.merged is False
    assert result.escalate is True
    assert "token" in result.reason.lower()


def test_merge_method_is_configurable():
    client = _FakeClient(_FakeResponse(200, {"merged": True, "sha": "z"}))
    _run(mp.merge_pull_request(
        repo="o/r", pr_number=3, token="t", client=client, merge_method="squash"))
    _, kwargs = client.calls[0]
    assert kwargs["json"]["merge_method"] == "squash"
