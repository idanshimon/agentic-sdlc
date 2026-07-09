"""Phase 1 org-model tests — configuration-plane identity spine.

Covers the openspec spec scenarios (add-configuration-plane):
  - decision attributed to a configured team (cost_center + m365_group resolve)
  - unknown team is REJECTED, not silently anonymized (once a model is loaded)
  - bootstrap mode (no org.yaml) stays permissive so a fresh deploy still runs
  - the shipped neutral config/org.yaml parses and contains the demo teams
"""
from __future__ import annotations

from pathlib import Path

import pytest

from apps.orchestrator import org_model as om


def _write(tmp_path, text: str) -> str:
    p = tmp_path / "org.yaml"
    p.write_text(text)
    return str(p)


NEUTRAL = """
identity:
  entra_tenant_id: "11111111-1111-1111-1111-111111111111"
  approver_rbac:
    resolver_gate_approve: ["role:engineering-lead"]
departments:
  - id: clinical-platform
    name: Clinical Platform Engineering
    owner: "lead@x.example"
    reviewer_roster:
      security: "sec@x.example"
teams:
  - id: cardiology
    name: Cardiology Engineering
    department: clinical-platform
    cost_center: "CC-4200-CARD"
    m365_group: "grp-cardiology@x.example"
"""


def test_decision_attributed_to_configured_team(tmp_path):
    model = om.load_org_model(_write(tmp_path, NEUTRAL))
    assert model.loaded is True
    t = model.resolve_team("cardiology")
    assert t.cost_center == "CC-4200-CARD"
    assert t.m365_group == "grp-cardiology@x.example"
    assert t.department == "clinical-platform"
    # identity + reviewer roster parsed
    assert model.entra_tenant_id == "11111111-1111-1111-1111-111111111111"
    assert model.departments["clinical-platform"].reviewer_roster["security"] == "sec@x.example"
    assert model.approver_rbac["resolver_gate_approve"] == ["role:engineering-lead"]


def test_unknown_team_is_rejected_not_anonymized(tmp_path):
    model = om.load_org_model(_write(tmp_path, NEUTRAL))
    with pytest.raises(om.UnknownTeamError) as ei:
        model.resolve_team("ghost-team")
    assert "ghost-team" in str(ei.value)
    assert "cardiology" in str(ei.value)  # lists known teams


def test_bootstrap_mode_is_permissive_when_no_file(tmp_path):
    # point at a non-existent path -> unloaded model, permissive
    model = om.load_org_model(str(tmp_path / "does-not-exist.yaml"))
    assert model.loaded is False
    # resolves ANY team as a synthesized placeholder so the pipeline still runs
    t = model.resolve_team("whatever")
    assert t.id == "whatever"
    assert t.department == "(unassigned)"


def test_shipped_neutral_config_parses():
    repo_root = Path(__file__).resolve().parents[3]
    org_path = repo_root / "config" / "org.yaml.example"
    assert org_path.exists(), f"expected shipped neutral template at {org_path}"
    model = om.load_org_model(str(org_path))
    assert model.loaded is True
    # the three demo teams from the neutral topology
    for team_id in ("cardiology", "interop", "platform-core"):
        t = model.resolve_team(team_id)
        assert t.cost_center.startswith("CC-")
        assert "@" in t.m365_group
    # neutral placeholder tenant, no real customer identifiers
    assert model.entra_tenant_id == "00000000-0000-0000-0000-000000000000"


def test_malformed_yaml_falls_back_to_bootstrap(tmp_path):
    bad = _write(tmp_path, "identity: [this is: not valid mapping\n  teams:::")
    model = om.load_org_model(bad)
    # bad YAML must NOT brick boot — degrade to permissive bootstrap
    assert model.loaded is False


def test_reload_swaps_singleton(tmp_path):
    om.reload_org_model(str(tmp_path / "none.yaml"))
    assert om.ORG_MODEL.loaded is False
    om.reload_org_model(_write(tmp_path, NEUTRAL))
    assert om.ORG_MODEL.loaded is True
    assert "cardiology" in om.ORG_MODEL.teams
