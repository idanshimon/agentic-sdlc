"""Domain models for Pipeline Doctor.

All Pydantic v2. Pure data — no I/O.
"""
from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid() -> str:
    return str(uuid4())


# --- drift signals -----------------------------------------------------------
class DriftSignalKind(str, Enum):
    AUTOPILOT_REJECTION_RATE_HIGH = "autopilot_rejection_rate_high"
    COST_PER_DECISION_CLIMBING = "cost_per_decision_climbing"
    CLASS_DRIFT_UNEXPECTED = "class_drift_unexpected"
    BUNDLE_RULE_UNUSED = "bundle_rule_unused"
    PHI_CLASS_VIOLATION = "phi_class_violation"


class DriftSignal(BaseModel):
    """A single drift signal surfaced by the detector."""
    id: str = Field(default_factory=_uuid)
    kind: DriftSignalKind
    detected_at: str = Field(default_factory=_now)
    bundle_ref: Optional[str] = None         # e.g. "security/v0.1.0/PHI-001"
    team_id: Optional[str] = None            # None = cross-team aggregate
    stage: Optional[str] = None              # e.g. "codegen"
    ambiguity_class: Optional[str] = None
    metric_value: Optional[float] = None     # the observed value
    metric_baseline: Optional[float] = None  # the baseline it deviates from
    sample_size: int = 0                     # how many ledger entries informed this
    evidence_entry_ids: List[str] = Field(default_factory=list)  # supporting ledger entries
    description: str = ""                    # human-readable summary


# --- envelope validation -----------------------------------------------------
class EnvelopeViolation(BaseModel):
    """Why a proposed auto-fix was rejected by the envelope validator."""
    reason: Literal[
        "phi_rule_forbidden",
        "deny_pattern_forbidden",
        "out_of_bounds",
        "preconditions_unmet",
        "rule_not_in_envelope",
        "rate_limit_exceeded",
    ]
    detail: str = ""


class EnvelopeCheck(BaseModel):
    """Result of validating an auto-fix proposal against a bundle's envelope."""
    allowed: bool
    violations: List[EnvelopeViolation] = Field(default_factory=list)


# --- auto-fix proposal -------------------------------------------------------
class AutoFixProposal(BaseModel):
    """An auto-fix the Doctor wants to apply, awaiting envelope validation."""
    id: str = Field(default_factory=_uuid)
    triggered_by: str  # drift signal id
    bundle_ref: str    # e.g. "finops/v0.1.0/AUTOPILOT-THRESHOLD"
    rule_id: str       # e.g. "AUTOPILOT-THRESHOLD"
    field_path: str    # e.g. "autopilot.threshold.auth-policy"
    current_value: Any
    proposed_value: Any
    rationale: str
    team_id: Optional[str] = None  # None = applies cluster-wide
    expected_impact: str = ""


# --- change proposal (becomes a PR) -----------------------------------------
class BlastClass(str, Enum):
    LOW = "LOW"
    MED = "MED"
    HIGH = "HIGH"


class ChangeProposal(BaseModel):
    """A change proposal that goes through the standards-change committee loop."""
    id: str = Field(default_factory=_uuid)
    triggered_by: str  # drift signal id
    dept: str          # "security" | "architect" | "privacy" | "finops"
    rule_id: str
    blast_class: BlastClass
    summary: str       # one-line: "PHI-001 retention extended to 8 years"
    rationale: str     # full multi-paragraph reasoning
    proposed_diff: str # the actual rules.yaml change as a unified diff
    drift_evidence: DriftSignal
    suggested_reviewers: List[str] = Field(default_factory=list)


# --- detector run summary ----------------------------------------------------
class DoctorRunSummary(BaseModel):
    """Output of one Doctor pass."""
    run_id: str = Field(default_factory=_uuid)
    started_at: str = Field(default_factory=_now)
    finished_at: Optional[str] = None
    signals_detected: int = 0
    auto_fixes_applied: int = 0
    auto_fixes_rejected: int = 0
    change_proposals_opened: int = 0
    errors: List[str] = Field(default_factory=list)
    dry_run: bool = False
