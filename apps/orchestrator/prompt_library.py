"""Prompt Library catalog — per-stage prompt variants keyed by (stage, model).

This module surfaces, as a first-class control-plane primitive, the system
prompts that drive each pipeline stage. It is the registry HCA's Apigee custom
scripts already implement informally; we promote it to a real catalog so the
orchestrator (and ultimately APIM circuit-breaker failover logic) can look up
the prompt variant compatible with whichever model is actually serving the
call right now.

Workshop framing (Kapil's Phase 1 ask, 2026-05-27):
    "A prompt library where I can sync up the gateway to basically say:
     if I get this [429], looking at the prompt library reference, it's
     going to go pick up: this is the prompt I want to use for system."

When the circuit breaker fails over (e.g. Gemini → GPT-4.1, or
Databricks-Claude → Foundry-Claude), the orchestrator calls
`get_prompt(stage, model)` to resolve the prompt variant whose
`model_compat_notes` are appropriate for the substitute model. Today every
stage/model pair returns `v1` — the public contract is the lookup shape;
adding genuine per-model variants is a Phase 1.5 change that does not require
re-plumbing this registry.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Canonical stage prompts — single source of truth, re-exported by stages.py.
# Keep these strings free of per-call interpolation: anything stage-specific
# (the PRD text, prior architecture, etc.) is the *user* prompt, not the
# *system* prompt — and only system prompts live in this catalog.
# ---------------------------------------------------------------------------

INGEST_PROMPT = (
    "You are the Ingest agent. Normalize the work-item input into a canonical "
    "spec-package: extract the goal, in-scope/out-of-scope, primary actors, "
    "and any explicit SLAs. Output JSON only — no prose, no markdown fences."
)

ASSESSOR_PROMPT = (
    "You are the Assessor agent in a healthcare SDLC pipeline. Read the PRD "
    "and surface 5-8 SPECIFIC ambiguities grounded in actual PRD text. For each "
    "ambiguity, propose 2 concrete resolution options (1 recommended + 1 plausible "
    "alternative) so the human reviewer can either Accept the recommendation, pick "
    "the alternative, write their own, or Reject as not-applicable.\n\n"
    "Return ONLY a JSON array. NO prose, NO markdown fences. Each item must "
    "include title, class, prd_quote, prd_section, gap_description, blast_usd, "
    "and a 2-element options array (label, resolution, rationale, "
    "downstream_impact, recommended).\n\n"
    "Recommendation guidance: for PHI/auth/data-retention, default to HIPAA-aligned "
    "options citing specific regs (§164.x). For SLA, cite measurable thresholds. For "
    "naming/scope, propose a single normative convention."
)

ARCHITECT_PROMPT = (
    "You are the Architect agent. Read the resolved decisions below and "
    "produce a concise solution architecture (8-12 bullets) that respects "
    "every decision. Cover: components, data flow, security/PHI handling, "
    "scale assumptions, observability. Cite which decision drove each bullet."
)

TEST_PLAN_PROMPT = (
    "You are the Test Planner. Produce 5 contract tests (Given/When/Then)."
)

CODEGEN_PROMPT = (
    "You are the CodeGen agent. Produce a working Python module that makes the "
    "given contract tests pass. Output a single complete code file. Include "
    "type hints, docstrings, and minimal error handling. Be concrete; no TODOs."
)

REVIEW_SCAN_PROMPT = (
    "You are the Review/Scan agent. Run policy + static analysis over the "
    "generated code and emit a JSON report: findings[], severity, rule_id, "
    "file, line, recommendation. Fail-hard on HIGH severity."
)


# ---------------------------------------------------------------------------
# Registry: PROMPT_CATALOG[stage][model] -> PromptVariant
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PromptVariant:
    template: str
    version: str
    model_compat_notes: str


# Compat-note shorthands — kept terse because they ride in API responses.
_GPT_NOTES = "OpenAI chat shape; JSON-mode safe; 128K ctx via APIM."
_CLAUDE_NOTES = (
    "Anthropic messages shape; prefers explicit 'no markdown fences' "
    "instruction; 200K ctx."
)
_CLAUDE_DBX_NOTES = (
    "Claude via Databricks Foundation Model API; same prompt shape as native "
    "Anthropic; carries x-databricks-use-coding-agent-mode header."
)
_GEMINI_NOTES = (
    "Google Gemini; tolerates OpenAI-shaped messages via APIM passthrough; "
    "tends to add markdown fences — emphasise 'NO markdown fences' literal."
)


def _stage(prompt: str) -> dict[str, PromptVariant]:
    """Build the per-model variant dict for a stage.

    Today every model maps to the same v1 template. The shape is what matters:
    when Phase 1.5 ships genuine per-model rewrites (e.g. Gemini variant with
    a stronger anti-fence guard, GPT variant using response_format=json),
    they slot in here without an API change.
    """
    return {
        "gpt-4-1": PromptVariant(prompt, "v1", _GPT_NOTES),
        "gpt-4-1-mini": PromptVariant(prompt, "v1", _GPT_NOTES),
        "claude-sonnet-4-6": PromptVariant(prompt, "v1", _CLAUDE_NOTES),
        "claude-opus-4-7": PromptVariant(prompt, "v1", _CLAUDE_NOTES),
        "databricks-claude-sonnet-4-6": PromptVariant(
            prompt, "v1", _CLAUDE_DBX_NOTES,
        ),
        "databricks-claude-opus-4-7": PromptVariant(
            prompt, "v1", _CLAUDE_DBX_NOTES,
        ),
        "gemini-2-5-pro": PromptVariant(prompt, "v1", _GEMINI_NOTES),
    }


PROMPT_CATALOG: dict[str, dict[str, PromptVariant]] = {
    "ingest": _stage(INGEST_PROMPT),
    "assessor": _stage(ASSESSOR_PROMPT),
    "architect": _stage(ARCHITECT_PROMPT),
    "test_plan": _stage(TEST_PLAN_PROMPT),
    "codegen": _stage(CODEGEN_PROMPT),
    "review_scan": _stage(REVIEW_SCAN_PROMPT),
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class UnknownStageError(KeyError):
    """Raised when get_prompt is called for a stage not in the catalog."""


def list_stages() -> list[str]:
    return list(PROMPT_CATALOG.keys())


def get_prompt(stage: str, model: str | None = None) -> dict[str, Any]:
    """Look up the prompt variant for (stage, model).

    Args:
        stage: canonical stage key (see list_stages()).
        model: model identifier as used in `STAGE_PROVIDERS[stage]["model"]`.
            When `None` or unknown, falls back to the first registered variant
            so the pipeline never wedges on an unrecognised model — the
            audit log captures the fallback so a Phase 1.5 variant can be
            added before production rollout.

    Returns:
        dict with keys: stage, model, template, version, model_compat_notes,
        fallback (bool — True iff the requested model was not found).
    """
    stage_key = stage.lower()
    variants = PROMPT_CATALOG.get(stage_key)
    if variants is None:
        raise UnknownStageError(stage)
    fallback = False
    if model is None or model not in variants:
        # Stable, deterministic fallback: first variant by registration order.
        model_key = next(iter(variants))
        fallback = model is not None and model != model_key
    else:
        model_key = model
    v = variants[model_key]
    return {
        "stage": stage_key,
        "model": model_key,
        "template": v.template,
        "version": v.version,
        "model_compat_notes": v.model_compat_notes,
        "fallback": fallback,
    }


def build_catalog_view(preview_chars: int = 200) -> dict[str, Any]:
    """Return the catalog shaped for the /api/prompt-library response.

    Shape:
        {
          stages: [
            {
              stage_name: "architect",
              providers: [
                { provider: "openai", model: "gpt-4-1",
                  prompt_version: "v1",
                  template_preview: "...",
                  model_compat_notes: "..." },
                ...
              ]
            },
            ...
          ]
        }

    `provider` is inferred from the model id prefix — this mirrors what the
    APIM Policy Decision Point sees when it routes a call, so an operator
    reading this page sees the same grouping the gateway uses.
    """
    stages_out: list[dict[str, Any]] = []
    for stage_name, variants in PROMPT_CATALOG.items():
        providers: list[dict[str, Any]] = []
        for model_id, variant in variants.items():
            providers.append({
                "provider": _infer_provider(model_id),
                "model": model_id,
                "prompt_version": variant.version,
                "template_preview": variant.template[:preview_chars],
                "model_compat_notes": variant.model_compat_notes,
            })
        stages_out.append({
            "stage_name": stage_name,
            "providers": providers,
        })
    return {"stages": stages_out}


def _infer_provider(model_id: str) -> str:
    m = model_id.lower()
    if m.startswith("databricks-"):
        return "databricks"
    if m.startswith("gpt-"):
        return "openai-apim"
    if m.startswith("claude-"):
        return "anthropic"
    if m.startswith("gemini-"):
        return "google"
    return "unknown"
