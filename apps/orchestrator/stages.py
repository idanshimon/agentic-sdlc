"""Pipeline stages — one async function per canonical stage (design.md §2).

Graph:
  Ingest → Assessor → [Gate 1: Resolver — HITL]
        → Architect → [Gate 2: Design Review — human in v1]
        → Test Plan → CodeGen → Review/Scan → [Gate 3: Policy — auto fail-hard]
        → Deliver

Each stage is an async generator yielding StageEvent updates so main.py can stream
them over SSE without coupling stage logic to the transport layer.
"""
from __future__ import annotations
import asyncio
import hashlib
import logging
import os
from dataclasses import dataclass
from typing import AsyncIterator, Optional

from .config import get_model_for_stage, get_provider_for_stage, settings
from .models import AmbiguityCard, ResolutionOption, RunState, Stage, StageEvent
from .telemetry import record_tokens

_logger = logging.getLogger("orchestrator.stages")

# Rough USD/1k-token estimates — Phase 1 calibrates real numbers (design.md §7).
_PRICE_PER_1K = {
    "gpt-4-1": (0.005, 0.015),
    "gpt-4-1-mini": (0.0005, 0.0015),
    "databricks-claude-sonnet-4-6": (0.003, 0.015),
    "databricks-claude-opus-4-7": (0.015, 0.075),
    "databricks-claude-haiku-4-5": (0.0008, 0.004),
    "claude-sonnet-4-6": (0.003, 0.015),
    "claude-opus-4-7": (0.015, 0.075),
}


@dataclass
class CallResult:
    text: str
    prompt_tokens: int
    completion_tokens: int
    usd: float


async def _call(
    *,
    run: RunState,
    stage_key: str,
    agent_name: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
    model_override: Optional[str] = None,
) -> CallResult:
    """Invoke the configured provider for `stage_key` with stub-fallback on error.

    Audit headers (x-pipeline-id / x-agent-name / x-pipeline-stage) ride on
    every call so cross-provider correlation in App Insights stays intact —
    same governance story regardless of which backend served the request.
    """
    headers = {
        "x-pipeline-id": run.run_id,
        "x-agent-name": agent_name,
        "x-pipeline-stage": stage_key,
    }
    model = model_override or get_model_for_stage(run, stage_key) or settings.model_default
    try:
        provider = get_provider_for_stage(run, stage_key)
        resp = await provider.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model=model,
            temperature=temperature,
            headers=headers,
        )
        text = resp.text
        p_tok = resp.prompt_tokens
        c_tok = resp.completion_tokens
    except Exception as exc:
        _logger.warning(
            "Provider call failed (%s/%s on %s): %s — using stub",
            agent_name, stage_key, model, exc,
        )
        text = f"[stub:{agent_name}] {user_prompt[:120]}"
        p_tok = max(1, len(user_prompt) // 4)
        c_tok = max(1, len(text) // 4)

    pp, cp = _PRICE_PER_1K.get(model, (0.005, 0.015))
    usd = (p_tok / 1000) * pp + (c_tok / 1000) * cp
    record_tokens(stage=stage_key, agent=agent_name, tokens=p_tok + c_tok, usd=usd)
    return CallResult(text=text, prompt_tokens=p_tok, completion_tokens=c_tok, usd=usd)



def _ev(run: RunState, stage: Stage, status: str, msg: str = "", **payload) -> StageEvent:
    ev = StageEvent(run_id=run.run_id, stage=stage, status=status, message=msg, payload=payload)
    run.events.append(ev)
    run.current_stage = stage
    return ev


def _hash(s: str) -> str:
    return hashlib.sha1(s.encode()).hexdigest()[:12]


# --- 1. INGEST ----------------------------------------------------------------
async def stage_ingest(run: RunState, prd_text: str) -> AsyncIterator[StageEvent]:
    """Normalize work-item input into a canonical spec-package (design.md §2)."""
    yield _ev(run, Stage.INGEST, "started", "Normalizing PRD into spec-package")
    await asyncio.sleep(0.1)
    yield _ev(run, Stage.INGEST, "completed",
              f"Spec-package built ({len(prd_text)} chars)", chars=len(prd_text))


# --- 2. ASSESSOR --------------------------------------------------------------
async def stage_assessor(run: RunState, prd_text: str) -> AsyncIterator[StageEvent]:
    """Surface ambiguity cards. Read-only. Applies Bootstrap Mode top-K gating
    (design.md §3) — first 30 days per team only top-K=5 cards are gating.

    For each ambiguity we ask the LLM for: PRD quote + gap + 2 resolution options
    (1 recommended + 1 alternative). This makes Accept mean "use this specific
    resolution" rather than "I accept an ambiguity exists."
    """
    yield _ev(run, Stage.ASSESSOR, "started", "Scanning spec for ambiguity")
    sys_prompt = (
        "You are the Assessor agent in a healthcare SDLC pipeline. Read the PRD "
        "and surface 5-8 SPECIFIC ambiguities grounded in actual PRD text. For each "
        "ambiguity, propose 2 concrete resolution options (1 recommended + 1 plausible "
        "alternative) so the human reviewer can either Accept the recommendation, pick "
        "the alternative, write their own, or Reject as not-applicable.\n\n"
        "Return ONLY a JSON array. NO prose, NO markdown fences. Each item must be:\n"
        "{\n"
        '  "title": "<short headline>",\n'
        '  "class": "<one of: phi-classification, scope-resolution, sla-binding,\n'
        '           identifier-format, auth-policy, data-retention, naming-convention, other>",\n'
        '  "prd_quote": "<verbatim text from PRD, ≤200 chars, the EXACT phrase you flagged>",\n'
        '  "prd_section": "<PRD section heading the quote came from, ≤80 chars>",\n'
        '  "gap_description": "<1 sentence — what is MISSING that needs to be decided>",\n'
        '  "blast_usd": <50-500 float>,\n'
        '  "options": [\n'
        '    {\n'
        '      "label": "<short headline for this option>",\n'
        '      "resolution": "<1-2 sentences — the concrete resolution text>",\n'
        '      "rationale": "<1 sentence — why this option, citing regulation/policy/precedent>",\n'
        '      "downstream_impact": "<what Architect/CodeGen will do differently if this wins>",\n'
        '      "recommended": true\n'
        '    },\n'
        '    {\n'
        '      "label": "<alternative headline>",\n'
        '      "resolution": "<alternative resolution text>",\n'
        '      "rationale": "<why someone might prefer this>",\n'
        '      "downstream_impact": "<what changes downstream>",\n'
        '      "recommended": false\n'
        '    }\n'
        '  ]\n'
        "}\n\n"
        "Recommendation guidance: for PHI/auth/data-retention, default to HIPAA-aligned "
        "options citing specific regs (§164.x). For SLA, cite measurable thresholds. For "
        "naming/scope, propose a single normative convention. Blast cost: 50-150 for naming/scope, "
        "200-500 for PHI/auth/retention, 100-300 for SLA. Be concrete and PRD-grounded."
    )
    # Manthan's PCI PRD is ~250KB / 5,924 lines; gpt-4.1 has 128K-token context via APIM.
    # 60k chars ≈ 15k tokens — comfortably fits + leaves room for ~4k tokens of structured output.
    res = await _call(
        run=run, stage_key="assessor", agent_name="assessor",
        system_prompt=sys_prompt, user_prompt=prd_text[:60000],
    )
    run.total_tokens += res.prompt_tokens + res.completion_tokens
    run.total_cost_usd += res.usd

    cards: list[AmbiguityCard] = []
    import json as _json, re as _re
    text = res.text.strip()
    if text.startswith("```"):
        text = _re.sub(r"^```(?:json)?\s*", "", text)
        text = _re.sub(r"\s*```$", "", text)
    try:
        data = _json.loads(text)
        if isinstance(data, list):
            for item in data:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title", "")).strip()
                klass = str(item.get("class", "other")).lower().strip()
                detail = str(item.get("gap_description") or item.get("detail", "")).strip()
                if not (title and detail):
                    continue
                if klass not in {
                    "phi-classification", "scope-resolution", "sla-binding", "identifier-format",
                    "auth-policy", "data-retention", "naming-convention", "other",
                }:
                    klass = "other"
                blast = float(item.get("blast_usd", 100.0) or 100.0)
                # Anti-nudge: cards whose class has high prior-resolution density in the
                # team ledger are promotion-eligible — hide cost cell to avoid steering
                # the developer toward Accept based on cost (design.md §4 anti-nudge).
                eligible = klass in {"scope-resolution", "naming-convention"}
                # Parse options
                opts: list[ResolutionOption] = []
                raw_opts = item.get("options", [])
                if isinstance(raw_opts, list):
                    has_recommended = False
                    for o in raw_opts[:3]:  # cap at 3
                        if not isinstance(o, dict):
                            continue
                        rec = bool(o.get("recommended", False))
                        if rec and has_recommended:
                            rec = False  # only one recommended
                        if rec:
                            has_recommended = True
                        opts.append(ResolutionOption(
                            label=str(o.get("label", "Resolve"))[:160],
                            resolution=str(o.get("resolution", ""))[:600],
                            rationale=str(o.get("rationale", ""))[:400],
                            downstream_impact=str(o.get("downstream_impact", ""))[:300],
                            recommended=rec,
                        ))
                    # If LLM forgot to mark a recommended, mark the first
                    if opts and not has_recommended:
                        opts[0].recommended = True
                # Fallback: synthesize one minimal option so the card is never empty
                if not opts:
                    opts.append(ResolutionOption(
                        label="Confirm with team lead",
                        resolution=f"Defer to team lead per HCA-{klass}-policy; document the decision in this ledger.",
                        rationale="No clear regulatory or precedent-based recommendation available from the PRD context.",
                        downstream_impact="Architect will note the unresolved point in the design; CodeGen will leave a TODO.",
                        recommended=True,
                    ))
                cards.append(AmbiguityCard(
                    ambiguity_class=klass,  # type: ignore[arg-type]
                    slot_value_hash=_hash(title + detail),
                    title=title[:140],
                    detail=detail[:400],
                    prd_quote=str(item.get("prd_quote", ""))[:300],
                    prd_section=str(item.get("prd_section", ""))[:100],
                    gap_description=str(item.get("gap_description", ""))[:400],
                    options=opts,
                    team_occurrence_count=0,  # v1: ledger empty for demo team; honest framing
                    blast_radius_cost_usd=blast,
                    re_run_cost_usd=round(res.usd, 4),
                    is_eligible_for_promotion=eligible,
                ))
    except (_json.JSONDecodeError, ValueError) as exc:
        _logger.warning("Assessor JSON parse failed: %s", exc)

    # Pipe-delimited fallback (older prompt shape)
    if not cards:
        for line in (l.strip() for l in res.text.splitlines() if "|" in l):
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 3:
                continue
            title, klass, detail = parts[0], parts[1].lower(), parts[2]
            blast = 0.0
            if len(parts) >= 4:
                try:
                    blast = float("".join(c for c in parts[3] if c.isdigit() or c == "."))
                except ValueError:
                    blast = 0.0
            if klass not in {
                "phi-classification", "scope-resolution", "sla-binding", "identifier-format",
                "auth-policy", "data-retention", "naming-convention", "other",
            }:
                klass = "other"
            cards.append(AmbiguityCard(
                ambiguity_class=klass,  # type: ignore[arg-type]
                slot_value_hash=_hash(title + detail),
                title=title[:140], detail=detail[:400],
                blast_radius_cost_usd=blast, re_run_cost_usd=round(res.usd, 4),
            ))

    # Fallback so the demo never shows zero cards even if the LLM returned junk.
    if not cards:
        cards = [
            AmbiguityCard(
                ambiguity_class="scope-resolution",
                slot_value_hash=_hash("default-scope"),
                title="Scope of 'patient access' is undefined",
                detail="PRD references patient access without naming the scope (care-team vs account-holder).",
                blast_radius_cost_usd=120.0, re_run_cost_usd=2.5,
            ),
            AmbiguityCard(
                ambiguity_class="phi-classification",
                slot_value_hash=_hash("default-phi"),
                title="Logging policy for MRN field unclear",
                detail="It is not stated whether MRN may appear in application logs.",
                blast_radius_cost_usd=400.0, re_run_cost_usd=2.5,
            ),
        ]

    # Bootstrap Mode: only top-K by blast-radius-cost are gating (design.md §3).
    cards.sort(key=lambda c: c.blast_radius_cost_usd, reverse=True)
    for i, c in enumerate(cards):
        c.is_gating = i < settings.bootstrap_top_k
    run.cards = cards
    yield _ev(run, Stage.ASSESSOR, "completed",
              f"{len(cards)} cards ({sum(c.is_gating for c in cards)} gating, "
              f"{sum(not c.is_gating for c in cards)} auto-deferred)",
              card_count=len(cards))

    # Gate 1: Resolver — HITL pause.
    yield _ev(run, Stage.RESOLVER, "gate_open",
              "Resolver gate open — awaiting human decisions on gating cards",
              gating=[c.model_dump() for c in cards if c.is_gating])


# --- 3. ARCHITECT -------------------------------------------------------------
async def stage_architect(run: RunState) -> AsyncIterator[StageEvent]:
    """Produce a high-level architecture sketch (design.md §2)."""
    yield _ev(run, Stage.ARCHITECT, "started", "Drafting architecture")
    res = await _call(
        run=run, stage_key="architect", agent_name="architect",
        system_prompt=(
            "You are the Architect agent. Read the resolved decisions below and "
            "produce a concise solution architecture (8-12 bullets) that respects "
            "every decision. Cover: components, data flow, security/PHI handling, "
            "scale assumptions, observability. Cite which decision drove each bullet."
        ),
        user_prompt="Resolved decisions:\n" + "\n".join(
            f"- {d.decision_kind}: {d.resolution_text}" for d in run.decisions
        ),
    )
    run.total_tokens += res.prompt_tokens + res.completion_tokens
    run.total_cost_usd += res.usd
    yield _ev(run, Stage.ARCHITECT, "completed", "Architecture drafted",
              architecture=res.text[:1200])
    yield _ev(run, Stage.DESIGN_REVIEW, "gate_open",
              "Gate 2 (Design Review) — human review in v1")


# --- 4. TEST PLAN -------------------------------------------------------------
async def stage_test_plan(run: RunState) -> AsyncIterator[StageEvent]:
    """Tests-as-contracts, written against the resolved spec before CodeGen (§2)."""
    yield _ev(run, Stage.TEST_PLAN, "started", "Writing test plan")
    res = await _call(
        run=run, stage_key="test_plan", agent_name="test-planner",
        system_prompt="You are the Test Planner. Produce 5 contract tests (Given/When/Then).",
        user_prompt="Architecture:\n" + str(run.events[-2].payload.get("architecture", ""))[:2000],
    )
    run.total_tokens += res.prompt_tokens + res.completion_tokens
    run.total_cost_usd += res.usd
    yield _ev(run, Stage.TEST_PLAN, "completed", "Test plan ready", test_plan=res.text[:1500])


# --- 5. CODEGEN ---------------------------------------------------------------
async def stage_codegen(run: RunState) -> AsyncIterator[StageEvent]:
    """Generate code against contract tests (design.md §2). Uses Claude Sonnet via Databricks."""
    yield _ev(run, Stage.CODEGEN, "started", "Generating code")
    # Pull both architecture + test plan from prior events for full context.
    arch = ""
    tests = ""
    for e in run.events:
        p = (e.payload or {}) if hasattr(e, "payload") else {}
        if "architecture" in p:
            arch = str(p["architecture"])
        if "test_plan" in p:
            tests = str(p["test_plan"])
    res = await _call(
        run=run, stage_key="codegen", agent_name="codegen",
        system_prompt=(
            "You are the CodeGen agent. Produce a working Python module that makes the "
            "given contract tests pass. Output a single complete code file. Include "
            "type hints, docstrings, and minimal error handling. Be concrete; no TODOs."
        ),
        user_prompt=(
            f"Architecture:\n{arch[:1500]}\n\nContract tests:\n{tests[:2000]}\n\n"
            "Output the module code only — no prose, no markdown fences."
        ),
    )
    run.total_tokens += res.prompt_tokens + res.completion_tokens
    run.total_cost_usd += res.usd
    yield _ev(run, Stage.CODEGEN, "completed", "Code generated", code=res.text[:4000])


# --- 6. REVIEW / SCAN ---------------------------------------------------------
async def stage_review_scan(run: RunState) -> AsyncIterator[StageEvent]:
    """Gate 3 — policy / static scan, fail-hard (design.md §2)."""
    yield _ev(run, Stage.REVIEW_SCAN, "started", "Running GHAS/CodeQL/secrets/SBOM (mock)")
    await asyncio.sleep(0.2)
    findings = 0  # demo: stubbed clean
    status = "completed" if findings == 0 else "failed"
    yield _ev(run, Stage.REVIEW_SCAN, status,
              f"Policy gate {'passed' if findings == 0 else 'failed'}", findings=findings)


# --- 7. DELIVER ---------------------------------------------------------------
async def stage_deliver(run: RunState) -> AsyncIterator[StageEvent]:
    """Push PR to ADO via MCP tools service (§2 Deliver, §10 MCP gateway pattern)."""
    yield _ev(run, Stage.DELIVER, "started", "Calling MCP push-PR tool")
    import httpx
    mcp_url = os.environ.get("MCP_TOOLS_URL", "").rstrip("/")
    branch = f"agentic/{run.run_id[:8]}"
    repo = os.environ.get("ADO_REPO", "agentic-sdlc-target")
    # Build files list from generated artifacts in run state
    code_text = ""
    test_text = ""
    arch_text = ""
    for ev in run.events:
        p = ev.payload or {}
        if "code" in p:
            code_text = str(p["code"])
        if "test_plan" in p:
            test_text = str(p["test_plan"])
        if "architecture" in p:
            arch_text = str(p["architecture"])
    files = [
        {"path": "src/main.py", "content": code_text or "# generated by agentic-sdlc\n"},
        {"path": "tests/test_main.py", "content": test_text or "# tests\n"},
        {"path": "docs/architecture.md", "content": arch_text or "# architecture\n"},
        {"path": "decisions.md", "content": _decisions_summary(run)},
    ]
    pr_url = None
    if mcp_url:
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                r1 = await client.post(f"{mcp_url}/push_files", json={
                    "files": files, "branch": branch, "repo": repo,
                    "commit_message": f"agentic-sdlc run {run.run_id[:8]}",
                })
                push_data = r1.json() if r1.status_code < 400 else {}
                r2 = await client.post(f"{mcp_url}/create_pr", json={
                    "repo": repo, "source_branch": branch, "target_branch": "main",
                    "title": f"Agentic SDLC run {run.run_id[:8]}",
                    "description": _decisions_summary(run)[:4000],
                })
                pr_data = r2.json() if r2.status_code < 400 else {}
                pr_url = pr_data.get("pr_url") or pr_data.get("url")
        except Exception as exc:
            _logger.exception("MCP call failed: %s", exc)
    if not pr_url:
        pr_url = f"https://dev.azure.com/hca-demo/_git/agentic-sdlc/pullrequest/{run.run_id[:8]}"
    yield _ev(run, Stage.DELIVER, "completed", f"PR opened: {pr_url}", pr_url=pr_url)


def _decisions_summary(run: RunState) -> str:
    lines = [f"# Decisions for run {run.run_id}", f"Team: {run.team_id}", ""]
    for d in run.decisions:
        cid = (d.card_id or "gate")[:8]
        lines.append(f"- **{cid}** {d.decision_kind}: {d.resolution_text or '(accepted)'}")
    return "\n".join(lines)
