"""experiments/run_phase_a_blind_read.py — single-run helper.

Runs Phase A once with a runtime patch that disables the 1200-char Architect
truncation, so the blind-read artifact captures the full Architect response
rather than the orchestrator's mid-sentence chop. Output goes to a separate
folder and is NOT used in the rubric scores.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
APPS_PATH = REPO_ROOT / "apps"
EXPERIMENTS_PATH = REPO_ROOT / "experiments"
for p in (APPS_PATH, EXPERIMENTS_PATH, REPO_ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

# Reuse Phase A harness wholesale (env injection + provider patch + run_one)
import run_phase_a as _pa  # noqa: E402
run_one_a = _pa.run_one


# --- patch the orchestrator's architecture truncation just for this helper ---
# stage_architect emits `architecture=res.text[:1200]` to the event payload —
# the cap chops most architectures mid-sentence, so the blind-read view of
# the deployed pipeline is unfairly short. Wrap the StageEvent constructor
# at runtime: when stage=ARCHITECT and `architecture` is in the payload,
# replace the truncated value with the full text from the most recent
# CallResult stashed on the run. The rubric runs DO NOT use this patch —
# those numbers stand as measured.
from orchestrator import _pipeline_stages as ps  # noqa: E402
from orchestrator import models as _m  # noqa: E402

_orig_call = ps._call
_last_results: dict[str, str] = {}


async def _call_capturing(*args, **kwargs):
    res = await _orig_call(*args, **kwargs)
    stage_key = kwargs.get("stage_key") or (args[0] if args else "")
    _last_results[stage_key] = res.text
    return res


ps._call = _call_capturing  # type: ignore[assignment]

_orig_ev = ps._ev


def _ev_full_arch(run, stage, status, msg="", **payload):
    if stage == _m.Stage.ARCHITECT and "architecture" in payload:
        full = _last_results.get("architect")
        if full:
            payload["architecture"] = full
    return _orig_ev(run, stage, status, msg, **payload)


ps._ev = _ev_full_arch  # type: ignore[assignment]


async def main() -> None:
    import yaml
    prd = (REPO_ROOT / "samples" / "prds" / "patient-vitals-streaming.txt").read_text()
    fixture = yaml.safe_load(
        (REPO_ROOT / "experiments" / "fixtures" / "resolver-decisions.yaml").read_text()
    )
    out = REPO_ROOT / "experiments" / "blind-read" / "phase-a-untruncated"
    summary = await run_one_a(99, prd, fixture, out)
    print(f"\nDone. Architecture full text at {out}/architecture.md")
    arch_path = out / "architecture.md"
    print(f"  bytes: {arch_path.stat().st_size}")


if __name__ == "__main__":
    asyncio.run(main())
