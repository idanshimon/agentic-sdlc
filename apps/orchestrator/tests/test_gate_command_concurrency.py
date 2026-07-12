from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from apps.orchestrator.auth import Principal
from apps.orchestrator.commands import begin_command, finish_command
from apps.orchestrator.models import RunState


class Request:
    def __init__(self, key="cmd-1", path="/api/runs/r1/approve"):
        self.headers = {"idempotency-key": key} if key else {}
        self.url = SimpleNamespace(path=path)


PRINCIPAL = Principal(
    subject="operator", kind="human", roles=frozenset({"operator"}),
    teams=frozenset({"team-demo"}), source="trusted_headers",
)


def test_identical_replay_returns_original_result():
    run = RunState(pending_gate={"version": 3})
    payload = {"card_id": "c1", "decision_kind": "accept"}
    record, replay = begin_command(run, Request(), PRINCIPAL, payload, expected_gate_version=3)
    assert replay is None
    finish_command(run, record, payload, {"ok": True, "decisions_count": 1})
    _, replay = begin_command(run, Request(), PRINCIPAL, payload, expected_gate_version=3)
    assert replay == {"ok": True, "decisions_count": 1}


def test_same_key_with_different_payload_conflicts():
    run = RunState(pending_gate={"version": 3})
    payload = {"card_id": "c1"}
    record, _ = begin_command(run, Request(), PRINCIPAL, payload, expected_gate_version=3)
    finish_command(run, record, payload, {"ok": True})
    with pytest.raises(HTTPException, match="idempotency_conflict"):
        begin_command(run, Request(), PRINCIPAL, {"card_id": "c2"}, expected_gate_version=3)


def test_stale_gate_version_conflicts_without_record():
    run = RunState(pending_gate={"version": 4})
    with pytest.raises(HTTPException, match="stale_gate_version"):
        begin_command(run, Request(), PRINCIPAL, {"card_id": "c1"}, expected_gate_version=3)
    assert run.command_records == {}


def test_missing_idempotency_key_is_rejected():
    with pytest.raises(HTTPException) as exc:
        begin_command(RunState(), Request(key=""), PRINCIPAL, {}, expected_gate_version=None)
    assert exc.value.status_code == 400
