"""Phase 2 autonomy-matrix tests — configuration-plane steering wheel.

Covers the openspec spec scenarios (add-configuration-plane):
  - PHI classes cannot be configured open (invariant hard-lock)
  - autopilot honors the configured threshold
  - autopilot_always auto-resolves
  - gate tightens a class
  - bootstrap (no file) preserves legacy mode-driven behaviour
  - the shipped neutral config/autonomy.yaml parses and is invariant-safe
"""
from __future__ import annotations

from pathlib import Path

import pytest

from apps.orchestrator import autonomy as au


def _write(tmp_path, text: str) -> str:
    p = tmp_path / "autonomy.yaml"
    p.write_text(text)
    return str(p)


GOOD = """
teams:
  "*":
    naming-convention: autopilot_always
    identifier-format: { mode: autopilot_above_threshold, threshold: 0.8 }
    scope-resolution: gate
  cardiology:
    sla-binding: { mode: autopilot_above_threshold, threshold: 0.75 }
"""


def test_invariant_class_cannot_be_configured_open(tmp_path):
    bad = """
teams:
  cardiology:
    phi-classification: autopilot_always
"""
    with pytest.raises(au.InvariantUnlockError) as ei:
        au.load_autonomy_matrix(_write(tmp_path, bad))
    assert "phi-classification" in str(ei.value)


def test_auth_policy_also_locked(tmp_path):
    bad = """
teams:
  "*":
    auth-policy: { mode: autopilot_above_threshold, threshold: 0.5 }
"""
    with pytest.raises(au.InvariantUnlockError):
        au.load_autonomy_matrix(_write(tmp_path, bad))


def test_invariant_always_gates_even_if_matrix_silent(tmp_path):
    m = au.load_autonomy_matrix(_write(tmp_path, GOOD))
    # matrix never mentions phi-classification, but rule_for still forces gate
    r = m.rule_for("cardiology", "phi-classification")
    assert r is not None and r.mode == "gate"
    r2 = m.rule_for("cardiology", "auth-policy")
    assert r2.mode == "gate"


def test_threshold_and_always_modes_parse(tmp_path):
    m = au.load_autonomy_matrix(_write(tmp_path, GOOD))
    # team-specific threshold wins
    r = m.rule_for("cardiology", "sla-binding")
    assert r.mode == "autopilot_above_threshold" and r.threshold == 0.75
    # default ("*") threshold applies to a team with no override
    r2 = m.rule_for("interop", "identifier-format")
    assert r2.mode == "autopilot_above_threshold" and r2.threshold == 0.8
    # autopilot_always parsed from bare string
    r3 = m.rule_for("interop", "naming-convention")
    assert r3.mode == "autopilot_always"


def test_gate_tightens_a_class(tmp_path):
    m = au.load_autonomy_matrix(_write(tmp_path, GOOD))
    r = m.rule_for("someteam", "scope-resolution")  # from "*" default
    assert r.mode == "gate"


def test_exact_team_rule_beats_default(tmp_path):
    text = """
teams:
  "*":
    sla-binding: gate
  cardiology:
    sla-binding: autopilot_always
"""
    m = au.load_autonomy_matrix(_write(tmp_path, text))
    assert m.rule_for("cardiology", "sla-binding").mode == "autopilot_always"
    assert m.rule_for("otherteam", "sla-binding").mode == "gate"


def test_bootstrap_when_no_file(tmp_path):
    m = au.load_autonomy_matrix(str(tmp_path / "nope.yaml"))
    assert m.loaded is False
    # unloaded -> rule_for returns None for non-invariants (caller falls back to mode)
    assert m.rule_for("cardiology", "sla-binding") is None
    # but invariants STILL gate even in bootstrap
    assert m.rule_for("cardiology", "phi-classification").mode == "gate"


def test_invalid_mode_rejected(tmp_path):
    bad = """
teams:
  cardiology:
    sla-binding: yolo-mode
"""
    with pytest.raises(ValueError):
        au.load_autonomy_matrix(_write(tmp_path, bad))


def test_shipped_neutral_config_parses_and_is_safe():
    repo_root = Path(__file__).resolve().parents[3]
    path = repo_root / "config" / "autonomy.yaml.example"
    assert path.exists(), f"expected shipped neutral template at {path}"
    # must not raise — proves the shipped config is invariant-safe
    m = au.load_autonomy_matrix(str(path))
    assert m.loaded is True
    # spot-check the documented neutral policy
    assert m.rule_for("cardiology", "sla-binding").mode == "autopilot_above_threshold"
    assert m.rule_for("interop", "identifier-format").mode == "gate"
    # invariants locked regardless
    assert m.rule_for("cardiology", "phi-classification").mode == "gate"


def test_reload_swaps_singleton(tmp_path):
    au.reload_autonomy_matrix(str(tmp_path / "none.yaml"))
    assert au.AUTONOMY_MATRIX.loaded is False
    au.reload_autonomy_matrix(_write(tmp_path, GOOD))
    assert au.AUTONOMY_MATRIX.loaded is True


def test_default_singleton_is_opt_in_not_auto_loaded(monkeypatch):
    """Posture A guarantee: with no AUTONOMY_PATH and no deploy-location file,
    a fresh load must stay in bootstrap — the repo config/ template is NEVER
    auto-discovered. Prevents the shipped neutral policy from silently gating."""
    monkeypatch.delenv("AUTONOMY_PATH", raising=False)
    # candidate paths must not include the repo config/ template dir
    for p in au._candidate_paths():
        assert "config/autonomy.yaml.example" not in str(p)
        assert not str(p).endswith("config/autonomy.yaml")
    # from a scratch cwd (no ./autonomy.yaml, no /app/autonomy.yaml) → bootstrap
    m = au.load_autonomy_matrix()
    assert m.loaded is False
