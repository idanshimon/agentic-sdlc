"""Tests for the remediation lifecycle (6d.14-6d.17).

Every case is a distributed-systems failure the adversarial review named:
partial writes, lost webhooks, duplicate delivery, out-of-order delivery,
post-verification edits. None of them are exotic — they are Tuesday.
"""
from __future__ import annotations

import pytest

from orchestrator.remediation_lifecycle import (
    Disagreement,
    ImpossibleTransition,
    Remediation,
    State,
    create_remediation,
    idempotency_key,
    order_events,
    reconcile,
)

KEY = "k-1"
DIGEST = "sha-patch-1"


def _rem(state=State.DRAFT, pr="pr-1", entry="e-1", digest=DIGEST, key=KEY):
    return Remediation(
        idempotency_key=key, state=state,
        ledger_entry_id=entry, pull_request_id=pr, patch_digest=digest,
    )


def _prs(digest=DIGEST, pr="pr-1"):
    return {pr: {"patch_digest": digest}}


def _entries(pr="pr-1", entry="e-1"):
    return {entry: {"pull_request_id": pr}}


# --- born non-mergeable ------------------------------------------------------

def test_remediation_is_born_non_mergeable():
    r = create_remediation(key=KEY, patch_digest=DIGEST, ledger_entry_id="e-1",
                           pull_request_id="pr-1")
    assert r.state is State.DRAFT
    assert r.mergeable is False


def test_only_merge_authorized_is_mergeable():
    for s in State:
        r = _rem(state=s)
        assert r.mergeable == (s is State.MERGE_AUTHORIZED)


# --- idempotency -------------------------------------------------------------

def test_same_failure_derives_the_same_key():
    a = idempotency_key(root_gate_instance="g1", parent_pr="36",
                        parent_head_sha="p" * 40, patch_digest=DIGEST)
    b = idempotency_key(root_gate_instance="g1", parent_pr="36",
                        parent_head_sha="p" * 40, patch_digest=DIGEST)
    assert a == b


def test_a_different_parent_commit_derives_a_different_key():
    a = idempotency_key(root_gate_instance="g1", parent_pr="36",
                        parent_head_sha="p" * 40, patch_digest=DIGEST)
    b = idempotency_key(root_gate_instance="g1", parent_pr="36",
                        parent_head_sha="z" * 40, patch_digest=DIGEST)
    assert a != b


def test_retry_after_ambiguous_failure_converges():
    """The classic double-create: the call timed out but actually succeeded."""
    first = create_remediation(key=KEY, patch_digest=DIGEST,
                               ledger_entry_id="e-1", pull_request_id="pr-1")
    retry = create_remediation(key=KEY, patch_digest=DIGEST,
                               ledger_entry_id="e-1", pull_request_id="pr-1",
                               existing=first)
    assert retry is first


# --- the state machine -------------------------------------------------------

def test_impossible_transition_is_refused():
    with pytest.raises(ImpossibleTransition):
        _rem(state=State.DRAFT).transition(State.MERGED)


def test_terminal_states_cannot_be_reopened():
    for terminal in (State.MERGED, State.SUPERSEDED, State.ABANDONED):
        with pytest.raises(ImpossibleTransition):
            _rem(state=terminal).transition(State.UNDER_REVIEW)


def test_transitions_are_recorded_in_history():
    r = _rem().transition(State.VERIFIED, reason="reconciled")
    assert r.history and "draft->verified" in r.history[0]


def test_the_legitimate_path_completes():
    r = _rem()
    for s in (State.VERIFIED, State.UNDER_REVIEW, State.APPROVED,
              State.MERGE_AUTHORIZED, State.MERGED):
        r = r.transition(s)
    assert r.state is State.MERGED


# --- reconciliation: partial writes ------------------------------------------

def test_pr_with_no_ledger_entry_is_quarantined():
    """The dangerous orphan: an unattributable agent action."""
    out, findings = reconcile(
        remediations=[_rem(entry=None)], repo_prs=_prs(), ledger_entries={})
    assert out[0].state is State.QUARANTINED
    assert out[0].mergeable is False
    assert findings[0].disagreement is Disagreement.ORPHAN_PR
    assert findings[0].blocks_ref is True


def test_ledger_entry_with_no_pr_does_not_block_the_ref():
    """The safe orphan: the record survived, the PR did not."""
    out, findings = reconcile(
        remediations=[_rem(pr=None)], repo_prs={}, ledger_entries=_entries(pr=None))
    assert findings[0].disagreement is Disagreement.ORPHAN_LEDGER
    assert findings[0].blocks_ref is False


def test_both_present_and_linked_verifies():
    out, findings = reconcile(
        remediations=[_rem()], repo_prs=_prs(), ledger_entries=_entries())
    assert out[0].state is State.VERIFIED
    assert not findings


def test_content_edited_after_verification_is_caught():
    """The approved diff is not the diff that would merge."""
    out, findings = reconcile(
        remediations=[_rem(state=State.APPROVED)],
        repo_prs=_prs(digest="sha-DIFFERENT"), ledger_entries=_entries())
    assert findings[0].disagreement is Disagreement.DIGEST_MISMATCH
    assert out[0].state is State.STALE
    assert out[0].mergeable is False


def test_broken_backlink_is_caught():
    out, findings = reconcile(
        remediations=[_rem()], repo_prs=_prs(),
        ledger_entries={"e-1": {"pull_request_id": "pr-OTHER"}})
    assert findings[0].disagreement is Disagreement.LINK_BROKEN


def test_duplicate_pr_claim_is_caught():
    out, findings = reconcile(
        remediations=[_rem(key="k-1"), _rem(key="k-2")],
        repo_prs=_prs(), ledger_entries=_entries())
    assert any(f.disagreement is Disagreement.DUPLICATE for f in findings)


def test_reconciliation_is_idempotent():
    args = dict(repo_prs=_prs(), ledger_entries={})
    once, _ = reconcile(remediations=[_rem(entry=None)], **args)
    twice, _ = reconcile(remediations=once, **args)
    assert twice[0].state == once[0].state


def test_quarantine_carries_a_readable_reason():
    out, _ = reconcile(remediations=[_rem(entry=None)], repo_prs=_prs(), ledger_entries={})
    assert out[0].quarantine_reason and len(out[0].quarantine_reason) > 30


def test_reconciliation_clears_quarantine_once_systems_agree():
    quarantined = _rem(state=State.QUARANTINED)
    out, findings = reconcile(
        remediations=[quarantined], repo_prs=_prs(), ledger_entries=_entries())
    assert out[0].state is State.VERIFIED
    assert out[0].quarantine_reason is None
    assert not findings


def test_merged_remediation_is_not_reopened_by_a_finding():
    out, findings = reconcile(
        remediations=[_rem(state=State.MERGED, entry=None)],
        repo_prs=_prs(), ledger_entries={})
    assert out[0].state is State.MERGED
    assert findings


# --- out-of-order and duplicate delivery ------------------------------------

def test_merge_before_create_is_reordered():
    events = [{"kind": "merged", "idempotency_key": KEY},
              {"kind": "created", "idempotency_key": KEY}]
    assert [e["kind"] for e in order_events(events)] == ["created", "merged"]


def test_duplicate_delivery_is_collapsed():
    events = [{"kind": "created", "idempotency_key": KEY},
              {"kind": "created", "idempotency_key": KEY}]
    assert len(order_events(events)) == 1


def test_explicit_sequence_numbers_win():
    events = [{"kind": "merged", "idempotency_key": KEY, "sequence": 1},
              {"kind": "created", "idempotency_key": KEY, "sequence": 2}]
    assert [e["kind"] for e in order_events(events)] == ["merged", "created"]


def test_unknown_event_kinds_sort_last_not_first():
    events = [{"kind": "mystery", "idempotency_key": KEY},
              {"kind": "created", "idempotency_key": KEY}]
    assert order_events(events)[0]["kind"] == "created"


def test_empty_delivery_is_handled():
    assert order_events([]) == []


# --- the ordering rule -------------------------------------------------------

def test_module_documents_ledger_first_ordering():
    """When only one write survives it must be the record, not the PR."""
    import inspect

    from orchestrator import remediation_lifecycle

    doc = inspect.getdoc(remediation_lifecycle) or ""
    assert "Ledger first" in doc or "ledger first" in doc.lower()
    assert "unattributable" in doc
