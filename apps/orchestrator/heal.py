"""Self-heal cowork — action types, heal-session data models, and the safety
validator.

This is the DECISION-INDEPENDENT safety kernel for the add-self-heal-cowork
openspec change. It is true regardless of which runtime ends up executing
heals (GitHub Copilot SDK vs Foundry agent — that fork is still open). What is
NOT open is the safety contract every heal must pass through, which is what
this module enforces:

  1. Every write-causing heal action requires explicit per-action human
     approval (spec: "Every heal action MUST require explicit per-action
     human approval").
  2. PHI-class and explicit-deny heals are hard-blocked at the validator,
     regardless of session state, human approval, or envelope config
     (spec: "PHI-class and explicit-deny rules MUST never be auto-healed").
  3. Heals are pinned to the ledger as a typed decision class with a shared
     heal_id chain (spec: "Heal decisions MUST be pinned to the ledger as a
     typed decision class").

The validator reuses INVARIANT_CLASSES from ledger_core so the PHI/auth block
is the SAME hard boundary the orchestrator already enforces — not a parallel
list that could drift out of sync.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

# Reuse the orchestrator's single source of truth for invariant (never-auto)
# classes rather than redeclaring. phi-classification + auth-policy.
try:
    from ledger_core.models import INVARIANT_CLASSES
except Exception:  # pragma: no cover - fallback if import path differs at runtime
    INVARIANT_CLASSES = {"phi-classification", "auth-policy"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid() -> str:
    return str(uuid4())


# --- heal action vocabulary ---------------------------------------------------
class HealActionType(str, Enum):
    """The bounded surgery a Cowork agent may propose. Each maps to a row in
    the proposal's action table.
    """
    RERUN_STAGE = "rerun_stage"        # re-run a failed stage, same inputs (idempotent)
    REPROMPT_STAGE = "reprompt_stage"  # bump a prompt-library version + re-run
    ASSIGN_CODE_HEAL = "assign_code_heal"  # hand a code fix to the GitHub coding agent (opens a PR)
    BUMP_BUNDLE_RULE = "bump_bundle_rule"  # propose a standards-bundle change (committee merges)
    ADJUST_AUTOPILOT = "adjust_autopilot"  # tune a confidence threshold (finops envelope; PHI never)


# Every heal action causes a write somewhere, so EVERY action requires human
# approval. This set exists to make that explicit and to fail closed if a new
# action type is added without a deliberate decision about its approval needs.
WRITE_CAUSING_ACTIONS: set[HealActionType] = {
    HealActionType.RERUN_STAGE,
    HealActionType.REPROMPT_STAGE,
    HealActionType.ASSIGN_CODE_HEAL,
    HealActionType.BUMP_BUNDLE_RULE,
    HealActionType.ADJUST_AUTOPILOT,
}

# Actions that mutate code MUST land as a PR via the executor, never a direct
# commit. Used by the executor boundary + asserted in tests.
CODE_MUTATING_ACTIONS: set[HealActionType] = {
    HealActionType.ASSIGN_CODE_HEAL,
}


# --- heal trigger -------------------------------------------------------------
class HealTrigger(str, Enum):
    """A heal session may ONLY be opened at one of these two human-invoked
    moments. There is no scheduled/daemon trigger — that's add-pipeline-doctor.
    """
    AT_GATE = "at_gate"            # run paused at resolver or design_review gate
    AT_RUN_END = "at_run_end"      # run reached completed or failed


# --- the proposed action ------------------------------------------------------
class HealAction(BaseModel):
    """A single concrete heal the Cowork agent proposes. Carries everything the
    validator needs to make an allow/block/escalate decision WITHOUT executing
    anything.
    """
    action_type: HealActionType
    # human-readable effect, shown in the session before approval
    summary: str
    # the rule/class this heal touches, if any (drives the PHI/deny block).
    # e.g. "phi-classification", "auth-policy", "sla-binding", or None for
    # pure code/rerun heals that touch no governed rule.
    target_class: Optional[str] = None
    # a deny-rule pattern this heal would loosen, if any (e.g. "deny/*").
    # Presence of a deny target is an automatic block.
    target_rule_pattern: Optional[str] = None
    # whether the heal would alter a rule explicitly carrying phi: true
    touches_phi_rule: bool = False
    # the stage this heal targets, when applicable
    stage: Optional[str] = None
    # free-form payload the executor will need (prompt id, PR title, etc.)
    # kept opaque here — the validator does not inspect it.
    payload: dict = Field(default_factory=dict)


# --- validator result ---------------------------------------------------------
class HealValidationOutcome(str, Enum):
    ALLOW_WITH_APPROVAL = "allow_with_approval"  # may proceed AFTER human approves
    BLOCK = "block"                              # hard-blocked, no path forward
    ESCALATE = "escalate"                        # convert to human-authored standards change


class HealValidationResult(BaseModel):
    outcome: HealValidationOutcome
    reason: str
    # always True for ALLOW_WITH_APPROVAL — encodes that NOTHING auto-applies
    requires_human_approval: bool = True
    # set when outcome == ESCALATE: where the human must go instead
    escalation_path: Optional[str] = None


# --- heal-session ledger chain models -----------------------------------------
# These three share a heal_id so the chain is queryable:
#   heal_proposed (agent) -> heal_decided (human) -> heal_executed (executor)
class HealProposal(BaseModel):
    heal_id: str = Field(default_factory=_uuid)
    run_id: str
    team_id: str
    trigger: HealTrigger
    action: HealAction
    # precedent the agent cited (prior heal_executed ledger entry ids)
    precedent_refs: list[str] = Field(default_factory=list)
    diagnosis: str = ""
    proposed_at: str = Field(default_factory=_now)


class HealDecision(BaseModel):
    heal_id: str
    # the human who approved/declined — m365 UPN
    approver_id: str
    approved: bool
    note: str = ""
    decided_at: str = Field(default_factory=_now)


class HealExecution(BaseModel):
    heal_id: str
    # what actually landed — a PR url for code heals, a re-run run_id, etc.
    result_ref: str
    success: bool
    detail: str = ""
    executed_at: str = Field(default_factory=_now)


# --- the validator (the safety kernel) ----------------------------------------
def validate_heal_action(action: HealAction) -> HealValidationResult:
    """The single safety chokepoint every heal passes through BEFORE it is
    shown to the human for approval.

    Order of checks (most-restrictive first — fail closed):
      1. PHI-touching heals  -> BLOCK / ESCALATE (never auto-healed)
      2. Invariant-class targets (phi-classification, auth-policy) -> ESCALATE
      3. Explicit-deny rule patterns -> BLOCK (deny rules cannot be loosened)
      4. Everything else -> ALLOW_WITH_APPROVAL (still needs human approval)

    This function NEVER returns a result that bypasses human approval. The
    most permissive outcome is ALLOW_WITH_APPROVAL.
    """
    # 1 + 2: PHI is the hardest boundary. A heal that touches a phi:true rule,
    # or targets an invariant class, can never be auto-applied. It becomes a
    # human-authored standards change instead.
    if action.touches_phi_rule or action.target_class == "phi-classification":
        return HealValidationResult(
            outcome=HealValidationOutcome.ESCALATE,
            reason=(
                "Heal touches a PHI-classified rule. PHI rules can never be "
                "auto-healed; this must become a human-authored standards change."
            ),
            requires_human_approval=True,
            escalation_path="standards-change",
        )

    if action.target_class in INVARIANT_CLASSES:
        return HealValidationResult(
            outcome=HealValidationOutcome.ESCALATE,
            reason=(
                f"Heal targets invariant class '{action.target_class}'. "
                "Invariant-class rules route through a human-authored standards change."
            ),
            requires_human_approval=True,
            escalation_path="standards-change",
        )

    # 3: explicit-deny rules can never be loosened by a heal.
    if action.target_rule_pattern and action.target_rule_pattern.startswith("deny/"):
        return HealValidationResult(
            outcome=HealValidationOutcome.BLOCK,
            reason=(
                f"Heal would modify an explicit-deny rule "
                f"('{action.target_rule_pattern}'). Deny rules cannot be loosened "
                "by a heal under any circumstances."
            ),
            requires_human_approval=True,
        )

    # 4: allowed — but ALWAYS behind explicit human approval. Nothing here
    # auto-applies.
    return HealValidationResult(
        outcome=HealValidationOutcome.ALLOW_WITH_APPROVAL,
        reason="Heal is within bounds; requires explicit human approval before execution.",
        requires_human_approval=True,
    )


def assert_human_invoked(trigger: HealTrigger, run_status: str) -> None:
    """Guard: a heal session may only be opened at a gate or at run end.

    Raises ValueError if the (trigger, run_status) combination is not a valid
    human-invoked moment. This enforces the spec invariant that no heal session
    is created on a schedule or from a drift signal alone.
    """
    if trigger == HealTrigger.AT_RUN_END:
        if run_status not in ("completed", "failed"):
            raise ValueError(
                f"AT_RUN_END heal requires a terminal run (completed/failed); "
                f"got status='{run_status}'."
            )
    elif trigger == HealTrigger.AT_GATE:
        if run_status != "awaiting_gate":
            raise ValueError(
                f"AT_GATE heal requires a run paused at a gate (awaiting_gate); "
                f"got status='{run_status}'."
            )
    else:  # pragma: no cover - exhaustive
        raise ValueError(f"Unknown heal trigger: {trigger}")
