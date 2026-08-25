"""Patch attestation — tasks 6d.4 and 6d.5.

## The attack this defeats

An adversarial review broke the first draft of `agent-remediation` in one move:

> A pull request's opener does not establish who wrote its contents.

An agent's patch cherry-picked into a human-opened PR is indistinguishable from
human work, so the rule "an agent may not approve agent-authored work" silently
stops applying and the agent has closed its own loop while appearing not to. A
squash merge then attributes the result to the merging human.

So authorship cannot be read from PR opener, commit author/committer fields,
trailers, branch names, or labels. **All of those are forgeable or lost.** It
must be derived from a signature over the patch content itself, which travels
with the patch wherever it is moved.

## What these tests pin

The digest binds the *content*, so moving a patch between branches, PRs, or
repositories does not change who is recorded as its author. Tampering with the
diff invalidates the attestation. Absent or unverifiable provenance fails
closed rather than defaulting to "probably human".

## Deliberately not cryptography yet

This module computes and verifies a content-bound digest with an HMAC over a
signing key. It is NOT a substitute for Sigstore/in-toto attestations bound to a
workflow identity, which is what 6d's live verification requires. What it does
provide is the *decision surface* — `derive_actor`, `verify` — so the call sites
can be written against a stable contract and the crypto swapped underneath. The
module says so rather than implying it is already the real thing.
"""
from __future__ import annotations

import pytest

from orchestrator.attestation import (
    AttestationError,
    PatchAttestation,
    UnverifiedProvenance,
    derive_actor,
    make_attestation,
    patch_digest,
    verify_attestation,
)

KEY = b"test-signing-key-not-a-real-one"
DIFF = "--- a/x.py\n+++ b/x.py\n@@\n-old\n+new\n"


def _att(diff=DIFF, **kw):
    base = dict(
        principal="idan@example.com",
        agent_id="agent:remediation-bot",
        workflow_run="https://github.com/o/r/actions/runs/1",
        source_revision="abc1234",
        toolchain="copilot/gpt-5",
    )
    base.update(kw)
    return make_attestation(diff, key=KEY, **base)


# --- the digest binds content, not location ---------------------------------

def test_digest_is_stable_for_identical_content():
    assert patch_digest(DIFF) == patch_digest(DIFF)


def test_digest_changes_when_the_diff_changes():
    assert patch_digest(DIFF) != patch_digest(DIFF + "\n+sneaky\n")


def test_attestation_survives_being_moved_to_another_branch():
    """THE transplant attack. Same patch, different branch/PR/opener.

    The recorded author must not change, because the signature is over content.
    """
    a = _att()
    # Same content arrives on a human-opened PR under a human's name.
    actor = derive_actor(DIFF, attestations=[a], key=KEY, pr_opener="human@example.com")
    assert actor.kind == "agent"
    assert actor.id == "agent:remediation-bot"


def test_pr_opener_never_overrides_an_attestation():
    a = _att()
    for opener in ("human@example.com", "ceo@example.com", None):
        assert derive_actor(DIFF, attestations=[a], key=KEY, pr_opener=opener).kind == "agent"


# --- tampering ---------------------------------------------------------------

def test_tampered_diff_fails_verification():
    a = _att()
    with pytest.raises(AttestationError):
        verify_attestation(DIFF + "\n+injected\n", a, key=KEY)


def test_tampered_signature_fails_verification():
    a = _att()
    forged = PatchAttestation(**{**a.__dict__, "signature": "0" * 64})
    with pytest.raises(AttestationError):
        verify_attestation(DIFF, forged, key=KEY)


def test_wrong_key_fails_verification():
    a = _att()
    with pytest.raises(AttestationError):
        verify_attestation(DIFF, a, key=b"different-key")


def test_swapping_the_agent_id_fails_verification():
    """Relabeling the author must invalidate, or the signature proves nothing."""
    a = _att()
    forged = PatchAttestation(**{**a.__dict__, "agent_id": "agent:innocent"})
    with pytest.raises(AttestationError):
        verify_attestation(DIFF, forged, key=KEY)


# --- fail closed -------------------------------------------------------------

def test_no_attestation_fails_closed_not_to_human():
    """Absent provenance is UNKNOWN, never 'probably the human who opened it'."""
    with pytest.raises(UnverifiedProvenance):
        derive_actor(DIFF, attestations=[], key=KEY, pr_opener="human@example.com")


def test_unverifiable_attestation_fails_closed():
    a = _att()
    with pytest.raises(UnverifiedProvenance):
        derive_actor(DIFF, attestations=[a], key=b"wrong-key", pr_opener="human@example.com")


def test_mixed_provenance_fails_closed():
    """A branch carrying one attested and one unattested patch is not clean."""
    a = _att()
    with pytest.raises(UnverifiedProvenance, match="mixed|unattested"):
        derive_actor(
            DIFF, attestations=[a], key=KEY, pr_opener="human@example.com",
            additional_diffs=["--- a/y.py\n+++ b/y.py\n@@\n-a\n+b\n"],
        )


def test_human_authorship_requires_an_explicit_human_attestation():
    """Human authorship is a positive claim, not the absence of an agent one."""
    h = make_attestation(
        DIFF, key=KEY, principal="idan@example.com", agent_id=None,
        workflow_run="local", source_revision="abc1234", toolchain="vscode",
    )
    actor = derive_actor(DIFF, attestations=[h], key=KEY, pr_opener="idan@example.com")
    assert actor.kind == "human"
    assert actor.id == "idan@example.com"


# --- the record --------------------------------------------------------------

def test_attestation_records_the_full_provenance_set():
    a = _att()
    for fld in ("principal", "agent_id", "workflow_run", "source_revision",
                "toolchain", "patch_digest", "signature"):
        assert getattr(a, fld), f"{fld} must be recorded"


def test_attestation_is_immutable():
    a = _att()
    with pytest.raises(Exception):
        a.signature = "x"  # type: ignore[misc]


def test_attestation_roundtrips_through_serialization():
    a = _att()
    restored = PatchAttestation.from_dict(a.to_dict())
    assert verify_attestation(DIFF, restored, key=KEY) is True


# --- honesty about what this is ---------------------------------------------

def test_module_declares_it_is_not_yet_workflow_bound_crypto():
    """6d requires attestations bound to a workflow identity (Sigstore/in-toto).

    This is a content-bound HMAC providing the decision surface. The module must
    say so rather than implying the stronger guarantee already exists.
    """
    import inspect

    from orchestrator import attestation

    doc = inspect.getdoc(attestation) or ""
    assert "not" in doc.lower()
    assert any(t in doc for t in ("Sigstore", "in-toto", "workflow identity"))
