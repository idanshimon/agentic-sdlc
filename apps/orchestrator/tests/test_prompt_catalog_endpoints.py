"""Phase 3: prompt catalog endpoints — list + detail.

Surfaces the orchestrator's lazy-loaded PromptCatalog over HTTP for the
UI tree-browse + version-detail pages, plus the future PR editor.
"""
from __future__ import annotations
import os, shutil
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from orchestrator import main as om
from orchestrator import _pipeline_stages as ps


@pytest.fixture
def fresh_prompts_root(tmp_path, monkeypatch):
    """Point the lazy catalog at a tmp prompts/ dir so tests don't depend
    on the real production prompts in the repo."""
    # Mirror the real production layout: prompts/global/<stage>/v1.yaml
    src = Path(__file__).resolve().parent.parent.parent.parent / "prompts"
    dst = tmp_path / "prompts"
    shutil.copytree(src, dst)
    monkeypatch.setenv("PROMPTS_ROOT", str(dst))
    ps.reset_prompt_catalog()  # force re-read from the new root
    yield dst
    ps.reset_prompt_catalog()


def _client() -> TestClient:
    return TestClient(om.app)


def test_catalog_list_returns_all_prompts(fresh_prompts_root):
    """GET /api/prompts/catalog returns flat + by_persona + by_stage."""
    r = _client().get("/api/prompts/catalog")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["count"] >= 6  # the 6 we shipped in Phase 2
    assert "prompts" in body
    assert "by_persona" in body
    assert "by_stage" in body

    # Spot-check shape
    first = body["prompts"][0]
    for required in ("prompt_id", "version", "stage", "scope", "owner_persona",
                     "status", "git_sha", "template_chars", "template_first_line"):
        assert required in first, f"missing {required} in {first}"

    # Templates not returned in flat list (avoid 50KB+ payloads)
    assert "template" not in first

    # Personas should include the ones we have YAMLs for
    personas = set(body["by_persona"].keys())
    assert {"pm", "architect", "qa", "sre", "seceng"}.issubset(personas)


def test_catalog_get_one_prompt_returns_full_template(fresh_prompts_root):
    """GET /api/prompts/assessor-global returns full template + version list."""
    r = _client().get("/api/prompts/assessor-global")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["prompt_id"] == "assessor-global"
    assert body["version"] == "v1"
    assert body["scope"] == "global"
    assert body["owner_persona"] == "pm"
    assert body["template"].startswith("You are the Assessor")
    assert len(body["template"]) > 800  # the real production assessor prompt is ~1831 chars
    assert body["versions"] == [{"version": "v1", "status": "published",
                                  "effective_from": "2026-06-16T00:00:00Z"}]


def test_catalog_get_unknown_prompt_returns_404(fresh_prompts_root):
    r = _client().get("/api/prompts/nope-does-not-exist")
    assert r.status_code == 404
    assert "not found" in r.json()["detail"]


def test_catalog_get_specific_version(fresh_prompts_root):
    """When ?version=v1 is passed, that exact version is returned."""
    r = _client().get("/api/prompts/assessor-global?version=v1")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "v1"


def test_catalog_get_unknown_version_returns_404(fresh_prompts_root):
    r = _client().get("/api/prompts/assessor-global?version=v99")
    assert r.status_code == 404
