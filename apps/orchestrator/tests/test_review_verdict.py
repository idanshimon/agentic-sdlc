"""Tests for the real review-scan verdict (PR-2).

Kills the `findings = 0  # demo: stubbed clean` stub in stage_review_scan and
replaces it with a real structured verdict that reuses the PR-1 deterministic
matcher (scripts/enforce_bundles.py) over the generated code.

Contract: openspec/changes/add-autonomous-review-loop task 0.0 + models.

Run:
    source .venv/bin/activate
    python -m pytest apps/orchestrator/tests/test_review_verdict.py -q
"""
from __future__ import annotations

import asyncio

from apps.orchestrator import review_verdict as rv
from apps.orchestrator.models import Blocker, ReviewVerdict, RunState, Stage


# --------------------------------------------------------------------------
# The verdict builder — pure, reuses the PR-1 matcher over code text
# --------------------------------------------------------------------------

def test_clean_code_yields_pass_verdict():
    verdict = rv.build_review_verdict(
        {"src/main.py": "def redacted_id():\n    return '***'\ndef handler():\n    return redacted_id()\n"},
        team="defaults",
    )
    assert isinstance(verdict, ReviewVerdict)
    assert verdict.status == "PASS"
    assert verdict.blockers == []


def test_hardcoded_secret_yields_fail_with_cited_blocker():
    verdict = rv.build_review_verdict(
        {"src/config.py": 'api_key = "AKIAIOSFODNN7EXAMPLEKEY123"\n'},
        team="defaults",
    )
    assert verdict.status == "FAIL"
    assert len(verdict.blockers) >= 1
    b = verdict.blockers[0]
    assert isinstance(b, Blocker)
    assert b.rule == "security/v0.1.0/SECRET-001"
    assert b.file == "src/config.py"
    assert b.line == 1
    assert b.check  # non-empty human-readable check name


def test_phi_in_logs_yields_fail_and_phi_flag():
    verdict = rv.build_review_verdict(
        {"svc.py": "logger.info(f'patient {MRN} seen')\n"},
        team="defaults",
    )
    assert verdict.status == "FAIL"
    phi_blockers = [b for b in verdict.blockers if b.phi]
    assert phi_blockers, "PHI-001 blocker must carry phi=True"
    assert phi_blockers[0].rule == "security/v0.1.0/PHI-001"


def test_verdict_carries_attempt_and_prior_ref_for_chaining():
    """Re-reviews must be chainable: the verdict records its attempt index and
    an optional reference to the prior verdict."""
    v1 = rv.build_review_verdict({"a.py": 'password = "hunter2hunter2hunter2"\n'},
                                 team="defaults", attempt=1)
    assert v1.attempt == 1
    assert v1.prior_verdict_ref is None
    v2 = rv.build_review_verdict({"a.py": "x = 1\n"}, team="defaults",
                                 attempt=2, prior_verdict_ref="verdict-1")
    assert v2.attempt == 2
    assert v2.prior_verdict_ref == "verdict-1"
    assert v2.status == "PASS"


def test_verdict_blockers_are_machine_consumable_dicts():
    """The loop controller (PR-3) consumes blockers programmatically — each
    must serialize to a dict with the contract keys."""
    verdict = rv.build_review_verdict(
        {"x.py": 'client_secret = "abcdef0123456789abcdef"\n'}, team="defaults")
    d = verdict.model_dump()
    assert d["status"] == "FAIL"
    assert isinstance(d["blockers"], list)
    b = d["blockers"][0]
    assert set(b) >= {"check", "rule", "detail", "file", "line", "phi"}


# --------------------------------------------------------------------------
# The stage — stage_review_scan now emits the real verdict, not findings=0
# --------------------------------------------------------------------------

def _drain(agen):
    async def _collect():
        return [ev async for ev in agen]
    return asyncio.run(_collect())


def test_stage_review_scan_fails_on_violating_generated_code():
    """A codegen event carrying a hardcoded secret must drive review_scan to a
    FAILED event with the verdict in the payload."""
    run = RunState(team_id="defaults")
    # Simulate the codegen stage having emitted violating code.
    from apps.orchestrator.models import StageEvent
    run.events.append(StageEvent(
        run_id=run.run_id, stage=Stage.CODEGEN, status="completed",
        payload={"code": 'api_key = "AKIAIOSFODNN7EXAMPLEKEY123"\n',
                 "app_code": 'api_key = "AKIAIOSFODNN7EXAMPLEKEY123"\n'},
    ))
    events = _drain(rv.run_review_scan(run))
    terminal = events[-1]
    assert terminal.status == "failed"
    assert terminal.payload.get("verdict", {}).get("status") == "FAIL"
    assert terminal.payload.get("findings", 0) >= 1


def test_stage_review_scan_passes_on_clean_generated_code():
    run = RunState(team_id="defaults")
    from apps.orchestrator.models import StageEvent
    run.events.append(StageEvent(
        run_id=run.run_id, stage=Stage.CODEGEN, status="completed",
        payload={"code": "def ok():\n    return 1\n",
                 "app_code": "def ok():\n    return 1\n"},
    ))
    events = _drain(rv.run_review_scan(run))
    terminal = events[-1]
    assert terminal.status == "completed"
    assert terminal.payload.get("verdict", {}).get("status") == "PASS"


def test_stage_review_scan_no_code_is_vacuous_pass():
    """No generated code (nothing to scan) is a PASS — the stage doesn't crash."""
    run = RunState(team_id="defaults")
    events = _drain(rv.run_review_scan(run))
    assert events[-1].status == "completed"
