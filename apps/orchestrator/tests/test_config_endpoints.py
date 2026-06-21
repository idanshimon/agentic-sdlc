"""Endpoint tests for the editing-plane save routes (#3).

Runs in dry-run mode (CONFIG_WRITE_DRY_RUN) so no git/gh is invoked — verifies
routing, request validation, path construction, and the governance boundary
(bundle save is accepted; path-injection is refused).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from apps.orchestrator import config_writer as cw
from apps.orchestrator.main import app


@pytest.fixture(autouse=True)
def _dry_run(monkeypatch):
    # Force dry-run so the endpoints never shell git/gh in tests.
    monkeypatch.setattr(cw, "_DRY_RUN", True)


client = TestClient(app)


def test_save_agent_dry_run_opens_no_pr_but_validates():
    r = client.post("/api/config/agents/save", json={
        "name": "architect",
        "content": "---\nname: architect\n---\n# edited",
        "commit_message": "tighten architect role",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["dry_run"] is True
    assert body["path"] == ".github/agents/architect.agent.md"
    assert body["pr_url"] is None


def test_save_bundle_dry_run_path():
    r = client.post("/api/config/bundles/save", json={
        "dept": "security", "version": "v0.1.0", "file": "rules.yaml",
        "content": "rules: []\n", "commit_message": "relax rule X",
    })
    assert r.status_code == 200, r.text
    assert r.json()["path"] == "standards-bundles/security/v0.1.0/rules.yaml"


def test_save_prompt_global_path():
    r = client.post("/api/config/prompts/save", json={
        "scope": "global", "stage": "architect", "version": "v2",
        "content": "prompt_id: architect-global\n", "commit_message": "new architect prompt",
    })
    assert r.status_code == 200, r.text
    assert r.json()["path"] == "prompts/global/architect/v2.yaml"


def test_save_prompt_persona_requires_persona():
    r = client.post("/api/config/prompts/save", json={
        "scope": "persona", "stage": "architect", "version": "v2",
        "content": "x", "commit_message": "y",
    })
    assert r.status_code == 400  # persona required


def test_save_prompt_persona_path():
    r = client.post("/api/config/prompts/save", json={
        "scope": "persona", "stage": "architect", "version": "v2", "persona": "qa",
        "content": "x", "commit_message": "y",
    })
    assert r.status_code == 200, r.text
    assert r.json()["path"] == "prompts/persona/qa/architect/v2.yaml"


def test_path_injection_in_agent_name_refused():
    r = client.post("/api/config/agents/save", json={
        "name": "../../apps/orchestrator/main",
        "content": "x", "commit_message": "y",
    })
    assert r.status_code == 400  # _safe_seg rejects '..' and '/'


def test_path_injection_in_bundle_dept_refused():
    r = client.post("/api/config/bundles/save", json={
        "dept": "../../etc", "version": "v0.1.0",
        "content": "x", "commit_message": "y",
    })
    assert r.status_code == 400


def test_reload_endpoint():
    r = client.post("/api/config/reload")
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True
    assert "agent_bundles" in r.json()["reloaded"]
