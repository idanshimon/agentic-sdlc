"""Config — env vars set by Container App. See design.md §1 (two-plane: governance config
is injected, never hardcoded so we can swap execution-plane impls without recompiling).

Multi-provider routing (Phase 1):
  Per-stage provider mapping lives in STAGE_PROVIDERS. Precedence:
      python defaults  <  ./config.yaml or /app/config.yaml  <  env vars
                                                              <  per-run override on RunState

  Env vars accepted (one per stage):
      STAGE_INGEST_PROVIDER, STAGE_INGEST_MODEL, STAGE_INGEST_VIA_APIM
      STAGE_ASSESSOR_PROVIDER, ...
      STAGE_ARCHITECT_PROVIDER, ...
      STAGE_TEST_PLAN_PROVIDER, ...
      STAGE_CODEGEN_PROVIDER, ...
      STAGE_REVIEW_SCAN_PROVIDER, ...

  YAML override file shape:
      stage_providers:
        architect:
          provider: foundry-anthropic
          model: claude-sonnet-4-6
          via_apim: false
"""
from __future__ import annotations
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

_logger = logging.getLogger("orchestrator.config")

STAGE_NAMES = ("ingest", "assessor", "architect", "test_plan", "codegen", "review_scan")


@dataclass(frozen=True)
class Settings:
    # APIM gateway in front of every model call (design.md §1 Governance Plane PDP).
    apim_base_url: str = os.getenv(
        "APIM_BASE_URL", "https://apim-agentic-ab9963.azure-api.net/openai/v1"
    )
    apim_subscription_key: str = os.getenv("APIM_SUBSCRIPTION_KEY", "")
    # Foundry / AOAI deployments fronted by APIM.
    model_default: str = os.getenv("MODEL_DEFAULT", "gpt-4-1")
    model_fast: str = os.getenv("MODEL_FAST", "gpt-4-1-mini")
    # Cosmos — typed Decision Ledger (design.md §4) + run state.
    cosmos_endpoint: str = os.getenv(
        "COSMOS_ENDPOINT", "https://cosmos-agentic-ab9963.documents.azure.com:443/"
    )
    cosmos_db: str = os.getenv("COSMOS_DB", "agentic-sdlc")
    cosmos_ledger_container: str = os.getenv("COSMOS_LEDGER_CONTAINER", "decision-ledger")
    cosmos_runs_container: str = os.getenv("COSMOS_RUNS_CONTAINER", "pipeline-runs")
    # Blob — immutable per-run decisions.md (design.md §7 storage decoupling).
    storage_account_url: str = os.getenv(
        "STORAGE_ACCOUNT_URL", "https://stagenticab9963.blob.core.windows.net"
    )
    storage_decisions_container: str = os.getenv("STORAGE_DECISIONS_CONTAINER", "decisions")
    storage_artifacts_container: str = os.getenv("STORAGE_ARTIFACTS_CONTAINER", "artifacts")
    # App Insights (design.md §7 cost telemetry).
    appi_conn: str = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "")
    # Bootstrap Mode (design.md §3): top-K=5 gating for first 30 days per team.
    bootstrap_top_k: int = int(os.getenv("BOOTSTRAP_TOP_K", "5"))
    bootstrap_days: int = int(os.getenv("BOOTSTRAP_DAYS", "30"))
    # Identity for signing decisions.md entries.
    signer_identity: str = os.getenv("SIGNER_IDENTITY", "orchestrator@apim-agentic-ab9963")


settings = Settings()


# --- Stage provider routing --------------------------------------------------
# Python defaults — matches the demo deployment today (May 2026): AOAI for
# ingest/assessor/test_plan/review_scan; Databricks-Anthropic for architect/codegen.
_STAGE_PROVIDERS_DEFAULTS: dict[str, dict[str, Any]] = {
    "ingest": {"provider": "aoai", "model": settings.model_fast, "via_apim": True},
    "assessor": {"provider": "aoai", "model": settings.model_default, "via_apim": True},
    "architect": {
        "provider": "databricks",
        "model": "databricks-claude-sonnet-4-6",
        "via_apim": False,
    },
    "test_plan": {"provider": "aoai", "model": settings.model_fast, "via_apim": True},
    "codegen": {
        "provider": "databricks",
        "model": "databricks-claude-sonnet-4-6",
        "via_apim": False,
    },
    "review_scan": {"provider": "aoai", "model": settings.model_default, "via_apim": True},
}


def _load_yaml_overrides() -> dict[str, dict[str, Any]]:
    """Read ./config.yaml or /app/config.yaml if present. Silent if absent."""
    candidates = [Path("/app/config.yaml"), Path("config.yaml")]
    for path in candidates:
        if not path.exists():
            continue
        try:
            import yaml  # PyYAML; available in the test venv + image
            data = yaml.safe_load(path.read_text()) or {}
            sp = data.get("stage_providers", {}) or {}
            if isinstance(sp, dict):
                _logger.info("stage_providers: loaded YAML overrides from %s", path)
                return {k: dict(v) for k, v in sp.items() if isinstance(v, dict)}
        except Exception as exc:  # pragma: no cover — bad YAML should not crash boot
            _logger.warning("failed to read %s: %s", path, exc)
    return {}


def _load_env_overrides() -> dict[str, dict[str, Any]]:
    """STAGE_<NAME>_PROVIDER / _MODEL / _VIA_APIM overrides."""
    out: dict[str, dict[str, Any]] = {}
    for stage in STAGE_NAMES:
        env_stage = stage.upper()
        prov = os.environ.get(f"STAGE_{env_stage}_PROVIDER")
        model = os.environ.get(f"STAGE_{env_stage}_MODEL")
        via = os.environ.get(f"STAGE_{env_stage}_VIA_APIM")
        if prov is None and model is None and via is None:
            continue
        entry: dict[str, Any] = {}
        if prov is not None:
            entry["provider"] = prov
        if model is not None:
            entry["model"] = model
        if via is not None:
            entry["via_apim"] = via.strip().lower() in ("1", "true", "yes", "on")
        out[stage] = entry
    return out


def _build_stage_providers() -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {k: dict(v) for k, v in _STAGE_PROVIDERS_DEFAULTS.items()}
    for stage, override in _load_yaml_overrides().items():
        if stage in merged:
            merged[stage].update(override)
    for stage, override in _load_env_overrides().items():
        if stage in merged:
            merged[stage].update(override)
    return merged


STAGE_PROVIDERS: dict[str, dict[str, Any]] = _build_stage_providers()


def reload_stage_providers() -> dict[str, dict[str, Any]]:
    """Re-read YAML + env. Used by tests; not called at runtime."""
    global STAGE_PROVIDERS
    STAGE_PROVIDERS = _build_stage_providers()
    return STAGE_PROVIDERS


def get_provider_for_stage(run: Any, stage: str) -> Any:
    """Return a configured Provider instance for `stage`, honouring per-run overrides.

    Lookup order:
      1. RunState.stage_provider_overrides[stage]   (per-run, set on submit)
      2. STAGE_PROVIDERS[stage]                     (env > yaml > defaults)
    """
    from .providers import get_provider  # late import to avoid cycle

    override: Optional[dict[str, Any]] = None
    overrides = getattr(run, "stage_provider_overrides", None) or {}
    if isinstance(overrides, dict) and stage in overrides and isinstance(overrides[stage], dict):
        override = overrides[stage]
    cfg = dict(STAGE_PROVIDERS.get(stage, {}))
    if override:
        cfg.update(override)
    provider_name = cfg.get("provider", "aoai")
    via_apim = bool(cfg.get("via_apim", provider_name == "aoai"))
    model = cfg.get("model")
    inst = get_provider(provider_name, via_apim=via_apim)
    # Stash the resolved model on the instance so stages can read it without a
    # second config lookup. Providers ignore unknown attrs.
    inst.resolved_model = model  # type: ignore[attr-defined]
    return inst


def get_model_for_stage(run: Any, stage: str) -> Optional[str]:
    overrides = getattr(run, "stage_provider_overrides", None) or {}
    if isinstance(overrides, dict):
        v = overrides.get(stage)
        if isinstance(v, dict) and v.get("model"):
            return v["model"]
    return STAGE_PROVIDERS.get(stage, {}).get("model")
