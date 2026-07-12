"""Contract tests for mapping and integrity of reviewed GitHub delivery files."""

import asyncio
from unittest.mock import AsyncMock, patch

from apps.orchestrator._pipeline_stages import (
    _artifact_manifest, _delivery_files, stage_deliver,
)
from apps.orchestrator.models import RunState, Stage, StageEvent


def test_delivery_files_use_generated_pytest_not_markdown_test_plan():
    run = RunState(run_id="run-delivery-contract", team_id="team-demo")
    run.events = [
        StageEvent(
            run_id=run.run_id,
            stage="architect",
            status="completed",
            payload={"architecture": "# Architecture"},
        ),
        StageEvent(
            run_id=run.run_id,
            stage="test_plan",
            status="completed",
            payload={"test_plan": "# TEST PLAN"},
        ),
        StageEvent(
            run_id=run.run_id,
            stage="codegen",
            status="completed",
            payload={"app_code": "APP", "test_code": "PYTEST", "code": "LEGACY"},
        ),
    ]

    files = {item["path"]: item["content"] for item in _delivery_files(run)}

    assert files["src/main.py"] == "APP"
    assert files["tests/test_main.py"] == "PYTEST"
    assert files["docs/test-plan.md"] == "# TEST PLAN"
    assert files["tests/test_main.py"] != "# TEST PLAN"


def test_artifact_manifest_is_stable_and_hashes_file_bytes():
    files = [
        {"path": "src/main.py", "content": "print('ok')\n"},
        {"path": "tests/test_main.py", "content": "def test_ok(): pass\n"},
    ]
    first = _artifact_manifest(files)
    second = _artifact_manifest(list(reversed(files)))
    assert first == second
    assert [item["path"] for item in first] == ["src/main.py", "tests/test_main.py"]
    assert all(len(item["sha256"]) == 64 for item in first)


def test_missing_review_manifest_blocks_delivery_before_github():
    run = RunState(run_id="no-review", team_id="team-demo", reviewed_artifact_manifest=[])
    run.events = [StageEvent(
        run_id=run.run_id, stage=Stage.CODEGEN, status="completed",
        payload={"app_code": "print('unreviewed')"},
    )]

    async def collect():
        return [event async for event in stage_deliver(run)]

    with patch("apps.orchestrator.deliver_pr.open_delivery_pr", new_callable=AsyncMock) as opener:
        events = asyncio.run(collect())

    assert events[-1].status == "failed"
    assert events[-1].payload["delivery_status"] == "blocked_unreviewed"
    opener.assert_not_awaited()


def test_delivery_rejects_artifact_drift_after_review():
    run = RunState(run_id="run-drift", team_id="team-demo")
    run.events = [StageEvent(
        run_id=run.run_id, stage="codegen", status="completed",
        payload={"app_code": "ORIGINAL", "test_code": "TESTS"},
    )]
    reviewed = _artifact_manifest(_delivery_files(run))
    run.reviewed_artifact_manifest = reviewed
    # Bytes changed after review, before delivery.
    run.events.append(StageEvent(
        run_id=run.run_id, stage="codegen", status="completed",
        payload={"app_code": "TAMPERED", "test_code": "TESTS"},
    ))

    async def collect():
        return [event async for event in stage_deliver(run)]

    with patch("apps.orchestrator.deliver_pr.open_delivery_pr", new=AsyncMock()) as opener:
        events = asyncio.run(collect())

    assert events[-1].status == "failed"
    assert events[-1].payload["delivery_status"] == "blocked_artifact_drift"
    opener.assert_not_awaited()
