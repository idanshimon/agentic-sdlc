"""Endpoint tests for the integrations plane.

Spec: openspec/changes/add-enterprise-integrations-plane/specs/integrations-plane/spec.md
Covers the endpoint-level requirements: status honesty, aggregate agreement,
section-failure isolation, and the no-credential-in-any-response guarantee.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.orchestrator import integrations as I
from apps.orchestrator import main as M

SECRET = "ghp_FAKE_ENDPOINT_TEST_TOKEN_abcdef123456"

REGISTRY = """
integrations:
  - id: code-host
    kind: code_host
    provider: github
    base_url: https://api.github.com
    identity: delivery-bot
    scopes: [repo]
    token_env: TEST_EP_GH_TOKEN
    target_repo: acme/platform
  - id: planning
    kind: planning_tracker
    provider: aha
    base_url: https://example.example/api/v1
    token_env: TEST_EP_PLANNING_TOKEN
    item_url_template: https://example.example/features/{ref}
"""


@pytest.fixture
def client():
    return TestClient(M.app)


@pytest.fixture
def loaded_registry(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("TEST_EP_GH_TOKEN", SECRET)
    monkeypatch.setenv("TEST_EP_PLANNING_TOKEN", SECRET)
    p = tmp_path / "integrations.yaml"
    p.write_text(REGISTRY)
    reg = I.load_integrations(str(p))
    monkeypatch.setattr(I, "INTEGRATIONS", reg)
    M._integration_probe_results.clear()
    return reg


# --- GET /api/integrations ----------------------------------------------------

def test_unconfigured_registry_returns_empty_not_error(client, monkeypatch):
    monkeypatch.setattr(I, "INTEGRATIONS", I.IntegrationsRegistry())
    resp = client.get("/api/integrations")
    assert resp.status_code == 200
    body = resp.json()
    assert body["loaded"] is False
    assert body["integrations"] == []


def test_declared_integration_reads_configured_not_verified(client, loaded_registry):
    body = client.get("/api/integrations").json()
    entry = next(i for i in body["integrations"] if i["id"] == "code-host")
    assert entry["status"] == "configured"
    assert entry["verified"] is False


def test_no_credential_appears_in_the_listing(client, loaded_registry):
    raw = client.get("/api/integrations").text
    assert SECRET not in raw
    assert "TEST_EP_GH_TOKEN" in raw  # the env var NAME is safe to show


def test_rejected_entries_are_surfaced_not_hidden(client, tmp_path, monkeypatch):
    p = tmp_path / "integrations.yaml"
    p.write_text("""
integrations:
  - id: bad
    kind: planning_tracker
    provider: notreal
    token_env: X
""")
    monkeypatch.setattr(I, "INTEGRATIONS", I.load_integrations(str(p)))
    body = client.get("/api/integrations").json()
    assert body["rejected"]
    assert "notreal" in body["rejected"][0]["reason"]


# --- POST /api/integrations/{id}/test ----------------------------------------

def test_probe_of_unknown_integration_is_404(client, loaded_registry):
    assert client.post("/api/integrations/nope/test").status_code == 404


def test_probe_result_is_recorded_and_folded_into_the_listing(client, loaded_registry, monkeypatch):
    async def fake_probe(_integration):
        from apps.orchestrator.planning_providers import ProbeResult
        return ProbeResult("verified", "reachable", "delivery-bot")

    monkeypatch.setattr("apps.orchestrator.planning_providers.probe_integration", fake_probe)
    resp = client.post("/api/integrations/code-host/test")
    assert resp.status_code == 200
    assert resp.json()["status"] == "verified"

    entry = next(
        i for i in client.get("/api/integrations").json()["integrations"]
        if i["id"] == "code-host"
    )
    assert entry["status"] == "verified"
    assert entry["verified"] is True


def test_failing_probe_surfaces_failure_without_credential(client, loaded_registry, monkeypatch):
    async def fake_probe(_integration):
        from apps.orchestrator.planning_providers import ProbeResult
        return ProbeResult("failing", "authentication rejected (HTTP 401)")

    monkeypatch.setattr("apps.orchestrator.planning_providers.probe_integration", fake_probe)
    resp = client.post("/api/integrations/code-host/test")
    body = resp.json()
    assert body["status"] == "failing"
    assert "401" in body["reason"]
    assert SECRET not in resp.text


def test_unimplemented_probe_returns_unknown_never_verified(client, loaded_registry, monkeypatch):
    async def fake_probe(_integration):
        from apps.orchestrator.planning_providers import ProbeResult
        return ProbeResult("unknown", "no reachability probe implemented")

    monkeypatch.setattr("apps.orchestrator.planning_providers.probe_integration", fake_probe)
    body = client.post("/api/integrations/planning/test").json()
    assert body["status"] == "unknown"

    entry = next(
        i for i in client.get("/api/integrations").json()["integrations"]
        if i["id"] == "planning"
    )
    assert entry["verified"] is False


# --- GET /api/config/settings -------------------------------------------------

def test_settings_returns_every_section_with_activation_and_editability(client, loaded_registry):
    body = client.get("/api/config/settings").json()
    names = {s["section"] for s in body["sections"]}
    assert {
        "organization", "integrations", "autonomy", "models",
        "standards_pins", "repo_autonomy", "governance",
    } <= names
    for section in body["sections"]:
        assert section["activation"] in ("activated", "bootstrap", "unknown")
        assert section["editable"] in ("editable_here", "governed_pr_only")


def test_governance_section_is_governed_pr_only_and_states_the_floor(client):
    body = client.get("/api/config/settings").json()
    gov = next(s for s in body["sections"] if s["section"] == "governance")
    assert gov["editable"] == "governed_pr_only"
    assert "phi-classification" in gov["floor"]
    assert "standards-change PR" in gov["explainer"]


def test_settings_integrations_section_agrees_with_the_individual_endpoint(client, loaded_registry):
    listing = client.get("/api/integrations").json()
    settings = client.get("/api/config/settings").json()
    section = next(s for s in settings["sections"] if s["section"] == "integrations")
    assert [i["id"] for i in section["integrations"]] == [
        i["id"] for i in listing["integrations"]
    ]


def test_one_failing_section_does_not_blank_the_whole_read(client, monkeypatch):
    """A broken loader must be a visible finding, not a silently missing section."""
    class Boom:
        @property
        def loaded(self):
            raise RuntimeError("loader exploded")

    monkeypatch.setattr("apps.orchestrator.model_policy.MODEL_POLICY", Boom())
    body = client.get("/api/config/settings").json()
    models = next(s for s in body["sections"] if s["section"] == "models")
    assert models["status"] == "error"
    assert "loader exploded" in models["error"]
    # the rest still rendered
    gov = next(s for s in body["sections"] if s["section"] == "governance")
    assert gov["status"] == "ok"


def test_settings_contains_no_credential_material(client, loaded_registry):
    assert SECRET not in client.get("/api/config/settings").text
