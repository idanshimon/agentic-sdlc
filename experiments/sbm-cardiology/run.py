"""experiments/sbm-cardiology/run.py — parameterized pipeline runner.

Drives the orchestrator's stages end-to-end against the SBM cardiology
deterioration alert PRD with FIXED resolver decisions. Parameterized:
  --model        which model carries the LLM stages (default: claude-sonnet-4-6)
  --provider     which provider to route through (default: databricks)
  --run-idx      run index for output folder naming (default: 1)
  --team-suffix  appended to team_id for Track B partition isolation

Honesty contract (mirrors run_phase_a.py):
  - Real LLM calls. File-shimmed ledger (JSONL); Cosmos NOT touched.
  - Deliver stage writes a local folder mimicking the PR shape, no GitHub call.
  - Resolver gate is satisfied positionally from the YAML fixture.
  - Provider max_tokens cap raised to 8192 in the test harness ONLY (matches
    run_phase_a.py — the deployed orchestrator is unmodified).

Output:
  experiments/sbm-cardiology/runs/<model-id>-run-<N>/
    ├── prd.txt
    ├── fixture.yaml
    ├── cards.json                       (Assessor output, all cards)
    ├── decisions.json                   (resolver decisions applied)
    ├── ledger.jsonl                     (LedgerEntry per decision)
    ├── architecture.md                  (Architect stage full text)
    ├── test_plan.md                     (TestPlan stage full text)
    ├── codegen.py                       (CodeGen stage full text)
    ├── decisions.md                     (the customer artifact)
    ├── pr_payload/                      (PR-shaped folder)
    ├── events.jsonl                     (every StageEvent)
    └── summary.json                     (rollup: tokens, USD, durations, model)

Usage:
  PYTHONPATH=apps python experiments/sbm-cardiology/run.py \
      --model databricks-claude-sonnet-4-6 --run-idx 1
  PYTHONPATH=apps python experiments/sbm-cardiology/run.py \
      --model databricks-claude-haiku-4-5 --run-idx 1
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
APPS_PATH = REPO_ROOT / "apps"
if str(APPS_PATH) not in sys.path:
    sys.path.insert(0, str(APPS_PATH))


# --- env injection: Databricks-Anthropic credentials -------------------------
def _inject_databricks_env(model: str) -> None:
    """Pull creds from ~/.claude/settings.json so we don't shell out for them.

    Pin every LLM stage to the chosen Databricks model. Phase-A runs were
    sonnet-only; this runner accepts haiku / opus too via --model."""
    claude_settings = Path.home() / ".claude" / "settings.json"
    if not claude_settings.exists():
        raise SystemExit(f"Missing {claude_settings}; cannot reach Databricks-Anthropic")
    raw = json.loads(claude_settings.read_text())
    env = raw.get("env", {})
    for k, v in env.items():
        if k.startswith("ANTHROPIC_") and v:
            os.environ.setdefault(k, v)
    for stage in ("INGEST", "ASSESSOR", "ARCHITECT", "TEST_PLAN", "CODEGEN", "REVIEW_SCAN"):
        os.environ[f"STAGE_{stage}_PROVIDER"] = "databricks"
        os.environ[f"STAGE_{stage}_MODEL"] = model
        os.environ[f"STAGE_{stage}_VIA_APIM"] = "false"


def _patch_provider_max_tokens() -> None:
    """Raise default max_tokens to 16384 so codegen output fits.

    Same pattern as run_phase_a.py — applies in the experiment harness ONLY.

    Why 16384 not 8192: codegen output for a multi-component healthcare service
    (FHIR gateway + scoring engine + notification fanout + dashboard + bulk
    export + auth simulators + tests) regularly exceeds 8K tokens. Empirically
    verified on the SBM cardiology PRD: both sonnet-4-6 and haiku-4-5 truncated
    around line 850-860 with unterminated string literals at 8K. Raising to
    16K gives ~1.5× headroom on the worst observed case.
    """
    from orchestrator.providers.databricks import DatabricksAnthropicProvider
    _orig_chat = DatabricksAnthropicProvider.chat

    async def _chat_with_higher_cap(
        self, messages, model, max_tokens=16384, temperature=0.2, headers=None
    ):
        return await _orig_chat(
            self, messages=messages, model=model, max_tokens=max_tokens,
            temperature=temperature, headers=headers,
        )

    DatabricksAnthropicProvider.chat = _chat_with_higher_cap


def _model_slug(model: str) -> str:
    """Filesystem-safe model slug: 'databricks-claude-sonnet-4-6' → 'sonnet-4-6'."""
    s = re.sub(r"^databricks-claude-", "", model)
    s = re.sub(r"^claude-", "", s)
    return re.sub(r"[^a-zA-Z0-9._-]", "-", s)


def _strip_code_fences(text: str) -> str:
    """Strip leading/trailing markdown code fences from LLM output.

    Despite the codegen prompt explicitly saying "no markdown fences", both
    sonnet and haiku occasionally still wrap their output in ```python ... ```
    blocks (caught on the haiku-4-5-run-2 SBM cardiology run). Defense in
    depth: strip them at parse time so the artifact reaches Container Apps
    deploy without a syntax error.

    Idempotent: if no fences, returns input unchanged.
    """
    s = text.strip()
    # Leading fence: ```python\n or ```\n
    m = re.match(r"^```(?:[a-zA-Z0-9_-]+)?\s*\n", s)
    if m:
        s = s[m.end():]
    # Trailing fence: \n```
    s = re.sub(r"\n```\s*$", "", s)
    return s


# --- file-shim ledger --------------------------------------------------------
class FileLedger:
    """JSONL ledger drop-in. Mirrors orchestrator.ledger.Ledger surface."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("")

    async def write_decision(self, entry) -> Any:
        with self.path.open("a") as fh:
            fh.write(entry.model_dump_json() + "\n")
        return entry


async def run_one(
    *,
    model: str,
    run_idx: int,
    team_suffix: str,
    prd_path: Path,
    fixture_path: Path,
    out_root: Path,
) -> dict:
    # late imports — must follow env injection
    from orchestrator import _pipeline_stages as stages  # noqa
    from orchestrator.models import (  # noqa
        GateDecision, LedgerEntry, RunMode, RunState,
    )

    slug = _model_slug(model)
    out_dir = out_root / f"{slug}-run-{run_idx}"
    out_dir.mkdir(parents=True, exist_ok=True)

    prd_text = prd_path.read_text()
    fixture = yaml.safe_load(fixture_path.read_text())
    (out_dir / "prd.txt").write_text(prd_text)
    (out_dir / "fixture.yaml").write_text(yaml.safe_dump(fixture, sort_keys=False))

    team_id = f"team-sbm-cardiology-{team_suffix}-{slug}-run-{run_idx}"
    run = RunState(team_id=team_id, mode=RunMode.MANUAL)
    ledger = FileLedger(out_dir / "ledger.jsonl")
    t0 = time.time()
    stage_durations: dict[str, float] = {}

    print(f"\n{'=' * 70}")
    print(f"[sbm] model={model} run={run_idx} run_id={run.run_id[:12]} team={team_id}")
    print('=' * 70)

    # 1. Ingest
    s = time.time()
    async for _ in stages.stage_ingest(run, prd_text):
        pass
    stage_durations["ingest"] = time.time() - s
    print(f"[sbm] ingest done ({stage_durations['ingest']:.1f}s)")

    # 2. Assessor
    s = time.time()
    async for _ in stages.stage_assessor(run, prd_text):
        pass
    stage_durations["assessor"] = time.time() - s
    n_gating = sum(c.is_gating for c in run.cards)
    print(f"[sbm] assessor done ({stage_durations['assessor']:.1f}s) — "
          f"{len(run.cards)} cards ({n_gating} gating)")
    (out_dir / "cards.json").write_text(
        json.dumps([c.model_dump() for c in run.cards], indent=2)
    )

    # 3. Resolver gate — apply fixture decisions positionally
    gating_cards = [c for c in run.cards if c.is_gating]
    fixture_decisions = fixture.get("decisions", [])
    decisions_applied: list[Any] = []
    for i, card in enumerate(gating_cards):
        if i < len(fixture_decisions):
            entry = fixture_decisions[i]
            kind = entry.get("decision_kind", "accept")
            actor = entry.get("actor", "experiment@sbm-cardiology")
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
            resolution = card.options[0].resolution if card.options else "(no options)"
            gd = GateDecision(
                card_id=card.card_id, decision_kind="accept",
                resolution_text=resolution, option_index=0,
                actor="experiment@sbm-cardiology",
            )
        run.decisions.append(gd)
        decisions_applied.append(gd)

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
    print(f"[sbm] resolver done — {len(decisions_applied)} decisions applied")

    # 4. Architect
    s = time.time()
    async for _ in stages.stage_architect(run):
        pass
    stage_durations["architect"] = time.time() - s
    arch_text = ""
    for ev in run.events:
        if (ev.payload or {}).get("architecture"):
            arch_text = ev.payload["architecture"]
    (out_dir / "architecture.md").write_text(arch_text or "(empty)")
    print(f"[sbm] architect done ({stage_durations['architect']:.1f}s, {len(arch_text)} chars)")

    # 5. Test plan
    s = time.time()
    async for _ in stages.stage_test_plan(run):
        pass
    stage_durations["test_plan"] = time.time() - s
    tp_text = ""
    for ev in run.events:
        if (ev.payload or {}).get("test_plan"):
            tp_text = ev.payload["test_plan"]
    (out_dir / "test_plan.md").write_text(tp_text or "(empty)")
    print(f"[sbm] test_plan done ({stage_durations['test_plan']:.1f}s, {len(tp_text)} chars)")

    # 6. Codegen — emits app_code + test_code separately (two LLM calls).
    s = time.time()
    async for _ in stages.stage_codegen(run):
        pass
    stage_durations["codegen"] = time.time() - s
    app_code = ""
    test_code = ""
    for ev in run.events:
        p = ev.payload or {}
        if "app_code" in p:
            app_code = p["app_code"]
        if "test_code" in p:
            test_code = p["test_code"]
    # Back-compat: if stage emitted only legacy `code`, treat it as app_code.
    if not app_code:
        for ev in run.events:
            if (ev.payload or {}).get("code"):
                app_code = ev.payload["code"]
    # Strip any markdown code fences the LLM may have added despite the prompt.
    app_code = _strip_code_fences(app_code)
    test_code = _strip_code_fences(test_code)
    (out_dir / "codegen.py").write_text(app_code or "# (empty)")
    (out_dir / "tests.py").write_text(test_code or "# (no tests)")
    print(f"[sbm] codegen done ({stage_durations['codegen']:.1f}s, "
          f"app={len(app_code)} chars, tests={len(test_code)} chars)")

    # 7. Review/scan
    s = time.time()
    async for _ in stages.stage_review_scan(run):
        pass
    stage_durations["review_scan"] = time.time() - s
    print(f"[sbm] review_scan done ({stage_durations['review_scan']:.1f}s)")

    # 8. Deliver — emit local PR-shaped folder. Now that codegen emits app +
    # tests separately, route them to the right paths instead of dumping
    # both into src/main.py.
    s = time.time()
    pr_dir = out_dir / "pr_payload"
    pr_dir.mkdir(exist_ok=True)
    decisions_summary = stages._decisions_summary(run)
    pr_files = {
        "app.py": app_code or "# generated\n",
        "tests/test_app.py": test_code or "# tests\n",
        "tests/test_plan.md": tp_text or "# test plan\n",
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

    # Events JSONL
    with (out_dir / "events.jsonl").open("w") as fh:
        for ev in run.events:
            fh.write(ev.model_dump_json() + "\n")

    total_seconds = time.time() - t0

    # Pull token + USD totals from RunState (orchestrator stages aggregate
    # there directly via run.total_tokens / run.total_cost_usd). Reading from
    # event payloads gives 0 because the stages don't emit per-event tokens
    # in the payload — they call record_tokens() which goes to telemetry.
    total_tokens = run.total_tokens
    total_usd = run.total_cost_usd

    summary = {
        "namespace": "sbm-cardiology",
        "model": model,
        "model_slug": slug,
        "run_idx": run_idx,
        "run_id": run.run_id,
        "team_id": team_id,
        "started_at": datetime.fromtimestamp(t0, timezone.utc).isoformat(),
        "wall_clock_seconds": round(total_seconds, 2),
        "stage_durations_seconds": {k: round(v, 2) for k, v in stage_durations.items()},
        "total_tokens": total_tokens,
        "total_cost_usd": round(total_usd, 4),
        "card_count": len(run.cards),
        "gating_card_count": n_gating,
        "decisions_applied": len(decisions_applied),
        "model_routing": {
            stage: {
                "provider": os.environ.get(f"STAGE_{stage.upper()}_PROVIDER"),
                "model": os.environ.get(f"STAGE_{stage.upper()}_MODEL"),
            }
            for stage in ("ingest", "assessor", "architect", "test_plan", "codegen", "review_scan")
        },
        "artifact_sizes": {
            "architecture_chars": len(arch_text),
            "test_plan_chars": len(tp_text),
            "codegen_chars": len(app_code),
            "test_code_chars": len(test_code),
            "decisions_md_chars": len(decisions_summary),
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"[sbm] DONE in {total_seconds:.1f}s · "
          f"{total_tokens} tokens · ${total_usd:.4f} · → {out_dir}")
    return summary


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="databricks-claude-sonnet-4-6",
                   help="Databricks-Anthropic model id (sonnet-4-6, haiku-4-5, opus-4-7)")
    p.add_argument("--run-idx", type=int, default=1)
    p.add_argument("--team-suffix", default="exp",
                   help="appended to team_id for Track B partition isolation")
    p.add_argument("--prd",
                   default=str(REPO_ROOT / "experiments" / "sbm-cardiology" / "prd.txt"))
    p.add_argument("--fixture",
                   default=str(REPO_ROOT / "experiments" / "sbm-cardiology"
                               / "fixtures" / "resolver-decisions.yaml"))
    p.add_argument("--out-root",
                   default=str(REPO_ROOT / "experiments" / "sbm-cardiology" / "runs"))
    args = p.parse_args()

    _inject_databricks_env(args.model)
    _patch_provider_max_tokens()

    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    asyncio.run(run_one(
        model=args.model,
        run_idx=args.run_idx,
        team_suffix=args.team_suffix,
        prd_path=Path(args.prd),
        fixture_path=Path(args.fixture),
        out_root=out_root,
    ))


if __name__ == "__main__":
    main()
