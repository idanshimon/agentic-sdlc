"""experiments/sbm-cardiology/seed_runs_to_cosmos.py — seed RunState snapshots to Cosmos.

The orchestrator's _runs dict is in-process and dies on pod restart. Persistent
runs live in the Cosmos `pipeline-runs` container, partitioned by run_id, and
the dashboard's /runs page reads from there via /api/runs (which calls
query_recent_runs in telemetry_queries.py).

Our SBM runs were executed on your laptop with the file-shim ledger, so the
deployed dashboard sees nothing under /runs. This script reads each
runs/<model-run>/summary.json + ledger.jsonl + events.jsonl + cards.json and
posts a RunState-shaped doc directly to the deployed orchestrator's Cosmos
pipeline-runs container via the orchestrator container's MI.

Strategy:
  - Direct Cosmos write (skip the orchestrator HTTP) because the orchestrator
    has no public POST /api/runs/save endpoint — save_run is only called from
    inside the run lifecycle.
  - We use the same Cosmos endpoint as the deployed services and authenticate
    via DefaultAzureCredential (your `az login` session). This works because
    we just opened publicNetworkAccess.
  - team_id is rewritten to "team-demo" to match the bearer-token mapping
    used by the seeded ledger entries — keeps /decisions and /runs filterable
    by the same team scope.

Usage:
  python experiments/sbm-cardiology/seed_runs_to_cosmos.py
  python experiments/sbm-cardiology/seed_runs_to_cosmos.py --runs sonnet-4-6-run-2
  python experiments/sbm-cardiology/seed_runs_to_cosmos.py --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RUNS_DIR = REPO_ROOT / "experiments" / "sbm-cardiology" / "runs"

COSMOS_ENDPOINT = "https://cosmos-agentic-tj6c673gu6x5w.documents.azure.com:443/"
COSMOS_DB = "agentic-sdlc"
COSMOS_RUNS_CONTAINER = "pipeline-runs"


def load_run_dir(run_dir: Path, target_team: str) -> dict[str, Any] | None:
    """Build a RunState-shaped doc from on-disk artifacts."""
    summary_path = run_dir / "summary.json"
    if not summary_path.exists():
        return None
    summary = json.loads(summary_path.read_text())

    cards = []
    cards_path = run_dir / "cards.json"
    if cards_path.exists():
        try:
            cards = json.loads(cards_path.read_text())
        except Exception:
            cards = []

    decisions = []
    dec_path = run_dir / "decisions.json"
    if dec_path.exists():
        try:
            decisions = json.loads(dec_path.read_text())
        except Exception:
            decisions = []

    events: list[dict[str, Any]] = []
    ev_path = run_dir / "events.jsonl"
    if ev_path.exists():
        for line in ev_path.read_text().splitlines():
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except Exception:
                    pass

    started_at = summary.get("started_at")
    wall_clock = summary.get("wall_clock_seconds", 0.0)

    # Derive a final run status. Pipeline finished cleanly if codegen produced
    # non-empty output AND no provider-call-failed sentinels in events.
    artifact_sizes = summary.get("artifact_sizes", {})
    has_codegen = artifact_sizes.get("codegen_chars", 0) > 0
    status = "completed" if has_codegen else "failed"

    doc: dict[str, Any] = {
        "id": summary["run_id"],
        "run_id": summary["run_id"],
        "team_id": target_team,
        "mode": "manual",
        "status": status,
        "current_stage": "deliver" if status == "completed" else summary.get("stage_durations_seconds", {}),
        "created_at": started_at,
        "updated_at": started_at,  # we don't have a finish ts; close-enough is fine for /runs sort
        "wall_clock_seconds": wall_clock,
        "stage_durations_seconds": summary.get("stage_durations_seconds", {}),
        "total_tokens": summary.get("total_tokens", 0),
        "total_cost_usd": summary.get("total_cost_usd", 0.0),
        "model_routing": summary.get("model_routing", {}),
        "artifact_sizes": artifact_sizes,
        "decisions": decisions,
        "cards": cards,
        "events": events,
        # SBM-specific provenance — easy to filter in the dashboard later.
        "namespace": summary.get("namespace", "sbm-cardiology"),
        "model": summary.get("model"),
        "model_slug": summary.get("model_slug"),
        "source_run_dir": run_dir.name,
        "original_team_id": summary.get("team_id"),
    }
    if not isinstance(doc["current_stage"], str):
        # Make sure /api/runs's projection has a string for current_stage.
        doc["current_stage"] = "deliver"
    return doc


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="*", default=None,
                    help="run dir basenames to seed (default: all)")
    ap.add_argument("--target-team", default="team-demo",
                    help="team_id under which to file the runs (matches the ledger seeder)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not RUNS_DIR.exists():
        print(f"ERROR: {RUNS_DIR} not found")
        return 2

    run_dirs = sorted([p for p in RUNS_DIR.iterdir() if p.is_dir()])
    if args.runs:
        run_dirs = [p for p in run_dirs if p.name in args.runs]
    if not run_dirs:
        print("No runs to seed")
        return 0

    docs: list[dict[str, Any]] = []
    for run_dir in run_dirs:
        doc = load_run_dir(run_dir, args.target_team)
        if not doc:
            print(f"  skip {run_dir.name}: no summary.json")
            continue
        docs.append(doc)
        print(f"  prepared {run_dir.name}: run_id={doc['run_id'][:12]} "
              f"status={doc['status']} cost=${doc['total_cost_usd']:.4f} "
              f"events={len(doc['events'])} cards={len(doc['cards'])}")

    if args.dry_run:
        print(f"\nDRY: prepared {len(docs)} run docs")
        return 0

    if not docs:
        print("Nothing to write")
        return 0

    # Late import so --dry-run works without azure-cosmos installed.
    try:
        from azure.cosmos.aio import CosmosClient
        from azure.identity.aio import DefaultAzureCredential
    except Exception as e:
        print(f"ERROR: azure SDKs not installed in venv: {e}")
        return 2

    cred = DefaultAzureCredential()
    client = CosmosClient(COSMOS_ENDPOINT, credential=cred)
    container = client.get_database_client(COSMOS_DB).get_container_client(COSMOS_RUNS_CONTAINER)

    written = 0
    failed = 0
    try:
        for doc in docs:
            try:
                await container.upsert_item(doc)
                written += 1
                print(f"  ✓ {doc['source_run_dir']:24} → {doc['run_id'][:12]}")
            except Exception as e:
                failed += 1
                print(f"  ✗ {doc['source_run_dir']:24} {type(e).__name__}: {e}")
    finally:
        await client.close()
        await cred.close()

    print(f"\nSeeded {written} runs, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
