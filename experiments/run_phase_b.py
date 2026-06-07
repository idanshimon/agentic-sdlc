"""experiments/run_phase_b.py — OpenSpec-instrumented pipeline runner.

Same harness as run_phase_a.py for ingest, assessor, resolver, codegen,
review_scan. The hypothesis is tested at the Architect / TestPlan / Deliver
stages, where free-form prose is replaced with typed OpenSpec deltas.

Architect emits a structured response with three sub-artifacts:
  - proposal.md   (Why / What Changes / Capabilities / Impact)
  - design.md     (Context / Goals / Non-Goals / Decisions / Risks)
  - spec.md       (## ADDED Requirements with MUST/SHALL + #### Scenario blocks)

Each Requirement carries an explicit `[decision: <card_id>]` back-reference
to the Resolver decision that drove it. This is mechanically auditable
(grep), not paraphrase-citation as in Phase A.

TestPlan reads the spec.md and emits one pytest skeleton per Scenario
block, mechanically. The mapping is 1:1, traceable by name.

Deliver writes `pr_payload/openspec/changes/<run-id>-patient-vitals/` with
the four canonical OpenSpec files, plus the Phase A-style files
(src/main.py, decisions.md). Then runs `openspec validate` on the change
to score dimension 5.

Ledger gains `entry_type=spec_delta` rows — one per ADDED Requirement.

Honesty contract:
  - Same model (Databricks claude-sonnet-4-6) at same temperature
  - Same fixture, same PRD, same Assessor + Resolver paths
  - max_tokens patch identical to Phase A
  - No Phase A artifact is touched

Usage:
  PYTHONPATH=apps python experiments/run_phase_b.py --run 1
  PYTHONPATH=apps python experiments/run_phase_b.py --run 1 --run 2 --run 3
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import subprocess
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


# --- env injection (identical to Phase A) -----------------------------------
def _inject_databricks_env() -> None:
    claude_settings = Path.home() / ".claude" / "settings.json"
    if not claude_settings.exists():
        raise SystemExit(f"Missing {claude_settings}")
    raw = json.loads(claude_settings.read_text())
    env = raw.get("env", {})
    for k, v in env.items():
        if k.startswith("ANTHROPIC_") and v:
            os.environ.setdefault(k, v)
    for stage in ("INGEST", "ASSESSOR", "ARCHITECT", "TEST_PLAN",
                  "CODEGEN", "REVIEW_SCAN"):
        os.environ[f"STAGE_{stage}_PROVIDER"] = "databricks"
        os.environ[f"STAGE_{stage}_MODEL"] = "databricks-claude-sonnet-4-6"
        os.environ[f"STAGE_{stage}_VIA_APIM"] = "false"


_inject_databricks_env()


def _patch_provider_max_tokens() -> None:
    """Identical patch to Phase A — fairness contract."""
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

from orchestrator import _pipeline_stages as stages  # noqa: E402
from orchestrator._pipeline_stages import _call, _ev  # noqa: E402
from orchestrator.models import (  # noqa: E402
    GateDecision, LedgerEntry, RunMode, RunState, Stage,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- file ledger (same as Phase A, plus spec_delta support) ------------------
class FileLedger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("")

    async def write_decision(self, entry: LedgerEntry) -> LedgerEntry:
        with self.path.open("a") as fh:
            fh.write(entry.model_dump_json() + "\n")
        return entry

    async def write_spec_delta(self, *, run_id: str, team_id: str,
                                capability: str, requirement_name: str,
                                must_text: str, decision_card_id: str,
                                scenarios: int) -> dict:
        """spec_delta is the new entry_type for OpenSpec-shaped artifacts."""
        row = {
            "id": f"spec-delta-{run_id[:8]}-{requirement_name[:32]}",
            "entry_type": "spec_delta",
            "team_id": team_id,
            "run_id": run_id,
            "capability": capability,
            "requirement_name": requirement_name,
            "must_text": must_text,
            "decision_card_id": decision_card_id,
            "scenario_count": scenarios,
            "created_at": _now(),
        }
        with self.path.open("a") as fh:
            fh.write(json.dumps(row) + "\n")
        return row


# --- Phase B custom stages ---------------------------------------------------
ARCHITECT_SYSTEM_PROMPT = """\
You are the Architect agent in a governed agentic-SDLC pipeline. The Resolver
gate has produced typed decisions. Your job is to translate those decisions
into a typed OpenSpec change proposal — three artifacts, each in its own
section delimited by markers.

You MUST output EXACTLY THREE SECTIONS in this order, each delimited by the
marker shown. No prose before, between, or after. NO markdown code fences.

=== PROPOSAL ===
# <Change title>

## Why
<2-3 sentences citing the PRD problem this change solves>

## What Changes
- <bullet, one per architectural commitment>
- <bullet>

## Capabilities
### New Capabilities
- `<capability-kebab-name>`: <one-line description>

## Impact
- Affected components: <list>
- Migration: <none/notes>

=== DESIGN ===
# Design

## Context
<3-5 sentences situating this change in the system>

## Goals
- <bullet>
## Non-Goals
- <bullet>

## Decisions
1. <Numbered decision with one-line rationale, citing card_id from the input>
2. ...

## Risks / Trade-offs
- **Risk**: <statement> — **Mitigation**: <statement>

=== SPEC ===
## ADDED Requirements

### Requirement: <Title>
The system MUST <testable invariant on a SINGLE FIRST LINE>. [decision: <card_id>]

#### Scenario: <name>
- **WHEN** <preconditions>
- **THEN** <expected outcome>

#### Scenario: <name>
- **WHEN** <preconditions>
- **THEN** <expected outcome>

### Requirement: <Title>
...

CRITICAL VALIDATOR RULES (your output WILL be validated):
1. Each requirement description MUST contain the word MUST or SHALL on its
   FIRST LINE. NOT "should", NOT "may". MUST or SHALL only, on line 1.
2. Each Requirement MUST have AT LEAST ONE `#### Scenario:` block. Two is
   better.
3. Each Scenario MUST use the literal `**WHEN**` and `**THEN**` bold tags.
4. Each Requirement MUST carry `[decision: <card_id>]` at the end of its
   description, citing the resolver decision card_id that drove it.
5. Capability name MUST be kebab-case and MUST match the
   `### New Capabilities` entry.
6. Output exactly ONE capability spec per change.
7. Output ONLY the three sections delimited by the markers. NO prose
   wrappers, NO commentary, NO ```markdown fences```.

If you can't satisfy a rule, output nothing rather than ill-formed output.
"""


TESTPLAN_SYSTEM_PROMPT = """\
You are the Test Planner. You receive an OpenSpec capability spec containing
ADDED Requirements with WHEN/THEN scenarios. Your job is mechanical
translation: emit ONE pytest function per `#### Scenario:` block, with the
requirement and scenario names preserved in the test name.

OUTPUT FORMAT (a single Python file, no markdown fences, no prose):

```
\"\"\"Generated tests — 1:1 mapping from spec scenarios.

Each test name encodes:
  test_<requirement_slug>__<scenario_slug>

The docstring of each test cites the requirement title and the scenario
description verbatim, so the test → spec link survives refactors.
\"\"\"
import pytest


def test_<req_slug>__<scenario_slug>():
    \"\"\"Requirement: <Requirement Title>
    Scenario: <Scenario name>
    WHEN <verbatim WHEN clause>
    THEN <verbatim THEN clause>
    \"\"\"
    # ARRANGE
    # ACT
    # ASSERT
    pytest.fail(\"not implemented — fill in steps from the scenario\")
```

CRITICAL RULES:
1. EXACTLY one test function per `#### Scenario:` block in the input spec.
2. The test docstring carries the verbatim Requirement title + Scenario
   description so traceability is auditable by grep.
3. Slug = lowercase, words separated by underscores, no special chars.
4. Test names use `__` (double underscore) to separate requirement from
   scenario.
5. No imports beyond `pytest`. No fixtures. The body is `pytest.fail(...)`
   with a hint — the goal is structure, not a working impl.
6. Output ONLY Python code. NO ``` fences, NO prose.
"""


# Markers used by Architect output
_RE_PROPOSAL = re.compile(r"=== PROPOSAL ===\s*\n(.*?)(?==== DESIGN ===)",
                          re.DOTALL)
_RE_DESIGN = re.compile(r"=== DESIGN ===\s*\n(.*?)(?==== SPEC ===)",
                        re.DOTALL)
_RE_SPEC = re.compile(r"=== SPEC ===\s*\n(.*)", re.DOTALL)


async def stage_architect_specshaped(run: RunState, run_dir: Path) -> dict:
    """Replacement Architect: emits proposal + design + spec markdowns."""
    decisions_block = "\n".join(
        f"- card_id={d.card_id[:8]}: [{d.decision_kind}] {d.resolution_text}"
        for d in run.decisions
    )
    res = await _call(
        run=run, stage_key="architect", agent_name="architect",
        system_prompt=ARCHITECT_SYSTEM_PROMPT,
        user_prompt=(
            "Resolved Resolver decisions (use card_id verbatim in [decision: "
            "<card_id>] tags inside the spec):\n\n"
            f"{decisions_block}\n\n"
            "Each decision should drive at least one Requirement. Decisions "
            "of type `swap` carry user-authored wording — preserve it."
        ),
    )
    run.total_tokens += res.prompt_tokens + res.completion_tokens
    run.total_cost_usd += res.usd

    text = res.text
    mp, md, ms = _RE_PROPOSAL.search(text), _RE_DESIGN.search(text), _RE_SPEC.search(text)
    proposal = (mp.group(1).strip() if mp else "")
    design = (md.group(1).strip() if md else "")
    spec = (ms.group(1).strip() if ms else "")

    (run_dir / "openspec_change").mkdir(parents=True, exist_ok=True)
    (run_dir / "openspec_change" / "proposal.md").write_text(proposal or
        "(empty — Architect failed to emit PROPOSAL section)")
    (run_dir / "openspec_change" / "design.md").write_text(design or
        "(empty — Architect failed to emit DESIGN section)")

    # Best-effort capability slug from `### New Capabilities` line
    cap_slug = "patient-vitals"
    cap_m = re.search(r"^- `([a-z0-9-]+)`", proposal, re.MULTILINE)
    if cap_m:
        cap_slug = cap_m.group(1)

    spec_dir = run_dir / "openspec_change" / "specs" / cap_slug
    spec_dir.mkdir(parents=True, exist_ok=True)
    (spec_dir / "spec.md").write_text(spec or "## ADDED Requirements\n\n(empty)\n")

    # Mechanical parse of Requirements + Scenario count
    requirements: list[dict] = []
    if spec:
        # Split on `### Requirement:` headers
        chunks = re.split(r"^### Requirement: ", spec, flags=re.MULTILINE)
        for chunk in chunks[1:]:  # first chunk is the prefix before the first Requirement
            title_line, _, rest = chunk.partition("\n")
            title = title_line.strip()
            # First line of body
            body_lines = [l for l in rest.split("\n") if l.strip()]
            first_line = body_lines[0] if body_lines else ""
            has_must = bool(re.search(r"\b(MUST|SHALL)\b", first_line))
            decision_m = re.search(r"\[decision:\s*([a-z0-9\-]+)\s*\]",
                                   chunk, re.IGNORECASE)
            decision_id = decision_m.group(1) if decision_m else ""
            scenario_count = len(re.findall(r"^####\s*Scenario:", chunk,
                                            re.MULTILINE))
            requirements.append({
                "name": title,
                "first_line": first_line,
                "has_must_or_shall_on_line_1": has_must,
                "decision_card_id": decision_id,
                "scenario_count": scenario_count,
            })

    return {
        "raw_response": text,
        "proposal": proposal,
        "design": design,
        "spec": spec,
        "capability": cap_slug,
        "requirements": requirements,
    }


async def stage_test_plan_specshaped(run: RunState, spec_text: str) -> str:
    """Replacement TestPlan: reads the spec; emits one pytest fn per Scenario."""
    res = await _call(
        run=run, stage_key="test_plan", agent_name="test-planner",
        system_prompt=TESTPLAN_SYSTEM_PROMPT,
        user_prompt="Capability spec to translate:\n\n" + spec_text,
    )
    run.total_tokens += res.prompt_tokens + res.completion_tokens
    run.total_cost_usd += res.usd
    return res.text


# --- main runner -------------------------------------------------------------
async def run_one(run_idx: int, prd_text: str, fixture: dict, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "prd.txt").write_text(prd_text)
    (out_dir / "fixture.yaml").write_text(yaml.safe_dump(fixture, sort_keys=False))

    run = RunState(team_id=f"experiment-phase-b-run-{run_idx}", mode=RunMode.MANUAL)
    ledger = FileLedger(out_dir / "ledger.jsonl")
    t0 = time.time()
    stage_durations: dict[str, float] = {}

    print(f"\n{'=' * 70}\n[B run {run_idx}] starting (run_id={run.run_id[:12]})\n{'=' * 70}")

    # ingest + assessor (unchanged from Phase A)
    s = time.time()
    async for _ in stages.stage_ingest(run, prd_text):
        pass
    stage_durations["ingest"] = time.time() - s

    s = time.time()
    async for _ in stages.stage_assessor(run, prd_text):
        pass
    stage_durations["assessor"] = time.time() - s
    (out_dir / "cards.json").write_text(
        json.dumps([c.model_dump() for c in run.cards], indent=2)
    )
    print(
        f"[B run {run_idx}] assessor done ({stage_durations['assessor']:.1f}s) — "
        f"{len(run.cards)} cards ({sum(c.is_gating for c in run.cards)} gating)"
    )

    # resolver (identical to Phase A)
    gating_cards = [c for c in run.cards if c.is_gating]
    fixture_decisions = fixture.get("decisions", [])
    decisions_applied = []
    for i, card in enumerate(gating_cards):
        if i < len(fixture_decisions):
            entry = fixture_decisions[i]
            kind = entry.get("decision_kind", "accept")
            actor = entry.get("actor", "experiment@local")
            if kind == "accept":
                opt_idx = int(entry.get("option_index", 0))
                if opt_idx >= len(card.options):
                    opt_idx = 0
                resolution = card.options[opt_idx].resolution if card.options else ""
                gd = GateDecision(card_id=card.card_id, decision_kind="accept",
                                  resolution_text=resolution, option_index=opt_idx,
                                  actor=actor)
            elif kind == "swap":
                gd = GateDecision(card_id=card.card_id, decision_kind="swap",
                                  resolution_text=str(entry.get("resolution_text", "")),
                                  actor=actor)
            else:
                gd = GateDecision(card_id=card.card_id, decision_kind="reject",
                                  resolution_text="", actor=actor)
        else:
            resolution = card.options[0].resolution if card.options else ""
            gd = GateDecision(card_id=card.card_id, decision_kind="accept",
                              resolution_text=resolution, option_index=0,
                              actor="experiment@local")
        run.decisions.append(gd)
        decisions_applied.append(gd)
        await ledger.write_decision(LedgerEntry(
            team_id=run.team_id, run_id=run.run_id, card_id=card.card_id,
            ambiguity_class=card.ambiguity_class,
            slot_value_hash=card.slot_value_hash,
            resolution_text=gd.resolution_text,
            decision_kind=gd.decision_kind, created_by=gd.actor,
        ))
    (out_dir / "decisions.json").write_text(
        json.dumps([d.model_dump() for d in decisions_applied], indent=2)
    )

    # *** Phase B Architect: spec-shaped output ***
    s = time.time()
    arch_out = await stage_architect_specshaped(run, out_dir)
    stage_durations["architect"] = time.time() - s
    print(
        f"[B run {run_idx}] architect done ({stage_durations['architect']:.1f}s) — "
        f"{len(arch_out['requirements'])} Requirements, "
        f"capability={arch_out['capability']}"
    )

    # spec_delta ledger entries — one per Requirement
    for req in arch_out["requirements"]:
        await ledger.write_spec_delta(
            run_id=run.run_id, team_id=run.team_id,
            capability=arch_out["capability"],
            requirement_name=req["name"],
            must_text=req["first_line"][:200],
            decision_card_id=req["decision_card_id"],
            scenarios=req["scenario_count"],
        )

    (out_dir / "architecture_raw.md").write_text(arch_out["raw_response"])

    # *** Phase B TestPlan: scenario-driven ***
    s = time.time()
    tests_text = await stage_test_plan_specshaped(run, arch_out["spec"])
    stage_durations["test_plan"] = time.time() - s
    # Strip code fences if the model included them despite instructions
    tests_text = re.sub(r"^```(?:python)?\s*\n", "", tests_text)
    tests_text = re.sub(r"\n```\s*$", "", tests_text)
    (out_dir / "openspec_change" / "specs" / arch_out["capability"]).mkdir(
        parents=True, exist_ok=True
    )
    (out_dir / "openspec_change" / "tasks.md").write_text(
        "## 1. Implementation\n\n" + "\n".join(
            f"- [ ] 1.{i+1} Implement: {req['name']}"
            for i, req in enumerate(arch_out["requirements"])
        ) + "\n\n## 2. Verification\n\n- [ ] 2.1 All generated pytest tests pass\n"
    )
    pr_payload = out_dir / "pr_payload"
    (pr_payload / "tests").mkdir(parents=True, exist_ok=True)
    (pr_payload / "tests" / "test_generated.py").write_text(tests_text)
    print(f"[B run {run_idx}] test_plan done ({stage_durations['test_plan']:.1f}s)")

    # *** Codegen-bridge fix ***
    # The unchanged codegen stage reads `architecture` and `test_plan` strings
    # from `run.events[*].payload`. Phase B's spec-shaped Architect / TestPlan
    # write to disk and to `arch_out`, NOT to events — so without this bridge
    # codegen sees empty input and stubs out (1.4s, "# Empty module").
    #
    # We synthesize two events that carry the same SHAPE codegen expects:
    #   - architecture: the proposal+design+spec rendered as a human-readable
    #     string (the same content Architect produced, just flattened);
    #   - test_plan: the generated pytest module text.
    #
    # This is NOT making the comparison unfair — Phase B's *spec-shaped*
    # artifacts are still what gets delivered + validated. Codegen was held
    # constant by design; the bridge just makes that hold-constant actually
    # hold.
    arch_for_codegen = (
        f"# {arch_out['capability']}\n\n"
        f"## Proposal\n{arch_out['proposal']}\n\n"
        f"## Design\n{arch_out['design']}\n\n"
        f"## Specification\n{arch_out['spec']}"
    )
    from orchestrator.models import StageEvent as _SE
    run.events.append(_SE(
        run_id=run.run_id, stage=Stage.ARCHITECT, status="completed",
        message="(phase-b-bridge) architecture synthesized from spec",
        payload={"architecture": arch_for_codegen[:6000]},
    ))
    run.events.append(_SE(
        run_id=run.run_id, stage=Stage.TEST_PLAN, status="completed",
        message="(phase-b-bridge) test_plan from generated pytest",
        payload={"test_plan": tests_text[:6000]},
    ))

    # Codegen (UNCHANGED — only the spec layer is the variable in this experiment)
    s = time.time()
    async for _ in stages.stage_codegen(run):
        pass
    stage_durations["codegen"] = time.time() - s
    code_text = ""
    for ev in run.events:
        if (ev.payload or {}).get("code"):
            code_text = ev.payload["code"]
    (pr_payload / "src").mkdir(exist_ok=True)
    (pr_payload / "src" / "main.py").write_text(code_text or "# (empty)")
    print(f"[B run {run_idx}] codegen done ({stage_durations['codegen']:.1f}s)")

    # Review/scan stub
    s = time.time()
    async for _ in stages.stage_review_scan(run):
        pass
    stage_durations["review_scan"] = time.time() - s

    # Deliver: copy openspec_change into pr_payload (the customer-facing artifact)
    s = time.time()
    pr_openspec = pr_payload / "openspec" / "changes" / f"add-{arch_out['capability']}"
    pr_openspec.mkdir(parents=True, exist_ok=True)
    src = out_dir / "openspec_change"
    for fn in ("proposal.md", "design.md", "tasks.md"):
        if (src / fn).exists():
            (pr_openspec / fn).write_text((src / fn).read_text())
    spec_src = src / "specs" / arch_out["capability"]
    spec_dst = pr_openspec / "specs" / arch_out["capability"]
    spec_dst.mkdir(parents=True, exist_ok=True)
    if (spec_src / "spec.md").exists():
        (spec_dst / "spec.md").write_text((spec_src / "spec.md").read_text())
    # decisions.md — same shape as Phase A
    (pr_payload / "decisions.md").write_text(stages._decisions_summary(run))
    stage_durations["deliver"] = time.time() - s

    # Validator pass — Phase B's dimension-5 evidence
    validator_status = _run_openspec_validate(pr_openspec)
    (out_dir / "validator_result.json").write_text(json.dumps(validator_status, indent=2))
    print(f"[B run {run_idx}] validator: {validator_status['exit_code']} "
          f"({validator_status['summary']})")

    # Events
    (out_dir / "events.jsonl").write_text(
        "\n".join(ev.model_dump_json() for ev in run.events)
    )

    summary = {
        "phase": "B",
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
        "spec_capability": arch_out["capability"],
        "spec_requirement_count": len(arch_out["requirements"]),
        "spec_scenario_total": sum(r["scenario_count"] for r in arch_out["requirements"]),
        "spec_must_on_line_1_count": sum(
            r["has_must_or_shall_on_line_1"] for r in arch_out["requirements"]
        ),
        "spec_decision_ref_count": sum(
            bool(r["decision_card_id"]) for r in arch_out["requirements"]
        ),
        "validator": validator_status,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    print(
        f"[B run {run_idx}] DONE  total={summary['wall_clock_seconds']:.1f}s  "
        f"tokens={summary['total_tokens']}  ${summary['total_cost_usd']:.4f}  "
        f"reqs={summary['spec_requirement_count']}  "
        f"scenarios={summary['spec_scenario_total']}  "
        f"valid={summary['validator']['exit_code']}"
    )
    return summary


def _run_openspec_validate(change_dir: Path) -> dict:
    """Run `openspec validate <change> --strict` against the emitted change."""
    # openspec needs to be run from a directory that has openspec/ subtree.
    # Build a minimal tmp openspec/ tree pointing at the change dir.
    parent = change_dir.parent  # .../changes/
    if not (parent.parent / "config.yaml").exists():
        # Build a throwaway openspec/ at change_dir.parent.parent
        _bootstrap_openspec_tree(parent.parent)
    change_name = change_dir.name
    try:
        proc = subprocess.run(
            ["openspec", "validate", change_name, "--strict"],
            cwd=parent.parent.parent,  # one level above openspec/
            capture_output=True, text=True, timeout=30,
        )
        return {
            "exit_code": proc.returncode,
            "stdout": proc.stdout[:4000],
            "stderr": proc.stderr[:2000],
            "summary": "PASS" if proc.returncode == 0 else "FAIL",
        }
    except FileNotFoundError:
        return {"exit_code": -1, "stdout": "", "stderr": "openspec CLI not found",
                "summary": "CLI MISSING"}
    except subprocess.TimeoutExpired:
        return {"exit_code": -2, "stdout": "", "stderr": "validator timed out",
                "summary": "TIMEOUT"}


def _bootstrap_openspec_tree(openspec_dir: Path) -> None:
    """Drop a minimal openspec/config.yaml so the validator can find changes."""
    openspec_dir.mkdir(parents=True, exist_ok=True)
    (openspec_dir / "config.yaml").write_text(
        "schema: spec-driven\n"
        "context: |\n"
        "  Phase B experiment validator harness.\n"
    )
    (openspec_dir / "specs").mkdir(exist_ok=True)


async def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--run", action="append", type=int)
    p.add_argument("--out", type=Path,
                   default=REPO_ROOT / "experiments" / "results" / "phase-b")
    args = p.parse_args()
    runs = args.run or [1, 2, 3]

    prd = (REPO_ROOT / "samples" / "prds" / "patient-vitals-streaming.txt").read_text()
    fixture = yaml.safe_load(
        (REPO_ROOT / "experiments" / "fixtures" / "resolver-decisions.yaml").read_text()
    )

    rollups: list[dict] = []
    for r in runs:
        rollups.append(await run_one(r, prd, fixture, args.out / f"run-{r}"))

    phase_summary = {
        "phase": "B",
        "ran_at": _now(),
        "n_runs": len(rollups),
        "total_seconds": round(sum(r["wall_clock_seconds"] for r in rollups), 2),
        "total_tokens": sum(r["total_tokens"] for r in rollups),
        "total_cost_usd": round(sum(r["total_cost_usd"] for r in rollups), 4),
        "validator_pass_count": sum(
            1 for r in rollups if r["validator"]["exit_code"] == 0
        ),
        "runs": rollups,
    }
    (args.out / "phase-summary.json").write_text(json.dumps(phase_summary, indent=2))
    print(
        f"\n=== PHASE B SUMMARY ===\n"
        f"  N={phase_summary['n_runs']}  "
        f"total={phase_summary['total_seconds']:.1f}s  "
        f"tokens={phase_summary['total_tokens']}  "
        f"${phase_summary['total_cost_usd']:.4f}  "
        f"validator_pass={phase_summary['validator_pass_count']}/{phase_summary['n_runs']}"
    )


if __name__ == "__main__":
    asyncio.run(main())
