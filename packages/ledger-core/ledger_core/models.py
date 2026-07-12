"""Decision Ledger — typed schema, runtime + meta entries.

v0.7 extends the v0.6 ledger schema with:
- entry_type discriminator (runtime | meta)
- bundle_refs for per-bundle attribution
- agent_session_id for cross-runtime audit (GH audit log xref)
- meta-only fields for standards-change merges
- A365 actor attribution

Backward compatible with v0.6 entries (entry_type defaults to "runtime").

Spec refs:
  * openspec/changes/extend-ledger-runtime-meta-entries/specs/ledger/spec-delta.md
  * AGENTS.md ledger contract section
"""
from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid() -> str:
    return str(uuid4())


# --- shared vocab ------------------------------------------------------------
EntryType = Literal["runtime", "meta"]
BlastClass = Literal["LOW", "MED", "HIGH"]
ActorKind = Literal["human", "agent"]
PHIClass = Literal["none", "low", "high"]
RuntimeKind = Literal[
    "stage_decision",       # orchestrator stage decision
    "ide_session_summary",  # SessionEnd hook output
    "ide_tool_call",        # PostToolUse hook output
    "auto_fix",             # pipeline-doctor auto-fix
    "delivered",            # deliver stage success (PR opened)
    "plan_proposed",        # Plan Mode capture
    "phi_block",            # pre-tool-use hook blocked a write
    "heal_proposed",        # self-heal cowork: agent proposed a heal (add-self-heal-cowork)
    "heal_decided",         # self-heal cowork: human approved/declined a heal
    "heal_executed",        # self-heal cowork: executor landed the heal (PR/re-run)
    "review_remediation",   # autonomous review loop: one bounded remediation attempt
    "loop_converged",       # autonomous review loop: terminal PASS (merged or awaiting)
    "loop_escalated",       # autonomous review loop: terminal escalation to a human
]
MetaKind = Literal[
    "bundle_change_merged",
    "bundle_canary_started",
    "bundle_canary_promoted",
    "bundle_canary_reverted",
]


# --- ambiguity classes (legacy, preserved) -----------------------------------
AmbiguityClass = Literal[
    "phi-classification", "scope-resolution", "sla-binding", "identifier-format",
    "auth-policy", "data-retention", "naming-convention", "other",
]
DecisionKind = Literal["accept", "swap", "reject", "auto-deferred"]
LedgerStatus = Literal["suggest", "shadow", "silent_apply", "demoted"]
INVARIANT_CLASSES: set[str] = {"phi-classification", "auth-policy"}


# --- attribution sub-models --------------------------------------------------
class Actor(BaseModel):
    """Who took the action — human (M365 UPN) or agent (A365 principal)."""
    kind: ActorKind
    id: str  # m365 UPN for humans, a365_principal_id for agents
    display_name: Optional[str] = None


class ReviewerAttribution(BaseModel):
    """For meta entries: who approved a standards change."""
    actor: Actor
    role: str  # "security_lead", "privacy_dpo", etc — from reviewers.yaml
    approved_at: str
    review_kind: Literal["approved", "approved_with_comments"] = "approved"


class CanaryMetrics(BaseModel):
    """For meta entries: metrics observed during the canary period."""
    canary_start: str
    canary_end: Optional[str] = None
    teams_pinned_count: int = 0
    rejection_rate_delta: Optional[float] = None  # vs pre-canary baseline
    cost_delta_pct: Optional[float] = None
    drift_signals_emitted: int = 0
    decision: Optional[Literal["promote", "revert", "extend"]] = None


# --- the entry itself --------------------------------------------------------
class LedgerEntry(BaseModel):
    model_config = {"protected_namespaces": ()}

    """Decision Ledger row — runtime OR meta.

    The discriminator is `entry_type`. Validation enforces required fields per type.
    """
    # core identity (every entry)
    id: str = Field(default_factory=_uuid)
    team_id: str  # partition key
    entry_type: EntryType = "runtime"
    created_at: str = Field(default_factory=_now)
    actor: Actor

    # the decision itself
    decision: str  # one-line summary
    rationale: str = ""  # full reasoning
    cost_usd: float = 0.0
    model_used: Optional[str] = None

    # cross-cutting attribution
    bundle_refs: List[str] = Field(default_factory=list)  # ["security/v0.1.0/PHI-001", ...]
    precedent_refs: List[str] = Field(default_factory=list)  # prior ledger entry IDs
    phi_class: PHIClass = "none"
    # config-plane (add-configuration-plane Phase 2): structured citation for the
    # autonomy rule that governed this decision — WHY autopilot vs gate. Read by
    # the Phase 5 compliance query. Empty on pre-Phase-2 / non-decision entries.
    autonomy_ref: str = ""

    # GitHub audit log cross-reference (set on Agent-HQ-driven entries)
    agent_session_id: Optional[str] = None
    gh_audit_xref: Optional[str] = None

    # ------------- runtime-only fields ----------------------
    run_id: Optional[str] = None        # orchestrator run id
    stage: Optional[str] = None          # stage name (orchestrator) or null (IDE/agent-hq)
    runtime_kind: Optional[RuntimeKind] = None
    # legacy v0.6 fields (preserved for backward compat)
    card_id: Optional[str] = None
    ambiguity_class: Optional[AmbiguityClass] = None
    slot_value_hash: Optional[str] = None
    resolution_text: Optional[str] = None
    decision_kind: Optional[DecisionKind] = None
    status: Optional[LedgerStatus] = None
    sample_count: int = 1
    accuracy_score: float = 0.0
    created_by: Optional[str] = None  # legacy field; use actor.id going forward
    precedent_id: Optional[str] = None
    confidence_source: Optional[Literal["human", "autopilot"]] = None
    pr_url: Optional[str] = None  # set on `delivered` runtime entries
    # self-heal cowork (add-self-heal-cowork): ties heal_proposed → heal_decided
    # → heal_executed into one queryable chain. Null on non-heal entries.
    heal_id: Optional[str] = None

    # ------------- meta-only fields -------------------------
    meta_kind: Optional[MetaKind] = None
    change_ticket_id: Optional[str] = None
    bundle_version_from: Optional[str] = None  # "security/v0.1.0"
    bundle_version_to: Optional[str] = None    # "security/v0.1.1"
    blast_class: Optional[BlastClass] = None
    reviewers: List[ReviewerAttribution] = Field(default_factory=list)
    canary_metrics: Optional[CanaryMetrics] = None
    pr_url_meta: Optional[str] = None  # standards-bundles PR (separate field to disambiguate)

    @model_validator(mode="after")
    def _validate_entry_type(self) -> "LedgerEntry":
        """Enforce per-entry-type required/forbidden fields."""
        if self.entry_type == "meta":
            missing = []
            if not self.change_ticket_id:
                missing.append("change_ticket_id")
            if not self.bundle_version_from:
                missing.append("bundle_version_from")
            if not self.bundle_version_to:
                missing.append("bundle_version_to")
            if not self.blast_class:
                missing.append("blast_class")
            if not self.reviewers:
                missing.append("reviewers")
            if missing:
                raise ValueError(
                    f"meta entry missing required fields: {missing}"
                )
            forbidden = []
            if self.run_id is not None:
                forbidden.append("run_id")
            if self.stage is not None:
                forbidden.append("stage")
            if forbidden:
                raise ValueError(
                    f"meta entry must not set: {forbidden}"
                )
        elif self.entry_type == "runtime":
            # at least one source attribution required
            if self.run_id is None and self.agent_session_id is None:
                raise ValueError(
                    "runtime entry requires at least one of: run_id, agent_session_id"
                )
        return self


# --- query helpers (as data, not Cosmos calls) -------------------------------
def is_phi_change(entry: LedgerEntry) -> bool:
    """A meta entry is PHI-class if any bundle_ref points at a PHI rule."""
    if entry.entry_type != "meta":
        return False
    return any(":phi:" in r or "/PHI-" in r for r in entry.bundle_refs)


def has_high_blast(entry: LedgerEntry) -> bool:
    return entry.entry_type == "meta" and entry.blast_class == "HIGH"


# --- back-compat: promote v0.6-shape dicts to LedgerEntry --------------------
def from_legacy_v06_dict(d: Dict[str, Any]) -> LedgerEntry:
    """Promote a v0.6 ledger entry dict to a v0.7 LedgerEntry.

    v0.6 entries lack `entry_type` (default "runtime"), `actor` (synthesized
    from `created_by`), and `bundle_refs` (default empty — backfilled by Doctor).
    """
    d = dict(d)  # copy

    # entry_type default
    d.setdefault("entry_type", "runtime")

    # Cross-model write compatibility (2026-06-21): the orchestrator's OWN
    # LedgerEntry model (apps/orchestrator/models.py) serializes its optional
    # heal fields `decision` and `rationale` as explicit JSON null when they're
    # unset (which is every non-heal stage_decision / swap entry). ledger_core's
    # LedgerEntry requires `decision` to be a non-null string and `rationale` to
    # be a string. A present-but-null value bypasses `setdefault`/`not in`
    # backfills below, so `LedgerEntry(**d)` raised ValidationError — which
    # find_precedent swallowed in its except, returning None. THAT silently
    # killed the teaching loop: every operator swap was unreadable as precedent.
    # Drop null-valued keys so the synthesis/defaults below take over.
    for _k in ("decision", "rationale"):
        if _k in d and d[_k] is None:
            del d[_k]

    # synthesize actor from legacy created_by + confidence_source
    if not d.get("actor"):
        legacy_id = d.get("created_by", "unknown")
        legacy_conf = d.get("confidence_source", "human")
        kind: ActorKind = "agent" if legacy_conf == "autopilot" else "human"
        d["actor"] = {"kind": kind, "id": legacy_id, "display_name": None}

    # required: decision (synthesize from resolution_text or decision_kind)
    if not d.get("decision"):
        if d.get("resolution_text"):
            d["decision"] = d["resolution_text"][:120]
        elif d.get("decision_kind"):
            d["decision"] = f"{d['decision_kind']} on {d.get('ambiguity_class', 'unknown')}"
        else:
            d["decision"] = "(legacy v0.6 entry)"

    # required: runtime_kind for runtime entries
    if d["entry_type"] == "runtime" and "runtime_kind" not in d:
        d["runtime_kind"] = "stage_decision"

    # ensure bundle_refs exists
    d.setdefault("bundle_refs", [])

    # required for runtime: at least run_id
    if d["entry_type"] == "runtime" and not d.get("run_id") and not d.get("agent_session_id"):
        d["run_id"] = "legacy-unknown"

    return LedgerEntry(**d)
