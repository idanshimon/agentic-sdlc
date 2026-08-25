"""Remediation lifecycle — tasks 6d.14, 6d.15, 6d.16, 6d.17.

## The finding this closes

The adversarial review's fourth point:

> GitHub and the ledger cannot be updated atomically. The specification
> requires bidirectional linkage but does not define failure ordering.

Concretely: the PR is created and the ledger write fails, leaving an actionable
orphan. Or the ledger records a planned PR that GitHub never created. Or the
merge webhook is lost, or delivered before the creation webhook. Or a retry
opens a second remediation. Or the body is edited after verification.

"Fail delivery closed" does not cover any of these, because they all happen
*after* delivery returned successfully.

## The shape of the fix

**Quarantine.** A remediation is born non-mergeable. It becomes eligible only
after reconciliation confirms both systems agree. A partial write is therefore
inert rather than actionable — the worst case is a PR nobody can merge, not a
PR that merges without a decision record.

**Idempotency keys.** Every operation carries one derived from its content, so
a retry after an ambiguous failure converges on the same remediation instead of
creating a second.

**A reconciler independent of webhooks.** Webhook delivery is not a
transaction: messages are lost, duplicated, and reordered. Something must
periodically compare the two systems and block what disagrees.

**An explicit state machine.** Out-of-order events must not produce impossible
histories. A merge event arriving before its creation event is a delivery
artifact, not a time-travelling merge, and the lifecycle has to say so.

## Ordering rule

Ledger first, then GitHub. A ledger entry with no PR is a harmless orphan the
reconciler retires. A PR with no ledger entry is an unattributable agent action
— the exact thing this project exists to prevent. When only one write can
survive, it must be the record.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Iterable, Optional, Sequence


class State(str, Enum):
    """Lifecycle of one remediation.

    `DRAFT` and `QUARANTINED` are both non-mergeable; the distinction is whether
    reconciliation has run yet.
    """

    DRAFT = "draft"                    # created, not yet reconciled
    QUARANTINED = "quarantined"        # reconciliation found a disagreement
    VERIFIED = "verified"              # both systems agree; eligible for review
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    STALE = "stale"                    # state drifted after approval
    MERGE_AUTHORIZED = "merge_authorized"
    MERGED = "merged"
    SUPERSEDED = "superseded"
    ABANDONED = "abandoned"


#: Transitions that may occur. Anything absent is impossible and is refused
#: rather than silently applied — an impossible history is worse than a stalled
#: one, because it looks authoritative.
_ALLOWED: dict[State, set[State]] = {
    State.DRAFT: {State.VERIFIED, State.QUARANTINED, State.ABANDONED},
    State.QUARANTINED: {State.VERIFIED, State.ABANDONED},
    State.VERIFIED: {State.UNDER_REVIEW, State.STALE, State.SUPERSEDED, State.ABANDONED},
    State.UNDER_REVIEW: {State.APPROVED, State.STALE, State.SUPERSEDED, State.ABANDONED},
    State.APPROVED: {State.MERGE_AUTHORIZED, State.STALE, State.SUPERSEDED, State.ABANDONED},
    State.MERGE_AUTHORIZED: {State.MERGED, State.STALE, State.ABANDONED},
    State.STALE: {State.UNDER_REVIEW, State.SUPERSEDED, State.ABANDONED},
    State.MERGED: set(),        # terminal
    State.SUPERSEDED: set(),    # terminal
    State.ABANDONED: set(),     # terminal
}

MERGEABLE_STATES = {State.MERGE_AUTHORIZED}
NON_MERGEABLE_ON_BIRTH = {State.DRAFT, State.QUARANTINED}


class ImpossibleTransition(Exception):
    """A transition the lifecycle does not permit."""


def idempotency_key(
    *,
    root_gate_instance: str,
    parent_pr: str,
    parent_head_sha: str,
    patch_digest: str,
) -> str:
    """Content-derived key for a remediation attempt.

    Two workers observing the same failure against the same parent commit with
    the same patch derive the same key, so a retry converges rather than
    creating a sibling.
    """
    return hashlib.sha256(
        json.dumps(
            {
                "root": root_gate_instance,
                "parent_pr": parent_pr,
                "parent_head_sha": parent_head_sha,
                "patch_digest": patch_digest,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()[:32]


@dataclass(frozen=True)
class Remediation:
    idempotency_key: str
    state: State
    ledger_entry_id: Optional[str] = None
    pull_request_id: Optional[str] = None
    patch_digest: str = ""
    quarantine_reason: Optional[str] = None
    history: tuple[str, ...] = ()

    @property
    def mergeable(self) -> bool:
        return self.state in MERGEABLE_STATES

    def transition(self, to: State, *, reason: str = "") -> "Remediation":
        if to not in _ALLOWED.get(self.state, set()):
            raise ImpossibleTransition(
                f"{self.state.value} -> {to.value} is not a permitted transition; "
                "refusing rather than recording an impossible history"
            )
        note = f"{self.state.value}->{to.value}" + (f" ({reason})" if reason else "")
        return replace(self, state=to, history=self.history + (note,))


def create_remediation(
    *,
    key: str,
    patch_digest: str,
    ledger_entry_id: Optional[str],
    pull_request_id: Optional[str],
    existing: Optional[Remediation] = None,
) -> Remediation:
    """Create a remediation, or return the existing one for this key.

    Born in DRAFT and therefore non-mergeable: a partial write is inert, not
    actionable.
    """
    if existing is not None and existing.idempotency_key == key:
        return existing
    return Remediation(
        idempotency_key=key,
        state=State.DRAFT,
        ledger_entry_id=ledger_entry_id,
        pull_request_id=pull_request_id,
        patch_digest=patch_digest,
    )


# --- reconciliation ----------------------------------------------------------

class Disagreement(str, Enum):
    ORPHAN_PR = "orphan_pr"                  # PR exists, no ledger entry
    ORPHAN_LEDGER = "orphan_ledger"          # ledger entry, no PR
    DUPLICATE = "duplicate"                  # two PRs for one key
    DIGEST_MISMATCH = "digest_mismatch"      # PR content changed after verify
    LINK_BROKEN = "link_broken"              # links do not point at each other


@dataclass(frozen=True)
class Finding:
    disagreement: Disagreement
    key: str
    detail: str
    blocks_ref: bool = True


def reconcile(
    *,
    remediations: Sequence[Remediation],
    repo_prs: dict[str, dict[str, Any]],
    ledger_entries: dict[str, dict[str, Any]],
) -> tuple[list[Remediation], list[Finding]]:
    """Compare both systems and quarantine whatever disagrees.

    Runs independently of webhook delivery, because delivery is not a
    transaction. Idempotent: reconciling twice yields the same result.
    """
    out: list[Remediation] = []
    findings: list[Finding] = []

    seen_pr_ids: dict[str, str] = {}

    for r in remediations:
        pr = repo_prs.get(r.pull_request_id or "")
        entry = ledger_entries.get(r.ledger_entry_id or "")
        problem: Optional[Finding] = None

        if r.pull_request_id and r.pull_request_id in seen_pr_ids:
            problem = Finding(
                Disagreement.DUPLICATE, r.idempotency_key,
                f"pull request {r.pull_request_id} is claimed by two remediations "
                f"({seen_pr_ids[r.pull_request_id]} and {r.idempotency_key})",
            )
        elif pr is None and entry is not None:
            problem = Finding(
                Disagreement.ORPHAN_LEDGER, r.idempotency_key,
                "ledger entry has no corresponding pull request; the record "
                "survived and the PR did not, which is the safe direction — "
                "retire the entry rather than acting on it",
                blocks_ref=False,
            )
        elif pr is not None and entry is None:
            problem = Finding(
                Disagreement.ORPHAN_PR, r.idempotency_key,
                "pull request exists with no decision record; an unattributable "
                "agent action must not become mergeable",
            )
        elif pr is not None and entry is not None:
            if pr.get("patch_digest") != r.patch_digest:
                problem = Finding(
                    Disagreement.DIGEST_MISMATCH, r.idempotency_key,
                    "pull request content changed after verification; the "
                    "approved diff is not the diff that would merge",
                )
            elif entry.get("pull_request_id") != r.pull_request_id:
                problem = Finding(
                    Disagreement.LINK_BROKEN, r.idempotency_key,
                    "ledger entry does not point back at this pull request; "
                    "bidirectional linkage is not established",
                )

        if r.pull_request_id:
            seen_pr_ids.setdefault(r.pull_request_id, r.idempotency_key)

        if problem is not None:
            findings.append(problem)
            if r.state in (State.MERGED, State.SUPERSEDED, State.ABANDONED):
                out.append(r)  # terminal states are not reopened
            elif r.state is State.QUARANTINED:
                out.append(replace(r, quarantine_reason=problem.detail))
            else:
                target = State.QUARANTINED if r.state is State.DRAFT else State.STALE
                try:
                    out.append(replace(
                        r.transition(target, reason=problem.disagreement.value),
                        quarantine_reason=problem.detail,
                    ))
                except ImpossibleTransition:
                    out.append(replace(r, quarantine_reason=problem.detail))
            continue

        if r.state in (State.DRAFT, State.QUARANTINED):
            out.append(replace(
                r.transition(State.VERIFIED, reason="reconciled"),
                quarantine_reason=None,
            ))
        else:
            out.append(r)

    return out, findings


# --- out-of-order event handling --------------------------------------------

_EVENT_ORDER = {
    "created": 0,
    "verified": 1,
    "review_requested": 2,
    "approved": 3,
    "merge_authorized": 4,
    "merged": 5,
}


def order_events(events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort delivered events into causal order and drop duplicates.

    A merge event arriving before its creation event is a delivery artifact, not
    a time-travelling merge. Sequence numbers, where present, win over the
    lifecycle ordering because they are authoritative.
    """
    seen: set[tuple[str, str]] = set()
    unique: list[dict[str, Any]] = []
    for e in events:
        ident = (str(e.get("kind", "")), str(e.get("idempotency_key", "")))
        if ident in seen:
            continue
        seen.add(ident)
        unique.append(e)

    return sorted(
        unique,
        key=lambda e: (
            e.get("sequence") if e.get("sequence") is not None else _EVENT_ORDER.get(
                str(e.get("kind", "")), 99
            ),
        ),
    )
