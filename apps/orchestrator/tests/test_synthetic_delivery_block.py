"""Synthetic provider output must never cross the GitHub delivery boundary."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from apps.orchestrator._pipeline_stages import stage_deliver
from apps.orchestrator.models import RunState


def test_delivery_refuses_synthetic_output_before_github_io():
    run = RunState(
        team_id="team-demo",
        contains_synthetic_output=True,
        synthetic_stages=["codegen"],
    )

    async def collect():
        return [event async for event in stage_deliver(run)]

    with patch("apps.orchestrator.deliver_pr.open_delivery_pr", new=AsyncMock()) as opener:
        events = asyncio.run(collect())

    assert len(events) == 1
    assert events[0].status == "failed"
    assert events[0].payload["delivery_status"] == "blocked_synthetic"
    assert events[0].payload["synthetic_stages"] == ["codegen"]
    opener.assert_not_awaited()
