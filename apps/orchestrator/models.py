"""Pydantic models — run state, ambiguity cards, ledger entries, stage events.
See design.md §2 (pipeline graph), §3 (ambiguity card shape), §4 (ledger schema)."""
from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid() -> str:
    return str(uuid4())


# --- pipeline graph (design.md §2) --------------------------------------------
class Stage(str, Enum):
    INGEST = "ingest"
    ASSESSOR = "assessor"
    RESOLVER = "resolver"  # Gate 1 — HITL
    ARCHITECT = "architect"
    DESIGN_REVIEW = "design_review"  # Gate 2 — auto+escalate (human in v1)
    TEST_PLAN = "test_plan"
    CODEGEN = "codegen"
    REVIEW_SCAN = "review_scan"  # Gate 3 — policy, fail-hard
    DELIVER = "deliver"


class RunStatus(str, Enum):
    RUNNING = "running"
    AWAITING_GATE = "awaiting_gate"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RunMode(str, Enum):
    """Per-run autopilot opt-in. See design.md §3 (Resolver gate)."""
    MANUAL = "manual"
    AUTOPILOT = "autopilot"
    HYBRID = "hybrid"


# --- ambiguity / ledger (design.md §3, §4) ------------------------------------
# Closed vocabulary lives in the Assessor; here we capture the shape only.
AmbiguityClass = Literal[
    "phi-classification", "scope-resolution", "sla-binding", "identifier-format",
    "auth-policy", "data-retention", "naming-convention", "other",
]
DecisionKind = Literal["accept", "swap", "reject", "auto-deferred"]
LedgerStatus = Literal["suggest", "shadow", "silent_apply", "demoted"]
# design.md §4: invariant-class entries are non-overridable (write-block).
INVARIANT_CLASSES: set[str] = {
    "phi-classification", "auth-policy",  # PHI + auth treated as invariant in v1
}


class ResolutionOption(BaseModel):
    """One concrete way to resolve an ambiguity. Cards carry 2 — recommended + 1 alternative.

    The Resolver UI surfaces these so Accept actually means "use this specific resolution"
    rather than "I accept that an ambiguity exists." See design.md §3.
    """
    label: str                # short headline, e.g. "HIPAA 7-year retention with audit"
    resolution: str           # 1-2 sentence concrete resolution text
    rationale: str            # one sentence — cites regulation/policy/precedent
    downstream_impact: str    # what Architect/CodeGen will change if this option wins
    recommended: bool = False # exactly one option per card carries this flag


class AmbiguityCard(BaseModel):
    """One Assessor finding. See design.md §3 (Resolver gate)."""
    card_id: str = Field(default_factory=_uuid)
    ambiguity_class: AmbiguityClass = "other"
    slot_value_hash: str = ""
    title: str
    detail: str
    prd_quote: str = ""           # verbatim text from the PRD (≤200 chars)
    prd_section: str = ""         # section heading the quote came from
    gap_description: str = ""     # one-sentence "what is missing"
    options: list[ResolutionOption] = Field(default_factory=list)
    team_occurrence_count: int = 0  # ledger lookups: how many times this team has seen this class
    blast_radius_cost_usd: float = 0.0
    re_run_cost_usd: float = 0.0
    is_gating: bool = True  # False = Bootstrap-Mode auto-deferred (design.md §3)
    is_eligible_for_promotion: bool = False  # True = anti-nudge UX: hide per-card cost
    # Tier-2 governance: True = this card's ambiguity_class is hard-gated
    # (PHI/auth by default) and can NEVER be bulk/soft-approved. Stamped by
    # the orchestrator at card-build time from HARD_GATE_CLASSES so the UI can
    # render the lock badge + exclude it from "Approve all" without a second
    # round-trip. The server independently enforces this (does not trust the
    # flag) — see the /approve handler's bulk-path guard.
    is_hard_gated: bool = False


class LedgerEntry(BaseModel):
    """Decision Ledger row. See design.md §4 typed schema.

    NOTE 2026-06-16: ledger-core's CosmosLedger.write_entry() (in
    packages/ledger-core/ledger_core/cosmos.py) branches on
    entry.entry_type to decide invariant-validation vs pass-through.
    The orchestrator's LedgerEntry model historically had no
    entry_type field, so every /approve call raised AttributeError
    on first reach into the invariant guard. Caught during Phase 0
    live-pipeline verification: per-card POST /api/runs/{id}/approve
    returned 500 even though the gate finalized cleanly via the
    auto-finalize default-recommended path. UI operator-agency
    buttons (Accept/Swap per card) were silently broken in prod.

    Defaulting to "runtime" matches the existing behaviour for every
    stage_decision-style write (which is everything the orchestrator
    emits today). Teaching-signal writes go through a different
    code path (the ledger-mcp tools, not this entry).

    NOTE 2026-06-16 (Phase 2.5): added prompt_resolution_path. When a
    stage writes a ledger entry, this field pins the full inheritance
    chain (team → persona → global) that produced the prompt — including
    the matched scope's prompt_id, version, git_sha, and owner_persona.
    This closes the audit loop: every decision is reproducible because
    we know exactly which prompt version was used at decision time, and
    the YAML files are immutable once published (per openspec Requirement 8).
    Old entries without this field render gracefully ("chain unavailable
    (pre-v2)") in the UI per openspec spec scenario.
    """
    id: str = Field(default_factory=_uuid)
    entry_type: str = "runtime"  # ledger-core write_entry() reads this
    team_id: str  # partition key
    run_id: str
    card_id: str = Field(default_factory=_uuid)  # default for non-card entries (e.g. heal)
    ambiguity_class: AmbiguityClass = "other"    # default for non-card entries
    slot_value_hash: str = ""
    resolution_text: str = ""
    decision_kind: DecisionKind = "accept"       # default for non-card entries
    status: LedgerStatus = "suggest"  # v1: writes only ever land as `suggest` (no promotion)
    sample_count: int = 1
    accuracy_score: float = 0.0
    created_at: str = Field(default_factory=_now)
    created_by: str = "unknown"
    precedent_id: Optional[str] = None  # for back-trace index (design.md §4 demote)
    confidence_source: Literal["human", "autopilot"] = "human"
    # Wire (2026-06-21): bundles the deciding agent subscribes to, resolved from
    # .github/agents/<agent>.agent.md bundle_subscriptions at write time. Closes
    # the agent→bundle gap — previously this was empty and the relationship was
    # display-only. ledger-core's LedgerEntry already has bundle_refs; the
    # orchestrator-local model was missing it (the recurring two-model drift).
    bundle_refs: list[str] = Field(default_factory=list)
    # self-heal cowork (add-self-heal-cowork): heal entries reuse this LedgerEntry
    # with runtime_kind in {heal_proposed, heal_decided, heal_executed} and a
    # shared heal_id tying the chain. These are optional so non-heal entries are
    # unaffected.
    runtime_kind: Optional[str] = None           # heal_proposed | heal_decided | heal_executed | ...
    heal_id: Optional[str] = None                # ties the 3-entry heal chain
    decision: Optional[str] = None               # one-line summary (heal entries)
    rationale: Optional[str] = None              # full reasoning (heal entries)
    actor_kind: Optional[str] = None             # "human" | "agent" (heal entries)
    actor_id: Optional[str] = None               # m365 upn or agent principal (heal entries)
    stage: Optional[str] = None                  # stage the heal targets
    pr_url: Optional[str] = None                 # PR / re-run ref on heal_executed
    precedent_refs: list[str] = Field(default_factory=list)  # cited prior heal ids
    # Phase 2.5: full prompt inheritance chain that produced this decision.
    # Populated by stages that have completed migration to prompt_library_v2;
    # None for legacy entries and for any entry not associated with a
    # specific catalog-resolved prompt (e.g. operator-only resolutions).
    prompt_resolution_path: Optional[list[dict[str, Any]]] = None


# --- stage events / run state -------------------------------------------------
class StageEvent(BaseModel):
    """SSE payload — one event per stage transition or progress tick."""
    run_id: str
    stage: Stage
    status: Literal["started", "progress", "completed", "gate_open", "failed"]
    message: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    ts: str = Field(default_factory=_now)


class Blocker(BaseModel):
    """A single BLOCK-severity finding from the review-scan verdict.

    Machine-consumable — the autonomous review loop (add-autonomous-review-loop)
    reads these programmatically to dispatch bounded remediation to codegen.
    """
    check: str                       # human-readable check name, e.g. "secret-scan"
    rule: str                        # structured citation: <dept>/v<ver>/<rule-id>
    detail: str                      # one-line description of what tripped
    file: str                        # path within the reviewed change
    line: int                        # 1-indexed line number
    phi: bool = False                # true => never inside the auto-remediation envelope


class ReviewVerdict(BaseModel):
    """Structured output of stage_review_scan — replaces the findings=0 stub.

    Chainable across re-reviews via `attempt` + `prior_verdict_ref` so the
    autonomous loop can reconstruct review → remediate → re-review.
    """
    status: Literal["PASS", "FAIL"]
    blockers: list[Blocker] = Field(default_factory=list)
    attempt: int = 1
    prior_verdict_ref: str | None = None


class GateDecision(BaseModel):
    """Approve / reject / demote action on an open gate.

    For card approvals, the client may either:
    - pass `option_index` (0-based into card.options) to accept that specific option
      verbatim — server fills resolution_text from card.options[option_index].resolution
    - pass `resolution_text` directly (for swap with user-authored text)
    - pass neither (server defaults to the recommended option)
    """
    card_id: Optional[str] = None  # None = whole-stage approve
    decision_kind: DecisionKind
    resolution_text: str = ""
    option_index: Optional[int] = None
    gate: Optional[str] = None
    actor: str = "demo-user@hca"
    confidence_source: Literal["human", "autopilot"] = "human"
    # Tier-2 governance (hard-gate): how this decision reached the server.
    # "individual" = operator explicitly decided this one card.
    # "bulk" = swept in by an "Approve all recommended" click. The server
    # REJECTS bulk decisions on hard-gated classes (PHI/auth) with 409 so a
    # client cannot rubber-stamp a class that must be owned explicitly.
    approval_path: Literal["bulk", "individual"] = "individual"


class RunState(BaseModel):
    """Persisted to Cosmos pipeline-runs container, partitioned by run_id.

    Pydantic config: `extra="allow"` so harness-seeded fields like
    `model`, `model_slug`, `namespace`, `source_run_dir`, `original_team_id`,
    `wall_clock_seconds`, `stage_durations_seconds`, `model_routing`,
    `artifact_sizes` survive round-trip through `_ledger.get_run` →
    `RunState.model_validate(doc)`. Without this, the get_run Cosmos
    fallback path silently strips those fields and the /runs/<id> page
    can't show experiment provenance or stage durations.
    """
    model_config = {"extra": "allow"}

    run_id: str = Field(default_factory=_uuid)
    team_id: str = "team-demo"
    prd_blob_url: str = ""
    status: RunStatus = RunStatus.RUNNING
    current_stage: Stage = Stage.INGEST
    cards: list[AmbiguityCard] = Field(default_factory=list)
    decisions: list[GateDecision] = Field(default_factory=list)
    events: list[StageEvent] = Field(default_factory=list)
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)
    # cost telemetry rollups (design.md §7)
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    gate_wall_clock_seconds: float = 0.0
    # autopilot (design.md §3)
    mode: RunMode = RunMode.MANUAL
    previous_mode: Optional[RunMode] = None  # set on /pause, consumed by /resume
    autopilot_overrides: list[str] = Field(default_factory=list)  # card_ids forced to human review
    autopilot_decisions: list[str] = Field(default_factory=list)  # card_ids auto-resolved
    # Per-run stage→provider override. Beats config. Shape:
    #   {"architect": {"provider": "foundry-anthropic", "model": "claude-sonnet-4-6", "via_apim": false}}
    stage_provider_overrides: dict[str, dict] = Field(default_factory=dict)
    # Phase 2.6: per-stage prompt resolution chains. Populated by each
    # stage helper after it calls catalog.resolve(); read by the ledger
    # writers (autopilot in main.py::_drive, per-card in /approve) so
    # every LedgerEntry pins the prompt chain that produced its
    # ambiguity-card recommendation. Keys are stage names ("assessor",
    # "architect", "test_plan", "codegen", "codegen-tests"); values
    # are the chain_as_list() output (list[dict] — JSON-safe).
    prompt_chain_by_stage: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
