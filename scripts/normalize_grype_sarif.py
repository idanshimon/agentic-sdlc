#!/usr/bin/env python3
"""normalize_grype_sarif.py — make grype's SBOM-mode SARIF ingestible by Code Scanning.

Why this exists
---------------
When grype scans a *filesystem* or an *image*, every finding carries the path of
the file that introduced the vulnerable package, so
`locations[].physicalLocation.artifactLocation.uri` is a real path.

When grype scans an **SBOM** (`grype sbom:sbom.spdx.json`, which is what
SUPPLY-001 requires — the rule is "the SBOM must be scanned", not "the working
tree must be re-scanned") there is no on-disk location to report. grype's SARIF
presenter still emits the `locations` block, but with an EMPTY uri:

    "artifactLocation": {"uri": ""}

GitHub Code Scanning rejects that document with

    locationFromSarifResult: expected artifact location

repeated once per affected result, and the whole upload fails with
`JOB_STATUS_CONFIGURATION_ERROR`. The findings are perfectly valid — 102 of
them, 33 at high — but none of them reach the Security tab, so the evidence the
gate reasoned over stays invisible to a reviewer.

That is the same failure class SUPPLY-001 was written to eliminate: a control
that produces a verdict nobody can audit. The gate blocking while the evidence
upload 500s is only half a control.

What this does
--------------
Rewrites empty artifact locations to point at the SBOM document itself, which
is the honest answer to "where was this observed?" — the finding genuinely came
from that SBOM, not from a source file. Results that already carry a real uri
are left untouched, so filesystem-mode SARIF passes through unchanged.

This is deliberately NOT done inside enforce_supply_chain.py. That script is the
gate and must reason over exactly what grype produced; rewriting its input would
mean the blocking decision and the published evidence came from different
documents. Normalization is a separate, explicit step in the pipeline.

Exit codes: 0 = wrote a normalized document, 2 = input missing or unparseable.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Code Scanning requires a non-empty relative uri. The SBOM path is checked into
# the run's workspace, so it resolves for a reviewer following the finding back.
_FALLBACK_URI = "sbom.spdx.json"


def normalize(doc: dict, fallback_uri: str = _FALLBACK_URI) -> tuple[dict, int]:
    """Fill empty artifact locations. Returns (document, number_repaired).

    Mutates and returns `doc`. A result with no `locations` at all is given one,
    because Code Scanning also rejects a results entry with an empty locations
    array.
    """
    repaired = 0
    for run in doc.get("runs", []):
        for result in run.get("results", []):
            locations = result.get("locations")
            if not locations:
                result["locations"] = [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": fallback_uri},
                            "region": {"startLine": 1, "startColumn": 1},
                        }
                    }
                ]
                repaired += 1
                continue
            for location in locations:
                physical = location.get("physicalLocation")
                if not physical:
                    location["physicalLocation"] = {
                        "artifactLocation": {"uri": fallback_uri},
                        "region": {"startLine": 1, "startColumn": 1},
                    }
                    repaired += 1
                    continue
                artifact = physical.setdefault("artifactLocation", {})
                if not artifact.get("uri"):
                    artifact["uri"] = fallback_uri
                    repaired += 1
    return doc, repaired


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sarif", required=True, help="grype SARIF to normalize")
    parser.add_argument(
        "--out",
        help="destination path (default: overwrite --sarif in place)",
    )
    parser.add_argument(
        "--fallback-uri",
        default=_FALLBACK_URI,
        help=f"uri to substitute for empty artifact locations (default: {_FALLBACK_URI})",
    )
    args = parser.parse_args(argv)

    source = Path(args.sarif)
    if not source.is_file() or source.stat().st_size == 0:
        print(
            f"::error::normalize_grype_sarif: no SARIF at '{source}'. "
            "The scan did not run to completion.",
            file=sys.stderr,
        )
        return 2

    try:
        doc = json.loads(source.read_text())
    except json.JSONDecodeError as exc:
        print(
            f"::error::normalize_grype_sarif: '{source}' is not valid JSON ({exc}). "
            "Truncated or malformed grype output.",
            file=sys.stderr,
        )
        return 2

    doc, repaired = normalize(doc, args.fallback_uri)
    destination = Path(args.out) if args.out else source
    destination.write_text(json.dumps(doc))

    total = sum(len(run.get("results", [])) for run in doc.get("runs", []))
    print(
        f"normalize_grype_sarif: {total} result(s), "
        f"{repaired} empty artifact location(s) set to '{args.fallback_uri}' -> {destination}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
