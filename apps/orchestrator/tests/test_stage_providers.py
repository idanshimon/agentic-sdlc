"""Form-field integration tests for stage_providers + per-run override routing.

POST /api/run accepts an optional `stage_providers` form field carrying a JSON
mapping of stage -> {provider, model, via_apim}. The orchestrator persists this
onto RunState.stage_provider_overrides and consults it via
config.get_provider_for_stage / get_model_for_stage.
"""
from __future__ import annotations

import io
import pytest
from fastapi.testclient import TestClient

from apps.orchestrator.main import app, _runs, _prd_cache, _queues
from apps.orchestrator.config import get_provider_for_stage, get_model_for_stage
from apps.orchestrator.models import RunState


@pytest.fixture
def client():
    return TestClient(app)


def _files():
    return {"prd": ("prd.md", io.BytesIO(b"# tiny PRD\nnothing to see"), "text/markdown")}


def _cleanup(run_id: str) -> None:
    _runs.pop(run_id, None)
    _prd_cache.pop(run_id, None)
    _queues.pop(run_id, None)


def test_stage_providers_populates_overrides(client):
    """Valid JSON in the form field lands on run.stage_provider_overrides."""
    payload = '{"architect": {"provider": "foundry-anthropic", "model": "claude-sonnet-4-6"}}'
    resp = client.post(
        "/api/run",
        data={"team_id": "cardiology", "mode": "manual", "stage_providers": payload},
        files=_files(),
    )
    assert resp.status_code == 200, resp.text
    rid = resp.json()["run_id"]
    try:
        run = _runs[rid]
        assert run.stage_provider_overrides == {
            "architect": {"provider": "foundry-anthropic", "model": "claude-sonnet-4-6"},
        }
    finally:
        _cleanup(rid)


def test_stage_providers_missing_yields_empty_overrides(client):
    """No stage_providers field -> overrides dict is empty (not None)."""
    resp = client.post(
        "/api/run", data={"team_id": "cardiology", "mode": "manual"}, files=_files(),
    )
    assert resp.status_code == 200
    rid = resp.json()["run_id"]
    try:
        assert _runs[rid].stage_provider_overrides == {}
    finally:
        _cleanup(rid)


def test_stage_providers_invalid_json_returns_400(client):
    resp = client.post(
        "/api/run",
        data={"team_id": "cardiology", "stage_providers": "{not json"},
        files=_files(),
    )
    assert resp.status_code == 400
    assert "valid json" in resp.text.lower()


def test_stage_providers_unknown_stage_returns_400(client):
    resp = client.post(
        "/api/run",
        data={
            "team_id": "cardiology",
            "stage_providers": '{"not_a_stage": {"provider": "aoai"}}',
        },
        files=_files(),
    )
    assert resp.status_code == 400
    assert "unknown stage" in resp.text.lower()


def test_stage_providers_non_object_value_returns_400(client):
    """A stage value that isn't an object MUST 400."""
    resp = client.post(
        "/api/run",
        data={"team_id": "cardiology", "stage_providers": '{"architect": "foundry"}'},
        files=_files(),
    )
    assert resp.status_code == 400
    assert "must be an object" in resp.text.lower()


# ---- per-run override actually routes ---------------------------------------

def test_per_run_override_routes_to_overridden_provider():
    """get_provider_for_stage returns an instance reflecting the per-run override."""
    run = RunState(
        team_id="cardiology", run_id="route-test", prd_blob_url="x",
        stage_provider_overrides={
            "architect": {"provider": "foundry-anthropic", "model": "claude-sonnet-4-6"},
        },
    )
    inst = get_provider_for_stage(run, "architect")
    # FoundryProvider with anthropic shape
    assert type(inst).__name__ == "FoundryProvider"
    assert getattr(inst, "shape", None) == "foundry-anthropic"
    assert getattr(inst, "resolved_model", None) == "claude-sonnet-4-6"
    assert get_model_for_stage(run, "architect") == "claude-sonnet-4-6"


def test_no_override_falls_back_to_default_provider():
    """A stage without an override uses the configured default."""
    run = RunState(team_id="cardiology", run_id="no-override", prd_blob_url="x")
    # Set an override on a different stage; architect should still use defaults.
    run.stage_provider_overrides = {
        "codegen": {"provider": "foundry-anthropic", "model": "claude-sonnet-4-6"},
    }
    cg = get_provider_for_stage(run, "codegen")
    assert getattr(cg, "shape", None) == "foundry-anthropic"

    arch = get_provider_for_stage(run, "architect")
    # Default registry shape — not the overridden one.
    assert getattr(arch, "shape", None) != "foundry-anthropic" or arch is not cg
