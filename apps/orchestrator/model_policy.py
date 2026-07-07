"""Model policy — configuration-plane Phase 4 (add-configuration-plane).

Which models may run which stages, which are cleared for PHI-adjacent work, and
the cost ceilings a run/team must stay under. Today model routing is code-
resident (config.STAGE_PROVIDERS defaults); this object makes the GOVERNANCE of
models authorable and enforceable at stage dispatch:

    allowlist[]        — if non-empty, only these models may run (deny-by-default)
    denylist[]         — models that may NEVER run (wins over allowlist)
    phi_eligible[]     — models cleared to run PHI-adjacent stages
    routing{stage:m}   — advisory per-stage default (the pipeline may still
                         override per-run; enforcement is on the RESOLVED model)
    cost_ceiling_usd   — {per_run, per_team_month} spend caps
    phi_stages[]       — stages treated as PHI-adjacent (default: architect,
                         codegen, review_scan — where PHI content is handled)

Enforcement posture mirrors autonomy.py / org_model.py:
    python default (permissive)  <  ./models.yaml or /app/models.yaml  <  MODELS_PATH

Opt-in: no models.yaml => bootstrap (permissive) — every model allowed, no
ceiling — identical to pre-Phase-4 behaviour. The repo config/models.yaml.example
is a TEMPLATE and is NOT auto-discovered (see config/README.md).

A refused model or an over-ceiling run does not crash: the caller gates/fails the
run and writes a ledger entry citing `rule_ref` (the audit answer the compliance
query reads). check_* helpers are pure so they're trivially testable.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

_logger = logging.getLogger("orchestrator.model_policy")

# Stages that handle PHI-adjacent content by default (where a non-cleared model
# must be refused). Overridable via models.yaml `phi_stages:`.
_DEFAULT_PHI_STAGES = frozenset({"architect", "codegen", "review_scan"})


@dataclass(frozen=True)
class PolicyVerdict:
    """Result of an enforcement check. `rule_ref` is the structured, grep-able
    citation stamped onto the ledger entry when a stage is refused."""
    allowed: bool
    reason: str = ""
    rule_ref: str = ""


_ALLOW = PolicyVerdict(allowed=True)


@dataclass(frozen=True)
class ModelPolicy:
    loaded: bool = False
    allowlist: frozenset[str] = field(default_factory=frozenset)
    denylist: frozenset[str] = field(default_factory=frozenset)
    phi_eligible: frozenset[str] = field(default_factory=frozenset)
    routing: dict[str, str] = field(default_factory=dict)
    phi_stages: frozenset[str] = _DEFAULT_PHI_STAGES
    cost_ceiling_per_run: Optional[float] = None
    cost_ceiling_per_team_month: Optional[float] = None

    def check_model(self, stage: str, model: str, *, phi: bool) -> PolicyVerdict:
        """Is `model` permitted to run `stage`? `phi` = this stage/run handles
        PHI-classified content (caller decides from run.phi_class / cards).

        Order: bootstrap-pass → denylist → allowlist (deny-by-default when set)
        → PHI eligibility (only on a phi stage or an explicit phi run).
        """
        if not self.loaded:
            return _ALLOW
        m = (model or "").strip()
        if m in self.denylist:
            return PolicyVerdict(
                False, f"model {m!r} is on the models.yaml denylist",
                f"models/denylist/{m}",
            )
        if self.allowlist and m not in self.allowlist:
            return PolicyVerdict(
                False,
                f"model {m!r} is not on the models.yaml allowlist (deny-by-default)",
                f"models/allowlist/{m}",
            )
        phi_stage = stage in self.phi_stages
        if (phi or phi_stage) and self.phi_eligible and m not in self.phi_eligible:
            return PolicyVerdict(
                False,
                f"model {m!r} is not phi_eligible but stage {stage!r} is "
                f"PHI-adjacent",
                f"models/phi_eligible/{stage}/{m}",
            )
        return _ALLOW

    def check_cost(
        self, *, run_cost_so_far: float, team_month_cost_so_far: float = 0.0,
    ) -> PolicyVerdict:
        """Is the run still within the configured spend ceilings?"""
        if not self.loaded:
            return _ALLOW
        if (self.cost_ceiling_per_run is not None
                and run_cost_so_far > self.cost_ceiling_per_run):
            return PolicyVerdict(
                False,
                f"run cost ${run_cost_so_far:.4f} exceeds per_run ceiling "
                f"${self.cost_ceiling_per_run:.2f}",
                f"models/cost_ceiling/per_run/{self.cost_ceiling_per_run:g}",
            )
        if (self.cost_ceiling_per_team_month is not None
                and team_month_cost_so_far > self.cost_ceiling_per_team_month):
            return PolicyVerdict(
                False,
                f"team month cost ${team_month_cost_so_far:.2f} exceeds "
                f"per_team_month ceiling ${self.cost_ceiling_per_team_month:.2f}",
                f"models/cost_ceiling/per_team_month/{self.cost_ceiling_per_team_month:g}",
            )
        return _ALLOW


def _candidate_paths() -> list[Path]:
    """Activation is OPT-IN — the repo config/models.yaml.example TEMPLATE is
    NOT auto-discovered. A fresh deploy stays permissive until an operator sets
    MODELS_PATH or drops /app/models.yaml (or ./models.yaml)."""
    env_path = os.getenv("MODELS_PATH")
    paths: list[Path] = []
    if env_path:
        paths.append(Path(env_path))
    paths.extend([Path("/app/models.yaml"), Path("models.yaml")])
    return paths


def _as_set(raw: object) -> frozenset[str]:
    if not isinstance(raw, list):
        return frozenset()
    return frozenset(str(x).strip() for x in raw if str(x).strip())


def load_model_policy(path: Optional[str] = None) -> ModelPolicy:
    """Load models.yaml. Returns an unloaded (permissive/bootstrap) policy when
    absent or malformed — model governance should fail OPEN to permissive
    (never brick the pipeline), logging loudly, since it's an additive control
    over the existing routing defaults."""
    search = [Path(path)] if path else _candidate_paths()
    for p in search:
        if not p.exists():
            continue
        try:
            import yaml
            data = yaml.safe_load(p.read_text()) or {}
        except Exception as exc:
            _logger.error("model_policy: failed to parse %s: %s — permissive", p, exc)
            return ModelPolicy(loaded=False)

        ceilings = data.get("cost_ceiling_usd", {}) or {}
        phi_stages_raw = _as_set(data.get("phi_stages"))
        _logger.info("model_policy: loaded %s", p)
        return ModelPolicy(
            loaded=True,
            allowlist=_as_set(data.get("allowlist")),
            denylist=_as_set(data.get("denylist")),
            phi_eligible=_as_set(data.get("phi_eligible")),
            routing={str(k): str(v) for k, v in (data.get("routing", {}) or {}).items()},
            phi_stages=phi_stages_raw or _DEFAULT_PHI_STAGES,
            cost_ceiling_per_run=(
                float(ceilings["per_run"]) if "per_run" in ceilings else None
            ),
            cost_ceiling_per_team_month=(
                float(ceilings["per_team_month"]) if "per_team_month" in ceilings else None
            ),
        )

    _logger.info("model_policy: no models.yaml found — bootstrap (permissive) mode")
    return ModelPolicy(loaded=False)


# Module-level singleton, mirroring config.STAGE_PROVIDERS / autonomy.AUTONOMY_MATRIX.
MODEL_POLICY: ModelPolicy = load_model_policy()


def reload_model_policy(path: Optional[str] = None) -> ModelPolicy:
    global MODEL_POLICY
    MODEL_POLICY = load_model_policy(path)
    return MODEL_POLICY
