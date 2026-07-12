import asyncio

from apps.orchestrator.models import RunState, RunStatus, Stage
from apps.orchestrator.recovery_worker import recover_nonterminal_runs


class Ledger:
    def __init__(self, docs): self.docs, self.replaced = docs, []
    async def query_nonterminal_runs(self): return self.docs
    async def replace_run_strict(self, run, *, expected_etag):
        self.replaced.append((run, expected_etag)); return run.model_dump()


def test_recovery_leases_and_resumes_next_stage():
    doc = RunState(
        run_id="r1", status=RunStatus.RUNNING,
        cursor_stage=Stage.CODEGEN, cursor_state="completed",
    ).model_dump(mode="json") | {"_etag": "v1"}
    ledger = Ledger([doc])
    calls = []
    async def resume(run, plan): calls.append((run.run_id, plan.action, plan.stage))
    summary = asyncio.run(recover_nonterminal_runs(ledger, owner="worker-1", resume=resume))
    assert summary["resumed"] == 1
    assert calls == [("r1", "resume", Stage.REVIEW_SCAN)]
    assert ledger.replaced[0][1] == "v1"


def test_recovery_preserves_open_gate_without_replaying_prior_stage():
    doc = RunState(
        run_id="r2", status=RunStatus.AWAITING_GATE,
        cursor_stage=Stage.RESOLVER, cursor_state="awaiting_gate",
        pending_gate={"status": "open", "version": 2},
    ).model_dump(mode="json") | {"_etag": "v2"}
    ledger = Ledger([doc])
    calls = []
    async def resume(run, plan): calls.append(plan.action)
    summary = asyncio.run(recover_nonterminal_runs(ledger, owner="worker-1", resume=resume))
    assert summary["awaiting_gate"] == 1
    assert calls == ["await_gate"]
