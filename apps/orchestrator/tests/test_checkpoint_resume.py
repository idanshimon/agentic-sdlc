from apps.orchestrator.models import RunState, RunStatus, Stage
from apps.orchestrator.recovery import checkpoint, plan_recovery


def test_completed_checkpoint_resumes_next_stage():
    run = RunState(cursor_stage=Stage.CODEGEN, cursor_state="completed")
    plan = plan_recovery(run)
    assert plan.action == "resume"
    assert plan.stage == Stage.REVIEW_SCAN


def test_awaiting_gate_remains_waiting_after_restart():
    run = RunState(
        status=RunStatus.AWAITING_GATE,
        cursor_stage=Stage.RESOLVER,
        cursor_state="awaiting_gate",
        pending_gate={"gate_id": "g1", "version": 2, "status": "open"},
    )
    plan = plan_recovery(run)
    assert plan.action == "await_gate"
    assert plan.stage == Stage.RESOLVER


def test_terminal_run_never_resumes():
    run = RunState(status=RunStatus.COMPLETED, cursor_stage=Stage.DELIVER, cursor_state="completed")
    assert plan_recovery(run).action == "none"


def test_checkpoint_advances_versions():
    run = RunState(run_version=4, checkpoint_version=7)
    checkpoint(run, Stage.ARCHITECT, "completed")
    assert run.cursor_stage == Stage.ARCHITECT
    assert run.run_version == 5
    assert run.checkpoint_version == 8
