from apps.orchestrator.main import _generators_from_stage
from apps.orchestrator.models import RunState, Stage


def test_recovery_generators_start_at_requested_stage_without_ingest_replay():
    run = RunState()
    generators = _generators_from_stage(run, "prd", Stage.REVIEW_SCAN)
    assert [stage for stage, _ in generators] == [Stage.REVIEW_SCAN, Stage.DELIVER]


def test_recovery_after_resolver_starts_at_architect():
    run = RunState()
    generators = _generators_from_stage(run, "prd", Stage.ARCHITECT)
    assert [stage for stage, _ in generators] == [
        Stage.ARCHITECT, Stage.TEST_PLAN, Stage.CODEGEN, Stage.REVIEW_SCAN, Stage.DELIVER,
    ]
