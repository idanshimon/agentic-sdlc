"""experiments/run_phase_a.py — baseline pipeline runner.

Runs the orchestrator's existing stages (ingest, assessor, architect, test_plan,
codegen, review_scan, deliver) end-to-end against the Patient Vitals Streaming
PRD with FIXED resolver decisions. Persists every artifact for offline analysis.

Honesty contract:
  - Real LLM calls (Databricks-Anthropic, claude-sonnet-4-6).
  - File-shimmed ledger (JSONL); Cosmos NOT touched.
  - Deliver stage writes a local folder mimicking the PR shape, no GitHub call.
  - Resolver gate is satisfied positionally from the YAML fixture.

Output (per run):
  experiments/results/phase-a/run-{N}/
    ├── prd.txt                          (verbatim copy of input PRD)
    ├── cards.json                       (Assessor output, all cards)
    ├── decisions.json                   (resolver decisions applied)
    ├── ledger.jsonl                     (LedgerEntry per decision)
    ├── architecture.md                  (Architect stage full text)
    ├── test_plan.md                     (TestPlan stage full text)
    ├── codegen.py                       (CodeGen stage full text)
    ├── decisions.md                     (decisions_md output, the customer artifact)
    ├── pr_payload.json                  (files dict the deliver stage assembles)
    ├── events.jsonl                     (every StageEvent from the run)
    └── summary.json                     (run-level rollup: tokens, USD, durations, model used)

Usage:
  PYTHONPATH=apps python experiments/run_phase_a.py --run 1
  PYTHONPATH=apps python experiments/run_phase_a.py --run 1 --run 2 --run 3
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
APPS_PATH = REPO_ROOT / "apps"
if str(APPS_PATH) not in sys.path:
    sys.path.insert(0, str(APPS_PATH))

# --- env injection: Databricks-Anthropic credentials -------------------------
def _inject_databricks_env() -> None:
    """Pull creds from ~/.claude/settings.json so we don't shell out for them."""
    claude_settings = Path.home() / ".claude" / "settings.json"
    if not claude_settings.exists():
        raise SystemExit(f"Missing {claude_settings}; cannot reach Databricks-Anthropic")
    raw = json.loads(claude_settings.read_text())
    env = raw.get("env", {})
    for k, v in env.items():
        if k.startswith("ANTHROPIC_") and v:
            os.environ.setdefault(k, v)
    # Force Databricks for the LLM stages: matches v0.7 default in config.py
    # (architect + codegen). Pin assessor + test_plan to Databricks too so
    # we don't depend on AOAI/APIM in this experiment.
    os.environ["STAGE_ASSESSOR_PROVIDER"] = "databricks"
    os.environ["STAGE_ASSESSOR_MODEL"] = "databricks-claude-sonnet-4-6"
    os.environ["STAGE_ASSESSOR_VIA_APIM"] = "false"
    os.environ["STAGE_TEST_PLAN_PROVIDER"] = "databricks"
    os.environ["STAGE_TEST_PLAN_MODEL"] = "databricks-claude-sonnet-4-6"
    os.environ["STAGE_TEST_PLAN_VIA_APIM"] = "false"
    os.environ["STAGE_REVIEW_SCAN_PROVIDER"] = "databricks"
    os.environ["STAGE_REVIEW_SCAN_MODEL"] = "databricks-claude-sonnet-4-6"
    os.environ["STAGE_REVIEW_SCAN_VIA_APIM"] = "false"
    os.environ["STAGE_INGEST_PROVIDER"] = "databricks"
    os.environ["STAGE_INGEST_MODEL"] = "databricks-claude-sonnet-4-6"
    os.environ["STAGE_INGEST_VIA_APIM"] = "false"
    os.environ["STAGE_ARCHITECT_VIA_APIM"] = "false"
    os.environ["STAGE_CODEGEN_VIA_APIM"] = "false"


_inject_databricks_env()


# --- runtime patch: raise max_tokens cap so Assessor JSON doesn't truncate ---
# The orchestrator's `_call()` helper does NOT pass max_tokens through to
# providers — providers default to 4096. The Assessor prompt requires ~5-8
# structured cards with options + rationale + downstream_impact, easily
# exceeding 4k tokens of output. Truncated JSON falls back to 2 hard-coded
# stub cards with no `options[]`, which makes resolver decisions land as
# "accept: (no options)" and breaks the downstream Architect.
#
# This patch is APPLIED ONLY IN THE EXPERIMENT HARNESS — it does not change
# the deployed orchestrator. Both Phase A and Phase B run with the same
# patched provider so the comparison stays fair. The patch raises the
# default to 8192, which fits the full Assessor output cleanly.
def _patch_provider_max_tokens() -> None:
    from orchestrator.providers.databricks import DatabricksAnthropicProvider
    _orig_chat = DatabricksAnthropicProvider.chat

    async def _chat_with_higher_cap(
        self, messages, model, max_tokens=8192, temperature=0.2, headers=None
    ):
        return await _orig_chat(
            self, messages=messages, model=model, max_tokens=max_tokens,
            temperature=temperature, headers=headers,
        )

    DatabricksAnthropicProvider.chat = _chat_with_higher_cap


_patch_provider_max_tokens()

# Imports from the orchestrator package (live code, no patches).
from orchestrator import _pipeline_stages as stages  # noqa: E402
from orchestrator.models import (  # noqa: E402
    AmbiguityCard,
    GateDecision,
    LedgerEntry,
    RunMode,
    RunState,
    Stage,
    StageEvent,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- file-shim ledger --------------------------------------------------------
class FileLedger:
    """Drop-in replacement for `orchestrator.ledger.Ledger` for local runs.

    Writes LedgerEntry rows as JSONL. Mirrors the small surface the experiment
    needs: write_decision, append. No invariant write-block (Phase A doesn't
    test invariants — that's a separate concern from spec-shape).
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # truncate
        self.path.write_text("")

    async def write_decision(self, entry: LedgerEntry) -> LedgerEntry:
        with self.path.open("a") as fh:
            fh.write(entry.model_dump_json() + "\n")
        return entry

    async def list_for_team(self, team_id: str) -> list[dict]:  # for completeness
        if not self.path.exists():
            return []
        out: list[dict] = []
        for line in self.path.read_text().splitlines():
            if line.strip():
                d = json.loads(line)
                if d.get("team_id") == team_id:
                    out.append(d)
        return out


# --- main runner -------------------------------------------------------------
async def run_one(run_idx: int, prd_text: str, fixture: dict, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "prd.txt").write_text(prd_text)
    (out_dir / "fixture.yaml").write_text(yaml.safe_dump(fixture, sort_keys=False))

    run = RunState(team_id=f"experiment-phase-a-run-{run_idx}", mode=RunMode.MANUAL)
    ledger = FileLedger(out_dir / "ledger.jsonl")
    t0 = time.time()
    stage_durations: dict[str, float] = {}

    print(f"\n{'=' * 70}\n[run {run_idx}] starting (run_id={run.run_id[:12]})\n{'=' * 70}")

    # 1. Ingest
    s = time.time()
    async for ev in stages.stage_ingest(run, prd_text):
        pass
    stage_durations["ingest"] = time.time() - s
    print(f"[run {run_idx}] ingest done ({stage_durations['ingest']:.1f}s)")

    # 2. Assessor
    s = time.time()
    async for ev in stages.stage_assessor(run, prd_text):
        pass
    stage_durations["assessor"] = time.time() - s
    print(
        f"[run {run_idx}] assessor done ({stage_durations['assessor']:.1f}s) — "
        f"{len(run.cards)} cards ({sum(c.is_gating for c in run.cards)} gating)"
    )
    (out_dir / "cards.json").write_text(
        json.dumps([c.model_dump() for c in run.cards], indent=2)
    )

    # 3. Resolver gate — apply fixture decisions to gating cards positionally
    gating_cards = [c for c in run.cards if c.is_gating]
    fixture_decisions = fixture.get("decisions", [])
    decisions_applied: list[GateDecision] = []
    for i, card in enumerate(gating_cards):
        if i < len(fixture_decisions):
            entry = fixture_decisions[i]
            kind = entry.get("decision_kind", "accept")
            actor = entry.get("actor", "experiment@local")
            if kind == "accept":
                opt_idx = int(entry.get("option_index", 0))
                if opt_idx >= len(card.options):
                    opt_idx = 0
                resolution = (
                    card.options[opt_idx].resolution if card.options else "(no options)"
                )
                gd = GateDecision(
                    card_id=card.card_id,
                    decision_kind="accept",
                    resolution_text=resolution,
                    option_index=opt_idx,
                    actor=actor,
                )
            elif kind == "swap":
                gd = GateDecision(
                    card_id=card.card_id,
                    decision_kind="swap",
                    resolution_text=str(entry.get("resolution_text", "")),
                    actor=actor,
                )
            else:  # reject
                gd = GateDecision(
                    card_id=card.card_id, decision_kind="reject",
                    resolution_text="", actor=actor,
                )
        else:
            # Default: accept-recommended (option 0)
            resolution = card.options[0].resolution if card.options else "(no options)"
            gd = GateDecision(
                card_id=card.card_id, decision_kind="accept",
                resolution_text=resolution, option_index=0,
                actor="experiment@local",
            )
        run.decisions.append(gd)
        decisions_applied.append(gd)

        # Write ledger entry (mimics main.py /approve handler)
        ledger_entry = LedgerEntry(
            team_id=run.team_id,
            run_id=run.run_id,
            card_id=card.card_id,
            ambiguity_class=card.ambiguity_class,
            slot_value_hash=card.slot_value_hash,
            resolution_text=gd.resolution_text,
            decision_kind=gd.decision_kind,
            created_by=gd.actor,
        )
        await ledger.write_decision(ledger_entry)

    (out_dir / "decisions.json").write_text(
        json.dumps([d.model_dump() for d in decisions_applied], indent=2)
    )
    print(f"[run {run_idx}] resolver done — {len(decisions_applied)} decisions applied")

    # 4. Architect
    s = time.time()
    async for ev in stages.stage_architect(run):
        pass
    stage_durations["architect"] = time.time() - s
    arch_text = ""
    for ev in run.events:
        if (ev.payload or {}).get("architecture"):
            arch_text = ev.payload["architecture"]
    (out_dir / "architecture.md").write_text(arch_text or "(empty)")
    print(f"[run {run_idx}] architect done ({stage_durations['architect']:.1f}s)")

    # 5. Test plan
    s = time.time()
    async for ev in stages.stage_test_plan(run):
        pass
    stage_durations["test_plan"] = time.time() - s
    tp_text = ""
    for ev in run.events:
        if (ev.payload or {}).get("test_plan"):
            tp_text = ev.payload["test_plan"]
    (out_dir / "test_plan.md").write_text(tp_text or "(empty)")
    print(f"[run {run_idx}] test_plan done ({stage_durations['test_plan']:.1f}s)")

    # 6. Codegen
    s = time.time()
    async for ev in stages.stage_codegen(run):
        pass
    stage_durations["codegen"] = time.time() - s
    code_text = ""
    for ev in run.events:
        if (ev.payload or {}).get("code"):
            code_text = ev.payload["code"]
    (out_dir / "codegen.py").write_text(code_text or "# (empty)")
    print(f"[run {run_idx}] codegen done ({stage_durations['codegen']:.1f}s)")

    # 7. Review/scan (stub — passes)
    s = time.time()
    async for ev in stages.stage_review_scan(run):
        pass
    stage_durations["review_scan"] = time.time() - s

    # 8. Deliver — emit local folder mimicking the PR
    s = time.time()
    pr_dir = out_dir / "pr_payload"
    pr_dir.mkdir(exist_ok=True)
    decisions_summary = stages._decisions_summary(run)
    pr_files = {
        "src/main.py": code_text or "# generated\n",
        "tests/test_main.py": tp_text or "# tests\n",
        "docs/architecture.md": arch_text or "# architecture\n",
        "decisions.md": decisions_summary,
    }
    for path, content in pr_files.items():
        full = pr_dir / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content)
    (out_dir / "pr_payload.json").write_text(
        json.dumps({"files": list(pr_files.keys())}, indent=2)
    )
    (out_dir / "decisions.md").write_text(decisions_summary)
    stage_durations["deliver"] = time.time() - s

    # Events log
    (out_dir / "events.jsonl").write_text(
        "\n".join(ev.model_dump_json() for ev in run.events)
    )

    summary = {
        "phase": "A",
        "run_idx": run_idx,
        "run_id": run.run_id,
        "team_id": run.team_id,
        "started_at": _now(),
        "wall_clock_seconds": round(time.time() - t0, 2),
        "stage_durations_seconds": {k: round(v, 2) for k, v in stage_durations.items()},
        "total_tokens": run.total_tokens,
        "total_cost_usd": round(run.total_cost_usd, 4),
        "card_count": len(run.cards),
        "gating_card_count": sum(c.is_gating for c in run.cards),
        "decisions_applied": len(decisions_applied),
        "model_routing": {
            "ingest": "databricks-claude-sonnet-4-6",
            "assessor": "databricks-claude-sonnet-4-6",
            "architect": "databricks-claude-sonnet-4-6",
            "test_plan": "databricks-claude-sonnet-4-6",
            "codegen": "databricks-claude-sonnet-4-6",
            "review_scan": "databricks-claude-sonnet-4-6",
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    print(
        f"[run {run_idx}] DONE  total={summary['wall_clock_seconds']:.1f}s  "
        f"tokens={summary['total_tokens']}  ${summary['total_cost_usd']:.4f}"
    )
    return summary


async def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--run", action="append", type=int,
                   help="Run index (1-based). May be passed multiple times.")
    p.add_argument("--out", type=Path,
                   default=REPO_ROOT / "experiments" / "results" / "phase-a")
    args = p.parse_args()
    runs = args.run or [1, 2, 3]

    prd = (REPO_ROOT / "samples" / "prds" / "patient-vitals-streaming.txt").read_text()
    fixture = yaml.safe_load(
        (REPO_ROOT / "experiments" / "fixtures" / "resolver-decisions.yaml").read_text()
    )

    rollups: list[dict] = []
    for r in runs:
        rollups.append(await run_one(r, prd, fixture, args.out / f"run-{r}"))

    # Phase summary
    phase_summary = {
        "phase": "A",
        "ran_at": _now(),
        "n_runs": len(rollups),
        "total_seconds": round(sum(r["wall_clock_seconds"] for r in rollups), 2),
        "total_tokens": sum(r["total_tokens"] for r in rollups),
        "total_cost_usd": round(sum(r["total_cost_usd"] for r in rollups), 4),
        "runs": rollups,
    }
    (args.out / "phase-summary.json").write_text(json.dumps(phase_summary, indent=2))
    print(
        f"\n=== PHASE A SUMMARY ===\n"
        f"  N={phase_summary['n_runs']}  "
        f"total={phase_summary['total_seconds']:.1f}s  "
        f"tokens={phase_summary['total_tokens']}  "
        f"${phase_summary['total_cost_usd']:.4f}"
    )


if __name__ == "__main__":
    asyncio.run(main())
