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
from pathlib import Path
from typing import AsyncIterator, Optional

from .config import get_model_for_stage, get_provider_for_stage, settings
from .models import AmbiguityCard, ResolutionOption, RunState, Stage, StageEvent
from .prompt_library_v2 import (
    PromptCatalog,
    PromptValidationError,
    ResolveResult,
    load_prompts,
)
from .telemetry import record_tokens

_logger = logging.getLogger("orchestrator.stages")

# ---------------------------------------------------------------------------
# Prompt catalog singleton — loaded at first use.
#
# Loaded lazily so that test fixtures that monkey-patch prompts/ get
# their own view (the catalog is a property, not a module-level constant).
# Production runs read once from /app/prompts/ inside the container image.
# ---------------------------------------------------------------------------
_catalog: PromptCatalog | None = None

def _prompts_root() -> Path:
    """Where to look for prompts/. Order:
      1. PROMPTS_ROOT env var (test fixtures / hot-reload future work)
      2. /app/prompts (production container layout from Dockerfile.repo-root)
      3. <repo_root>/prompts (developer-laptop layout)
    """
    env = os.environ.get("PROMPTS_ROOT")
    if env:
        return Path(env)
    container = Path("/app/prompts")
    if container.is_dir():
        return container
    # Walk up from this file to find the monorepo root
    here = Path(__file__).resolve()
    for parent in [here.parent.parent.parent, here.parent.parent]:
        candidate = parent / "prompts"
        if candidate.is_dir():
            return candidate
    return Path("prompts")  # last resort; loader will raise if missing

def get_prompt_catalog() -> PromptCatalog:
    """Lazy-load the catalog. Raises PromptValidationError if any
    prompt file is malformed — orchestrator startup will fail-fast
    rather than silently fall back to hardcoded defaults."""
    global _catalog
    if _catalog is None:
        root = _prompts_root()
        _logger.info("Loading prompt catalog from %s", root)
        _catalog = load_prompts(root)
    return _catalog

def reset_prompt_catalog() -> None:
    """For tests + hot-reload: force the next get_prompt_catalog() call
    to reload from disk."""
    global _catalog
    _catalog = None


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
    # 2026-06-16: per Phase 2 wiring, every _call that resolved its prompt
    # through the catalog records the chain here. Stages then propagate it
    # to events / ledger so the audit trail pins (prompt_id, version, git_sha,
    # owner_persona) on every decision. None when the stage didn't use the
    # catalog (legacy inline-prompt path still works).
    prompt_resolution: Optional[ResolveResult] = None


class ModelPolicyRefusal(Exception):
    """Raised at stage dispatch when config/models.yaml forbids the resolved
    model for this stage (Phase 4, add-configuration-plane). Carries the
    structured `rule_ref` the orchestrator stamps onto the refusal ledger entry
    (autonomy_ref-style) so the compliance query can cite WHY the stage failed.
    """

    def __init__(self, stage: str, model: str, reason: str, rule_ref: str) -> None:
        self.stage = stage
        self.model = model
        self.reason = reason
        self.rule_ref = rule_ref
        super().__init__(
            f"model policy refused {model!r} for stage {stage!r}: {reason} "
            f"[{rule_ref}]"
        )


def enforce_model_policy(
    stage_key: str,
    model: str,
    *,
    phi: bool,
    policy=None,
) -> None:
    """Refuse a forbidden model at stage dispatch. No-op when the policy is
    unloaded (bootstrap/permissive) or the model is allowed. Raises
    ModelPolicyRefusal otherwise. Pure w.r.t. the injected `policy` so it's
    unit-testable without touching the module singleton."""
    from .model_policy import MODEL_POLICY

    pol = policy if policy is not None else MODEL_POLICY
    verdict = pol.check_model(stage_key, model, phi=phi)
    if not verdict.allowed:
        raise ModelPolicyRefusal(stage_key, model, verdict.reason, verdict.rule_ref)


def _run_handles_phi(run: RunState) -> bool:
    """Does this run touch PHI-classified content? True when any surfaced card
    is a phi-classification ambiguity, or the run carries an explicit truthy
    `phi_class` (harness/seed can set it via RunState extra='allow'). Drives the
    phi_eligible model check — conservative: unknown ⇒ False (permissive), the
    phi_stages default still guards architect/codegen/review_scan structurally.
    """
    pc = getattr(run, "phi_class", None)
    if isinstance(pc, str) and pc.lower() in ("low", "high"):
        return True
    for card in getattr(run, "cards", None) or []:
        if getattr(card, "ambiguity_class", None) == "phi-classification":
            return True
    return False


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
    # Phase 4 (add-configuration-plane): enforce model policy at the single
    # stage-dispatch chokepoint. A denied / non-allowlisted model, or a non-
    # phi_eligible model on a PHI-adjacent stage, raises ModelPolicyRefusal —
    # the caller (stage driver) turns that into a failed run with a ledger entry
    # citing rule_ref. No-op when models.yaml isn't activated (permissive).
    # `phi` is true when this run handles PHI-classified content (any card is a
    # phi-classification ambiguity, or the run carries an explicit phi flag).
    _phi = _run_handles_phi(run)
    enforce_model_policy(stage_key, model, phi=_phi)
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


def _slot_key(ambiguity_class: str, prd_section: str = "") -> str:
    """Stable precedent key for findPrecedent matching.

    THE TEACHING-LOOP FIX (2026-06-20): slot_value_hash was previously
    _hash(title + detail), but title/detail come from the LLM assessor's prose
    output, which varies run-to-run even for the SAME PRD. That made the
    precedent key unstable, so an operator's swap on run A never matched the
    same ambiguity on run B — findPrecedent (exact match on team + class +
    slot_value_hash) could never fire. Verified empirically: the same PRD
    produced a different slot hash for every class across two runs.

    The fix: key on the STABLE semantic identity of the ambiguity — its class
    plus the PRD section it came from (normalized) — NOT the LLM's wording.
    The PRD section is a stable anchor (same PRD → same sections); the class is
    the assessor's stable taxonomy field. When no section is available we fall
    back to class-only, which is how the hardcoded demo cards already key
    (e.g. _hash("default-scope")). This makes an operator's teaching signal on
    one run match the same ambiguity bucket on the next run, for the same team.
    """
    norm_section = " ".join(prd_section.lower().split()) if prd_section else ""
    return _hash(f"{ambiguity_class}|{norm_section}")


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

    # Phase 2 wiring (2026-06-16): resolve the assessor system prompt through
    # the per-team / per-persona / global inheritance catalog instead of
    # hardcoding it inline. The resolved chain is captured into the event
    # payload + ledger so every ambiguity card the assessor surfaces is
    # auditable to a specific prompt_id/version/git_sha.
    #
    # Falls back to a clear PromptValidationError if the catalog is misconfigured
    # (e.g. global YAML missing) — fail-loud over silent inline default.
    catalog = get_prompt_catalog()
    resolved = catalog.resolve(
        stage="assessor",
        model=get_model_for_stage(run, "assessor"),
        team=run.team_id,
    )
    sys_prompt = resolved.template
    res = await _call(
        run=run, stage_key="assessor", agent_name="assessor",
        system_prompt=sys_prompt, user_prompt=prd_text[:60000],
    )
    res.prompt_resolution = resolved   # carry chain to caller for ledger pinning
    # Phase 2.6: stash chain on RunState so the ledger writers (autopilot
    # in main.py::_drive and per-card /approve in main.py::approve) can
    # pin it on every LedgerEntry that derives from this assessor pass.
    run.prompt_chain_by_stage["assessor"] = resolved.chain_as_list()
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
                    slot_value_hash=_slot_key(klass, str(item.get("prd_section", ""))),
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
                slot_value_hash=_slot_key(klass),
                title=title[:140], detail=detail[:400],
                blast_radius_cost_usd=blast, re_run_cost_usd=round(res.usd, 4),
            ))

    # Fallback so the demo never shows zero cards even if the LLM returned junk.
    if not cards:
        cards = [
            AmbiguityCard(
                ambiguity_class="scope-resolution",
                slot_value_hash=_slot_key("scope-resolution"),
                title="Scope of 'patient access' is undefined",
                detail="PRD references patient access without naming the scope (care-team vs account-holder).",
                blast_radius_cost_usd=120.0, re_run_cost_usd=2.5,
            ),
            AmbiguityCard(
                ambiguity_class="phi-classification",
                slot_value_hash=_slot_key("phi-classification"),
                title="Logging policy for MRN field unclear",
                detail="It is not stated whether MRN may appear in application logs.",
                blast_radius_cost_usd=400.0, re_run_cost_usd=2.5,
            ),
        ]

    # Bootstrap Mode: only top-K by blast-radius-cost are gating (design.md §3).
    cards.sort(key=lambda c: c.blast_radius_cost_usd, reverse=True)
    from .config import HARD_GATE_CLASSES
    for i, c in enumerate(cards):
        c.is_gating = i < settings.bootstrap_top_k
        # Tier-2 governance: stamp hard-gate status so the UI can lock these
        # out of bulk-approve. The server still enforces independently.
        c.is_hard_gated = c.ambiguity_class in HARD_GATE_CLASSES
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

    # Phase 2.3 wiring (2026-06-16): architect prompt now flows through the
    # YAML resolver. owner_persona for architect-global is `architect`, so
    # the Architect persona team owns this prompt in CODEOWNERS — PM cannot
    # change it without their review, and vice versa.
    catalog = get_prompt_catalog()
    resolved = catalog.resolve(
        stage="architect",
        model=get_model_for_stage(run, "architect"),
        team=run.team_id,
    )
    res = await _call(
        run=run, stage_key="architect", agent_name="architect",
        system_prompt=resolved.template,
        user_prompt="Resolved decisions:\n" + "\n".join(
            f"- {d.decision_kind}: {d.resolution_text}" for d in run.decisions
        ),
    )
    res.prompt_resolution = resolved
    run.prompt_chain_by_stage["architect"] = resolved.chain_as_list()
    run.total_tokens += res.prompt_tokens + res.completion_tokens
    run.total_cost_usd += res.usd
    # NOTE: previously truncated to 1200 chars, which silently dropped
    # observability / scale / security / Tier 2+3 sections of any non-trivial
    # architecture (caught on the SBM cardiology PRD — Tier 2 cohort dashboard
    # got chopped mid-sentence, leaving TestPlan and CodeGen ungrounded on
    # critical decisions). The 8K max_tokens cap on the upstream call already
    # bounds the size; further truncation here was a footgun.
    yield _ev(run, Stage.ARCHITECT, "completed", "Architecture drafted",
              architecture=res.text)
    yield _ev(run, Stage.DESIGN_REVIEW, "gate_open",
              "Gate 2 (Design Review) — human review in v1")


# --- 4. TEST PLAN -------------------------------------------------------------
async def stage_test_plan(
    run: RunState,
    prd_text: str | None = None,
) -> AsyncIterator[StageEvent]:
    """Tests-as-contracts, written against the resolved spec before CodeGen (§2).

    Consumes three context sources to keep tests grounded in real
    architectural assertions rather than pattern-matching to generic
    REST-CRUD scaffolding:

      1. The most recent ``architecture`` payload from prior stage events.
      2. The Resolver-resolved decisions (each one is a contract the tests
         MUST verify).
      3. The PRD text (transport, scope, SLA, compliance language).

    Without any of these the stage previously emitted generics — see
    `experiments/COMPARISON.md` for the empirical write-up.
    """
    yield _ev(run, Stage.TEST_PLAN, "started", "Writing test plan")

    arch_text = ""
    for ev in run.events:
        p = ev.payload or {}
        if "architecture" in p:
            arch_text = str(p["architecture"])

    decisions_block = "\n".join(
        f"- [{d.decision_kind}] {d.resolution_text}" for d in run.decisions
    ) or "(no decisions resolved — Resolver gate skipped)"

    prd_excerpt = (prd_text or "")[:3000]

    # Phase 2.4 wiring (2026-06-16): test_plan prompt now flows through the
    # YAML resolver. owner_persona is `qa` — QA team CODEOWNS the test_plan
    # prompt, so changes require their review even if the change is filed
    # by SRE or platform-team.
    catalog = get_prompt_catalog()
    resolved = catalog.resolve(
        stage="test_plan",
        model=get_model_for_stage(run, "test_plan"),
        team=run.team_id,
    )
    sys_prompt = resolved.template

    user_prompt = (
        f"PRD excerpt:\n{prd_excerpt}\n\n"
        f"Resolved decisions:\n{decisions_block}\n\n"
        f"Architecture:\n{arch_text}\n\n"
        "Produce the test plan now. Markdown only."
    )

    res = await _call(
        run=run, stage_key="test_plan", agent_name="test-planner",
        system_prompt=sys_prompt, user_prompt=user_prompt,
    )
    res.prompt_resolution = resolved
    run.prompt_chain_by_stage["test_plan"] = resolved.chain_as_list()
    run.total_tokens += res.prompt_tokens + res.completion_tokens
    run.total_cost_usd += res.usd
    yield _ev(run, Stage.TEST_PLAN, "completed", "Test plan ready",
              test_plan=res.text)


# --- 5. CODEGEN ---------------------------------------------------------------
async def stage_codegen(run: RunState) -> AsyncIterator[StageEvent]:
    """Generate deployable code from architecture + test plan (design.md §2).

    Splits codegen into TWO calls:
      1. app.py   — the FastAPI service implementation
      2. tests.py — pytest contract tests against app.py

    Why split: a single combined call regularly exceeds the provider's
    max_tokens cap on non-trivial healthcare services (caught on the SBM
    cardiology PRD — sonnet-4-6 + haiku-4-5 both truncated at ~8K tokens
    mid-string-literal, producing an unparseable Python file).

    Splitting also lets each call run with a tighter contract:
    impl knows it's producing a single FastAPI module; tests know they're
    pytest cases that exercise the impl. Earlier single-shot prompt produced
    a hybrid file with classes + fixtures + tests stuffed together,
    forcing the deliver stage to dump it into src/main.py while tests/
    got the markdown test plan.
    """
    yield _ev(run, Stage.CODEGEN, "started", "Generating code")
    # Pull both architecture + test plan from prior events for full context.
    arch = ""
    tests_md = ""
    for e in run.events:
        p = (e.payload or {}) if hasattr(e, "payload") else {}
        if "architecture" in p:
            arch = str(p["architecture"])
        if "test_plan" in p:
            tests_md = str(p["test_plan"])

    # Phase 2.4 wiring (2026-06-16): both codegen calls now flow through
    # the YAML resolver. Each call gets its own prompt_id resolved:
    #   - "codegen"        owner: sre  (impl prompt)
    #   - "codegen-tests"  owner: sre  (tests prompt)
    # Both owned by SRE — these prompts encode operability constraints
    # (stub fallbacks, no-PHI rule, no-markdown-fences) that SRE has to
    # uphold in incident review.
    catalog = get_prompt_catalog()
    impl_resolved = catalog.resolve(
        stage="codegen",
        model=get_model_for_stage(run, "codegen"),
        team=run.team_id,
    )
    tests_resolved = catalog.resolve(
        stage="codegen-tests",
        model=get_model_for_stage(run, "codegen"),
        team=run.team_id,
    )

    # Call 1: implementation
    impl_res = await _call(
        run=run, stage_key="codegen", agent_name="codegen-impl",
        system_prompt=impl_resolved.template,
        user_prompt=(
            f"Architecture:\n{arch}\n\n"
            f"Contract tests (markdown spec to satisfy):\n{tests_md}\n\n"
            "Output the FastAPI module code only — no prose, no markdown fences. "
            "Start with imports and end with the uvicorn block."
        ),
    )
    impl_res.prompt_resolution = impl_resolved
    run.prompt_chain_by_stage["codegen"] = impl_resolved.chain_as_list()
    run.total_tokens += impl_res.prompt_tokens + impl_res.completion_tokens
    run.total_cost_usd += impl_res.usd

    # Call 2: pytest tests against the impl
    test_res = await _call(
        run=run, stage_key="codegen", agent_name="codegen-tests",
        system_prompt=tests_resolved.template,
        user_prompt=(
            f"Implementation (app.py):\n{impl_res.text}\n\n"
            f"Test plan (markdown spec):\n{tests_md}\n\n"
            "Output the pytest module code only — no prose, no markdown fences."
        ),
    )
    test_res.prompt_resolution = tests_resolved
    run.prompt_chain_by_stage["codegen-tests"] = tests_resolved.chain_as_list()
    run.total_tokens += test_res.prompt_tokens + test_res.completion_tokens
    run.total_cost_usd += test_res.usd

    # Emit both as separate payload keys so the deliver stage can route them
    # to the right files. Keep the legacy `code` key for backwards compat
    # with anything reading the old single-output shape.
    yield _ev(run, Stage.CODEGEN, "completed",
              f"Code generated: app={len(impl_res.text)} chars, "
              f"tests={len(test_res.text)} chars",
              code=impl_res.text,
              app_code=impl_res.text,
              test_code=test_res.text)


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
    """Open a REAL GitHub PR with the run's generated artifacts (§2 Deliver).

    No fakes: opens a real PR via the GitHub Git Data API when delivery is
    configured (DELIVER_TARGET_REPO + GH_TOKEN), or emits an honest
    "not configured / failed" event with pr_url=None. Never fabricates a URL.
    The optional MCP push path is still honoured first when MCP_TOOLS_URL is set.
    """
    from .deliver_pr import open_delivery_pr

    yield _ev(run, Stage.DELIVER, "started", "Preparing delivery PR")
    branch = f"agentic/{run.run_id[:8]}"
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

    # 1. Optional MCP push path (when an MCP tools service is wired).
    mcp_url = os.environ.get("MCP_TOOLS_URL", "").rstrip("/")
    if mcp_url:
        import httpx
        repo = os.environ.get("ADO_REPO", "agentic-sdlc-target")
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                await client.post(f"{mcp_url}/push_files", json={
                    "files": files, "branch": branch, "repo": repo,
                    "commit_message": f"agentic-sdlc run {run.run_id[:8]}",
                })
                r2 = await client.post(f"{mcp_url}/create_pr", json={
                    "repo": repo, "source_branch": branch, "target_branch": "main",
                    "title": f"Agentic SDLC run {run.run_id[:8]}",
                    "description": _decisions_summary(run)[:4000],
                })
                pr_data = r2.json() if r2.status_code < 400 else {}
                pr_url = pr_data.get("pr_url") or pr_data.get("url")
        except Exception as exc:
            _logger.exception("MCP delivery call failed: %s", exc)

    # 2. Real GitHub PR via the Git Data API (the production path).
    if not pr_url:
        result = await open_delivery_pr(
            run_id=run.run_id,
            team_id=run.team_id,
            files=files,
            title=f"Agentic SDLC run {run.run_id[:8]} — {run.team_id}",
            body=_decisions_summary(run)[:60000],
        )
        if result.ok and result.pr_url:
            pr_url = result.pr_url
        else:
            # Honest failure — NO fabricated URL. Surface why so the operator
            # knows whether it's a config gap or a real error.
            yield _ev(
                run, Stage.DELIVER, "completed",
                f"Artifacts ready — PR not opened: {result.reason}",
                pr_url=None,
                delivery_status="not_delivered",
                delivery_reason=result.reason,
                artifact_files=result.files,
            )
            return

    yield _ev(run, Stage.DELIVER, "completed", f"PR opened: {pr_url}",
              pr_url=pr_url, delivery_status="delivered")


def _decisions_summary(run: RunState) -> str:
    lines = [f"# Decisions for run {run.run_id}", f"Team: {run.team_id}", ""]
    for d in run.decisions:
        cid = (d.card_id or "gate")[:8]
        lines.append(f"- **{cid}** {d.decision_kind}: {d.resolution_text or '(accepted)'}")
    return "\n".join(lines)
