"""Tests for bundle-citation honesty (task 2.1-2.4).

The governing rule: a citation must not claim more than was actually done.
"""
from __future__ import annotations

import pathlib
import re

import pytest

from orchestrator.bundle_citation import (
    cite_rules_evaluated,
    cite_subscriptions,
    classify_citation,
    is_bundle_ref,
    is_rule_ref,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]


# --- reference shapes --------------------------------------------------------

def test_rule_ref_recognized():
    assert is_rule_ref("security/v0.2.0/PHI-001")
    assert is_rule_ref("architect/v0.1.0/SERVICE-CONTAINERIZED-001")


def test_bundle_ref_is_not_a_rule_ref():
    assert is_bundle_ref("security/v0.2.0")
    assert not is_rule_ref("security/v0.2.0")


def test_malformed_refs_rejected():
    for bad in ["", "security", "security/0.2.0/PHI-001", "Security/v0.2.0/PHI-001", "/v0.2.0/X"]:
        assert not is_rule_ref(bad)
        assert not is_bundle_ref(bad)


# --- rules evaluated ---------------------------------------------------------

def test_rules_evaluated_keeps_only_rules():
    out = cite_rules_evaluated(["security/v0.2.0/PHI-001", "security/v0.2.0"])
    assert out == ["security/v0.2.0/PHI-001"]


def test_rules_evaluated_dedupes_preserving_order():
    out = cite_rules_evaluated(
        ["security/v0.2.0/PHI-001", "architect/v0.1.0/A-1", "security/v0.2.0/PHI-001"]
    )
    assert out == ["security/v0.2.0/PHI-001", "architect/v0.1.0/A-1"]


def test_empty_is_empty_not_invented():
    assert cite_rules_evaluated(None) == []
    assert cite_rules_evaluated([]) == []


# --- subscriptions -----------------------------------------------------------

def test_subscription_reduces_rule_ref_to_its_bundle():
    """In a subscription context, keeping the rule component would overstate."""
    assert cite_subscriptions(["security/v0.2.0/PHI-001"]) == ["security/v0.2.0"]


def test_subscription_dedupes_after_reduction():
    out = cite_subscriptions(["security/v0.2.0/PHI-001", "security/v0.2.0/PHI-002"])
    assert out == ["security/v0.2.0"]


# --- classification: the anti-overclaim kernel -------------------------------

def test_all_rules_infers_rule_evaluated():
    refs, kind = classify_citation(["security/v0.2.0/PHI-001", "architect/v0.1.0/A-1"])
    assert kind == "rule_evaluated"
    assert len(refs) == 2


def test_mixed_set_fails_closed_to_subscription():
    """A set that is not all rules cannot claim rule-level precision."""
    refs, kind = classify_citation(["security/v0.2.0/PHI-001", "architect/v0.1.0"])
    assert kind == "subscription"
    assert refs == ["security/v0.2.0", "architect/v0.1.0"]


def test_claimed_rule_evaluated_is_downgraded_when_unsupported():
    """A caller asserting rule_evaluated over bundle refs is corrected, not trusted."""
    refs, kind = classify_citation(["security/v0.2.0"], kind="rule_evaluated")
    assert kind == "subscription"
    assert refs == ["security/v0.2.0"]


def test_explicit_subscription_is_honoured():
    refs, kind = classify_citation(["security/v0.2.0/PHI-001"], kind="subscription")
    assert kind == "subscription"
    assert refs == ["security/v0.2.0"]


def test_no_refs_is_subscription_with_empty_list():
    refs, kind = classify_citation([])
    assert refs == [] and kind == "subscription"


# --- repo-level guard: task 2.4 ---------------------------------------------

def test_no_hardcoded_rule_id_in_stage_code():
    """A standards rule ID MUST NOT be a literal in stage implementation code.

    This is the regression guard for the audit finding: deliver_github.py
    stamped `architect/v0.1.0/SERVICE-CONTAINERIZED-001` on every delivered
    entry, citing a rule that delivery never evaluated.
    """
    rule_literal = re.compile(r"[\"'][a-z][a-z0-9_-]*/v\d+\.\d+\.\d+/[A-Z][A-Z0-9-]*[\"']")
    scanned = 0
    offenders: list[str] = []

    for path in (REPO_ROOT / "apps" / "orchestrator").rglob("*.py"):
        parts = set(path.parts)
        if ".venv" in parts or "tests" in parts or "__pycache__" in parts:
            continue
        # this module documents the defect in prose; its own docstrings are exempt
        if path.name == "bundle_citation.py":
            continue
        scanned += 1
        for lineno, line in enumerate(path.read_text().splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if rule_literal.search(line):
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{lineno}: {stripped[:90]}")

    assert scanned > 5, "scan found too few files — the glob is wrong, not the code"
    assert not offenders, "hardcoded standards rule ID in stage code:\n" + "\n".join(offenders)
