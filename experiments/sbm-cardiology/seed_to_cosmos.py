"""experiments/sbm-cardiology/seed_to_cosmos.py — seed file-shim ledger entries to deployed Cosmos.

Reads every ledger.jsonl from experiments/sbm-cardiology/runs/<model-run>/, posts each entry
to the deployed ledger-mcp via ledger.write_runtime, so they show up in the deployed
/decisions dashboard as DecisionCards / DecisionTable rows with the new TeachingSignalBar.

The MCP enforces token-scoped team_id. The only token configured today maps to "team-demo",
so we rewrite team_id at upload time. The original SBM team_id is preserved in the entry's
agent_session_id and decision text so the partition shift is honest about what happened.

Usage:
  python experiments/sbm-cardiology/seed_to_cosmos.py
  python experiments/sbm-cardiology/seed_to_cosmos.py --runs haiku-4-5-run-2
  python experiments/sbm-cardiology/seed_to_cosmos.py --dry-run

Env required:
  LEDGER_MCP_URL    deployed MCP base URL (default: ca-ledger-mcp.whitewater-...)
  LEDGER_MCP_TOKEN  bearer token for team-demo
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import urllib.request
import urllib.error

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RUNS_DIR = REPO_ROOT / "experiments" / "sbm-cardiology" / "runs"

DEFAULT_MCP_URL = (
    "https://ca-ledger-mcp.whitewater-f74a5db8.eastus2.azurecontainerapps.io"
)
DEFAULT_TOKEN = "REDACTED_ROTATED_TOKEN"


def post_runtime(url: str, token: str, entry: dict[str, Any]) -> tuple[int, dict | str]:
    body = json.dumps(entry).encode()
    req = urllib.request.Request(
        f"{url}/tools/ledger.write_runtime",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            data = json.loads(e.read().decode() or "{}")
        except Exception:
            data = e.read().decode() if hasattr(e, "read") else str(e)
        return e.code, data
    except Exception as e:
        return 0, f"error: {type(e).__name__}: {e}"


# Pretty stage labels — file-shim entries don't carry a stage field on
# resolver decisions; the orchestrator emits them as runtime entries with
# decision_kind. We synthesize a stage="resolver" so the dashboard can show
# them in the table's Stage column instead of a blank.
def _decorate(entry: dict[str, Any], target_team_id: str, source_run: str) -> dict[str, Any]:
    out = dict(entry)
    original_team = out.get("team_id", "(unknown)")
    out["team_id"] = target_team_id
    out["actor"] = {
        "kind": "human",
        "id": entry.get("created_by") or entry.get("actor", {}).get("id") or "experiment@sbm-cardiology",
    }
    if "decision" not in out:
        out["decision"] = entry.get("resolution_text") or entry.get("ambiguity_class") or "(no decision text)"
    if "rationale" not in out:
        ratl = []
        if entry.get("ambiguity_class"):
            ratl.append(f"Ambiguity class: {entry['ambiguity_class']}")
        if entry.get("decision_kind"):
            ratl.append(f"Decision kind: {entry['decision_kind']}")
        ratl.append(f"Source run: {source_run} (original team_id: {original_team})")
        out["rationale"] = ". ".join(ratl)
    out.setdefault("phi_class", "low" if "phi" in (entry.get("ambiguity_class") or "") else "none")
    out.setdefault("model_used", "")  # fill from summary later if useful
    out.setdefault("stage", "resolver")
    out.setdefault("runtime_kind", "stage_decision")
    out.setdefault("bundle_refs", [])
    out.setdefault("agent_session_id", f"sbm-{source_run}-{entry.get('card_id', 'unknown')[:8]}")
    return out


def load_summary_models(run_dir: Path) -> str:
    summary = run_dir / "summary.json"
    if summary.exists():
        try:
            data = json.loads(summary.read_text())
            return data.get("model", "")
        except Exception:
            return ""
    return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="*", default=None,
                    help="run dir basenames to seed (default: all)")
    ap.add_argument("--mcp-url", default=os.environ.get("LEDGER_MCP_URL", DEFAULT_MCP_URL))
    ap.add_argument("--token", default=os.environ.get("LEDGER_MCP_TOKEN", DEFAULT_TOKEN))
    ap.add_argument("--target-team", default="team-demo",
                    help="team_id to write under (must match the MCP's bearer token mapping)")
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

    total_posted = 0
    total_failed = 0
    for run_dir in run_dirs:
        ledger_path = run_dir / "ledger.jsonl"
        if not ledger_path.exists():
            print(f"  skip {run_dir.name}: no ledger.jsonl")
            continue
        model = load_summary_models(run_dir)
        entries = []
        for line in ledger_path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            entries.append(json.loads(line))
        print(f"\n{run_dir.name} ({len(entries)} entries, model={model})")

        for entry in entries:
            decorated = _decorate(entry, args.target_team, run_dir.name)
            if model and not decorated.get("model_used"):
                decorated["model_used"] = model

            if args.dry_run:
                print(f"  DRY {decorated['ambiguity_class']:24} team={decorated['team_id']}")
                total_posted += 1
                continue

            status, data = post_runtime(args.mcp_url, args.token, decorated)
            if status == 200:
                eid = data.get("id", "?") if isinstance(data, dict) else "?"
                print(f"  ✓   {decorated['ambiguity_class']:24} → {eid[:12]}")
                total_posted += 1
            else:
                print(f"  ✗   {decorated['ambiguity_class']:24} status={status}: "
                      f"{json.dumps(data) if isinstance(data, dict) else data}")
                total_failed += 1
            time.sleep(0.05)  # be gentle with Cosmos

    print(f"\nSeeded {total_posted} entries, {total_failed} failed")
    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
