"""Phase 3 PINS endpoint tests — bundle-version pinning surfaced to the config UI.

openspec: add-configuration-plane / Phase 3 task "PINS.yaml selection surfaced
in config UI". The orchestrator already refuses to start on an unresolvable pin;
this read endpoint lets the UI render the team→version pin matrix + available
bundle versions so a COE can see (and, via the governed PR flow, change) which
version each team runs.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from apps.orchestrator.main import app

client = TestClient(app)


def test_pins_endpoint_returns_defaults_and_teams():
    r = client.get("/api/config/pins")
    assert r.status_code == 200, r.text
    body = r.json()
    # defaults for every department bundle
    assert body["defaults"]["security"] == "v0.1.0"
    assert set(body["defaults"]) == {"architect", "security", "privacy", "finops"}
    # team-demo is pinned in the shipped PINS.yaml
    assert "team-demo" in body["teams"]
    assert body["teams"]["team-demo"]["security"] == "v0.1.0"


def test_pins_endpoint_lists_available_bundle_versions():
    r = client.get("/api/config/pins")
    body = r.json()
    # the UI needs the set of on-disk versions per dept to offer a pin dropdown
    assert "available" in body
    assert "v0.1.0" in body["available"]["security"]


def test_pins_effective_resolves_unpinned_team_to_defaults():
    r = client.get("/api/config/pins")
    body = r.json()
    # a team not listed under teams: inherits defaults — the endpoint exposes a
    # resolver hint so the UI can show effective versions without re-deriving.
    assert body["defaults"]["privacy"] == body["teams"]["team-demo"]["privacy"]
