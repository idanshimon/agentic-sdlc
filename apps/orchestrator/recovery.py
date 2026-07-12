"""Pure checkpoint planning for bounded restart recovery."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .models import RunState, RunStatus, Stage


PIPELINE_ORDER = [
    Stage.INGEST, Stage.ASSESSOR, Stage.RESOLVER, Stage.ARCHITECT,
    Stage.DESIGN_REVIEW, Stage.TEST_PLAN, Stage.CODEGEN, Stage.REVIEW_SCAN,
    Stage.DELIVER,
]


@dataclass(frozen=True)
class RecoveryPlan:
    action: Literal["resume", "await_gate", "none"]
    stage: Stage | None
    reason: str


def plan_recovery(run: RunState) -> RecoveryPlan:
    if run.status in {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED}:
        return RecoveryPlan("none", None, "run is terminal")
    if run.cursor_state == "awaiting_gate" or run.status == RunStatus.AWAITING_GATE:
        return RecoveryPlan("await_gate", run.cursor_stage, "durable gate remains open")
    if run.cursor_state == "completed" and run.cursor_stage == Stage.DELIVER:
        return RecoveryPlan("none", None, "pipeline cursor is complete")
    try:
        index = PIPELINE_ORDER.index(run.cursor_stage)
    except ValueError:
        return RecoveryPlan("none", None, "unrecognized cursor")
    if run.cursor_state == "completed":
        index += 1
    if index >= len(PIPELINE_ORDER):
        return RecoveryPlan("none", None, "pipeline cursor is complete")
    return RecoveryPlan("resume", PIPELINE_ORDER[index], "resume next incomplete boundary")


def checkpoint(run: RunState, stage: Stage, state: str) -> None:
    run.cursor_stage = stage
    run.cursor_state = state  # type: ignore[assignment]
    run.checkpoint_version += 1
    run.run_version += 1
