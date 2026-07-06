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
    # Path-construction test: point at a NEW (non-existent) bundle version so
    # there is no existing rules.yaml to protect — governance validation is
    # skipped for a brand-new bundle, leaving this a pure routing/path check.
    r = client.post("/api/config/bundles/save", json={
        "dept": "security", "version": "v9.9.9", "file": "rules.yaml",
        "content": "rules: []\n", "commit_message": "seed new bundle version",
    })
    assert r.status_code == 200, r.text
    assert r.json()["path"] == "standards-bundles/security/v9.9.9/rules.yaml"


def test_save_bundle_weakening_phi_rule_is_refused():
    """Governance teeth: an edit to an EXISTING bundle that deletes/unlocks a
    phi_locked rule is refused (HTTP 409) BEFORE any PR is opened — even in
    dry-run. `rules: []` wipes the shipped PHI-001..PHI-005 locked rules."""
    r = client.post("/api/config/bundles/save", json={
        "dept": "security", "version": "v0.1.0", "file": "rules.yaml",
        "content": "rules: []\n", "commit_message": "relax PHI rules",
    })
    assert r.status_code == 409, r.text
    assert "PHI" in r.text  # cites the offending locked rule


def test_save_bundle_non_rules_file_skips_lock_validation():
    """envelope.yaml / reviewers.yaml carry no rules — lock validation is
    scoped to rules.yaml, so these still route normally."""
    r = client.post("/api/config/bundles/save", json={
        "dept": "security", "version": "v0.1.0", "file": "envelope.yaml",
        "content": "allowed_auto_fixes: []\n", "commit_message": "tune envelope",
    })
    assert r.status_code == 200, r.text
    assert r.json()["path"] == "standards-bundles/security/v0.1.0/envelope.yaml"


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
