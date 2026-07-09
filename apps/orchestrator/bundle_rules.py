"""Standards-bundle rule model — Phase 3 of the configuration-plane capability.

openspec: add-configuration-plane / Requirement "authorable standards bundles
with blast class and PHI lock".

Today the four bundles (architect, security, privacy, finops) are read only as
directory NAMES (agent_bundles._load_known_bundles) — nothing parses the RULES
inside rules.yaml. This module makes bundle rules first-class so:

  1. each rule carries `blast_class` (LOW|MED|HIGH) and `phi_locked` (bool),
     driving reviewer-quorum selection (reviewers.yaml) and the Doctor's
     auto-fix envelope;
  2. a governed edit (the /api/config/bundles/save PR flow) can be VALIDATED
     before it opens the PR — a diff that would unlock, weaken, or delete a
     phi_locked rule is REFUSED. This is the teeth of the governance story and
     mirrors autonomy.py's invariant hard-lock: even a well-formed edit cannot
     quietly relax a PHI control. Strengthening is always allowed.

`phi_locked` defaults to the rule's `phi` flag: a PHI rule is locked unless the
YAML explicitly (and only ever more strictly) says otherwise — and it can never
be flipped to False by an edit (validate_bundle_edit enforces).

Loading here is pure (text/dir in, dataclasses out) so it is trivially testable
and reusable by the save endpoint, the Doctor, and the compliance surface.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

_logger = logging.getLogger("orchestrator.bundle_rules")

BlastClass = str  # normalized to one of _VALID_BLAST
_VALID_BLAST = {"LOW", "MED", "HIGH"}
_SEVERITY_RANK = {"LOG": 0, "WARN": 1, "BLOCK": 2}


class PhiLockViolation(Exception):
    """Raised when a bundle edit would unlock, weaken, or delete a phi_locked
    rule. The governed-PR save path refuses the edit before opening the PR."""

    def __init__(self, rule_id: str, reason: str) -> None:
        self.rule_id = rule_id
        super().__init__(
            f"refused: edit would {reason} the PHI-locked rule {rule_id!r}. "
            f"PHI controls can only be strengthened, never weakened — this is a "
            f"hard governance lock (defense in depth). Author a new rule or raise "
            f"a standards-change with explicit security+privacy sign-off instead."
        )


@dataclass(frozen=True)
class BundleRule:
    id: str
    title: str = ""
    phi: bool = False
    phi_locked: bool = False
    blast_class: BlastClass = "MED"
    severity: str = "BLOCK"
    rationale: str = ""

    @property
    def severity_rank(self) -> int:
        return _SEVERITY_RANK.get(self.severity, 2)


@dataclass(frozen=True)
class Bundle:
    dept: str
    version: str = ""
    rules: dict[str, BundleRule] = field(default_factory=dict)


def _norm_blast(raw: object, rule_id: str) -> str:
    if raw is None:
        return "MED"
    val = str(raw).strip().upper()
    if val not in _VALID_BLAST:
        raise ValueError(
            f"rule {rule_id!r}: invalid blast_class {raw!r}; "
            f"expected one of {sorted(_VALID_BLAST)}"
        )
    return val


def _rule_from_dict(d: dict) -> BundleRule:
    rid = str(d.get("id", "")).strip()
    if not rid:
        raise ValueError("bundle rule missing required 'id'")
    phi = bool(d.get("phi", False))
    # phi_locked defaults to the phi flag: a PHI rule is locked unless the YAML
    # is explicit. (validate_bundle_edit still forbids ever flipping it False.)
    phi_locked = bool(d.get("phi_locked", phi))
    return BundleRule(
        id=rid,
        title=str(d.get("title", "")),
        phi=phi,
        phi_locked=phi_locked,
        blast_class=_norm_blast(d.get("blast_class"), rid),
        severity=str(d.get("severity", "BLOCK")).strip().upper(),
        rationale=str(d.get("rationale", "")),
    )


def load_bundle_from_text(text: str) -> Bundle:
    """Parse a rules.yaml body into a Bundle. Raises ValueError on a malformed
    rule (bad blast_class, missing id) — a broken bundle should fail loudly."""
    import yaml

    data = yaml.safe_load(text) or {}
    meta = data.get("metadata", {}) or {}
    rules: dict[str, BundleRule] = {}
    for r in data.get("rules", []) or []:
        if not isinstance(r, dict):
            continue
        rule = _rule_from_dict(r)
        rules[rule.id] = rule
    return Bundle(
        dept=str(meta.get("bundle", "")),
        version=str(meta.get("version", "")),
        rules=rules,
    )


def load_bundle(
    dept: str, version: str, *, bundles_dir: Optional[Path] = None,
) -> Bundle:
    """Load standards-bundles/<dept>/<version>/rules.yaml from disk."""
    root = Path(bundles_dir) if bundles_dir else (
        Path(__file__).resolve().parents[2] / "standards-bundles"
    )
    path = root / dept / version / "rules.yaml"
    return load_bundle_from_text(path.read_text(encoding="utf-8"))


def validate_bundle_edit(existing: Bundle, proposed: Bundle) -> None:
    """Refuse a proposed bundle that would weaken a phi_locked rule.

    For every rule that is phi_locked in `existing`, the `proposed` bundle must:
      - still contain it (no deletion),
      - keep phi_locked True (no unlock),
      - keep phi True (a PHI rule cannot be de-classified),
      - not lower its severity (no BLOCK -> WARN downgrade).

    Adding rules, tightening severity, and strengthening locks are all allowed.
    Raises PhiLockViolation on the first offending rule.
    """
    for rid, old in existing.rules.items():
        if not old.phi_locked:
            continue
        new = proposed.rules.get(rid)
        if new is None:
            raise PhiLockViolation(rid, "delete")
        if not new.phi_locked:
            raise PhiLockViolation(rid, "unlock (phi_locked -> false) on")
        if old.phi and not new.phi:
            raise PhiLockViolation(rid, "de-classify (phi -> false) on")
        if new.severity_rank < old.severity_rank:
            raise PhiLockViolation(rid, "downgrade severity of")
