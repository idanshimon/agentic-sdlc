"""Autonomy matrix — the COE's steering wheel.

Phase 2 of the configuration-plane capability (openspec: add-configuration-plane).
Replaces the code-resident autopilot behaviour (mode = autopilot/hybrid, binary)
with an authorable per-(decision_class × team) policy:

    gate                         — always require a human decision
    autopilot_above_threshold(t) — auto-resolve only when ledger precedent
                                    confidence >= t; otherwise gate
    autopilot_always             — auto-resolve on the recommended option

Hard invariant (openspec scenario "PHI classes cannot be configured open"):
phi-classification and auth-policy are validator-hard-locked to `gate`. The
matrix may TIGHTEN any class to gate, but can NEVER open an invariant class to
any autopilot mode — the loader refuses such a config and the resolver double-
checks at decision time. Defense in depth: even a hand-mangled autonomy.yaml
cannot un-gate PHI.

Precedence mirrors config.py / org_model.py (inject-never-hardcode):
    python default  <  ./autonomy.yaml or /app/autonomy.yaml  <  AUTONOMY_PATH env

Default when no file is present (bootstrap): preserve today's behaviour exactly —
non-invariant classes follow run.mode, invariants always gate. So an un-authored
deployment behaves identically to pre-Phase-2.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

_logger = logging.getLogger("orchestrator.autonomy")

# Kept local to avoid an import cycle with models at module load; validated
# against models.INVARIANT_CLASSES in _validate().
_INVARIANT_CLASSES = {"phi-classification", "auth-policy"}

AutonomyMode = Literal["gate", "autopilot_above_threshold", "autopilot_always"]
_VALID_MODES = {"gate", "autopilot_above_threshold", "autopilot_always"}


class InvariantUnlockError(Exception):
    """Raised when an autonomy.yaml tries to set an invariant class to autopilot."""

    def __init__(self, decision_class: str, team_id: str, mode: str) -> None:
        super().__init__(
            f"autonomy.yaml sets invariant class {decision_class!r} for team "
            f"{team_id!r} to {mode!r}; invariant classes (phi-classification, "
            f"auth-policy) are hard-locked to 'gate' and cannot be configured open."
        )


@dataclass(frozen=True)
class AutonomyRule:
    mode: AutonomyMode = "gate"
    threshold: float = 0.0  # only meaningful for autopilot_above_threshold


@dataclass(frozen=True)
class AutonomyMatrix:
    """Per-(team, decision_class) autonomy policy. `loaded=False` = bootstrap
    (mode-driven legacy behaviour)."""
    loaded: bool = False
    # (team_id, decision_class) -> AutonomyRule ; team_id "*" = default for all teams
    rules: dict[tuple[str, str], AutonomyRule] = field(default_factory=dict)

    def rule_for(self, team_id: str, decision_class: str) -> Optional[AutonomyRule]:
        """Resolve the rule: exact (team, class) wins, then ("*", class) default.
        Returns None when unloaded or unspecified (caller falls back to mode)."""
        # Invariants are always gate, regardless of what the matrix says.
        if decision_class in _INVARIANT_CLASSES:
            return AutonomyRule(mode="gate")
        if not self.loaded:
            return None
        exact = self.rules.get((team_id, decision_class))
        if exact is not None:
            return exact
        return self.rules.get(("*", decision_class))


def autonomy_ref(
    team_id: str,
    decision_class: str,
    *,
    matrix: "Optional[AutonomyMatrix]" = None,
    loaded_source: str = "matrix",
    reason: str = "",
) -> str:
    """Render a stable, queryable citation for WHY a decision was autopiloted or
    gated — the audit answer the Phase 5 compliance query reads.

    Shape: ``autonomy/<source>/<scope>/<class>/<mode>[@t=<threshold>]:<reason>``
      - source: "matrix" (config-plane rule) or "mode" (bootstrap/legacy default)
      - scope:  the team_id whose rule matched, "*" for the default row, or
                "invariant" for the hard-lock, or "bootstrap" when no matrix
      - mode:   gate | autopilot_always | autopilot_above_threshold
      - reason: short machine tag (e.g. "precedent>=0.8", "no-precedent",
                "phi-hard-lock", "autopilot-mode")

    Deterministic and grep-able so it can be filtered in the ledger query. Never
    free text alone — the structured prefix is the contract.
    """
    m = matrix if matrix is not None else AUTONOMY_MATRIX
    if decision_class in _INVARIANT_CLASSES:
        return f"autonomy/invariant/{decision_class}/gate:phi-auth-hard-lock"
    rule = m.rule_for(team_id, decision_class) if m is not None else None
    if rule is None:
        # bootstrap / mode-driven — no matrix rule governed this
        tag = reason or "mode-driven"
        return f"autonomy/mode/bootstrap/{decision_class}/{'gate'}:{tag}"
    # Which scope matched: exact team row or the "*" default.
    scope = team_id if (team_id, decision_class) in m.rules else "*"
    base = f"autonomy/{loaded_source}/{scope}/{decision_class}/{rule.mode}"
    if rule.mode == "autopilot_above_threshold":
        base += f"@t={rule.threshold:g}"
    if reason:
        base += f":{reason}"
    return base


def _candidate_paths() -> list[Path]:
    """Activation is OPT-IN. The shipped config/autonomy.yaml is a TEMPLATE and is
    deliberately NOT auto-discovered — a fresh deploy stays in bootstrap
    (mode-driven) mode until an operator explicitly activates the matrix by
    either setting AUTONOMY_PATH or dropping a file at a deploy location
    (/app/autonomy.yaml or ./autonomy.yaml). This keeps the neutral demo policy
    from silently gating decisions the moment the image ships. See config/README.md."""
    env_path = os.getenv("AUTONOMY_PATH")
    paths: list[Path] = []
    if env_path:
        paths.append(Path(env_path))
    # Deploy locations an operator opts into by placing a file there. The repo
    # config/ template dir is intentionally excluded from auto-discovery.
    paths.extend([Path("/app/autonomy.yaml"), Path("autonomy.yaml")])
    return paths


def _validate(team_id: str, decision_class: str, mode: str) -> None:
    if mode not in _VALID_MODES:
        raise ValueError(
            f"autonomy.yaml: invalid mode {mode!r} for ({team_id}, {decision_class}); "
            f"expected one of {sorted(_VALID_MODES)}"
        )
    if decision_class in _INVARIANT_CLASSES and mode != "gate":
        raise InvariantUnlockError(decision_class, team_id, mode)


def load_autonomy_matrix(path: Optional[str] = None) -> AutonomyMatrix:
    """Load autonomy.yaml. Returns an unloaded (bootstrap) matrix when absent.

    YAML shape:
        teams:
          cardiology:
            sla-binding: autopilot_always
            identifier-format: { mode: autopilot_above_threshold, threshold: 0.8 }
          "*":                       # default for every team
            naming-convention: autopilot_always

    A row may be a bare mode string or a {mode, threshold} object.
    Raises InvariantUnlockError / ValueError on an invalid or unsafe config —
    a malformed autonomy policy should fail loudly, not silently mis-gate.
    """
    search = [Path(path)] if path else _candidate_paths()
    for p in search:
        if not p.exists():
            continue
        try:
            import yaml
            data = yaml.safe_load(p.read_text()) or {}
        except Exception as exc:
            # Unlike org_model, a broken autonomy policy is safety-relevant: fall
            # back to bootstrap (mode-driven) rather than guess. Log loudly.
            _logger.error("autonomy: failed to parse %s: %s — falling back to mode-driven", p, exc)
            return AutonomyMatrix(loaded=False)

        rules: dict[tuple[str, str], AutonomyRule] = {}
        teams = data.get("teams", {}) or {}
        for team_id, class_map in teams.items():
            if not isinstance(class_map, dict):
                continue
            for decision_class, spec in class_map.items():
                if isinstance(spec, str):
                    mode, threshold = spec, 0.0
                elif isinstance(spec, dict):
                    mode = spec.get("mode", "gate")
                    threshold = float(spec.get("threshold", 0.0))
                else:
                    continue
                _validate(str(team_id), str(decision_class), str(mode))
                rules[(str(team_id), str(decision_class))] = AutonomyRule(
                    mode=mode, threshold=threshold,  # type: ignore[arg-type]
                )
        _logger.info("autonomy: loaded %s (%d rules)", p, len(rules))
        return AutonomyMatrix(loaded=True, rules=rules)

    _logger.info("autonomy: no autonomy.yaml found — bootstrap (mode-driven) mode")
    return AutonomyMatrix(loaded=False)


# Module-level singleton, mirroring config.STAGE_PROVIDERS + org_model.ORG_MODEL.
AUTONOMY_MATRIX: AutonomyMatrix = load_autonomy_matrix()


def reload_autonomy_matrix(path: Optional[str] = None) -> AutonomyMatrix:
    global AUTONOMY_MATRIX
    AUTONOMY_MATRIX = load_autonomy_matrix(path)
    return AUTONOMY_MATRIX
