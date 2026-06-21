"""Tests for agent_bundles — the agent→bundle wiring (closes the display-only gap).

Verifies the parser handles the real .github/agents/*.agent.md files correctly:
inline-comment noise stripped, prose placeholders rejected, validated against
real bundle dirs, and the stage→agent→bundles mapping.
"""
from __future__ import annotations

from apps.orchestrator import agent_bundles as ab


def test_known_bundles_are_the_real_dirs():
    # standards-bundles/<dept>/ — at least the four canonical bundles exist.
    assert {"architect", "security", "privacy", "finops"} <= set(ab._KNOWN_BUNDLES)


def test_architect_agent_subscribes_to_architect_and_security():
    assert ab.bundles_for_agent("architect") == ["architect", "security"]


def test_assessor_agent_subscribes_to_security_and_privacy():
    assert ab.bundles_for_agent("assessor") == ["security", "privacy"]


def test_inline_comment_noise_is_stripped():
    # pipeline-doctor declares "finops   # primary bundle (...)" — the comment
    # must not leak into the bundle ref.
    assert ab.bundles_for_agent("pipeline-doctor") == ["finops"]


def test_prose_placeholder_is_rejected():
    # standards-change declares "all (read-only)" — not a real bundle dir, so
    # it must be filtered out, yielding [].
    assert ab.bundles_for_agent("standards-change") == []


def test_unknown_agent_returns_empty():
    assert ab.bundles_for_agent("does-not-exist") == []


def test_stage_to_agent_mapping():
    # The stages the pipeline actually emits map to the right agent's bundles.
    assert ab.bundles_for_stage("assessor") == ["security", "privacy"]
    assert ab.bundles_for_stage("architect") == ["architect", "security"]
    assert ab.bundles_for_stage("codegen") == ["architect", "security"]
    assert ab.bundles_for_stage("review_scan") == ["security", "privacy"]


def test_unmapped_stage_returns_empty_not_error():
    # test_plan has no agent file yet — must return [] so callers can stamp
    # bundle_refs unconditionally without a guard.
    assert ab.bundles_for_stage("test_plan") == []
    assert ab.bundles_for_stage("nonsense-stage") == []


def test_reload_clears_cache():
    # Smoke: reload must not raise and must keep the map consistent.
    before = ab.bundles_for_agent("architect")
    ab.reload_agent_bundles()
    assert ab.bundles_for_agent("architect") == before
