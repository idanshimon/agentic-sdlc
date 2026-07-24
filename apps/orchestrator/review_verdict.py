"""review_verdict — the real review-scan verdict (replaces the findings=0 stub).

This is the load-bearing input of the autonomous review loop
(openspec/changes/add-autonomous-review-loop, task 0.0). It reuses the PR-1
deterministic matcher (scripts/enforce_bundles.py) over the generated code and
emits a structured, chainable `ReviewVerdict` — NOT a hardcoded pass.

Dependency direction: this module reaches DOWN to the standalone enforcer, not
the other way around. The enforcer stays orchestrator-free (that is its whole
point — it must run in CI with zero orchestrator import); the orchestrator is
allowed to consume it.
"""
from __future__ import annotations

import pathlib
import sys
from typing import AsyncIterator, Optional

from .models import Blocker, ReviewVerdict, RunState, Stage, StageEvent

# Make scripts/enforce_bundles.py importable (repo_root/scripts).
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import enforce_bundles as eb  # noqa: E402

_BUNDLES_ROOT = _REPO_ROOT / "standards-bundles"

# Map a bundle department to a human-readable check name for the verdict.
_CHECK_BY_DEPT = {
    "security": "security-scan",
    "privacy": "privacy-scan",
    "architect": "architecture-scan",
    "finops": "finops-scan",
}


def _now_ref(run_id: str, attempt: int) -> str:
    return f"verdict-{run_id[:8]}-{attempt}"


def build_review_verdict(
    code_files: dict[str, str],
    *,
    team: str = "defaults",
    attempt: int = 1,
    prior_verdict_ref: Optional[str] = None,
) -> ReviewVerdict:
    """Run the deterministic BLOCK+pattern rules over `code_files` and return a
    structured verdict. `code_files` maps a display path -> file content.

    Reuses enforce_bundles.load_ci_rules + scan_file so the CI lane and the
    pipeline review agree on exactly the same rule-set and matcher.
    """
    pins = eb.load_pins(_BUNDLES_ROOT / "PINS.yaml")
    resolved = eb.resolve_versions(pins, team)
    rules = eb.load_ci_rules(_BUNDLES_ROOT, resolved)

    blockers: list[Blocker] = []
    for display_path, content in code_files.items():
        # Scan the text directly by writing to an in-memory-ish temp path.
        for viol in _scan_text(content, rules, display_path):
            dept = viol.citation.split("/", 1)[0]
            blockers.append(Blocker(
                check=_CHECK_BY_DEPT.get(dept, f"{dept}-scan"),
                rule=viol.citation,
                detail=viol.title,
                file=viol.display_path,
                line=viol.line,
                phi=viol.phi,
            ))

    status = "FAIL" if blockers else "PASS"
    return ReviewVerdict(
        status=status,
        blockers=blockers,
        attempt=attempt,
        prior_verdict_ref=prior_verdict_ref,
    )


def _scan_text(content: str, rules, display_path: str):
    """Apply enforce_bundles rules to raw text (no temp file needed).

    Uses the same context-scoped matcher as the CI lane (CIRule.matches_line),
    so pipeline review and CI agree on exactly which lines violate — including
    context_pattern / safe_wrapper_pattern semantics (e.g. PHI-001 fires only on
    cleartext logging, not legitimate field/param usage)."""
    compiled = [
        (r, r.compiled(), r.compiled_context(), r.compiled_safe_wrapper())
        for r in rules
    ]
    out = []
    for lineno, line in enumerate(content.splitlines(), start=1):
        for rule, rx, ctx, safe in compiled:
            if rule.matches_line(line, _rx=rx, _ctx=ctx, _safe=safe):
                out.append(eb.Violation(
                    display_path=display_path, line=lineno,
                    rule_id=rule.rule_id, citation=rule.citation,
                    title=rule.title, phi=rule.phi,
                ))
    return out


def _generated_code_from_run(run: RunState) -> dict[str, str]:
    """Pull the generated code artifacts a codegen event emitted into the run.

    Codegen emits `app_code` (impl) and `test_code`; older shape used `code`.
    We scan the impl + tests as the reviewed change.
    """
    files: dict[str, str] = {}
    for ev in run.events:
        p = ev.payload or {}
        if p.get("app_code"):
            files["src/main.py"] = str(p["app_code"])
        elif p.get("code"):
            files["src/main.py"] = str(p["code"])
        if p.get("test_code"):
            files["tests/test_main.py"] = str(p["test_code"])
    return files


def _ev(run: RunState, status: str, msg: str, **payload) -> StageEvent:
    return StageEvent(
        run_id=run.run_id, stage=Stage.REVIEW_SCAN, status=status,
        message=msg, payload=payload,
    )


async def run_review_scan(
    run: RunState,
    *,
    attempt: int = 1,
    prior_verdict_ref: Optional[str] = None,
) -> AsyncIterator[StageEvent]:
    """Gate 3 — real policy/static scan over the generated code (fail-hard).

    Replaces the old `findings = 0  # demo: stubbed clean` stub. Emits a
    `started` event, then a terminal `completed`(PASS) or `failed`(FAIL) event
    carrying the full `ReviewVerdict` in the payload.
    """
    yield _ev(run, "started", "Running bundle BLOCK-rule scan over generated code")

    code_files = _generated_code_from_run(run)
    # Pin the complete delivery file set, not only the subset scanned by the
    # deterministic rule matcher, so review→delivery byte equality is enforceable.
    from ._pipeline_stages import _artifact_manifest, _delivery_files
    run.reviewed_artifact_manifest = _artifact_manifest(_delivery_files(run))
    verdict = build_review_verdict(
        code_files, team=run.team_id or "defaults",
        attempt=attempt, prior_verdict_ref=prior_verdict_ref,
    )

    if verdict.status == "FAIL":
        cited = ", ".join(sorted({b.rule for b in verdict.blockers}))
        yield _ev(
            run, "failed",
            f"Policy gate FAILED — {len(verdict.blockers)} blocker(s): {cited}",
            findings=len(verdict.blockers),
            verdict=verdict.model_dump(),
        )
    else:
        yield _ev(
            run, "completed", "Policy gate passed (0 BLOCK violations)",
            findings=0, verdict=verdict.model_dump(),
        )
