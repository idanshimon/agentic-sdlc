#!/usr/bin/env python3
"""enforce_supply_chain.py — the SUPPLY-001 gate.

Reads a grype SARIF report and fails the build when critical/high findings are
present. Exists as a separate script rather than relying on the scan action's
own `fail-build` for three reasons:

1. **Citable failure.** AGENTS.md requires standards rules to be cited as
   `[<dept>/<version>/<rule-id>]`. An action failing with "grype found
   vulnerabilities" does not tell an operator which bundle rule blocked them.
2. **Honest empty state.** If the SARIF is missing or unparseable, that is a
   BROKEN SCAN, not a clean one. Treating an absent report as a pass is exactly
   the failure this rule was written to eliminate.
3. **Testable.** The severity logic runs locally against fixtures.

Exit codes: 0 = pass, 1 = blocked by findings, 2 = scan broken/unavailable.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

# SARIF severity lives in `level` (error/warning/note) and, for grype, in the
# rule's `properties.security-severity` (a CVSS number).
#
# ORDER MATTERS, and CVSS must NOT come first. In grype's SARIF presenter
# (grype/presenter/sarif/presenter.go) these two fields have different
# provenance and legitimately disagree:
#
#   * `properties.security-severity` is `securitySeverityValue()` — the raw
#     CVSS base score, preferring vendor metrics then falling back to NVD.
#   * `level` is `levelValue()` and the rule's shortDescription text is
#     `severityText()` — BOTH derived from `m.Vulnerability.Severity`, the
#     advisory's own (GHSA/vendor-assigned) label.
#
# A CVSS 7.5 finding that GHSA labels "medium" is common: NVD scores the
# theoretical worst case, the vendor scores the realistic one. Mapping CVSS
# first stamped `[HIGH]` on findings whose own message text read "A medium
# vulnerability in python package: aiohttp". That mismatch is not cosmetic —
# the citation and the evidence in the same audit record contradicted each
# other, and it inflated the block with findings grype did not consider
# blocking.
#
# So: trust grype's own verdict (its label, corroborated by `level`), and use
# CVSS only as a fallback when the authoritative label is absent.
_LEVEL_RANK = {"error": 3, "warning": 2, "note": 1, "none": 0}
_CUTOFF_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1}

# grype writes shortDescription as
#   "<CVE> <severity> vulnerability for <pkg> package"
# and the result message as
#   "A <severity> vulnerability in <type> package: <pkg>, version <v> ..."
_DESC_SEVERITY = re.compile(
    r"\b(critical|high|medium|low)\s+vulnerability\b", re.IGNORECASE
)


def _severity_of(result: dict, rules_by_id: dict[str, dict]) -> str:
    """Severity for a SARIF result, preferring the scanner's own verdict.

    Precedence: explicit string severity -> grype's own severity word (from
    the rule shortDescription, falling back to the result message) -> SARIF
    `level` -> CVSS score. See the note above for why CVSS is last.
    """
    rule_id = result.get("ruleId", "")
    rule = rules_by_id.get(rule_id, {})
    props = rule.get("properties", {}) or {}

    # 1. An explicit string severity, if a scanner provides one.
    for key in ("severity", "problem.severity"):
        val = props.get(key)
        if isinstance(val, str) and val.lower() in _CUTOFF_RANK:
            return val.lower()

    # 2. grype states its verdict in words. Prefer the rule's
    #    shortDescription; fall back to the result message, which carries the
    #    same word and is what an operator reads in the log. `level` collapses
    #    critical and high into "error", so the word is strictly more precise.
    for text in (
        (rule.get("shortDescription") or {}).get("text") or "",
        (result.get("message") or {}).get("text") or "",
    ):
        match = _DESC_SEVERITY.search(text)
        if match:
            return match.group(1).lower()

    # 3. SARIF level. critical and high are indistinguishable here (both
    #    "error"), so report the lower of the two rather than overstate.
    level = (result.get("level") or "").lower()
    if level == "error":
        return "high"
    if level == "warning":
        return "medium"
    if level == "note":
        return "low"

    # 4. Last resort: CVSS. Only reached when the scanner gave no label at
    #    all, in which case a numeric score beats guessing.
    cvss = props.get("security-severity")
    if cvss is not None:
        try:
            score = float(cvss)
            if score >= 9.0:
                return "critical"
            if score >= 7.0:
                return "high"
            if score >= 4.0:
                return "medium"
            return "low"
        except (TypeError, ValueError):
            pass

    return "low"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sarif", required=True)
    ap.add_argument("--rule-id", default="SUPPLY-001")
    ap.add_argument("--bundle", default="security/v0.2.0")
    ap.add_argument("--severity-cutoff", default="high",
                    choices=sorted(_CUTOFF_RANK))
    args = ap.parse_args()

    citation = f"[{args.bundle}/{args.rule_id}]"
    path = Path(args.sarif) if args.sarif else None

    # A missing report is a broken scan, never a pass.
    if not path or not path.exists():
        print(f"{citation} BLOCKED — no SARIF report at {args.sarif!r}.")
        print("  The scan did not produce a report. An absent report is treated")
        print("  as a failure: a rule that passes when its scanner is missing")
        print("  enforces nothing.")
        return 2

    try:
        sarif = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        print(f"{citation} BLOCKED — SARIF at {path} is unreadable: {exc}")
        return 2

    cutoff = _CUTOFF_RANK[args.severity_cutoff]
    counts: Counter[str] = Counter()
    blocking: list[tuple[str, str, str]] = []

    for run in sarif.get("runs", []):
        driver = (run.get("tool") or {}).get("driver") or {}
        rules_by_id = {r.get("id"): r for r in driver.get("rules", []) if r.get("id")}
        for result in run.get("results", []):
            sev = _severity_of(result, rules_by_id)
            counts[sev] += 1
            if _CUTOFF_RANK.get(sev, 0) >= cutoff:
                msg = ((result.get("message") or {}).get("text") or "").strip()
                blocking.append((sev, result.get("ruleId", "?"), msg[:120]))

    total = sum(counts.values())
    summary = ", ".join(f"{n} {s}" for s, n in sorted(
        counts.items(), key=lambda kv: -_CUTOFF_RANK.get(kv[0], 0))) or "none"
    print(f"{citation} scanned SBOM — {total} finding(s): {summary}")

    if not blocking:
        print(f"{citation} PASS — no findings at or above '{args.severity_cutoff}'.")
        return 0

    print(f"\n{citation} BLOCKED — {len(blocking)} finding(s) at or above "
          f"'{args.severity_cutoff}':\n")
    for sev, rule_id, msg in blocking[:25]:
        print(f"  [{sev.upper():>8}] {rule_id}  {msg}")
    if len(blocking) > 25:
        print(f"  … and {len(blocking) - 25} more (see the Security tab).")
    print("\n  Remediate by upgrading the affected dependency. If a finding is")
    print("  a false positive, it must be dispositioned in the bundle via a")
    print("  standards-change proposal — not silenced in this workflow.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
