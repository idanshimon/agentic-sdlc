"""Decision-record helpers for the governed decision schema.

Adds the three facts the ledger could not previously answer:

1. WHICH ALTERNATIVES WERE WEIGHED — `rejected_options`. Before this, a
   resolved card persisted only the chosen `resolution_text` + `option_index`,
   so the options an agent actually offered were discarded at persist time even
   though `AmbiguityCard.options` carried them. An auditor asking "why not the
   other option?" could not be answered from the record.

2. WHY THE GATE OPENED — `gate_reason`, a typed queryable enum. `autonomy_ref`
   already carried the specific rule reference; `gate_reason` adds the coarse
   classification an operator feed can group and count by.

3. HOW CONFIDENT THE AGENT WAS — `decision_confidence`, recorded as evidence.

The hard rule enforced by this module's docstring and by
`test_confidence_is_not_a_gate`: confidence is EVIDENCE, never AUTHORITY.
Gating is decided by classification (`ambiguity_class` against
`HARD_GATE_CLASSES`) and autonomy posture. A confident agent does not earn its
way past an invariant class. This is the axis on which this system differs from
platforms that gate on a confidence threshold.

Spec: openspec/changes/adopt-github-native-execution-substrate/specs/ledger/spec.md
"""
from __future__ import annotations

from typing import Iterable, Optional, Sequence

from ledger_core import GateReason, RejectedOption

from .config import HARD_GATE_CLASSES


def collect_rejected_options(
    options: Optional[Sequence],
    chosen_index: Optional[int],
    chosen_text: Optional[str] = None,
) -> list[RejectedOption]:
    """Return every presented option that was NOT selected.

    `options` are `ResolutionOption`s from the ambiguity card. Selection is
    identified by `chosen_index` when supplied; otherwise by matching
    `chosen_text` against each option's resolution. When neither identifies a
    selection we fall back to the card's `recommended` option, mirroring how
    `/approve` resolves `final_text`.

    An empty result is legitimate — a single-option card has no alternatives.
    It MUST NOT be read as missing data.
    """
    if not options:
        return []

    selected: Optional[int] = None
    if chosen_index is not None and 0 <= chosen_index < len(options):
        selected = chosen_index
    elif chosen_text:
        for i, opt in enumerate(options):
            if getattr(opt, "resolution", None) == chosen_text:
                selected = i
                break
    if selected is None:
        for i, opt in enumerate(options):
            if getattr(opt, "recommended", False):
                selected = i
                break

    rejected: list[RejectedOption] = []
    for i, opt in enumerate(options):
        if i == selected:
            continue
        rejected.append(
            RejectedOption(
                resolution=getattr(opt, "resolution", "") or "",
                rationale=getattr(opt, "rationale", "") or "",
                option_index=i,
                recommended=bool(getattr(opt, "recommended", False)),
            )
        )
    return rejected


def classify_gate_reason(
    ambiguity_class: Optional[str],
    *,
    had_precedent: bool = True,
    autonomy_says_gate: bool = False,
) -> GateReason:
    """Classify WHY a gate opened.

    Precedence is deliberate and must not be reordered: an invariant class is
    reported as `invariant_class` even when other reasons also apply, because
    that is the reason a human cannot override. Reporting a PHI gate as
    `low_precedent` would understate why it is unbypassable.
    """
    if ambiguity_class and ambiguity_class in HARD_GATE_CLASSES:
        return "invariant_class"
    if autonomy_says_gate:
        return "autonomy_tier"
    if not had_precedent:
        return "low_precedent"
    return "autonomy_tier"


def is_hard_gated(ambiguity_class: Optional[str]) -> bool:
    """True when this class can never be auto-resolved or bulk-approved.

    Reads `HARD_GATE_CLASSES` live rather than caching, so an operator widening
    the set takes effect without a restart. The set may be extended by
    environment, never shrunk below `INVARIANT_CLASSES`.
    """
    return bool(ambiguity_class) and ambiguity_class in HARD_GATE_CLASSES


def approval_satisfies_quorum(
    approver_roles: Iterable[str],
    required_approvers: int,
    must_include_roles: Iterable[str],
) -> tuple[bool, str]:
    """Evaluate an approval set against a bundle's declared quorum policy.

    The policy lives in `standards-bundles/<dept>/<version>/reviewers.yaml`,
    which declares per `blast_class` a `required_approvers` count and
    `must_include_roles`. GitHub Environments cannot express this: they accept
    ONE approval from up to six reviewers, with no role binding and no N-of-M
    quorum. So a GitHub approval is ONE CONTRIBUTING SIGNATURE and never
    satisfaction of the quorum — this function is the authority.

    Returns `(satisfied, reason)`; `reason` is empty when satisfied.
    """
    roles = [r for r in approver_roles if r]
    distinct = set(roles)

    missing = [r for r in must_include_roles if r and r not in distinct]
    if missing:
        return False, f"missing required role(s): {', '.join(sorted(missing))}"

    if len(roles) < required_approvers:
        return False, (
            f"quorum not met: {len(roles)} of {required_approvers} required approvers"
        )

    return True, ""
