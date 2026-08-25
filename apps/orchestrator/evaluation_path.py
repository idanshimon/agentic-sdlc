"""Evaluation-path integrity — tasks 6d.6 and 6d.7.

## The line this closes

The sharpest sentence in the adversarial review:

> An agent that can't weaken a rule can still weaken the test that proves it.

The system protects `standards-bundles/**` under CODEOWNERS and refuses edits
that unlock a `phi_locked` rule. That is real, and it is not enough. A rule is
only as trustworthy as the machinery that evaluates it, and that machinery is
ordinary code sitting in the same repository:

- the **workflow** that runs the gate — disable a step, add `continue-on-error`,
  narrow a path filter and the gate never fires;
- the **actions** it calls, including transitive and floating tags;
- the **verifier** that interprets the rule — invert a comparison and every
  patch passes;
- the **collectors** producing the evidence — return an empty finding list and
  there is nothing to block on;
- the **publisher** that reports the check — publish success unconditionally;
- the **pinned versions** themselves — repointing a pin is a policy change
  wearing a dependency-bump costume.

Protecting `rules.yaml` while leaving any of these writable is a gate in name
only. So the protected set is not "the rules" — it is **the whole path by which
a rule becomes a verdict**.

## Why a path filter is the subtle one

`paths:` and `paths-ignore:` look like performance tuning. They are policy: a
gate that does not run cannot fail. A change narrowing a gate's path filter is
a governance change and must be reviewed as one, which is easy to miss in a
diff that otherwise looks like CI housekeeping.

## Self-referential integrity

This module's own file is in the protected set. A check that can be edited by
the thing it checks is decorative — the integrity checker must be as protected
as what it protects, or an agent's first move is to weaken the checker.

## What this is NOT

This evaluates a *supplied* set of changed paths and a *supplied* protection
configuration. It does not read the repository, resolve transitive action
dependencies, or verify that CODEOWNERS is actually enforced on the ref. Those
require live repository state (6d.2/6d.3). This decides, given a diff, whether
the evaluation path was touched — which is the decision CI needs to make on
every pull request.
"""
from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Optional, Sequence


class PathClass(str, Enum):
    """Why a changed file is governance-relevant."""

    RULES = "rules"                  # the standards bundles themselves
    WORKFLOW = "workflow"            # what runs the gate
    ACTION = "action"                # what the workflow calls
    VERIFIER = "verifier"            # what interprets a rule
    COLLECTOR = "collector"          # what produces the evidence
    PUBLISHER = "publisher"          # what reports the verdict
    PIN = "pin"                      # pinned versions of any of the above
    INTEGRITY = "integrity"          # this checker itself
    OWNERSHIP = "ownership"          # CODEOWNERS / protection config


#: Glob -> class. Order matters: the first match wins, so more specific
#: patterns precede general ones.
_PATTERNS: list[tuple[str, PathClass]] = [
    ("**/evaluation_path.py", PathClass.INTEGRITY),
    ("**/test_evaluation_path.py", PathClass.INTEGRITY),
    ("CODEOWNERS", PathClass.OWNERSHIP),
    (".github/CODEOWNERS", PathClass.OWNERSHIP),
    ("**/branch-protection*.y*ml", PathClass.OWNERSHIP),
    # PIN patterns precede RULES: `standards-bundles/PINS.yaml` matches both,
    # and it is a pin (which version of the rules applies), not a rule.
    ("**/PINS.yaml", PathClass.PIN),
    ("**/requirements*.txt", PathClass.PIN),
    ("**/pnpm-lock.yaml", PathClass.PIN),
    ("**/uv.lock", PathClass.PIN),
    ("standards-bundles/**", PathClass.RULES),
    (".github/workflows/**", PathClass.WORKFLOW),
    (".github/actions/**", PathClass.ACTION),
    (".github/agents/**", PathClass.VERIFIER),
    ("**/bundle_rules.py", PathClass.VERIFIER),
    ("**/review_verdict.py", PathClass.VERIFIER),
    ("**/autonomy.py", PathClass.VERIFIER),
    ("**/merge_authorization.py", PathClass.VERIFIER),
    ("**/attestation.py", PathClass.VERIFIER),
    ("**/bundle_citation.py", PathClass.VERIFIER),
    ("**/teaching_signal.py", PathClass.VERIFIER),
    ("**/decision_record.py", PathClass.COLLECTOR),
    ("**/accuracy.py", PathClass.COLLECTOR),
    ("**/replay.py", PathClass.COLLECTOR),
    ("**/remediation_lifecycle.py", PathClass.COLLECTOR),
    ("**/telemetry_queries.py", PathClass.PUBLISHER),
    ("**/compliance_query.py", PathClass.PUBLISHER),
    ("**/deliver_github.py", PathClass.PUBLISHER),
]


def _matches(path: str, pattern: str) -> bool:
    if fnmatch.fnmatch(path, pattern):
        return True
    # `**/x` should also match a bare `x` at the repository root.
    if pattern.startswith("**/") and fnmatch.fnmatch(path, pattern[3:]):
        return True
    return False


def classify_path(path: str) -> Optional[PathClass]:
    """Return why `path` is governance-relevant, or None if it is ordinary code."""
    normalized = (path or "").strip()
    # NOT lstrip("./") — that strips characters, not a prefix, so
    # ".github/workflows/x.yml" would lose its leading dot and never match.
    while normalized.startswith("./"):
        normalized = normalized[2:]
    normalized = normalized.lstrip("/")
    for pattern, cls in _PATTERNS:
        if _matches(normalized, pattern):
            return cls
    return None


@dataclass(frozen=True)
class PathFinding:
    path: str
    path_class: PathClass
    detail: str


def classify_changes(paths: Iterable[str]) -> list[PathFinding]:
    """Classify a diff's changed paths against the evaluation path."""
    findings: list[PathFinding] = []
    for p in paths:
        cls = classify_path(p)
        if cls is None:
            continue
        findings.append(PathFinding(
            path=p,
            path_class=cls,
            detail=_DETAIL[cls],
        ))
    return findings


_DETAIL: dict[PathClass, str] = {
    PathClass.RULES: "changes a standards rule",
    PathClass.WORKFLOW: "changes what runs a gate; a gate that does not run cannot fail",
    PathClass.ACTION: "changes what a gate workflow executes",
    PathClass.VERIFIER: "changes how a rule is interpreted; an inverted comparison passes every patch",
    PathClass.COLLECTOR: "changes the evidence a gate reasons over; empty findings block nothing",
    PathClass.PUBLISHER: "changes how a verdict is reported; a check can be published green unconditionally",
    PathClass.PIN: "repoints a pinned version — a policy change wearing a dependency-bump costume",
    PathClass.INTEGRITY: "changes the integrity checker itself; a checker its subject can edit is decorative",
    PathClass.OWNERSHIP: "changes who may approve governance changes",
}


# --- workflow-level weakening ------------------------------------------------

class Weakening(str, Enum):
    CONTINUE_ON_ERROR = "continue_on_error"
    PATH_FILTER_NARROWED = "path_filter_narrowed"
    TRIGGER_REMOVED = "trigger_removed"
    STEP_REMOVED = "step_removed"
    FLOATING_REF = "floating_ref"
    PERMISSION_WIDENED = "permission_widened"


@dataclass(frozen=True)
class WeakeningFinding:
    kind: Weakening
    detail: str


_SHA_PIN = re.compile(r"^[0-9a-f]{40}$")


def detect_weakening(
    *,
    before: Optional[dict],
    after: Optional[dict],
) -> list[WeakeningFinding]:
    """Compare two parsed workflow definitions for governance-weakening edits.

    Only weakening is reported. Strengthening a gate is always permitted, which
    mirrors the PHI-lock rule in `bundle_rules`: controls may tighten freely and
    may only loosen through review.
    """
    out: list[WeakeningFinding] = []
    before = before or {}
    after = after or {}

    b_jobs = (before.get("jobs") or {})
    a_jobs = (after.get("jobs") or {})

    # continue-on-error turns a failing gate into a passing one.
    for job_name, job in a_jobs.items():
        for step in (job.get("steps") or []):
            if step.get("continue-on-error") is True:
                out.append(WeakeningFinding(
                    Weakening.CONTINUE_ON_ERROR,
                    f"job {job_name!r} step {step.get('name', '?')!r} has "
                    "continue-on-error: a failing gate would report success",
                ))
            uses = step.get("uses") or ""
            if uses and "@" in uses:
                ref = uses.split("@", 1)[1]
                if not _SHA_PIN.match(ref):
                    out.append(WeakeningFinding(
                        Weakening.FLOATING_REF,
                        f"job {job_name!r} uses {uses!r} at a floating ref; the "
                        "code a gate runs could change without a diff",
                    ))

    # A removed job or step is a removed gate.
    for job_name, job in b_jobs.items():
        if job_name not in a_jobs:
            out.append(WeakeningFinding(
                Weakening.STEP_REMOVED,
                f"job {job_name!r} was removed",
            ))
            continue
        b_steps = {s.get("name") for s in (job.get("steps") or []) if s.get("name")}
        a_steps = {s.get("name") for s in (a_jobs[job_name].get("steps") or []) if s.get("name")}
        for gone in sorted(b_steps - a_steps):
            out.append(WeakeningFinding(
                Weakening.STEP_REMOVED,
                f"job {job_name!r} step {gone!r} was removed",
            ))

    b_on = _normalize_on(before.get("on") or before.get(True))
    a_on = _normalize_on(after.get("on") or after.get(True))

    for trigger in sorted(set(b_on) - set(a_on)):
        out.append(WeakeningFinding(
            Weakening.TRIGGER_REMOVED,
            f"trigger {trigger!r} was removed; the gate no longer fires on it",
        ))

    # Path filters are policy, not performance tuning.
    for trigger in sorted(set(b_on) & set(a_on)):
        b_cfg = b_on.get(trigger) or {}
        a_cfg = a_on.get(trigger) or {}
        if not isinstance(b_cfg, dict) or not isinstance(a_cfg, dict):
            continue
        b_paths = set(b_cfg.get("paths") or [])
        a_paths = set(a_cfg.get("paths") or [])
        if not b_paths and a_paths:
            out.append(WeakeningFinding(
                Weakening.PATH_FILTER_NARROWED,
                f"trigger {trigger!r} gained a paths filter; the gate previously "
                "ran on every change and now runs on a subset",
            ))
        elif b_paths and a_paths and a_paths < b_paths:
            out.append(WeakeningFinding(
                Weakening.PATH_FILTER_NARROWED,
                f"trigger {trigger!r} paths filter narrowed from {len(b_paths)} "
                f"to {len(a_paths)} pattern(s)",
            ))
        b_ignore = set(b_cfg.get("paths-ignore") or [])
        a_ignore = set(a_cfg.get("paths-ignore") or [])
        if a_ignore > b_ignore:
            out.append(WeakeningFinding(
                Weakening.PATH_FILTER_NARROWED,
                f"trigger {trigger!r} paths-ignore widened; more changes now "
                "skip the gate entirely",
            ))

    # Widened token permissions.
    b_perm = before.get("permissions") or {}
    a_perm = after.get("permissions") or {}
    if isinstance(b_perm, dict) and isinstance(a_perm, dict):
        for scope, level in a_perm.items():
            if level == "write" and b_perm.get(scope) != "write":
                out.append(WeakeningFinding(
                    Weakening.PERMISSION_WIDENED,
                    f"permission {scope!r} widened to write",
                ))

    return out


def _normalize_on(on: object) -> dict:
    """`on:` may be a string, a list, or a mapping. Normalize to a mapping."""
    if isinstance(on, str):
        return {on: {}}
    if isinstance(on, list):
        return {k: {} for k in on}
    if isinstance(on, dict):
        return on
    return {}


# --- the combined decision ---------------------------------------------------

@dataclass(frozen=True)
class IntegrityVerdict:
    touches_evaluation_path: bool
    findings: tuple[PathFinding, ...]
    weakenings: tuple[WeakeningFinding, ...]
    required_reviewers: tuple[str, ...]
    detail: str


def evaluate_integrity(
    *,
    changed_paths: Sequence[str],
    workflow_before: Optional[dict] = None,
    workflow_after: Optional[dict] = None,
    governance_reviewers: Sequence[str] = ("governance",),
) -> IntegrityVerdict:
    """Decide whether a diff requires governance review of the evaluation path."""
    findings = tuple(classify_changes(changed_paths))
    weakenings = tuple(detect_weakening(before=workflow_before, after=workflow_after))
    touches = bool(findings or weakenings)

    if not touches:
        return IntegrityVerdict(
            touches_evaluation_path=False,
            findings=(),
            weakenings=(),
            required_reviewers=(),
            detail="no change to the path by which a rule becomes a verdict",
        )

    classes = sorted({f.path_class.value for f in findings})
    parts = []
    if classes:
        parts.append(f"touches {', '.join(classes)}")
    if weakenings:
        parts.append(f"{len(weakenings)} weakening signal(s)")

    return IntegrityVerdict(
        touches_evaluation_path=True,
        findings=findings,
        weakenings=weakenings,
        required_reviewers=tuple(governance_reviewers),
        detail=(
            f"governance review required — {'; '.join(parts)}. A rule is only as "
            "trustworthy as the machinery that evaluates it."
        ),
    )
