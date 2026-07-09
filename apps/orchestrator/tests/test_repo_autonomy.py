"""Tests for per-repo autonomy tiers (PR-4).

repo_autonomy.py is the "move the dial per repo" control. It mirrors the shipped
config.py::_hard_gate_classes() env-floor idiom + the fail-closed heal.py
validator shape. A repo not listed defaults to Tier C (advisory) — safe by
absence; deploying the image changes no repo's behavior.

Governance teeth (tightening-only, enforced at load AND runtime):
  * a repo may not be granted Tier A while it has a recent PHI/deny blocker
    (RepoTierUnlockError at load; forced escalation at runtime).

Run:
    source .venv/bin/activate
    python -m pytest apps/orchestrator/tests/test_repo_autonomy.py -q
"""
from __future__ import annotations

import textwrap

import pytest

from apps.orchestrator import repo_autonomy as ra


# --------------------------------------------------------------------------
# Absence = safe: unlisted repo is Tier C, deploying changes nothing
# --------------------------------------------------------------------------

def test_default_singleton_is_opt_in_not_auto_loaded(monkeypatch):
    """With no config file present, every repo resolves to Tier C."""
    monkeypatch.delenv("REPO_AUTONOMY_PATH", raising=False)
    policy = ra.load_repo_autonomy(path="/nonexistent/repo_autonomy.yaml")
    assert policy.tier_for("any-repo") == "C"
    assert policy.tier_for("delivery") == "C"
    assert policy.is_bootstrap is True


def test_candidate_paths_never_auto_discovers_example(monkeypatch):
    monkeypatch.delenv("REPO_AUTONOMY_PATH", raising=False)
    paths = ra._candidate_paths()
    assert all(".example" not in str(p) for p in paths)


# --------------------------------------------------------------------------
# Tier resolution from a real config
# --------------------------------------------------------------------------

def _write(tmp_path, body):
    p = tmp_path / "repo_autonomy.yaml"
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return str(p)


def test_explicit_tiers_resolve(tmp_path):
    path = _write(tmp_path, """
        repos:
          delivery-autonomous: {tier: A}
          delivery-reviewed: {tier: B}
          engine: {tier: C}
    """)
    policy = ra.load_repo_autonomy(path=path)
    assert policy.tier_for("delivery-autonomous") == "A"
    assert policy.tier_for("delivery-reviewed") == "B"
    assert policy.tier_for("engine") == "C"
    assert policy.tier_for("unlisted") == "C"  # fallback
    assert policy.is_bootstrap is False


# --------------------------------------------------------------------------
# Governance teeth: Tier A refused for a repo with recent PHI/deny history
# --------------------------------------------------------------------------

def test_tier_a_refused_at_load_for_phi_history(tmp_path):
    path = _write(tmp_path, """
        repos:
          risky: {tier: A, recent_phi_or_deny_blocker: true}
    """)
    with pytest.raises(ra.RepoTierUnlockError):
        ra.load_repo_autonomy(path=path)


def test_tier_a_allowed_when_history_clean(tmp_path):
    path = _write(tmp_path, """
        repos:
          clean: {tier: A, recent_phi_or_deny_blocker: false}
    """)
    policy = ra.load_repo_autonomy(path=path)
    assert policy.tier_for("clean") == "A"


def test_runtime_forces_escalation_when_phi_present_regardless_of_tier(tmp_path):
    """Even a Tier-A repo must escalate at runtime if the CURRENT change carries
    a PHI/deny blocker — the floor is enforced twice (load AND runtime)."""
    path = _write(tmp_path, """
        repos:
          clean: {tier: A}
    """)
    policy = ra.load_repo_autonomy(path=path)
    # effective_tier downgrades to escalation-forcing 'C' when phi present now
    assert policy.effective_tier("clean", has_phi_or_deny=True) == "C"
    assert policy.effective_tier("clean", has_phi_or_deny=False) == "A"


# --------------------------------------------------------------------------
# Fail closed on malformed config (never silently permissive)
# --------------------------------------------------------------------------

def test_malformed_yaml_falls_back_to_bootstrap_not_permissive(tmp_path):
    p = tmp_path / "repo_autonomy.yaml"
    p.write_text("repos: [ this is: broken", encoding="utf-8")
    policy = ra.load_repo_autonomy(path=str(p))
    # A malformed file degrades to bootstrap (all Tier C), logged — never a
    # half-applied permissive policy.
    assert policy.is_bootstrap is True
    assert policy.tier_for("anything") == "C"


def test_invalid_tier_value_rejected(tmp_path):
    path = _write(tmp_path, """
        repos:
          weird: {tier: SUPER}
    """)
    with pytest.raises(ra.RepoTierUnlockError):
        ra.load_repo_autonomy(path=path)


# --------------------------------------------------------------------------
# reload for tests + endpoint
# --------------------------------------------------------------------------

def test_reload_repo_autonomy_rereads(tmp_path, monkeypatch):
    path = _write(tmp_path, "repos:\n  a: {tier: B}\n")
    monkeypatch.setenv("REPO_AUTONOMY_PATH", path)
    policy = ra.reload_repo_autonomy()
    assert policy.tier_for("a") == "B"


def test_posture_summary_lists_tiers_and_why_capped(tmp_path):
    path = _write(tmp_path, """
        repos:
          clean: {tier: A}
          held: {tier: B, recent_phi_or_deny_blocker: true, note: "PHI seen 30d"}
    """)
    policy = ra.load_repo_autonomy(path=path)
    summary = policy.posture_summary()
    assert summary["bootstrap"] is False
    repos = {r["repo"]: r for r in summary["repos"]}
    assert repos["clean"]["tier"] == "A"
    assert repos["held"]["tier"] == "B"
