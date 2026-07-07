"""PINS reader — team → bundle-version pin matrix (Phase 3, config-plane).

standards-bundles/PINS.yaml pins every team to a bundle version per department;
unlisted teams inherit `defaults`. The orchestrator refuses to start on an
unresolvable pin (that guard lives in the bundle loader / startup path). This
module is the READ surface the config UI renders: the pin matrix plus the set
of bundle versions that actually exist on disk (so the UI can offer a valid pin
dropdown and a COE can change a pin through the governed PR flow).

Pure + dependency-light so it is trivially testable and reusable.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

_logger = logging.getLogger("orchestrator.pins")

_DEPTS = ("architect", "security", "privacy", "finops")


def _bundles_root(bundles_dir: Optional[Path] = None) -> Path:
    return Path(bundles_dir) if bundles_dir else (
        Path(__file__).resolve().parents[2] / "standards-bundles"
    )


def available_versions(bundles_dir: Optional[Path] = None) -> dict[str, list[str]]:
    """{dept: [v0.1.0, ...]} — the bundle versions present on disk per dept."""
    root = _bundles_root(bundles_dir)
    out: dict[str, list[str]] = {}
    for dept in _DEPTS:
        d = root / dept
        if not d.is_dir():
            out[dept] = []
            continue
        out[dept] = sorted(
            p.name for p in d.iterdir()
            if p.is_dir() and not p.name.startswith(".")
        )
    return out


def read_pins(bundles_dir: Optional[Path] = None) -> dict:
    """Read PINS.yaml into a UI-shaped payload:
        {defaults: {dept: version}, teams: {team: {dept: version}},
         available: {dept: [versions]}}
    Missing PINS.yaml → empty defaults/teams (still returns available)."""
    root = _bundles_root(bundles_dir)
    pins_path = root / "PINS.yaml"
    defaults: dict[str, str] = {}
    teams: dict[str, dict[str, str]] = {}
    if pins_path.exists():
        try:
            import yaml
            data = yaml.safe_load(pins_path.read_text()) or {}
            defaults = {k: str(v) for k, v in (data.get("defaults", {}) or {}).items()}
            for team, pins in (data.get("teams", {}) or {}).items():
                if isinstance(pins, dict):
                    teams[str(team)] = {k: str(v) for k, v in pins.items()}
        except Exception as exc:  # pragma: no cover - defensive
            _logger.warning("pins: failed to read %s: %s", pins_path, exc)
    return {
        "defaults": defaults,
        "teams": teams,
        "available": available_versions(bundles_dir),
    }


def effective_pins(team_id: str, bundles_dir: Optional[Path] = None) -> dict[str, str]:
    """Effective version per dept for a team: its explicit pins over defaults."""
    payload = read_pins(bundles_dir)
    eff = dict(payload["defaults"])
    eff.update(payload["teams"].get(team_id, {}))
    return eff
