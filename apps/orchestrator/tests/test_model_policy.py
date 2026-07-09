"""Phase 4 model-policy tests — configuration-plane model governance.

openspec: add-configuration-plane / Requirement "model policy enforcement":
  - config/models.yaml (allowlist, denylist, phi_eligible, per-stage routing,
    cost_ceiling_usd) read + enforced at stage dispatch
  - a denied / non-allowlisted model blocks the stage (cited refusal)
  - a PHI-adjacent stage routing to a non-phi_eligible model is refused
  - opt-in: no models.yaml => bootstrap (permissive), nothing enforced
  - shipped models.yaml.example parses and is permissive-safe

RED first: apps/orchestrator/model_policy.py does not exist yet.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from apps.orchestrator import model_policy as mp


GOOD = """
allowlist:
  - gpt-4-1
  - gpt-4-1-mini
  - databricks-claude-sonnet-4-6
denylist:
  - gpt-3-5-turbo
phi_eligible:
  - gpt-4-1
  - databricks-claude-sonnet-4-6
routing:
  codegen: databricks-claude-sonnet-4-6
  assessor: gpt-4-1
cost_ceiling_usd:
  per_run: 5.0
  per_team_month: 500.0
phi_stages:
  - architect
  - codegen
  - review_scan
"""


def _write(tmp_path, text: str) -> str:
    p = tmp_path / "models.yaml"
    p.write_text(text)
    return str(p)


# ---- loading / bootstrap ----------------------------------------------------

def test_bootstrap_when_no_file(tmp_path):
    pol = mp.load_model_policy(str(tmp_path / "nope.yaml"))
    assert pol.loaded is False
    # permissive: everything allowed, no ceiling
    assert pol.check_model("codegen", "any-model", phi=False).allowed is True


def test_loads_allow_deny_phi_eligible(tmp_path):
    pol = mp.load_model_policy(_write(tmp_path, GOOD))
    assert pol.loaded is True
    assert "gpt-4-1" in pol.allowlist
    assert "gpt-3-5-turbo" in pol.denylist
    assert "gpt-4-1" in pol.phi_eligible
    assert pol.cost_ceiling_per_run == 5.0


# ---- enforcement: allow / deny ---------------------------------------------

def test_denylisted_model_is_blocked(tmp_path):
    pol = mp.load_model_policy(_write(tmp_path, GOOD))
    v = pol.check_model("assessor", "gpt-3-5-turbo", phi=False)
    assert v.allowed is False
    assert "denylist" in v.reason
    assert v.rule_ref.startswith("models/")


def test_non_allowlisted_model_is_blocked_when_allowlist_present(tmp_path):
    pol = mp.load_model_policy(_write(tmp_path, GOOD))
    v = pol.check_model("assessor", "some-random-model", phi=False)
    assert v.allowed is False
    assert "allowlist" in v.reason


def test_allowlisted_model_passes(tmp_path):
    pol = mp.load_model_policy(_write(tmp_path, GOOD))
    v = pol.check_model("assessor", "gpt-4-1", phi=False)
    assert v.allowed is True


# ---- enforcement: PHI eligibility ------------------------------------------

def test_phi_stage_requires_phi_eligible_model(tmp_path):
    pol = mp.load_model_policy(_write(tmp_path, GOOD))
    # gpt-4-1-mini is allowlisted but NOT phi_eligible; codegen is a phi stage
    v = pol.check_model("codegen", "gpt-4-1-mini", phi=True)
    assert v.allowed is False
    assert "phi_eligible" in v.reason


def test_phi_eligible_model_passes_on_phi_stage(tmp_path):
    pol = mp.load_model_policy(_write(tmp_path, GOOD))
    v = pol.check_model("codegen", "gpt-4-1", phi=True)
    assert v.allowed is True


def test_non_phi_stage_ignores_phi_eligibility(tmp_path):
    pol = mp.load_model_policy(_write(tmp_path, GOOD))
    # gpt-4-1-mini not phi_eligible, but assessor isn't a phi stage → fine
    v = pol.check_model("assessor", "gpt-4-1-mini", phi=False)
    assert v.allowed is True


# ---- cost ceiling -----------------------------------------------------------

def test_run_cost_ceiling_enforced(tmp_path):
    pol = mp.load_model_policy(_write(tmp_path, GOOD))
    # projected run cost already over the per_run ceiling
    v = pol.check_cost(run_cost_so_far=5.5)
    assert v.allowed is False
    assert "per_run" in v.reason


def test_run_cost_under_ceiling_passes(tmp_path):
    pol = mp.load_model_policy(_write(tmp_path, GOOD))
    assert pol.check_cost(run_cost_so_far=1.0).allowed is True


def test_no_ceiling_when_unset(tmp_path):
    pol = mp.load_model_policy(_write(tmp_path, "allowlist: [gpt-4-1]\n"))
    assert pol.check_cost(run_cost_so_far=1e9).allowed is True


# ---- opt-in guarantee -------------------------------------------------------

def test_default_singleton_is_opt_in_not_auto_loaded(monkeypatch):
    monkeypatch.delenv("MODELS_PATH", raising=False)
    for p in mp._candidate_paths():
        assert "config/models.yaml.example" not in str(p)
        assert not str(p).endswith("config/models.yaml")
    pol = mp.load_model_policy()
    assert pol.loaded is False


# ---- shipped template -------------------------------------------------------

def test_shipped_models_example_parses(tmp_path):
    repo_root = Path(__file__).resolve().parents[3]
    path = repo_root / "config" / "models.yaml.example"
    assert path.exists(), f"expected shipped template at {path}"
    pol = mp.load_model_policy(str(path))
    assert pol.loaded is True
