"""experiments/score_phase_a_fixed.py — score the Phase A FIXED variant.

Runs the same scoring logic as score_rubric.py but reads from
results/phase-a-fixed/ instead of phase-a/, then prints a 3-way
comparison: Phase A (broken) vs Phase A FIXED vs Phase B.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "experiments"))

from score_rubric import collect_phase  # noqa: E402

PHASE_A = REPO_ROOT / "experiments" / "results" / "phase-a"
PHASE_A_FIXED = REPO_ROOT / "experiments" / "results" / "phase-a-fixed"
PHASE_B = REPO_ROOT / "experiments" / "results" / "phase-b"


def main() -> None:
    a = collect_phase("A", PHASE_A)
    a_fix = collect_phase("A", PHASE_A_FIXED)
    b = collect_phase("B", PHASE_B)
    out = {"phase_a_baseline": a, "phase_a_fixed": a_fix, "phase_b": b}
    out_path = REPO_ROOT / "experiments" / "SCORES_3WAY.json"
    out_path.write_text(json.dumps(out, indent=2))

    print(f"\n=== 3-WAY RUBRIC SCORES ===\n")
    print(f"{'Dimension':<30}{'A (baseline)':>15}{'A (fixed)':>15}{'B (openspec)':>15}")
    print(f"{'-' * 75}")
    for dim, label in [
        ("mean_traceability_score", "1. Traceability"),
        ("mean_test_spec_coverage_score", "2. Test-spec coverage"),
        ("mean_validator_grade_score", "5. Validator-grade"),
    ]:
        av = a.get(dim, "—")
        afv = a_fix.get(dim, "—")
        bv = b.get(dim, "—")
        print(f"{label:<30}{av:>15}{afv:>15}{bv:>15}")
    av = a["regen_stability"]["score"]
    afv = a_fix["regen_stability"]["score"]
    bv = b["regen_stability"]["score"]
    print(f"{'3. Regen stability':<30}{av:>15}{afv:>15}{bv:>15}")
    print(f"{'   pairwise dist %':<30}"
          f"{a['regen_stability']['mean_distance_pct']:>14.1f}%"
          f"{a_fix['regen_stability']['mean_distance_pct']:>14.1f}%"
          f"{b['regen_stability']['mean_distance_pct']:>14.1f}%")

    print(f"\n{'Cost / latency':<30}{'A (baseline)':>15}{'A (fixed)':>15}{'B (openspec)':>15}")
    print(f"{'-' * 75}")
    print(f"{'   Mean wall (s)':<30}{a['mean_wall_seconds']:>15}{a_fix['mean_wall_seconds']:>15}"
          f"{b['mean_wall_seconds']:>15}")
    print(f"{'   Total tokens':<30}{a['total_tokens']:>15}{a_fix['total_tokens']:>15}"
          f"{b['total_tokens']:>15}")
    print(f"{'   Total cost (USD)':<30}{a['total_cost_usd']:>15}{a_fix['total_cost_usd']:>15}"
          f"{b['total_cost_usd']:>15}")
    print(f"\nFull scores: {out_path}")


if __name__ == "__main__":
    main()
