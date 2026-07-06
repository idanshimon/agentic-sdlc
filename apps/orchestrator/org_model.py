"""Organization model — the identity spine of the Decision Record.

Phase 1 of the configuration-plane capability (openspec: add-configuration-plane).
Loads an authorable `org.yaml` defining departments, teams (with cost_center and
m365_group), and identity mapping, then resolves a run's team_id to that real
attribution. Every ledger entry can then carry a non-null team + cost_center +
identity instead of a placeholder — which is what makes the acceptance query
("every AI decision on PHI data, the governing rule, the actor, the cost")
return complete rows.

Design posture (matches config.py §two-plane): governance config is INJECTED,
never hardcoded. Same precedence spirit as STAGE_PROVIDERS:
    python default (empty)  <  ./org.yaml or /app/org.yaml  <  ORG_MODEL_PATH env

Hard rule (openspec spec scenario): a run referencing a team absent from the
org model is REJECTED, not silently written as an anonymous entry. No org model
loaded at all = permissive (bootstrap/demo), because refusing every run when the
customer hasn't authored org.yaml yet would brick the pipeline. Once an org
model IS present, unknown teams are refused.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

_logger = logging.getLogger("orchestrator.org_model")


class UnknownTeamError(Exception):
    """Raised when a run references a team_id not in a loaded org model."""

    def __init__(self, team_id: str, known: list[str]) -> None:
        self.team_id = team_id
        self.known = known
        super().__init__(
            f"team_id {team_id!r} is not defined in the organization model "
            f"(known teams: {', '.join(sorted(known)) or '(none)'}). "
            f"Add it to org.yaml or submit under a configured team."
        )


@dataclass(frozen=True)
class Team:
    id: str
    name: str
    department: str
    cost_center: str = ""
    m365_group: str = ""


@dataclass(frozen=True)
class Department:
    id: str
    name: str
    owner: str = ""
    reviewer_roster: dict[str, str] = field(default_factory=dict)  # role -> upn


@dataclass(frozen=True)
class OrgModel:
    """A loaded organization model. `loaded=False` means no org.yaml was found,
    which puts resolution in permissive bootstrap mode (see module docstring)."""
    loaded: bool = False
    entra_tenant_id: str = ""
    departments: dict[str, Department] = field(default_factory=dict)
    teams: dict[str, Team] = field(default_factory=dict)
    approver_rbac: dict[str, list[str]] = field(default_factory=dict)  # action -> [upn|role]

    def resolve_team(self, team_id: str) -> Team:
        """Resolve a team_id to its Team. In bootstrap mode (no org loaded), synth
        a placeholder Team so the pipeline still runs. Once loaded, an unknown
        team_id is a hard error (openspec scenario: unknown team is rejected)."""
        if team_id in self.teams:
            return self.teams[team_id]
        if not self.loaded:
            _logger.info("org_model: bootstrap mode, synthesizing team %r", team_id)
            return Team(id=team_id, name=team_id, department="(unassigned)")
        raise UnknownTeamError(team_id, list(self.teams))


def _candidate_paths() -> list[Path]:
    env_path = os.getenv("ORG_MODEL_PATH")
    paths: list[Path] = []
    if env_path:
        paths.append(Path(env_path))
    paths.extend([Path("/app/org.yaml"), Path("org.yaml"),
                  Path(__file__).resolve().parent.parent.parent / "config" / "org.yaml"])
    return paths


def load_org_model(path: Optional[str] = None) -> OrgModel:
    """Load the org model from YAML. Returns an unloaded (bootstrap) OrgModel when
    no file is found — never raises on absence, so a fresh deploy still runs."""
    search = [Path(path)] if path else _candidate_paths()
    for p in search:
        if not p.exists():
            continue
        try:
            import yaml  # PyYAML — present in image + test venv
            data = yaml.safe_load(p.read_text()) or {}
        except Exception as exc:  # pragma: no cover — bad YAML shouldn't brick boot
            _logger.warning("org_model: failed to read %s: %s", p, exc)
            continue

        departments: dict[str, Department] = {}
        for d in data.get("departments", []) or []:
            if not isinstance(d, dict) or "id" not in d:
                continue
            departments[d["id"]] = Department(
                id=d["id"],
                name=d.get("name", d["id"]),
                owner=d.get("owner", ""),
                reviewer_roster=dict(d.get("reviewer_roster", {}) or {}),
            )

        teams: dict[str, Team] = {}
        for t in data.get("teams", []) or []:
            if not isinstance(t, dict) or "id" not in t:
                continue
            teams[t["id"]] = Team(
                id=t["id"],
                name=t.get("name", t["id"]),
                department=t.get("department", "(unassigned)"),
                cost_center=t.get("cost_center", ""),
                m365_group=t.get("m365_group", ""),
            )

        identity = data.get("identity", {}) or {}
        _logger.info("org_model: loaded %s (%d departments, %d teams)",
                     p, len(departments), len(teams))
        return OrgModel(
            loaded=True,
            entra_tenant_id=identity.get("entra_tenant_id", ""),
            departments=departments,
            teams=teams,
            approver_rbac={k: list(v) for k, v in (identity.get("approver_rbac", {}) or {}).items()},
        )

    _logger.info("org_model: no org.yaml found — bootstrap (permissive) mode")
    return OrgModel(loaded=False)


# Module-level singleton, mirroring config.STAGE_PROVIDERS.
ORG_MODEL: OrgModel = load_org_model()


def reload_org_model(path: Optional[str] = None) -> OrgModel:
    """Re-read org.yaml (tests + config-reload endpoint use this)."""
    global ORG_MODEL
    ORG_MODEL = load_org_model(path)
    return ORG_MODEL
