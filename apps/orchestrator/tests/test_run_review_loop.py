"""Tests for the run_review_loop async glue (PR-3, task 0.4/0.5).

The glue runs verdict -> plan_next_loop_action -> (remediate | merge | escalate)
with injected review + remediation callables so the whole loop is testable with
zero real codegen or GitHub. It records a ledger hop per action.

Run:
    source .venv/bin/activate
    python -m pytest apps/orchestrator/tests/test_run_review_loop.py -q
"""
from __future__ import annotations

import asyncio

from apps.orchestrator import review_loop as rl
from apps.orchestrator.models import Blocker, ReviewVerdict


def _fail(blockers=None):
    return ReviewVerdict(status="FAIL", blockers=blockers or [
        Blocker(check="secret-scan", rule="security/v0.1.0/SECRET-001",
                detail="secret", file="a.py", line=1, phi=False)])


def _pass():
    return ReviewVerdict(status="PASS")


def _run(coro):
    return asyncio.run(coro)


def test_tier_a_fail_then_pass_converges_and_merges():
    """Attempt 1 FAILs, remediation fixes it, attempt 2 PASSes -> merged."""
    verdicts = iter([_fail(), _pass()])
    merged = {"called": False}

    async def review(_files):
        return next(verdicts)

    async def remediate(_verdict, _files):
        return {"a.py": "x = 1\n"}  # "fixed" code

    async def do_merge(_repo):
        merged["called"] = True
        return "https://github.com/o/delivery/pull/7"

    result = _run(rl.run_review_loop(
        repo="delivery", tier="A", code_files={"a.py": "secret\n"},
        review=review, remediate=remediate, do_merge=do_merge,
    ))
    assert result.outcome == "converged"
    assert result.merged is True
    assert merged["called"] is True
    assert result.attempts == 1  # one remediation before the pass
    # ledger hops: 1 remediation + 1 converged
    kinds = [h["runtime_kind"] for h in result.ledger_hops]
    assert "review_remediation" in kinds
    assert "loop_converged" in kinds


def test_tier_a_never_converges_escalates_at_max_attempts():
    """Every re-review still FAILs -> exhausts MAX_ATTEMPTS -> escalates, no merge."""
    merged = {"called": False}

    async def review(_files):
        return _fail()

    async def remediate(_verdict, _files):
        return {"a.py": "still bad\n"}

    async def do_merge(_repo):
        merged["called"] = True
        return "url"

    result = _run(rl.run_review_loop(
        repo="delivery", tier="A", code_files={"a.py": "secret\n"},
        review=review, remediate=remediate, do_merge=do_merge,
    ))
    assert result.outcome == "escalated"
    assert result.merged is False
    assert merged["called"] is False
    assert result.escalation_reason == "max_attempts"
    assert any(h["runtime_kind"] == "loop_escalated" for h in result.ledger_hops)


def test_phi_blocker_escalates_immediately_no_remediation():
    remediated = {"called": False}

    async def review(_files):
        return _fail([Blocker(check="privacy", rule="security/v0.1.0/PHI-001",
                              detail="MRN", file="a.py", line=1, phi=True)])

    async def remediate(_verdict, _files):
        remediated["called"] = True
        return {}

    async def do_merge(_repo):
        return "url"

    result = _run(rl.run_review_loop(
        repo="delivery", tier="A", code_files={"a.py": "MRN\n"},
        review=review, remediate=remediate, do_merge=do_merge,
    ))
    assert result.outcome == "escalated"
    assert result.escalation_reason == "tier_floor_phi"
    assert remediated["called"] is False  # PHI floor: never auto-remediate


def test_tier_b_pass_awaits_human_merge_not_auto():
    merged = {"called": False}

    async def review(_files):
        return _pass()

    async def remediate(_verdict, _files):
        return {}

    async def do_merge(_repo):
        merged["called"] = True
        return "url"

    result = _run(rl.run_review_loop(
        repo="delivery", tier="B", code_files={"a.py": "x = 1\n"},
        review=review, remediate=remediate, do_merge=do_merge,
    ))
    assert result.outcome == "awaiting_human_merge"
    assert result.merged is False
    assert merged["called"] is False


def test_tier_c_comments_only_no_remediation_no_merge():
    async def review(_files):
        return _fail()

    async def remediate(_verdict, _files):
        raise AssertionError("tier C must never remediate")

    async def do_merge(_repo):
        raise AssertionError("tier C must never merge")

    result = _run(rl.run_review_loop(
        repo="delivery", tier="C", code_files={"a.py": "secret\n"},
        review=review, remediate=remediate, do_merge=do_merge,
    ))
    assert result.outcome == "advisory"
    assert result.merged is False


def test_every_action_writes_a_cited_ledger_hop():
    async def review(_files):
        return _pass()

    async def remediate(_verdict, _files):
        return {}

    async def do_merge(_repo):
        return "url"

    result = _run(rl.run_review_loop(
        repo="delivery", tier="A", code_files={"a.py": "x = 1\n"},
        review=review, remediate=remediate, do_merge=do_merge,
    ))
    for hop in result.ledger_hops:
        assert hop["autonomy_ref"].startswith("reviewloop/")
