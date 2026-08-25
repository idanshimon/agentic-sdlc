"""Merge authorization — tasks 6d.1, 6d.8, 6d.10.

## The pair

`attestation.py` answers **who wrote this**. This module answers **what may
merge**. Together they are the "topology is not authorship" correction made
real: authorship rides on a signature over content, and enforcement rides on an
authorization bound to an exact commit.

## Why an API refusal is not enough

The control plane already returns HTTP 409 when a bulk approval targets a
hard-gated card, and that is correct. But the adversarial review named the hole:

> If GitHub can merge independently of the control plane, the hard gate is
> advisory. An administrator, GitHub App, merge queue, or workflow with
> sufficient permissions can bypass the API returning 409.

A verdict is only real if it is bound to the merge itself. So authorization
names the **exact resulting SHA**. An authorization for SHA `A` is worthless
against SHA `B`, which means a moved base branch, a rebase, or a force-push
invalidates it rather than silently carrying over.

## Compare-and-swap on the state tuple

The reviewer's second finding was that the spec had no concurrency semantics.
Two workers could observe the same failed gate and open sibling remediations;
both could be approved against the same parent SHA; the second could merge stale
after the first landed.

So every authorization carries an immutable `MergeState` — repository, root gate
instance, parent PR and its head SHA, target base SHA, policy bundle digest, and
the remediation head SHA. Merge is a compare-and-swap against that tuple. Any
drift invalidates both the authorization and the approvals that were gathered
under it, because an approval is consent to a specific diff landing on a
specific base, not a general blessing.

## Fail closed on every ambiguity

Unknown state, missing authorization, mismatched SHA, rotated policy, stale
approval — all refuse. There is no path where an unverifiable condition results
in a permitted merge.

## What this is NOT

This is the decision surface. It does not configure GitHub rulesets, disable
administrator bypass, or bind required checks to a publishing app identity —
those are live repository settings (6d.2, 6d.3) that must be applied to a real
repo and verified against it, not asserted in a unit test. `scan_ref_protection`
below evaluates a *supplied* protection snapshot so drift can be detected, but
something else must fetch that snapshot.

Stated plainly because the distinction matters: this module can prove a merge
*should* be refused. Only a correctly configured governed ref can prove one
*was*.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from enum import Enum
from typing import Any, Iterable, Optional, Sequence


class Refusal(str, Enum):
    NO_AUTHORIZATION = "no_authorization"
    SHA_MISMATCH = "sha_mismatch"
    STATE_DRIFT = "state_drift"
    POLICY_ROTATED = "policy_rotated"
    QUORUM_SHORT = "quorum_short"
    AGENT_SELF_APPROVAL = "agent_self_approval"
    UNVERIFIED_PROVENANCE = "unverified_provenance"
    CONCURRENT_REMEDIATION = "concurrent_remediation"
    BUDGET_EXCEEDED = "budget_exceeded"


@dataclass(frozen=True)
class MergeState:
    """The tuple an authorization is bound to.

    Any change to any field invalidates authorizations and approvals taken
    against it.
    """

    repository_id: str
    root_gate_instance: str
    parent_pr: str
    parent_head_sha: str
    target_base_sha: str
    policy_bundle_digest: str
    remediation_head_sha: str

    def fingerprint(self) -> str:
        return hashlib.sha256(
            json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()


@dataclass(frozen=True)
class Approval:
    """One recorded approval, bound to what it approved."""

    approver_id: str
    approver_kind: str          # "human" | "agent"
    patch_digest: str
    merge_sha: str
    roles: tuple[str, ...] = ()


@dataclass(frozen=True)
class MergeAuthorization:
    """Permission for ONE resulting SHA under ONE state tuple."""

    resulting_sha: str
    state_fingerprint: str
    gate_instance: str
    classification: str
    policy_bundle_digest: str


@dataclass(frozen=True)
class MergeVerdict:
    permitted: bool
    refusal: Optional[Refusal]
    detail: str

    @property
    def gate_reason(self) -> Optional[str]:
        """Map a refusal onto the ledger's typed vocabulary."""
        if self.permitted:
            return None
        if self.refusal is Refusal.BUDGET_EXCEEDED:
            return "budget_exceeded"
        if self.refusal in (Refusal.QUORUM_SHORT, Refusal.AGENT_SELF_APPROVAL):
            return "invariant_class"
        return "verification_failed"


def authorize(
    state: MergeState,
    *,
    gate_instance: str,
    classification: str,
) -> MergeAuthorization:
    """Issue an authorization for exactly this state's resulting SHA."""
    return MergeAuthorization(
        resulting_sha=state.remediation_head_sha,
        state_fingerprint=state.fingerprint(),
        gate_instance=gate_instance,
        classification=classification,
        policy_bundle_digest=state.policy_bundle_digest,
    )


def _independent_humans(
    approvals: Sequence[Approval],
    *,
    requester_id: str,
    agent_operator_id: Optional[str],
    patch_digest: str,
    merge_sha: str,
) -> list[Approval]:
    """Approvals that count: distinct humans, independent, bound to this merge."""
    excluded = {requester_id}
    if agent_operator_id:
        excluded.add(agent_operator_id)
    seen: set[str] = set()
    out: list[Approval] = []
    for a in approvals:
        if a.approver_kind != "human":
            continue
        if a.approver_id in excluded or a.approver_id in seen:
            continue
        if a.patch_digest != patch_digest or a.merge_sha != merge_sha:
            continue  # approval was for a different diff or a different result
        seen.add(a.approver_id)
        out.append(a)
    return out


def evaluate_merge(
    *,
    current_state: MergeState,
    authorization: Optional[MergeAuthorization],
    attempted_sha: str,
    approvals: Sequence[Approval] = (),
    patch_digest: str = "",
    requester_id: str = "",
    agent_operator_id: Optional[str] = None,
    author_kind: str = "agent",
    required_approvers: int = 1,
    must_include_roles: Iterable[str] = (),
    active_remediations: int = 1,
    budget_remaining: int = 1,
    provenance_verified: bool = True,
) -> MergeVerdict:
    """Decide whether a merge may proceed. Refuses on any ambiguity."""

    def no(r: Refusal, d: str) -> MergeVerdict:
        return MergeVerdict(permitted=False, refusal=r, detail=d)

    if not provenance_verified:
        return no(
            Refusal.UNVERIFIED_PROVENANCE,
            "patch provenance is unverified; authorship cannot be established "
            "and MUST NOT default to the pull request's opener",
        )

    if budget_remaining <= 0:
        return no(
            Refusal.BUDGET_EXCEEDED,
            "the root gate instance's remediation budget is exhausted; the agent "
            "cannot satisfy this gate and that is a governance event, not a retry",
        )

    if active_remediations > 1:
        return no(
            Refusal.CONCURRENT_REMEDIATION,
            f"{active_remediations} active remediations on one gate instance; "
            "siblings break the linear stack the reviewability claim depends on",
        )

    if authorization is None:
        return no(
            Refusal.NO_AUTHORIZATION,
            "no control-plane authorization for this merge; an API verdict that a "
            "merge path can route around is advisory, so the ref refuses by default",
        )

    if authorization.resulting_sha != attempted_sha:
        return no(
            Refusal.SHA_MISMATCH,
            f"authorization names {authorization.resulting_sha[:12]} but the merge "
            f"would produce {attempted_sha[:12]}; authorization does not transfer "
            "between commits",
        )

    if authorization.policy_bundle_digest != current_state.policy_bundle_digest:
        return no(
            Refusal.POLICY_ROTATED,
            "the pinned policy bundle rotated after authorization was issued; the "
            "verdict was reached under rules that no longer apply",
        )

    if authorization.state_fingerprint != current_state.fingerprint():
        return no(
            Refusal.STATE_DRIFT,
            "the merge state changed after authorization (force-push, rebase, or "
            "the base branch moved); approvals consented to a specific diff "
            "landing on a specific base, so both are invalidated",
        )

    counted = _independent_humans(
        approvals,
        requester_id=requester_id,
        agent_operator_id=agent_operator_id,
        patch_digest=patch_digest,
        merge_sha=attempted_sha,
    )

    if author_kind == "agent" and not counted:
        return no(
            Refusal.AGENT_SELF_APPROVAL,
            "no independent human approval on agent-authored work; an agent that "
            "opens, approves and merges its own pull request has closed its own loop",
        )

    if len(counted) < max(1, required_approvers):
        return no(
            Refusal.QUORUM_SHORT,
            f"{len(counted)} of {required_approvers} required independent approvals; "
            "a GitHub Environment accepts one-of-six and cannot express an N-of-M "
            "named-approver quorum, so the control plane evaluates it",
        )

    required_roles = set(must_include_roles)
    if required_roles:
        held = {r for a in counted for r in a.roles}
        missing = required_roles - held
        if missing:
            return no(
                Refusal.QUORUM_SHORT,
                f"approval set is missing required role(s): {sorted(missing)}",
            )

    return MergeVerdict(
        permitted=True,
        refusal=None,
        detail=(
            f"authorized for {attempted_sha[:12]} under gate "
            f"{authorization.gate_instance} with {len(counted)} independent "
            "human approval(s)"
        ),
    )


# --- drift detection (task 6a.4) --------------------------------------------

@dataclass(frozen=True)
class ProtectionFinding:
    control: str
    detail: str


def scan_ref_protection(snapshot: dict[str, Any]) -> list[ProtectionFinding]:
    """Evaluate a governed ref's protection snapshot for drift.

    Takes a snapshot rather than fetching one: fetching is an authenticated
    repository read that belongs to a caller with credentials, and keeping this
    pure makes the policy itself testable.

    Administrator bypass is ON by default in GitHub, so its absence from a
    snapshot is treated as enabled — the dangerous reading, deliberately.
    """
    findings: list[ProtectionFinding] = []

    if snapshot.get("enforce_admins") is not True:
        findings.append(ProtectionFinding(
            "admin_bypass",
            "administrator bypass is not disabled; it is ON by default in GitHub "
            "and must be explicitly disabled or the gate is advisory for admins",
        ))

    if snapshot.get("prevent_self_review") is not True:
        findings.append(ProtectionFinding(
            "self_review",
            "self-review prevention is not enabled; an author could satisfy their "
            "own required review",
        ))

    if snapshot.get("allow_force_pushes") is True:
        findings.append(ProtectionFinding(
            "force_push",
            "force pushes are permitted on a governed ref; history a decision was "
            "authorized against could be rewritten after approval",
        ))

    checks = snapshot.get("required_status_checks") or {}
    contexts = checks.get("contexts") or []
    app_bound = checks.get("checks") or []
    if not contexts and not app_bound:
        findings.append(ProtectionFinding(
            "no_required_checks",
            "no required status checks on a governed ref; policy-as-code that "
            "does not gate the merge is reporting, not enforcement",
        ))
    elif contexts and not app_bound:
        findings.append(ProtectionFinding(
            "unbound_checks",
            "required checks are matched by name only; a check of the same name "
            "published by another identity would satisfy the gate",
        ))

    if not snapshot.get("required_pull_request_reviews"):
        findings.append(ProtectionFinding(
            "no_review_requirement",
            "no pull-request review requirement on a governed ref",
        ))

    return findings
