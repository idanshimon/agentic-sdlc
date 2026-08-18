"""Tests for the SUPPLY-001 gate.

The fixtures here mirror the real shape grype v0.110.0 emits (see
grype/presenter/sarif/presenter.go), not an idealised SARIF. The load-bearing
detail is that a rule's `properties.security-severity` (CVSS base score) and
its `shortDescription` / result `level` (the advisory's own label) have
different provenance and legitimately disagree.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from enforce_supply_chain import _DESC_SEVERITY, _severity_of, main  # noqa: E402

SCRIPT = Path(__file__).resolve().parents[1] / "enforce_supply_chain.py"


def _rule(rule_id: str, severity_word: str, cvss: str | None) -> dict:
    """A grype rule descriptor, as written by its SARIF presenter."""
    props: dict = {}
    if cvss is not None:
        props["security-severity"] = cvss
    return {
        "id": rule_id,
        "shortDescription": {
            "text": f"{rule_id} {severity_word} vulnerability for somepkg package"
        },
        "properties": props,
    }


def _result(rule_id: str, level: str, text: str) -> dict:
    return {"ruleId": rule_id, "level": level, "message": {"text": text}}


def _sarif(rules: list[dict], results: list[dict]) -> dict:
    return {
        "version": "2.1.0",
        "runs": [{"tool": {"driver": {"name": "Grype", "rules": rules}}, "results": results}],
    }


def _write(tmp_path: Path, doc: dict) -> Path:
    p = tmp_path / "results.sarif"
    p.write_text(json.dumps(doc))
    return p


def _run(sarif_path: Path, cutoff: str = "high") -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--sarif", str(sarif_path),
         "--severity-cutoff", cutoff],
        capture_output=True, text=True,
    )


# --- the regression this file exists for --------------------------------

def test_medium_advisory_with_high_cvss_is_not_promoted_to_high():
    """The bug: CVSS-first mapping stamped HIGH on a medium advisory.

    GHSA-27mf-ghqm-j3j8 (aiohttp) is labelled medium by the advisory but
    carries a CVSS base score in the high band. The gate reported
    `[HIGH] ... A medium vulnerability in python package: aiohttp` — the
    citation contradicting the evidence in the same audit line.
    """
    rules = {"GHSA-27mf-ghqm-j3j8-aiohttp":
             _rule("GHSA-27mf-ghqm-j3j8-aiohttp", "medium", "7.5")}
    result = _result("GHSA-27mf-ghqm-j3j8-aiohttp", "warning",
                     "A medium vulnerability in python package: aiohttp")

    assert _severity_of(result, rules) == "medium"


def test_medium_advisory_does_not_block_a_high_cutoff_build(tmp_path):
    """End-to-end: a medium-only report must PASS a --severity-cutoff high."""
    doc = _sarif(
        [_rule("GHSA-medium-x", "medium", "7.5")],
        [_result("GHSA-medium-x", "warning",
                 "A medium vulnerability in python package: aiohttp")],
    )
    proc = _run(_write(tmp_path, doc))
    assert proc.returncode == 0, proc.stdout
    assert "PASS" in proc.stdout
    assert "HIGH" not in proc.stdout


# --- severity mapping precedence ----------------------------------------

@pytest.mark.parametrize("word,expected", [
    ("critical", "critical"),
    ("high", "high"),
    ("medium", "medium"),
    ("low", "low"),
])
def test_description_label_is_authoritative(word, expected):
    """grype's own word wins over the CVSS number in every band."""
    rules = {"R": _rule("R", word, "9.8")}
    assert _severity_of(_result("R", "error", "msg"), rules) == expected


def test_explicit_string_severity_outranks_everything():
    rule = _rule("R", "low", "1.0")
    rule["properties"]["severity"] = "critical"
    assert _severity_of(_result("R", "note", "msg"), {"R": rule}) == "critical"


def test_falls_back_to_cvss_when_scanner_gives_no_label():
    """No description, no level — a number beats guessing."""
    rules = {"R": {"id": "R", "properties": {"security-severity": "9.8"}}}
    assert _severity_of({"ruleId": "R"}, rules) == "critical"


def test_level_used_when_description_is_unparseable():
    rules = {"R": {"id": "R", "shortDescription": {"text": "no severity word"},
                   "properties": {}}}
    assert _severity_of(_result("R", "error", "m"), rules) == "high"
    assert _severity_of(_result("R", "warning", "m"), rules) == "medium"
    assert _severity_of(_result("R", "note", "m"), rules) == "low"


def test_critical_is_not_understated_when_only_level_is_present():
    """`level` collapses critical into "error"; we report high, not critical,
    rather than overstate a severity we cannot actually distinguish."""
    rules = {"R": {"id": "R", "properties": {}}}
    assert _severity_of(_result("R", "error", "m"), rules) == "high"


def test_malformed_cvss_does_not_crash():
    rules = {"R": {"id": "R", "properties": {"security-severity": "not-a-number"}}}
    assert _severity_of({"ruleId": "R"}, rules) == "low"


# --- gate behaviour ------------------------------------------------------

def test_high_finding_blocks(tmp_path):
    doc = _sarif(
        [_rule("GHSA-high-x", "high", "8.1")],
        [_result("GHSA-high-x", "error", "A high vulnerability in npm package: next")],
    )
    proc = _run(_write(tmp_path, doc))
    assert proc.returncode == 1
    assert "BLOCKED" in proc.stdout
    assert "security/v0.2.0/SUPPLY-001" in proc.stdout


def test_clean_report_passes(tmp_path):
    proc = _run(_write(tmp_path, _sarif([], [])))
    assert proc.returncode == 0
    assert "PASS" in proc.stdout


def test_missing_sarif_is_a_broken_scan_not_a_pass(tmp_path):
    """An absent report must never be reported as clean."""
    proc = _run(tmp_path / "does-not-exist.sarif")
    assert proc.returncode == 2
    assert "BLOCKED" in proc.stdout


def test_unparseable_sarif_is_a_broken_scan(tmp_path):
    p = tmp_path / "results.sarif"
    p.write_text("{ truncated")
    proc = _run(p)
    assert proc.returncode == 2
    assert "BLOCKED" in proc.stdout


def test_citation_format_matches_agents_md(tmp_path):
    """AGENTS.md requires [<dept>/<version>/<rule-id>]."""
    doc = _sarif([_rule("R", "high", "8.0")], [_result("R", "error", "m")])
    proc = _run(_write(tmp_path, doc))
    assert "[security/v0.2.0/SUPPLY-001]" in proc.stdout


# --- real-artifact guard -------------------------------------------------
#
# Synthetic fixtures alone once let a stale copy of this script pass all
# tests: the edit silently failed to land on disk, pytest imported the OLD
# module, and the hand-written cases happened to exercise paths that passed
# either way. CI then reported an unchanged 36-finding block while the suite
# was green. These tests run against a trimmed slice of an ACTUAL grype
# v0.110.0 SARIF pulled from a real CI run, so they fail loudly if the
# severity precedence regresses.

REAL_SARIF = Path(__file__).parent / "fixtures" / "grype_real_excerpt.sarif"


def test_real_grype_artifact_severities_match_grypes_own_words():
    """Every result must be classified as the word grype itself printed."""
    doc = json.loads(REAL_SARIF.read_text())
    run = doc["runs"][0]
    rules = {r["id"]: r for r in run["tool"]["driver"]["rules"]}

    seen = []
    for result in run["results"]:
        text = result["message"]["text"]
        stated = _DESC_SEVERITY.search(text).group(1).lower()
        assert _severity_of(result, rules) == stated, (
            f"{result['ruleId']}: gate said "
            f"{_severity_of(result, rules)!r} but grype's own message says "
            f"{stated!r} — the citation would contradict the evidence"
        )
        seen.append(stated)

    # Guard the guard: the fixture must actually contain the disagreement
    # case (a medium advisory carrying a high CVSS), or this proves nothing.
    assert "medium" in seen and "high" in seen


def test_real_grype_artifact_blocks_only_the_true_highs():
    """CVSS-first mapping blocked 4/4 here; grype's own labels block 2/4."""
    proc = _run(REAL_SARIF)
    assert proc.returncode == 1, proc.stdout
    assert "2 finding(s) at or above 'high'" in proc.stdout
    # The two medium aiohttp advisories must not appear as blockers.
    assert "GHSA-27mf-ghqm-j3j8" not in proc.stdout
    assert "GHSA-m5qp-6w8w-w647" not in proc.stdout


def test_no_blocking_line_contradicts_its_own_message(tmp_path):
    """No printed line may read '[HIGH] ... A medium vulnerability'."""
    proc = _run(REAL_SARIF)
    for line in proc.stdout.splitlines():
        match = re.match(r"\s*\[\s*(\w+)\]", line)
        if not match:
            continue
        stated = _DESC_SEVERITY.search(line)
        if stated:
            assert match.group(1).lower() == stated.group(1).lower(), (
                f"citation/evidence mismatch on: {line.strip()}"
            )

