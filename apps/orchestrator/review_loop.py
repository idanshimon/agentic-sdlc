"""review_loop — the bounded autonomous review→remediate→re-review controller.

This is the "smart layer" above the deterministic CI floor (PR-1). Given a
structured ReviewVerdict (PR-2), it decides the next action, bounded by:

  * a per-repo autonomy tier (A=auto-merge, B=auto-review/human-merge,
    C=advisory) — the "move the dial per repo" control;
  * a hard attempt ceiling (MAX_ATTEMPTS) so an unreliable model can never
    thrash or loop unbounded — it escalates to a human instead;
  * a per-run cost ceiling;
  * a PHI/deny FLOOR that forces human escalation regardless of tier, attempt,
    or cost — PHI/auth/deny changes are NEVER inside the autonomous envelope.

The `plan_next_loop_action` function is PURE (zero I/O) so the entire policy is
unit-testable as a truth table. The async `run_review_loop` glue (separate) is
the only part that touches the ledger / GitHub.

Design invariants (openspec/changes/add-autonomous-review-loop):
  - Never a silent merge: MERGE only on a Tier-A PASS with no PHI/deny.
  - Absence = safe: an unknown/unlisted tier degrades to COMMENT_ONLY.
  - Model variance is CONTAINED (bound + escalation), not solved.
"""
from __future__ import annotations

import enum
import os
from typing import Optional

from .models import ReviewVerdict

# Hard attempt ceiling. Env may LOWER it; a value < 1 is rejected (unbounded
# loops are never permitted). Default 3 — cheap, escalates fast.
try:
    _env_max = int(os.environ.get("REVIEW_LOOP_MAX_ATTEMPTS", "3"))
except ValueError:
    _env_max = 3
MAX_ATTEMPTS: int = max(1, _env_max)

# Per-run cost ceiling in USD. A loop that would exceed it escalates.
try:
    COST_CEILING_USD: float = float(os.environ.get("REVIEW_LOOP_COST_CEILING_USD", "5.0"))
except ValueError:
    COST_CEILING_USD = 5.0


class LoopAction(str, enum.Enum):
    REMEDIATE = "remediate"                 # dispatch bounded codegen remediation
    MERGE = "merge"                         # Tier-A auto-merge, human-out
    AWAIT_HUMAN_MERGE = "await_human_merge" # Tier-B: passed, human clicks merge
    COMMENT_ONLY = "comment_only"           # Tier-C / unlisted: advisory only
    ESCALATE = "escalate"                   # exhaustion / cost / PHI floor -> human


_VALID_TIERS = {"A", "B", "C"}


def has_phi_or_deny(verdict: ReviewVerdict) -> bool:
    """True if any blocker is a PHI rule or an explicit-deny pattern.

    These can never be auto-remediated or auto-merged — they force escalation.
    """
    for b in verdict.blockers:
        if b.phi:
            return True
        # explicit-deny convention: a rule id / citation under a deny/* path.
        if "/deny/" in b.rule or b.rule.lower().endswith("-deny"):
            return True
    return False


def plan_next_loop_action(
    verdict: ReviewVerdict,
    *,
    attempt: int,
    tier: str,
    cost_usd: float,
) -> LoopAction:
    """The pure governor. Returns exactly one LoopAction. Order matters:

    1. PHI/deny FLOOR — highest precedence, escalate regardless of anything.
    2. Unknown tier — safe by absence, advisory only.
    3. PASS — merge per tier (A auto, B human, C comment).
    4. FAIL on Tier C — advisory comment, never remediate.
    5. Cost ceiling exceeded — escalate.
    6. Attempt bound reached — escalate (never a silent merge, never unbounded).
    7. FAIL on A/B within bounds — remediate.
    """
    # 1. PHI/deny floor — before tier/attempt/cost are even consulted.
    if verdict.status == "FAIL" and has_phi_or_deny(verdict):
        return LoopAction.ESCALATE

    # 2. Unknown/unlisted tier — never auto-act.
    if tier not in _VALID_TIERS:
        return LoopAction.COMMENT_ONLY

    # 3. PASS — merge behavior by tier.
    if verdict.status == "PASS":
        if tier == "A":
            return LoopAction.MERGE
        if tier == "B":
            return LoopAction.AWAIT_HUMAN_MERGE
        return LoopAction.COMMENT_ONLY  # tier C

    # --- verdict is FAIL (non-PHI) from here ---

    # 4. Tier C never remediates.
    if tier == "C":
        return LoopAction.COMMENT_ONLY

    # 5. Cost ceiling.
    if cost_usd > COST_CEILING_USD:
        return LoopAction.ESCALATE

    # 6. Attempt bound.
    if attempt >= MAX_ATTEMPTS:
        return LoopAction.ESCALATE

    # 7. Within bounds on A/B -> remediate.
    return LoopAction.REMEDIATE


def loop_citation(
    tier: str,
    repo: str,
    action: LoopAction,
    *,
    attempt: int,
    reason: Optional[str] = None,
) -> str:
    """Structured, grep-able citation for the controller's decision, mirroring
    the autonomy_ref/rule_ref convention so the compliance query can filter it.

    Format: reviewloop/<tier>/<repo>/<action>@attempt=<N>[:<reason>]
    """
    base = f"reviewloop/{tier}/{repo}/{action.value}@attempt={attempt}"
    return f"{base}:{reason}" if reason else base


# ---------------------------------------------------------------------------
# Async glue — run_review_loop (the only part that touches remediation/GitHub)
# ---------------------------------------------------------------------------

import dataclasses  # noqa: E402
from typing import Awaitable, Callable  # noqa: E402


@dataclasses.dataclass
class LoopResult:
    outcome: str                       # converged | escalated | awaiting_human_merge | advisory
    merged: bool = False
    attempts: int = 0                  # number of remediation attempts performed
    escalation_reason: Optional[str] = None
    pr_url: Optional[str] = None
    ledger_hops: list[dict] = dataclasses.field(default_factory=list)


# Injected callables (so the loop is testable with zero real codegen / GitHub):
ReviewFn = Callable[[dict], Awaitable[ReviewVerdict]]
RemediateFn = Callable[[ReviewVerdict, dict], Awaitable[dict]]
MergeFn = Callable[[str], Awaitable[str]]


def _hop(kind: str, ref: str, detail: str) -> dict:
    return {"runtime_kind": kind, "autonomy_ref": ref, "detail": detail}


async def run_review_loop(
    *,
    repo: str,
    tier: str,
    code_files: dict,
    review: ReviewFn,
    remediate: RemediateFn,
    do_merge: MergeFn,
    cost_usd: float = 0.0,
) -> LoopResult:
    """Drive review -> plan -> (remediate | merge | escalate) to a terminal state.

    Bounded by MAX_ATTEMPTS and the PHI/deny floor. Records a ledger hop per
    action. `review`, `remediate`, `do_merge` are injected so the pure policy
    (plan_next_loop_action) is what's exercised — no real GitHub in tests.

    Returns a LoopResult with the terminal outcome + the ledger hop chain.
    """
    result = LoopResult(outcome="advisory")
    files = dict(code_files)
    attempt = 1

    while True:
        verdict = await review(files)
        action = plan_next_loop_action(
            verdict, attempt=attempt, tier=tier, cost_usd=cost_usd)

        if action is LoopAction.MERGE:
            pr_url = await do_merge(repo)
            ref = loop_citation(tier, repo, action, attempt=attempt)
            result.ledger_hops.append(_hop("loop_converged", ref, "auto-merged"))
            result.outcome = "converged"
            result.merged = True
            result.pr_url = pr_url
            return result

        if action is LoopAction.AWAIT_HUMAN_MERGE:
            ref = loop_citation(tier, repo, action, attempt=attempt)
            result.ledger_hops.append(_hop("loop_converged", ref, "awaiting human merge"))
            result.outcome = "awaiting_human_merge"
            return result

        if action is LoopAction.COMMENT_ONLY:
            ref = loop_citation(tier, repo, action, attempt=attempt)
            result.ledger_hops.append(_hop("loop_escalated", ref, "advisory comment only"))
            result.outcome = "advisory"
            return result

        if action is LoopAction.ESCALATE:
            reason = _escalation_reason(verdict, attempt, cost_usd)
            ref = loop_citation(tier, repo, action, attempt=attempt, reason=reason)
            result.ledger_hops.append(_hop("loop_escalated", ref, f"escalated: {reason}"))
            result.outcome = "escalated"
            result.escalation_reason = reason
            return result

        # action is REMEDIATE
        ref = loop_citation(tier, repo, action, attempt=attempt)
        result.ledger_hops.append(_hop("review_remediation", ref,
                                       f"remediation attempt {attempt}"))
        files = await remediate(verdict, files)
        result.attempts = attempt
        attempt += 1


def _escalation_reason(verdict: ReviewVerdict, attempt: int, cost_usd: float) -> str:
    if verdict.status == "FAIL" and has_phi_or_deny(verdict):
        return "tier_floor_phi"
    if cost_usd > COST_CEILING_USD:
        return "cost_ceiling"
    if attempt >= MAX_ATTEMPTS:
        return "max_attempts"
    return "unknown"
