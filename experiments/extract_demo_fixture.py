#!/usr/bin/env python3
"""Extract pre-canned demo fixtures from experiments/results/phase-a-fixed/run-1.

Writes a single TypeScript module to apps/ledger-insights-ui/src/lib/demo/
fixtures.ts containing the full pipeline output (cards, decisions, ledger
entries, architecture, test plan, code, decisions.md) baked in as
exported constants. The dashboard's demo mode replays this verbatim so
the customer sees the same artifacts every demo, no LLM calls, no risk.

Run from repo root:
    python experiments/extract_demo_fixture.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from textwrap import indent

REPO = Path(__file__).resolve().parent.parent
# Hybrid source: best-of-both runs.
#   blind-read/phase-a-untruncated/ — Bug #3 patched out (full architecture)
#   results/phase-a-fixed/run-1/ — Bug #2 fixed (decision-cited test plan)
# Both use identical Resolver decisions (same fixture, same model), so the
# cards/decisions/ledger are interchangeable. We pull each artifact from
# whichever source has it in its full, post-fix form.
SRC_FULL_ARCH = REPO / "experiments" / "blind-read" / "phase-a-untruncated"
SRC_FIXED_TESTS = REPO / "experiments" / "results" / "phase-a-fixed" / "run-1"
DST = REPO / "apps" / "ledger-insights-ui" / "src" / "lib" / "demo" / "fixtures.ts"


def js(s: str) -> str:
    """JSON-encode a Python value as a TS literal."""
    return json.dumps(s, ensure_ascii=False)


def js_obj(obj: object) -> str:
    """Pretty TS literal."""
    return json.dumps(obj, ensure_ascii=False, indent=2)


def main() -> None:
    if not SRC_FULL_ARCH.exists() or not SRC_FIXED_TESTS.exists():
        sys.exit(f"Source missing — checked {SRC_FULL_ARCH} and {SRC_FIXED_TESTS}")

    # Use phase-a-fixed/run-1 for the cards/decisions/ledger/code/decisions.md/
    # PRD/summary; use blind-read/phase-a-untruncated for the full architecture.
    cards = json.loads((SRC_FIXED_TESTS / "cards.json").read_text())
    decisions = json.loads((SRC_FIXED_TESTS / "decisions.json").read_text())
    ledger_lines = (SRC_FIXED_TESTS / "ledger.jsonl").read_text().splitlines()
    ledger = [json.loads(l) for l in ledger_lines if l.strip()]
    summary = json.loads((SRC_FIXED_TESTS / "summary.json").read_text())
    architecture = (SRC_FULL_ARCH / "architecture.md").read_text()
    test_plan = (SRC_FIXED_TESTS / "test_plan.md").read_text()
    code = (SRC_FIXED_TESTS / "codegen.py").read_text()
    decisions_md = (SRC_FIXED_TESTS / "decisions.md").read_text()
    prd = (SRC_FIXED_TESTS / "prd.txt").read_text()

    DST.parent.mkdir(parents=True, exist_ok=True)

    out = []
    out.append("/* AUTO-GENERATED — do not edit by hand.")
    out.append(" * Source: experiments/results/phase-a-fixed/run-1/")
    out.append(" * Re-generate: python experiments/extract_demo_fixture.py")
    out.append(" *")
    out.append(" * This file contains the full pre-canned Phase-A-fixed output for")
    out.append(" * the Patient Vitals Streaming PRD. Demo Mode replays this verbatim")
    out.append(" * so the dashboard renders a real, audit-grade pipeline run with")
    out.append(" * no LLM calls and no network risk during demos.")
    out.append(" *")
    out.append(" * RIP-OUT: deleting this file + src/lib/demo/ + the four guards under")
    out.append(" * `if (isDemoMode())` removes Demo Mode entirely. See DEMO-MODE.md.")
    out.append(" */")
    out.append("")
    out.append("export const VITALS_PRD = " + js(prd) + ";")
    out.append("")
    out.append("export const VITALS_CARDS = " + js_obj(cards) + " as const;")
    out.append("")
    out.append("export const VITALS_DECISIONS = " + js_obj(decisions) + " as const;")
    out.append("")
    out.append("export const VITALS_LEDGER = " + js_obj(ledger) + " as const;")
    out.append("")
    out.append("export const VITALS_ARCHITECTURE_MD = " + js(architecture) + ";")
    out.append("")
    out.append("export const VITALS_TEST_PLAN_MD = " + js(test_plan) + ";")
    out.append("")
    out.append("export const VITALS_CODE_PY = " + js(code) + ";")
    out.append("")
    out.append("export const VITALS_DECISIONS_MD = " + js(decisions_md) + ";")
    out.append("")
    out.append("export const VITALS_SUMMARY = " + js_obj(summary) + " as const;")
    out.append("")

    DST.write_text("\n".join(out))
    print(f"Wrote {DST.relative_to(REPO)} ({DST.stat().st_size:,} bytes)")
    print(f"  cards: {len(cards)}")
    print(f"  decisions: {len(decisions)}")
    print(f"  ledger entries: {len(ledger)}")
    print(f"  architecture: {len(architecture):,} chars")
    print(f"  test_plan: {len(test_plan):,} chars")
    print(f"  code: {len(code):,} chars")


if __name__ == "__main__":
    main()
