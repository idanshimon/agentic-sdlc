"""repo_autonomy — per-repo autonomy tiers for the autonomous review loop.

The "move the dial per repo" control (add-autonomous-review-loop, Phase 1).
Written fresh against two shipped idioms:

  * config.py::_hard_gate_classes() — env-first, bootstrap-on-absence, reload_().
  * heal.py::validate_heal_action() — fail-closed, most-restrictive-first.

Tiers:
  A — autonomous merge (human-out). Permitted only for explicitly graduated
      repos with a clean recent history (no PHI/deny blocker).
  B — autonomous review, human clicks merge. Default for opted-in repos.
  C — advisory only. Default for EVERY repo not listed (safe by absence).

Governance teeth (tightening-only, enforced twice):
  * load time: a repo requesting Tier A while it has a recent PHI/deny blocker
    is refused with RepoTierUnlockError — graduation must be earned.
  * runtime: effective_tier() downgrades to escalation-forcing when the CURRENT
    change carries a PHI/deny blocker, regardless of the configured tier.

Deploying the image changes no repo's behavior until a human graduates it.
"""
from __future__ import annotations

import dataclasses
import logging
import os
import pathlib
from typing import Optional

import yaml

_logger = logging.getLogger(__name__)

VALID_TIERS = {"A", "B", "C"}
_DEFAULT_TIER = "C"


class RepoTierUnlockError(Exception):
    """Raised when a config grants a tier that the governance floor forbids —
    e.g. Tier A for a repo with a recent PHI/deny blocker, or an invalid tier.
    Mirrors heal.py's fail-closed posture: the unsafe config is refused, not
    half-applied.
    """


@dataclasses.dataclass(frozen=True)
class _RepoTier:
    tier: str
    recent_phi_or_deny_blocker: bool = False
    note: str = ""


@dataclasses.dataclass
class RepoAutonomyPolicy:
    repos: dict[str, _RepoTier]
    is_bootstrap: bool = False

    def tier_for(self, repo: str) -> str:
        """Configured tier for `repo`, or Tier C if unlisted (safe by absence)."""
        rt = self.repos.get(repo)
        return rt.tier if rt else _DEFAULT_TIER

    def effective_tier(self, repo: str, *, has_phi_or_deny: bool) -> str:
        """Runtime tier. The PHI/deny floor forces escalation (treated as the
        advisory 'C' — the loop controller then escalates rather than merging)
        whenever the current change carries a PHI/deny blocker, regardless of
        the configured tier. This is the second half of the double enforcement.
        """
        if has_phi_or_deny:
            return _DEFAULT_TIER
        return self.tier_for(repo)

    def posture_summary(self) -> dict:
        """Legible posture for the /api/config/repo-autonomy endpoint + UI."""
        return {
            "bootstrap": self.is_bootstrap,
            "default_tier": _DEFAULT_TIER,
            "repos": [
                {
                    "repo": name,
                    "tier": rt.tier,
                    "recent_phi_or_deny_blocker": rt.recent_phi_or_deny_blocker,
                    "why_capped": rt.note or (
                        "PHI/deny blocker in recent history — Tier A withheld"
                        if rt.recent_phi_or_deny_blocker else ""
                    ),
                }
                for name, rt in sorted(self.repos.items())
            ],
        }


def _candidate_paths() -> list[pathlib.Path]:
    """Env var first, then deploy locations. NEVER the repo's .example template
    (mirrors the opt-in-loader posture-A guarantee)."""
    out: list[pathlib.Path] = []
    env = os.getenv("REPO_AUTONOMY_PATH", "").strip()
    if env:
        out.append(pathlib.Path(env))
    out.append(pathlib.Path("/app/repo_autonomy.yaml"))
    out.append(pathlib.Path("./repo_autonomy.yaml"))
    return out


def _bootstrap() -> RepoAutonomyPolicy:
    return RepoAutonomyPolicy(repos={}, is_bootstrap=True)


def _validate_and_build(data: dict) -> RepoAutonomyPolicy:
    """Build a policy from parsed YAML, enforcing the governance teeth at load."""
    repos_raw = (data or {}).get("repos") or {}
    if not isinstance(repos_raw, dict):
        raise RepoTierUnlockError("`repos` must be a mapping of repo -> {tier: ...}")
    repos: dict[str, _RepoTier] = {}
    for name, spec in repos_raw.items():
        if not isinstance(spec, dict):
            raise RepoTierUnlockError(f"repo '{name}' spec must be a mapping")
        tier = str(spec.get("tier", _DEFAULT_TIER)).strip().upper()
        if tier not in VALID_TIERS:
            raise RepoTierUnlockError(
                f"repo '{name}' has invalid tier '{tier}' (must be A, B, or C)"
            )
        phi_hist = bool(spec.get("recent_phi_or_deny_blocker", False))
        # TEETH: Tier A requires a clean recent history. Graduation is earned.
        if tier == "A" and phi_hist:
            raise RepoTierUnlockError(
                f"repo '{name}' cannot be Tier A: a PHI/deny blocker in its "
                f"recent history withholds autonomous merge (graduation must be "
                f"earned with a clean window)."
            )
        repos[name] = _RepoTier(
            tier=tier, recent_phi_or_deny_blocker=phi_hist,
            note=str(spec.get("note", "")),
        )
    return RepoAutonomyPolicy(repos=repos, is_bootstrap=False)


def load_repo_autonomy(path: Optional[str] = None) -> RepoAutonomyPolicy:
    """Load the policy. Absence -> bootstrap (all Tier C). A malformed file
    degrades to bootstrap (logged loudly) — never a half-applied permissive
    policy. A well-formed file that violates the teeth raises RepoTierUnlockError
    (a deliberate unsafe config must fail loudly, not silently downgrade).
    """
    candidates = [pathlib.Path(path)] if path else _candidate_paths()
    for p in candidates:
        if not p.exists():
            continue
        try:
            data = yaml.safe_load(p.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            _logger.error(
                "repo_autonomy: %s failed to parse (%s) — degrading to bootstrap "
                "(all repos Tier C). Fix the file to restore configured tiers.",
                p, exc,
            )
            return _bootstrap()
        return _validate_and_build(data if isinstance(data, dict) else {})
    return _bootstrap()


# Module singleton loaded at import (opt-in — bootstrap unless a file is present).
REPO_AUTONOMY: RepoAutonomyPolicy = load_repo_autonomy()


def reload_repo_autonomy(path: Optional[str] = None) -> RepoAutonomyPolicy:
    """Re-read the config (tests + the /api/config/reload endpoint)."""
    global REPO_AUTONOMY
    REPO_AUTONOMY = load_repo_autonomy(path)
    return REPO_AUTONOMY
