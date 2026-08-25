"""Patch attestation — authorship that survives being moved.

Tasks 6d.4 and 6d.5 of adopt-github-native-execution-substrate.

## Why this exists

An adversarial review defeated the first draft of `agent-remediation` in one
move: **a pull request's opener does not establish who wrote its contents.**

Concrete laundering paths the review named:

- the agent prepares a patch, a human-controlled account opens the PR;
- a human opens an empty PR and an agent fills the branch;
- agent commits are cherry-picked into a nominally human-authored PR;
- the remediation is squash-merged, leaving only the merging identity.

In every case the work is agent-produced, the PR looks human-authored, and the
rule "an agent may not satisfy required review on agent-authored work" silently
stops applying. The agent has closed its own loop while appearing not to.

So authorship MUST NOT be read from PR opener, commit author/committer fields,
commit trailers, branch names, or labels. All of those are forgeable, and squash
merge destroys the honest ones. It is derived instead from a signature over the
**patch content**, which travels with the patch wherever it is moved.

## The rule

    A patch is attributed to whoever signed its content.
    Not to whoever opened the PR it arrived in.

## Fail closed, and specifically

Three distinct failures, none of which may degrade to "probably the human":

- **no attestation** -> `UnverifiedProvenance`. Absent provenance is unknown,
  not human. Defaulting to human is what the transplant attack exploits.
- **verification fails** -> `AttestationError`. Tampering with the diff, the
  signature, or the recorded agent id all invalidate.
- **mixed** -> `UnverifiedProvenance`. A branch carrying one attested and one
  unattested patch is not clean, and merging the two claims would launder the
  unattested half.

Human authorship is likewise a **positive claim** requiring its own attestation,
not the absence of an agent one.

## What this is NOT

This computes an HMAC over canonicalized patch content plus its provenance
fields. That binds authorship to content, which is the property the transplant
attack requires — but it is **not** the workflow-identity binding 6d ultimately
needs. Real closure means Sigstore / in-toto attestations minted by the
executing workflow, verified server-side, so a stolen signing key is not
sufficient to forge authorship.

What this module provides is the **decision surface** — `make_attestation`,
`verify_attestation`, `derive_actor` — so call sites can be written against a
stable contract and the cryptography swapped underneath without touching them.
Saying so explicitly matters: a governance control that overstates its own
strength is the failure mode this project keeps finding in itself.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Optional, Sequence


class AttestationError(Exception):
    """The attestation does not verify against the patch and key."""


class UnverifiedProvenance(Exception):
    """Authorship could not be established. Never degrades to a default."""


def patch_digest(diff: str) -> str:
    """Content digest of a patch.

    Canonicalizes line endings only. Whitespace inside the diff is meaningful —
    normalizing it would let a semantically different patch share a digest.
    """
    normalized = (diff or "").replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PatchAttestation:
    """Who produced a patch, bound to the patch's content.

    `agent_id is None` denotes a human-authored patch. That is an explicit
    claim carried by a signature, not an absence.
    """

    principal: str          # the initiating human principal (UPN)
    agent_id: Optional[str] # agent principal, or None for human-authored
    workflow_run: str       # where it executed
    source_revision: str    # the revision it was produced against
    toolchain: str          # what produced it
    patch_digest: str
    signature: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PatchAttestation":
        return cls(**{k: d.get(k) for k in cls.__dataclass_fields__})  # type: ignore[arg-type]


def _payload(
    *,
    principal: str,
    agent_id: Optional[str],
    workflow_run: str,
    source_revision: str,
    toolchain: str,
    digest: str,
) -> bytes:
    """Canonical signed payload.

    Every provenance field is covered, so relabeling the author invalidates the
    signature. A signature over the digest alone would let an attacker swap
    `agent_id` and keep it valid — which would make the whole control useless.
    """
    return json.dumps(
        {
            "principal": principal,
            "agent_id": agent_id,
            "workflow_run": workflow_run,
            "source_revision": source_revision,
            "toolchain": toolchain,
            "patch_digest": digest,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def make_attestation(
    diff: str,
    *,
    key: bytes,
    principal: str,
    agent_id: Optional[str],
    workflow_run: str,
    source_revision: str,
    toolchain: str,
) -> PatchAttestation:
    """Sign a patch's content together with its provenance."""
    digest = patch_digest(diff)
    sig = hmac.new(
        key,
        _payload(
            principal=principal, agent_id=agent_id, workflow_run=workflow_run,
            source_revision=source_revision, toolchain=toolchain, digest=digest,
        ),
        hashlib.sha256,
    ).hexdigest()
    return PatchAttestation(
        principal=principal,
        agent_id=agent_id,
        workflow_run=workflow_run,
        source_revision=source_revision,
        toolchain=toolchain,
        patch_digest=digest,
        signature=sig,
    )


def verify_attestation(diff: str, att: PatchAttestation, *, key: bytes) -> bool:
    """Verify an attestation against a patch. Raises on any mismatch."""
    digest = patch_digest(diff)
    if att.patch_digest != digest:
        raise AttestationError(
            "patch digest mismatch: the content does not match what was signed "
            "(the diff was altered after attestation)"
        )
    expected = hmac.new(
        key,
        _payload(
            principal=att.principal, agent_id=att.agent_id,
            workflow_run=att.workflow_run, source_revision=att.source_revision,
            toolchain=att.toolchain, digest=digest,
        ),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, att.signature or ""):
        raise AttestationError(
            "signature mismatch: the attestation was not produced by this key, "
            "or a provenance field was altered after signing"
        )
    return True


@dataclass(frozen=True)
class DerivedActor:
    kind: str            # "human" | "agent"
    id: str
    attestation: PatchAttestation


def derive_actor(
    diff: str,
    *,
    attestations: Sequence[PatchAttestation],
    key: bytes,
    pr_opener: Optional[str] = None,
    additional_diffs: Optional[Iterable[str]] = None,
) -> DerivedActor:
    """Determine who authored a patch, from attestation alone.

    `pr_opener` is accepted only so callers need not strip it, and is
    deliberately never consulted — the parameter exists to make its irrelevance
    explicit at the call site rather than implicit by omission.
    """
    extra = [d for d in (additional_diffs or []) if d]
    if extra:
        attested = {a.patch_digest for a in attestations}
        unattested = [d for d in extra if patch_digest(d) not in attested]
        if unattested:
            raise UnverifiedProvenance(
                f"mixed provenance: {len(unattested)} patch(es) on this branch carry "
                "no attestation; merging attested and unattested work would launder "
                "the unattested half"
            )

    if not attestations:
        raise UnverifiedProvenance(
            "no attestation for this patch — authorship is unknown and MUST NOT "
            "default to the pull request's opener, which is exactly the "
            "transplant path this control exists to close"
        )

    digest = patch_digest(diff)
    for att in attestations:
        if att.patch_digest != digest:
            continue
        try:
            verify_attestation(diff, att, key=key)
        except AttestationError as exc:
            raise UnverifiedProvenance(
                f"attestation present but unverifiable: {exc}"
            ) from exc
        if att.agent_id:
            return DerivedActor(kind="agent", id=att.agent_id, attestation=att)
        return DerivedActor(kind="human", id=att.principal, attestation=att)

    raise UnverifiedProvenance(
        "no attestation matches this patch's content digest"
    )
