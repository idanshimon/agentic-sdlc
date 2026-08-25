"""Tests for evaluation-path integrity (6d.6, 6d.7).

Driving line: *an agent that can't weaken a rule can still weaken the test that
proves it.* Each test is a way to neuter a gate without touching a single rule.
"""
from __future__ import annotations

import pytest
import yaml

from orchestrator.evaluation_path import (
    PathClass,
    Weakening,
    classify_path,
    detect_weakening,
    evaluate_integrity,
)


def _wf(src: str) -> dict:
    return yaml.safe_load(src)


# --- the protected set is the whole path, not just the rules -----------------

@pytest.mark.parametrize("path,expected", [
    ("standards-bundles/security/rules.yaml", PathClass.RULES),
    (".github/workflows/bundle-enforce.yml", PathClass.WORKFLOW),
    (".github/actions/scan/action.yml", PathClass.ACTION),
    ("apps/orchestrator/bundle_rules.py", PathClass.VERIFIER),
    ("apps/orchestrator/review_verdict.py", PathClass.VERIFIER),
    ("apps/orchestrator/decision_record.py", PathClass.COLLECTOR),
    ("apps/orchestrator/telemetry_queries.py", PathClass.PUBLISHER),
    ("standards-bundles/PINS.yaml", PathClass.PIN),
    ("CODEOWNERS", PathClass.OWNERSHIP),
])
def test_evaluation_path_members_are_classified(path, expected):
    assert classify_path(path) is expected


def test_ordinary_code_is_not_governance_relevant():
    """The set must be precise. Flagging everything trains people to ignore it."""
    for p in ("apps/web/src/Button.tsx", "README.md", "docs/architecture/x.html"):
        assert classify_path(p) is None


def test_the_integrity_checker_protects_itself():
    """A checker its subject can edit is decorative."""
    assert classify_path("apps/orchestrator/evaluation_path.py") is PathClass.INTEGRITY
    assert classify_path("apps/orchestrator/tests/test_evaluation_path.py") is PathClass.INTEGRITY


def test_pins_are_policy_not_dependency_bumps():
    for p in ("standards-bundles/PINS.yaml", "requirements-dev.txt", "pnpm-lock.yaml"):
        assert classify_path(p) is PathClass.PIN


# --- neutering a gate without touching a rule --------------------------------

def test_continue_on_error_is_detected():
    after = _wf("""
jobs:
  enforce:
    steps:
      - name: scan
        continue-on-error: true
""")
    k = [f.kind for f in detect_weakening(before=None, after=after)]
    assert Weakening.CONTINUE_ON_ERROR in k


def test_removing_a_step_is_detected():
    before = _wf("jobs:\n  enforce:\n    steps:\n      - name: scan\n      - name: report\n")
    after = _wf("jobs:\n  enforce:\n    steps:\n      - name: report\n")
    f = detect_weakening(before=before, after=after)
    assert any(x.kind is Weakening.STEP_REMOVED and "scan" in x.detail for x in f)


def test_removing_a_whole_job_is_detected():
    before = _wf("jobs:\n  enforce:\n    steps: []\n  audit:\n    steps: []\n")
    after = _wf("jobs:\n  enforce:\n    steps: []\n")
    f = detect_weakening(before=before, after=after)
    assert any(x.kind is Weakening.STEP_REMOVED and "audit" in x.detail for x in f)


def test_removing_a_trigger_is_detected():
    before = _wf("on:\n  pull_request:\n  push:\n")
    after = _wf("on:\n  push:\n")
    f = detect_weakening(before=before, after=after)
    assert any(x.kind is Weakening.TRIGGER_REMOVED for x in f)


def test_floating_action_ref_is_detected():
    after = _wf("""
jobs:
  enforce:
    steps:
      - name: checkout
        uses: actions/checkout@v4
""")
    f = detect_weakening(before=None, after=after)
    assert any(x.kind is Weakening.FLOATING_REF for x in f)


def test_sha_pinned_action_is_not_flagged():
    after = _wf("""
jobs:
  enforce:
    steps:
      - name: checkout
        uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683
""")
    assert not [f for f in detect_weakening(before=None, after=after)
                if f.kind is Weakening.FLOATING_REF]


def test_widened_permission_is_detected():
    before = _wf("permissions:\n  contents: read\n")
    after = _wf("permissions:\n  contents: write\n")
    f = detect_weakening(before=before, after=after)
    assert any(x.kind is Weakening.PERMISSION_WIDENED for x in f)


# --- the subtle one: path filters are policy ---------------------------------

def test_adding_a_path_filter_narrows_a_gate():
    """Looks like performance tuning. A gate that does not run cannot fail."""
    before = _wf("on:\n  pull_request:\n    branches: ['**']\n")
    after = _wf("on:\n  pull_request:\n    branches: ['**']\n    paths: ['src/**']\n")
    f = detect_weakening(before=before, after=after)
    assert any(x.kind is Weakening.PATH_FILTER_NARROWED for x in f)


def test_shrinking_an_existing_path_filter_is_detected():
    before = _wf("on:\n  pull_request:\n    paths: ['src/**', 'apps/**', 'packages/**']\n")
    after = _wf("on:\n  pull_request:\n    paths: ['src/**']\n")
    f = detect_weakening(before=before, after=after)
    assert any(x.kind is Weakening.PATH_FILTER_NARROWED for x in f)


def test_widening_paths_ignore_is_detected():
    before = _wf("on:\n  pull_request:\n    paths-ignore: ['docs/**']\n")
    after = _wf("on:\n  pull_request:\n    paths-ignore: ['docs/**', 'apps/**']\n")
    f = detect_weakening(before=before, after=after)
    assert any(x.kind is Weakening.PATH_FILTER_NARROWED for x in f)


def test_broadening_a_path_filter_is_not_weakening():
    """Strengthening must always be permitted, mirroring the PHI-lock rule."""
    before = _wf("on:\n  pull_request:\n    paths: ['src/**']\n")
    after = _wf("on:\n  pull_request:\n    paths: ['src/**', 'apps/**']\n")
    assert not [f for f in detect_weakening(before=before, after=after)
                if f.kind is Weakening.PATH_FILTER_NARROWED]


def test_adding_a_job_is_not_weakening():
    before = _wf("jobs:\n  enforce:\n    steps: []\n")
    after = _wf("jobs:\n  enforce:\n    steps: []\n  extra:\n    steps: []\n")
    assert not [f for f in detect_weakening(before=before, after=after)
                if f.kind is Weakening.STEP_REMOVED]


# --- the combined verdict ----------------------------------------------------

def test_ordinary_change_requires_no_governance_review():
    v = evaluate_integrity(changed_paths=["apps/web/src/Button.tsx", "README.md"])
    assert v.touches_evaluation_path is False
    assert v.required_reviewers == ()


def test_verifier_change_requires_governance_review():
    v = evaluate_integrity(changed_paths=["apps/orchestrator/bundle_rules.py"])
    assert v.touches_evaluation_path is True
    assert "governance" in v.required_reviewers
    assert "trustworthy as the machinery" in v.detail


def test_a_weakening_alone_triggers_review_with_no_governance_paths():
    """The diff touches only ordinary files, but neuters a gate."""
    after = _wf("jobs:\n  enforce:\n    steps:\n      - name: scan\n        continue-on-error: true\n")
    v = evaluate_integrity(changed_paths=["apps/web/src/Button.tsx"],
                           workflow_after=after)
    assert v.touches_evaluation_path is True
    assert v.weakenings


def test_verdict_names_every_class_touched():
    v = evaluate_integrity(changed_paths=[
        "standards-bundles/security/rules.yaml",
        ".github/workflows/bundle-enforce.yml",
        "apps/orchestrator/bundle_rules.py",
    ])
    for expected in ("rules", "workflow", "verifier"):
        assert expected in v.detail


def test_every_finding_explains_the_risk():
    v = evaluate_integrity(changed_paths=[
        "apps/orchestrator/review_verdict.py",
        "apps/orchestrator/telemetry_queries.py",
        "standards-bundles/PINS.yaml",
    ])
    for f in v.findings:
        assert len(f.detail) > 20, f"{f.path_class} must explain why it matters"


def test_empty_diff_is_clean():
    v = evaluate_integrity(changed_paths=[])
    assert v.touches_evaluation_path is False


# --- self-referential guard --------------------------------------------------

def test_this_repos_gate_workflow_is_in_the_protected_set():
    """Regression guard: the real workflow paths must actually be covered."""
    for real in (".github/workflows/bundle-enforce.yml",
                 ".github/workflows/supply-chain-scan.yml"):
        assert classify_path(real) is PathClass.WORKFLOW
