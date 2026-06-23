"""Tests for deliver_pr — real GitHub PR delivery (replaces the fake-URL paths).

All exercised against an httpx.MockTransport so no network/token is needed. We
verify: no-token degradation, repo resolution (explicit + convention default),
empty-repo bootstrap, auto-create, the full Git Data API happy path, and that a
failure NEVER yields a fabricated URL.
"""
from __future__ import annotations

import asyncio

import httpx
import pytest

from apps.orchestrator import deliver_pr as dp


_FILES = [
    {"path": "src/main.py", "content": "print('hi')\n"},
    {"path": "tests/test_main.py", "content": "def test_x():\n    assert True\n"},
    {"path": "decisions.md", "content": "# Decisions\n"},
]


# --- no token: honest failure, no URL -----------------------------------------

def test_no_token_returns_clean_failure(monkeypatch):
    monkeypatch.setattr(dp, "_TARGET_REPO", "owner/repo")
    monkeypatch.setattr(dp, "_DRY_RUN", False)
    for v in ("DELIVER_GH_TOKEN", "DELIVERY_GH_TOKEN", "CONFIG_GH_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"):
        monkeypatch.delenv(v, raising=False)
    res = asyncio.run(dp.open_delivery_pr(
        run_id="r1", team_id="t", files=_FILES, title="x", body="y"))
    assert res.ok is False
    assert res.pr_url is None
    assert "token" in res.reason.lower()


# --- dry run: ok, but no URL --------------------------------------------------

def test_dry_run_no_url(monkeypatch):
    monkeypatch.setattr(dp, "_TARGET_REPO", "owner/repo")
    monkeypatch.setattr(dp, "_DRY_RUN", True)
    monkeypatch.setenv("DELIVER_GH_TOKEN", "ghp_fake")
    res = asyncio.run(dp.open_delivery_pr(
        run_id="r1", team_id="t", files=_FILES, title="x", body="y"))
    assert res.ok is True
    assert res.pr_url is None
    assert "DRY-RUN" in res.reason


# --- happy path against a full mock Git Data API ------------------------------

def _happy_handler(*, repo_exists=True, base_ready=True, pr_exists=False):
    state = {"branch_created": False}

    def handler(request: httpx.Request) -> httpx.Response:
        m, url = request.method, str(request.url)
        if url.endswith("/user") and m == "GET":
            return httpx.Response(200, json={"login": "owner"})
        if "/repos/owner/repo" in url and url.endswith("/repos/owner/repo") and m == "GET":
            return httpx.Response(200 if repo_exists else 404, json={"full_name": "owner/repo"})
        if m == "POST" and url.endswith("/user/repos"):
            return httpx.Response(201, json={"full_name": "owner/repo"})
        if "/git/refs/heads/main" in url and m == "GET":
            if not base_ready and not state["branch_created"]:
                return httpx.Response(409, json={"message": "Git Repository is empty."})
            return httpx.Response(200, json={"object": {"sha": "basesha"}})
        if "/contents/README.md" in url and m == "PUT":
            state["branch_created"] = True
            return httpx.Response(201, json={"commit": {"sha": "seedsha"}})
        if "/git/commits/basesha" in url and m == "GET":
            return httpx.Response(200, json={"tree": {"sha": "basetree"}})
        if url.endswith("/git/blobs") and m == "POST":
            return httpx.Response(201, json={"sha": "blobsha"})
        if url.endswith("/git/trees") and m == "POST":
            return httpx.Response(201, json={"sha": "newtree"})
        if url.endswith("/git/commits") and m == "POST":
            return httpx.Response(201, json={"sha": "newcommit"})
        if url.endswith("/git/refs") and m == "POST":
            return httpx.Response(201, json={"ref": "refs/heads/agentic/r1"})
        if url.endswith("/pulls") and m == "POST":
            if pr_exists:
                return httpx.Response(422, json={"message": "A pull request already exists for owner:agentic/r1."})
            return httpx.Response(201, json={"html_url": "https://github.com/owner/repo/pull/7", "number": 7})
        if "/pulls?" in url or (url.endswith("/pulls") and m == "GET"):
            return httpx.Response(200, json=[{"html_url": "https://github.com/owner/repo/pull/5"}])
        return httpx.Response(500, json={"message": f"unexpected {m} {url}"})

    return handler


def _call_with(monkeypatch, handler, **cfg):
    monkeypatch.setattr(dp, "_DRY_RUN", False)
    monkeypatch.setenv("DELIVER_GH_TOKEN", "ghp_fake")
    for k, v in cfg.items():
        monkeypatch.setattr(dp, k, v)
    real_client = httpx.AsyncClient

    def patched(*a, **kw):
        kw["transport"] = httpx.MockTransport(handler)
        return real_client(*a, **kw)

    monkeypatch.setattr(dp.httpx, "AsyncClient", patched)
    return asyncio.run(dp.open_delivery_pr(
        run_id="r1", team_id="t", files=_FILES, title="run", body="body"))


def test_happy_path_explicit_repo(monkeypatch):
    res = _call_with(monkeypatch, _happy_handler(), _TARGET_REPO="owner/repo")
    assert res.ok is True
    assert res.pr_url == "https://github.com/owner/repo/pull/7"
    assert res.branch == "agentic/r1"


def test_default_repo_from_token_owner(monkeypatch):
    # No explicit repo → derived as <owner>/<default-name>.
    res = _call_with(
        monkeypatch, _happy_handler(),
        _TARGET_REPO="", _DEFAULT_REPO_NAME="repo")
    assert res.ok is True
    assert res.pr_url == "https://github.com/owner/repo/pull/7"


def test_empty_repo_is_bootstrapped(monkeypatch):
    # Base branch 409 (empty) → README seeded → then succeeds.
    res = _call_with(
        monkeypatch, _happy_handler(base_ready=False), _TARGET_REPO="owner/repo")
    assert res.ok is True
    assert res.pr_url == "https://github.com/owner/repo/pull/7"


def test_missing_repo_without_autocreate_fails_cleanly(monkeypatch):
    res = _call_with(
        monkeypatch, _happy_handler(repo_exists=False),
        _TARGET_REPO="owner/repo", _AUTO_CREATE=False)
    assert res.ok is False
    assert res.pr_url is None
    assert "does not exist" in res.reason


def test_missing_repo_with_autocreate_succeeds(monkeypatch):
    res = _call_with(
        monkeypatch, _happy_handler(repo_exists=False, base_ready=False),
        _TARGET_REPO="owner/repo", _AUTO_CREATE=True)
    assert res.ok is True
    assert res.pr_url == "https://github.com/owner/repo/pull/7"


def test_existing_pr_is_resolved_not_duplicated(monkeypatch):
    res = _call_with(
        monkeypatch, _happy_handler(pr_exists=True), _TARGET_REPO="owner/repo")
    assert res.ok is True
    assert res.pr_url == "https://github.com/owner/repo/pull/5"
