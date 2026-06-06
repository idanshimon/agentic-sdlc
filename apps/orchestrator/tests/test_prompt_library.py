"""Tests for the Prompt Library catalog + endpoint.

Covers Kapil's Phase 1 ask: a per-stage / per-model prompt registry that
APIM circuit-breaker failover can consult. We test the public contract:
catalog shape, per-model variants, compat notes, unknown stages, fallback.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from apps.orchestrator import prompt_library as pl
from apps.orchestrator.main import app


client = TestClient(app)


# ── catalog endpoint ────────────────────────────────────────────────────────
def test_catalog_endpoint_returns_all_stages() -> None:
    r = client.get("/api/prompt-library")
    assert r.status_code == 200
    body = r.json()
    assert "stages" in body
    names = {s["stage_name"] for s in body["stages"]}
    assert names == {
        "ingest", "assessor", "architect",
        "test_plan", "codegen", "review_scan",
    }


def test_catalog_has_per_model_variants() -> None:
    """Each stage MUST list >=3 model variants — registry shape is the contract."""
    r = client.get("/api/prompt-library")
    body = r.json()
    for stage in body["stages"]:
        models = [p["model"] for p in stage["providers"]]
        assert len(models) >= 3, f"stage {stage['stage_name']} has only {models}"
        # GPT, Claude, Databricks-Claude families all present
        assert any(m.startswith("gpt-") for m in models)
        assert any(m.startswith("claude-") for m in models)
        assert any(m.startswith("databricks-") for m in models)


def test_catalog_template_preview_is_capped() -> None:
    r = client.get("/api/prompt-library")
    body = r.json()
    for stage in body["stages"]:
        for p in stage["providers"]:
            assert len(p["template_preview"]) <= 200
            assert p["prompt_version"] == "v1"
            assert p["model_compat_notes"]
            assert p["provider"] in {
                "openai-apim", "anthropic", "databricks", "google", "unknown",
            }


# ── lookup endpoint ─────────────────────────────────────────────────────────
def test_get_prompt_returns_compat_notes() -> None:
    r = client.get("/api/prompt-library/architect", params={"model": "gpt-4-1"})
    assert r.status_code == 200
    body = r.json()
    assert body["stage"] == "architect"
    assert body["model"] == "gpt-4-1"
    assert body["version"] == "v1"
    assert "OpenAI" in body["model_compat_notes"]
    assert "Architect agent" in body["template"]
    assert body["fallback"] is False


def test_get_prompt_unknown_model_falls_back() -> None:
    r = client.get(
        "/api/prompt-library/codegen", params={"model": "some-bogus-model"},
    )
    assert r.status_code == 200
    body = r.json()
    # Did not 500 — fell back to first registered variant + flagged it
    assert body["fallback"] is True
    assert body["model"] != "some-bogus-model"
    assert body["template"]


def test_unknown_stage_returns_404() -> None:
    r = client.get("/api/prompt-library/nonexistent-stage")
    assert r.status_code == 404
    assert "Unknown stage" in r.json()["detail"]


# ── module-level helpers ────────────────────────────────────────────────────
def test_list_stages_matches_pipeline_graph() -> None:
    """Catalog stages MUST track the canonical pipeline graph (design.md §2)."""
    assert pl.list_stages() == [
        "ingest", "assessor", "architect",
        "test_plan", "codegen", "review_scan",
    ]


def test_get_prompt_no_model_returns_default_variant() -> None:
    out = pl.get_prompt("assessor")
    assert out["stage"] == "assessor"
    assert out["fallback"] is False  # None requested, not a miss
    assert out["template"].startswith("You are the Assessor agent")


# ── viewer-modal endpoint contract ──────────────────────────────────────────
def test_single_variant_endpoint_returns_full_template() -> None:
    """Viewer modal must receive the FULL template, not the 200-char preview."""
    r = client.get(
        "/api/prompt-library/assessor", params={"model": "gpt-4-1"},
    )
    assert r.status_code == 200
    body = r.json()
    # Full Assessor prompt is well over 200 chars and contains a marker only
    # present past the truncation point (the JSON-shape guidance).
    assert len(body["template"]) > 200
    assert "blast_usd" in body["template"]
    assert body["fallback"] is False


def test_missing_model_returns_404() -> None:
    """strict=true: unknown model 404s instead of silently falling back."""
    r = client.get(
        "/api/prompt-library/codegen",
        params={"model": "no-such-model", "strict": "true"},
    )
    assert r.status_code == 404
    assert "no-such-model" in r.json()["detail"]


def test_failover_lookup_pattern() -> None:
    """The exact lookup the APIM circuit breaker would make on Gemini → GPT failover."""
    gemini = pl.get_prompt("codegen", "gemini-2-5-pro")
    gpt = pl.get_prompt("codegen", "gpt-4-1")
    assert gemini["template"] == gpt["template"]  # v1 — same content, different compat
    assert "Gemini" in gemini["model_compat_notes"]
    assert "OpenAI" in gpt["model_compat_notes"]
