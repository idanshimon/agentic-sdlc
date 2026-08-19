#!/usr/bin/env python3
"""capture_graph_demo_fixture.py - turn seed_graph_demo.py's scenario into a
LOCAL fixture the UI can render with no Cosmos credentials.

WHY: seed_graph_demo.py writes to the live ledger, which needs
LEDGER_MCP_TOKEN. For a demo on a laptop (or any machine where the backend
answers 401) the graph surfaces need the same scenario available offline.

The fixture is generated FROM the seeder by swapping its write() function, so
the story has exactly one source. Hand-copying it is how the two drift.

Usage:
  python3 scripts/capture_graph_demo_fixture.py
"""
from __future__ import annotations

import json
import pathlib
import sys
import uuid
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "apps/ledger-insights-ui/src/lib/demo/graph-fixture.json"

# Deterministic ids so re-running does not churn the diff.
NS = uuid.UUID("5f9c1c62-0000-4000-8000-000000000000")

CAPTURED: list[dict] = []
# Fixed anchor, not now(), or every regeneration rewrites every timestamp.
_T = [datetime(2026, 8, 12, 9, 0, tzinfo=timezone.utc)]


def _next_ts() -> str:
    _T[0] += timedelta(minutes=7)
    return _T[0].isoformat()


def _capture(entry: dict) -> str:
    """Stand-in for seed_graph_demo.write() - records instead of POSTing."""
    entry.setdefault("team_id", "team-demo")
    eid = str(uuid.uuid5(NS, entry["decision"]))
    entry["id"] = eid
    entry["entry_type"] = "runtime"
    entry.setdefault("runtime_kind", "stage_decision")
    entry.setdefault("phi_class", "none")
    entry.setdefault("cost_usd", 0)
    entry.setdefault("model_used", "")
    entry.setdefault("bundle_refs", [])
    entry["created_at"] = _next_ts()
    CAPTURED.append(entry)
    return eid


def main() -> int:
    sys.path.insert(0, str(ROOT / "scripts"))
    import seed_graph_demo as seed  # type: ignore

    seed.DRY = False
    seed.write = _capture  # type: ignore[assignment]
    seed.TOKEN = "capture-mode"

    seed.main()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(CAPTURED, indent=2) + "\n")

    kinds: dict[str, int] = {}
    for e in CAPTURED:
        k = e.get("runtime_kind", "stage_decision")
        kinds[k] = kinds.get(k, 0) + 1
    print("captured %d entries -> %s" % (len(CAPTURED), OUT.relative_to(ROOT)))
    for k, v in sorted(kinds.items()):
        print("  %-20s %d" % (k, v))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
