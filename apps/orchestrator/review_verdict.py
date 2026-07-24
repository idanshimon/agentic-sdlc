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


def _static_runnability_blockers(code_files: dict[str, str]) -> "list[Blocker]":
    """Catch generated code that will not even import/run: syntax errors and
    use-before-definition of any name at module scope (e.g. `TestClient(app)`
    with no `from fastapi.testclient import TestClient`, or `time.time()` with no
    `import time`). This is a governance guarantee that delivered code at least
    parses and has its module-level names resolvable — the difference between
    'plausible-looking' and 'actually runnable'. Deterministic, stdlib-only
    (ast + symtable), so it runs identically in the pipeline and CI.

    Detection is scoped to MODULE-level references (import-time NameErrors), the
    class of defect that breaks a delivered file on `import`/collection. It uses
    Python's own symbol table so it generalizes to any undefined name (third
    party like TestClient, stdlib like time, or a typo) rather than a hand
    allowlist. Builtins are excluded; nested function/class scopes are not
    flagged (their free vars may legitimately resolve to module globals or
    late-bound names).
    """
    import ast
    import builtins
    import symtable

    _BUILTINS = set(dir(builtins)) | {
        "__name__", "__file__", "__doc__", "__package__", "__loader__",
        "__spec__", "__builtins__", "__annotations__", "__dict__",
    }

    blockers: list[Blocker] = []
    for path, content in code_files.items():
        if not path.endswith(".py"):
            continue
        # 1. Syntax must parse (and compile, catching a wider error class).
        try:
            tree = ast.parse(content, filename=path)
        except SyntaxError as exc:
            blockers.append(Blocker(
                check="static-runnability", rule="runnability/v0.1.0/SYNTAX-001",
                detail=f"file does not parse: {exc.msg}",
                file=path, line=exc.lineno or 1, phi=False,
            ))
            continue
        try:
            table = symtable.symtable(content, path, "exec")
        except (SyntaxError, ValueError):
            continue

        # 2. Module-scope names that are referenced but never bound anywhere in
        #    module scope (not imported, assigned, def/class'd, or global'd) and
        #    are not builtins → they will NameError at import time.
        module_defined: set[str] = set()
        module_referenced: set[str] = set()
        for sym in table.get_symbols():
            if sym.is_assigned() or sym.is_imported() or sym.is_parameter():
                module_defined.add(sym.get_name())
            # namespaces (def/class) bind their own name in the module scope
            if sym.is_namespace():
                module_defined.add(sym.get_name())
            if sym.is_referenced():
                module_referenced.add(sym.get_name())

        undefined = {
            n for n in module_referenced
            if n not in module_defined and n not in _BUILTINS
        }

        # 3. Map each undefined name to the first line it's used on a MODULE-level
        #    statement (an import-time NameError), for a precise, actionable
        #    blocker. Only flag names actually used at module top level.
        module_level_names: dict[str, int] = {}
        for node in tree.body:  # top-level statements only
            for sub in ast.walk(node):
                if (isinstance(sub, ast.Name)
                        and isinstance(sub.ctx, ast.Load)
                        and sub.id in undefined
                        and sub.id not in module_level_names):
                    module_level_names[sub.id] = getattr(sub, "lineno", 1)

        for name, line in sorted(module_level_names.items(), key=lambda kv: kv[1]):
            blockers.append(Blocker(
                check="static-runnability",
                rule="runnability/v0.1.0/IMPORT-001",
                detail=f"name `{name}` is used at module scope but never defined "
                       f"or imported (NameError at import time)",
                file=path, line=line, phi=False,
            ))

        # 4. Function/method bodies: a name that resolves to a module GLOBAL
        #    (free var with no local binding) but is never defined at module
        #    scope and isn't a builtin → NameError when that function runs
        #    (e.g. `time.time()` inside a test with no top-level `import time`).
        #    Walk nested scopes via symtable so comprehensions/args/locals are
        #    correctly excluded.
        def _walk_scopes(tbl):
            for child in tbl.get_children():
                yield child
                yield from _walk_scopes(child)

        fn_undefined: dict[str, int] = {}
        for scope in _walk_scopes(table):
            if scope.get_type() != "function":
                continue
            for sym in scope.get_symbols():
                nm = sym.get_name()
                if (sym.is_global()
                        and sym.is_referenced()
                        and not sym.is_assigned()
                        and nm not in module_defined
                        and nm not in _BUILTINS
                        and nm not in fn_undefined):
                    fn_undefined[nm] = 0  # line filled from the AST below

        if fn_undefined:
            for node in ast.walk(tree):
                if (isinstance(node, ast.Name)
                        and isinstance(node.ctx, ast.Load)
                        and node.id in fn_undefined
                        and fn_undefined[node.id] == 0):
                    fn_undefined[node.id] = getattr(node, "lineno", 1)
            for name, line in sorted(fn_undefined.items(), key=lambda kv: kv[1]):
                blockers.append(Blocker(
                    check="static-runnability",
                    rule="runnability/v0.1.0/IMPORT-001",
                    detail=f"name `{name}` is used in a function but never defined "
                           f"or imported at module scope (NameError at call time)",
                    file=path, line=line or 1, phi=False,
                ))
    return blockers


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
    pipeline review agree on exactly the same rule-set and matcher. Also runs a
    static runnability check (syntax + use-before-import) so unrunnable
    generated code is a first-class blocker, not something a team discovers on
    checkout.
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

    # Static runnability: syntax + use-before-import (does the code actually run?)
    blockers.extend(_static_runnability_blockers(code_files))

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
