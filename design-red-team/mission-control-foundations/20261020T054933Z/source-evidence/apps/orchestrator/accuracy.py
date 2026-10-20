"""Read-time `accuracy_score` projection for autonomy precedents.

Why this module exists
----------------------
`LedgerEntry.accuracy_score` was declared in two models, defaulted to 0.0, read
in exactly one place, and assigned by nothing. The consequence was live in
`main.py`: a rule with `mode: autopilot_above_threshold` compares the score to
its threshold, so a structurally-zero score meant that mode **always gated**. It
was dead code wearing a working mode's name — the config plane accepted it, the
docs described it, operators could select it, and it never once granted
autonomy.

That failure is *safe*, which is why it survived so long. But a governance
control that cannot fire is not conservative, it is absent, and a threshold an
operator tunes with no effect is worse than no threshold at all.

Why read-time and not materialised
----------------------------------
Nothing here writes to the ledger. `replay.py` states the constraint this obeys:

    A replay NEVER writes to the decision ledger. Scoring is a read-only
    projection; inventing ledger rows to make a metric look populated would
    corrupt the audit substrate this system exists to protect.

A stored score would also be stale by construction — it would reflect the
agreement record at write time, not at the moment autonomy is being decided.
The question is "should this be autopiloted *now*", so it is computed now.

Why it reuses replay.py rather than scoring independently
---------------------------------------------------------
The autonomy gate and the operator-facing replay report must never disagree
about the same history. A second scorer with slightly different semantics would
let one grant autonomy while the other reported the class as failing, and an
operator would have no way to tell which was lying. `score_replay`,
`cases_from_ledger` and `_equivalent` are used unchanged.

Every honesty constraint here points the same direction: when in doubt, gate.
"""
from __future__ import annotations

import logging
from typing import Any, Optional, Sequence

from .replay import DEFAULT_POLICY, ReplayPolicy, cases_from_ledger, score_replay

_logger = logging.getLogger("orchestrator.accuracy")


def project_accuracy_score(
    entries: Sequence[dict[str, Any]],
    *,
    team_id: str,
    ambiguity_class: str,
    policy: Optional[ReplayPolicy] = None,
) -> float:
    """Agreement rate of prior autopilot decisions for one (team, class).

    Returns a value in [0.0, 1.0]. Returns **0.0** — which gates — for every
    condition where the evidence does not clearly support autonomy:

      * fewer than `policy.min_samples` scored cases (a perfect 4-for-4 record
        scores 0.0, not 1.0; that is the point)
      * no scored cases at all
      * the class is an invariant, however well it scores
      * any failure computing the projection

    Pure: does not mutate `entries` and performs no I/O.
    """
    pol = policy or DEFAULT_POLICY

    # An invariant is never eligible for autonomy, regardless of its record.
    # Checked FIRST so a perfect history can never bypass it.
    if pol.is_invariant(ambiguity_class):
        return 0.0

    try:
        scoped = [
            e
            for e in entries
            if isinstance(e, dict)
            and e.get("team_id") == team_id
            and e.get("ambiguity_class") == ambiguity_class
        ]
        if not scoped:
            return 0.0

        report = score_replay(cases_from_ledger(scoped), policy=pol)
        cls = report.classes.get(ambiguity_class)
        if cls is None:
            return 0.0

        # Below the evidence bar, report 0.0 rather than a flattering rate
        # computed from a handful of samples. ClassScore returns None here for
        # the same reason; None must become 0.0 (gate), never be read as
        # "no disagreements".
        if cls.scored < pol.min_samples:
            return 0.0

        return cls.agreements / cls.scored
    except Exception as exc:  # noqa: BLE001
        # A partially-failed computation must never leak into the autonomy path
        # as a passing score. Gate, and say so.
        _logger.warning(
            "accuracy projection failed for %s/%s: %s — gating",
            team_id, ambiguity_class, exc,
        )
        return 0.0
