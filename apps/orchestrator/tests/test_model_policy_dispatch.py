"""Phase 4 dispatch-enforcement tests — model policy blocks a stage at _call.

openspec scenario "denied model blocks the stage" + "PHI-adjacent stage requires
a cleared model": the enforcement runs at the single stage-dispatch chokepoint
(_pipeline_stages._call). A refused model raises ModelPolicyRefusal carrying the
rule_ref, which the orchestrator turns into a gated/failed run with a ledger
entry citing the rule — never a silent run on a forbidden model.

We test the pure enforcement helper directly (deterministic, no LLM) rather than
driving a whole run, per TDD "test behavior not plumbing".
"""
from __future__ import annotations

import pytest

from apps.orchestrator import _pipeline_stages as ps
from apps.orchestrator import model_policy as mp


DENY = """
allowlist: [gpt-4-1, databricks-claude-sonnet-4-6]
phi_eligible: [gpt-4-1]
phi_stages: [codegen]
"""


def _policy(tmp_path, text):
    p = tmp_path / "models.yaml"
    p.write_text(text)
    return mp.load_model_policy(str(p))


def test_enforce_passes_allowlisted_non_phi(tmp_path):
    pol = _policy(tmp_path, DENY)
    # returns None (no raise) when allowed
    ps.enforce_model_policy("assessor", "gpt-4-1", phi=False, policy=pol)


def test_enforce_raises_on_non_allowlisted(tmp_path):
    pol = _policy(tmp_path, DENY)
    with pytest.raises(ps.ModelPolicyRefusal) as ei:
        ps.enforce_model_policy("assessor", "random-model", phi=False, policy=pol)
    assert ei.value.rule_ref.startswith("models/allowlist/")
    assert "allowlist" in str(ei.value)


def test_enforce_raises_on_phi_stage_non_eligible(tmp_path):
    pol = _policy(tmp_path, DENY)
    # sonnet is allowlisted but not phi_eligible; codegen is a phi stage
    with pytest.raises(ps.ModelPolicyRefusal) as ei:
        ps.enforce_model_policy(
            "codegen", "databricks-claude-sonnet-4-6", phi=True, policy=pol,
        )
    assert "phi_eligible" in ei.value.rule_ref


def test_enforce_noop_when_policy_unloaded(tmp_path):
    pol = mp.load_model_policy(str(tmp_path / "none.yaml"))
    assert pol.loaded is False
    # permissive: any model on any stage is fine
    ps.enforce_model_policy("codegen", "anything", phi=True, policy=pol)


def test_refusal_carries_stage_and_model(tmp_path):
    pol = _policy(tmp_path, DENY)
    with pytest.raises(ps.ModelPolicyRefusal) as ei:
        ps.enforce_model_policy("assessor", "random-model", phi=False, policy=pol)
    assert ei.value.stage == "assessor"
    assert ei.value.model == "random-model"
