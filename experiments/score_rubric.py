"""experiments/score_rubric.py — mechanical scoring of Phase A vs Phase B.

Reads `experiments/results/phase-{a,b}/run-{1,2,3}/summary.json` plus the raw
artifacts and computes scores for the 6 rubric dimensions WHERE MECHANICAL.
Customer-readability (#4) stays manual — we just stage two artifacts for blind
read.

Outputs: experiments/SCORES.json + a printed table.
"""
from __future__ import annotations

import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PHASE_A = REPO_ROOT / "experiments" / "results" / "phase-a"
PHASE_B = REPO_ROOT / "experiments" / "results" / "phase-b"


def _score_traceability(arch_text: str, decisions: list[dict],
                        spec_text: str = "", phase: str = "A") -> tuple[int, dict]:
    """1=worst, 5=best. Phase A: count *(Decision: ...) parens citations.
    Phase B: count [decision: <card_id>] tags AND verify the card_id exists in
    decisions.json.
    """
    n_decisions = len(decisions)
    if n_decisions == 0:
        return 1, {"reason": "no decisions to cite"}

    if phase == "A":
        # Phase A: paraphrase citation in parens, e.g. *(Decision: WebSocket JWT auth)*
        cites = re.findall(r"\*\(Decision[s]?:.*?\)\*", arch_text, re.IGNORECASE)
        # Crude: count unique citations
        unique = set(c.lower() for c in cites)
        cite_count = len(unique)
        # Best estimate: how many decisions appear to be cited (paraphrase heuristic)
        # If ≥ n_decisions cites exist, assume coverage; degrade for less.
        cov = min(1.0, cite_count / n_decisions)
        if cov >= 1.0:
            score = 4  # paraphrase coverage but no stable IDs → 4 not 5
        elif cov >= 0.8:
            score = 3
        elif cov >= 0.5:
            score = 2
        else:
            score = 1
        return score, {
            "cite_count": cite_count, "n_decisions": n_decisions,
            "coverage_ratio": round(cov, 2), "kind": "paraphrase",
        }
    else:  # Phase B
        # [decision: <card_id>] tags
        tag_card_ids = set(re.findall(r"\[decision:\s*([a-z0-9\-]+)\s*\]",
                                       spec_text, re.IGNORECASE))
        decision_card_ids = set((d.get("card_id") or "")[:8] for d in decisions)
        # The Architect prompt instructs short ids (first 8 chars); be lenient
        # and match either prefix.
        matched = set()
        for tag in tag_card_ids:
            for full in decision_card_ids:
                if full.startswith(tag) or tag.startswith(full[:8]):
                    matched.add(full)
                    break
        cov = len(matched) / max(1, n_decisions)
        if cov >= 1.0 and len(tag_card_ids) >= n_decisions:
            score = 5  # mechanical, stable, complete
        elif cov >= 1.0:
            score = 4
        elif cov >= 0.8:
            score = 3
        elif cov >= 0.5:
            score = 2
        else:
            score = 1
        return score, {
            "tag_count": len(tag_card_ids), "n_decisions": n_decisions,
            "matched_decisions": len(matched), "coverage_ratio": round(cov, 2),
            "kind": "mechanical-id",
        }


def _score_test_spec_coverage(arch_text: str, test_text: str,
                               spec_text: str, phase: str) -> tuple[int, dict]:
    """Phase A: heuristic — does the test plan reference architectural words?
    Phase B: count test functions and compare to scenario count.
    """
    if phase == "A":
        # Architectural keywords (rough): pull capitalized noun phrases of len >=2 words.
        # Then count how many appear in the test plan.
        arch_lower = arch_text.lower()
        test_lower = test_text.lower()
        # Specific assertion vocabulary worth checking
        domain_terms = [
            "websocket", "jwt", "rs256", "mtls", "oauth", "client_credentials",
            "phi", "hmac", "fhir", "observation", "p95", "p99", "latency",
            "uptime", "vendor", "redaction", "tokenization",
        ]
        in_arch = [t for t in domain_terms if t in arch_lower]
        in_test = [t for t in domain_terms if t in test_lower]
        overlap = set(in_arch) & set(in_test)
        if not in_arch:
            return 1, {"reason": "no architectural terms found"}
        cov = len(overlap) / len(in_arch)
        if cov >= 1.0:
            score = 5
        elif cov >= 0.75:
            score = 4
        elif cov >= 0.5:
            score = 3
        elif cov >= 0.25:
            score = 2
        else:
            score = 1
        return score, {
            "domain_terms_in_arch": in_arch,
            "domain_terms_in_test": in_test,
            "overlap": list(overlap),
            "coverage_ratio": round(cov, 2),
            "kind": "domain-vocabulary-overlap",
        }
    else:  # Phase B — mechanical: test functions vs scenarios
        scenario_count = len(re.findall(r"^####\s*Scenario:", spec_text,
                                         re.MULTILINE))
        test_fn_count = len(re.findall(r"^def test_", test_text, re.MULTILINE))
        if scenario_count == 0:
            return 1, {"reason": "no scenarios in spec"}
        cov = test_fn_count / scenario_count
        # Verify each test docstring references a scenario word ("Scenario:" or "WHEN")
        whens = len(re.findall(r"\bWHEN\b", test_text))
        thens = len(re.findall(r"\bTHEN\b", test_text))
        if cov >= 1.0 and whens >= scenario_count and thens >= scenario_count:
            score = 5
        elif cov >= 1.0:
            score = 4
        elif cov >= 0.75:
            score = 3
        elif cov >= 0.5:
            score = 2
        else:
            score = 1
        return score, {
            "scenario_count": scenario_count,
            "test_fn_count": test_fn_count,
            "when_count": whens,
            "then_count": thens,
            "coverage_ratio": round(cov, 2),
            "kind": "scenario-to-test-mechanical",
        }


def _score_regen_stability(texts: list[str]) -> tuple[int, dict]:
    """Pairwise normalized Levenshtein distance across runs."""
    if len(texts) < 2:
        return 3, {"reason": "<2 runs available"}
    distances = []
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            sm = SequenceMatcher(None, texts[i], texts[j])
            ratio = sm.ratio()  # 1.0 = identical
            mean_len = (len(texts[i]) + len(texts[j])) / 2
            normalized_distance = 1 - ratio  # 0 = identical
            distances.append(normalized_distance)
    mean_dist = sum(distances) / len(distances)
    pct = mean_dist * 100
    if pct < 5:
        score = 5
    elif pct < 15:
        score = 4
    elif pct < 30:
        score = 3
    elif pct < 60:
        score = 2
    else:
        score = 1
    return score, {
        "pairwise_normalized_distances": [round(d, 3) for d in distances],
        "mean_distance_pct": round(pct, 1),
        "kind": "pairwise-levenshtein-mean",
    }


def _score_validator(summary: dict, phase: str) -> tuple[int, dict]:
    if phase == "A":
        return 1, {"reason": "Phase A free-form prose; not OpenSpec-shaped"}
    v = summary.get("validator", {})
    if v.get("exit_code") == 0 and "FAIL" not in v.get("stdout", ""):
        return 5, {"summary": "PASS, no warnings detected", "exit_code": 0}
    if v.get("exit_code") == 0:
        return 4, {"summary": "PASS with warnings", "exit_code": 0}
    return 1, {"exit_code": v.get("exit_code"),
               "stderr": v.get("stderr", "")[:200]}


def collect_phase(phase: str, root: Path) -> dict:
    out = {"phase": phase, "runs": []}
    runs = sorted([d for d in root.iterdir() if d.is_dir() and d.name.startswith("run-")])
    arch_texts = []
    spec_texts = []
    for d in runs:
        try:
            summary = json.load(open(d / "summary.json"))
        except FileNotFoundError:
            continue
        decisions = json.load(open(d / "decisions.json"))
        if phase == "A":
            arch_text = (d / "architecture.md").read_text()
            test_text = (d / "test_plan.md").read_text()
            spec_text = ""
        else:
            arch_text = (d / "openspec_change" / "proposal.md").read_text() + \
                        "\n\n" + (d / "openspec_change" / "design.md").read_text()
            spec_text = (d / "openspec_change" / "specs" /
                         summary["spec_capability"] / "spec.md").read_text()
            test_text = (d / "pr_payload" / "tests" / "test_generated.py").read_text()
            arch_texts.append(arch_text + "\n\n" + spec_text)

        if phase == "A":
            arch_texts.append(arch_text)
        spec_texts.append(spec_text)

        trace_score, trace_detail = _score_traceability(
            arch_text, decisions, spec_text=spec_text, phase=phase
        )
        ts_score, ts_detail = _score_test_spec_coverage(
            arch_text, test_text, spec_text, phase
        )
        v_score, v_detail = _score_validator(summary, phase)
        out["runs"].append({
            "run_dir": d.name,
            "wall_clock_seconds": summary["wall_clock_seconds"],
            "tokens": summary["total_tokens"],
            "cost_usd": summary["total_cost_usd"],
            "scores": {
                "traceability": {"score": trace_score, **trace_detail},
                "test_spec_coverage": {"score": ts_score, **ts_detail},
                "validator_grade": {"score": v_score, **v_detail},
            },
        })

    # Cross-run dimension: regen stability (one score per phase)
    regen_score, regen_detail = _score_regen_stability(arch_texts)
    out["regen_stability"] = {"score": regen_score, **regen_detail}

    # Aggregates
    if out["runs"]:
        out["mean_wall_seconds"] = round(
            sum(r["wall_clock_seconds"] for r in out["runs"]) / len(out["runs"]), 1
        )
        out["total_tokens"] = sum(r["tokens"] for r in out["runs"])
        out["total_cost_usd"] = round(sum(r["cost_usd"] for r in out["runs"]), 4)
        for dim in ("traceability", "test_spec_coverage", "validator_grade"):
            scores = [r["scores"][dim]["score"] for r in out["runs"]]
            out[f"mean_{dim}_score"] = round(sum(scores) / len(scores), 2)

    return out


def main() -> None:
    a = collect_phase("A", PHASE_A)
    b = collect_phase("B", PHASE_B)
    out = {"phase_a": a, "phase_b": b}
    out_path = REPO_ROOT / "experiments" / "SCORES.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\n=== RUBRIC SCORES (mechanical, dimensions 1/2/3/5/6) ===")
    print(f"\n{'Dimension':<32}{'Phase A':>12}{'Phase B':>12}{'Δ':>10}")
    print(f"{'-' * 66}")
    for dim, label in [
        ("mean_traceability_score", "1. Traceability"),
        ("mean_test_spec_coverage_score", "2. Test-spec coverage"),
        ("mean_validator_grade_score", "5. Validator-grade"),
    ]:
        av = a.get(dim, "—")
        bv = b.get(dim, "—")
        delta = (bv - av) if isinstance(av, (int, float)) and isinstance(bv, (int, float)) else "—"
        print(f"{label:<32}{av:>12}{bv:>12}{str(delta):>10}")
    # Regen
    av = a["regen_stability"]["score"]
    bv = b["regen_stability"]["score"]
    print(f"{'3. Regen stability':<32}{av:>12}{bv:>12}{bv - av:>10}")
    print(f"{'   (mean pairwise distance %)':<32}"
          f"{a['regen_stability']['mean_distance_pct']:>11.1f}%"
          f"{b['regen_stability']['mean_distance_pct']:>11.1f}%")

    # Cost / latency
    print(f"\n{'Cost / latency':<32}{'Phase A':>12}{'Phase B':>12}{'ratio':>10}")
    print(f"{'-' * 66}")
    print(f"{'   Mean wall (s)':<32}{a['mean_wall_seconds']:>12}{b['mean_wall_seconds']:>12}"
          f"{(b['mean_wall_seconds']/a['mean_wall_seconds']):>9.2f}x")
    print(f"{'   Total tokens':<32}{a['total_tokens']:>12}{b['total_tokens']:>12}"
          f"{(b['total_tokens']/a['total_tokens']):>9.2f}x")
    print(f"{'   Total cost (USD)':<32}{a['total_cost_usd']:>12}{b['total_cost_usd']:>12}"
          f"{(b['total_cost_usd']/a['total_cost_usd']):>9.2f}x")
    print(f"\nFull scores: {out_path}")


if __name__ == "__main__":
    main()
