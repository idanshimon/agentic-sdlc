"""Startup recovery scanning over durable checkpoints and CAS leases."""
from __future__ import annotations

import logging
from typing import Awaitable, Callable

from .leases import LeaseConflict, acquire_lease
from .models import RunState
from .recovery import RecoveryPlan, plan_recovery

_logger = logging.getLogger("orchestrator.recovery_worker")

ResumeFn = Callable[[RunState, RecoveryPlan], Awaitable[None]]


async def recover_nonterminal_runs(ledger, *, owner: str, resume: ResumeFn) -> dict:
    summary = {"scanned": 0, "leased": 0, "resumed": 0, "awaiting_gate": 0, "skipped": 0}
    for doc in await ledger.query_nonterminal_runs():
        summary["scanned"] += 1
        run = RunState.model_validate(doc)
        plan = plan_recovery(run)
        if plan.action == "none":
            summary["skipped"] += 1
            continue
        try:
            acquire_lease(run, owner)
            etag = doc.get("_etag")
            if not etag:
                raise LeaseConflict("candidate lacks Cosmos ETag")
            await ledger.replace_run_strict(run, expected_etag=etag)
        except Exception as exc:
            _logger.info("recovery lease skipped for %s: %s", run.run_id, exc)
            summary["skipped"] += 1
            continue
        summary["leased"] += 1
        if plan.action == "await_gate":
            summary["awaiting_gate"] += 1
            await resume(run, plan)
            continue
        await resume(run, plan)
        summary["resumed"] += 1
    return summary
