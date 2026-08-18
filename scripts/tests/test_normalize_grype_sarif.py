"""Tests for the grype SARIF normalizer.

The load-bearing fixture here is the shape grype v0.110.0 emits when scanning an
SBOM rather than a filesystem: `artifactLocation.uri` is present but EMPTY. That
document is well-formed SARIF and parses fine — it is rejected only at upload,
by Code Scanning, with `locationFromSarifResult: expected artifact location`.

A test built from an idealised SARIF would never have caught this, which is why
these fixtures mirror the real rejected document byte-shape.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from normalize_grype_sarif import normalize  # noqa: E402

SCRIPT = Path(__file__).resolve().parents[1] / "normalize_grype_sarif.py"


def _result_with_empty_uri(rule_id: str = "GHSA-wp53-j4wj-2cfg-python-multipart") -> dict:
    """Exactly what grype writes in SBOM mode — verified against run 32075679327."""
    return {
        "ruleId": rule_id,
        "level": "error",
        "message": {"text": "A high vulnerability in python package: python-multipart"},
        "locations": [
            {
                "physicalLocation": {
                    "artifactLocation": {"uri": ""},
                    "region": {
                        "startLine": 1,
                        "startColumn": 1,
                        "endLine": 1,
                        "endColumn": 1,
                    },
                }
            }
        ],
    }


def _sarif(results: list[dict]) -> dict:
    return {
        "version": "2.1.0",
        "runs": [{"tool": {"driver": {"name": "Grype"}}, "results": results}],
    }


def _uris(doc: dict) -> list[str]:
    return [
        loc["physicalLocation"]["artifactLocation"]["uri"]
        for run in doc["runs"]
        for result in run["results"]
        for loc in result["locations"]
    ]


def test_empty_uri_is_filled():
    doc, repaired = normalize(_sarif([_result_with_empty_uri()]))
    assert repaired == 1
    assert _uris(doc) == ["sbom.spdx.json"]


def test_real_uri_is_left_alone():
    """Filesystem-mode SARIF must pass through untouched."""
    result = _result_with_empty_uri()
    result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] = "apps/api/requirements.txt"
    doc, repaired = normalize(_sarif([result]))
    assert repaired == 0
    assert _uris(doc) == ["apps/api/requirements.txt"]


def test_missing_locations_array_gets_one():
    """Code Scanning rejects an empty locations array too, not just an empty uri."""
    result = _result_with_empty_uri()
    del result["locations"]
    doc, repaired = normalize(_sarif([result]))
    assert repaired == 1
    assert _uris(doc) == ["sbom.spdx.json"]


def test_missing_physical_location_gets_one():
    doc, repaired = normalize(_sarif([{"ruleId": "X", "level": "error", "locations": [{}]}]))
    assert repaired == 1
    assert _uris(doc) == ["sbom.spdx.json"]


def test_no_empty_uri_survives_a_mixed_document():
    """The acceptance property: after normalizing, ZERO empty uris remain.

    This is the exact condition Code Scanning enforces, so assert it directly
    rather than asserting a repair count.
    """
    good = _result_with_empty_uri("GHSA-good")
    good["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] = "package-lock.json"
    doc, _ = normalize(_sarif([_result_with_empty_uri(), good, _result_with_empty_uri("GHSA-3")]))
    assert all(uri for uri in _uris(doc))
    assert len(_uris(doc)) == 3


def test_fallback_uri_is_configurable():
    doc, _ = normalize(_sarif([_result_with_empty_uri()]), fallback_uri="custom-sbom.json")
    assert _uris(doc) == ["custom-sbom.json"]


def test_cli_writes_to_out_and_leaves_source_untouched(tmp_path: Path):
    source = tmp_path / "results.sarif"
    source.write_text(json.dumps(_sarif([_result_with_empty_uri()])))
    out = tmp_path / "normalized.sarif"

    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--sarif", str(source), "--out", str(out)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert _uris(json.loads(out.read_text())) == ["sbom.spdx.json"]
    # the gate reads the original document, so it must not have been rewritten
    assert _uris(json.loads(source.read_text())) == [""]


def test_cli_missing_sarif_is_a_broken_scan_not_a_pass(tmp_path: Path):
    """Absent input must exit 2 (scan broken), never 0."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--sarif", str(tmp_path / "nope.sarif")],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 2
    assert "did not run to completion" in proc.stderr


def test_cli_malformed_json_is_a_broken_scan(tmp_path: Path):
    source = tmp_path / "results.sarif"
    source.write_text('{"runs": [')
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--sarif", str(source)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 2
    assert "not valid JSON" in proc.stderr
