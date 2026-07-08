#!/usr/bin/env python3
"""enforce_bundles.py — standalone GitHub-native bundle enforcer (ci_checks lane).

The deterministic subset of the `review-scan` agent: it applies
`severity: BLOCK` bundle rules that carry a machine-checkable `pattern` to a
set of changed files and fails closed. It is the third enforcement surface
(alongside `pipeline_stages` and `ide_hooks`) — the one that fires on ANY pull
request, including a cloud Coding Agent's PR that never runs the orchestrator.

Design invariants (see openspec/changes/add-bundle-ci-enforcement):
  * ZERO orchestrator import, ZERO Cosmos, ZERO LLM. stdlib + PyYAML only.
  * Loads rules straight from `standards-bundles/**` honoring `PINS.yaml`.
  * Fails CLOSED: a missing dir / parse error / unresolvable pin exits non-zero;
    it is NEVER treated as an empty rule set that passes.
  * A rule runs in CI iff: severity == BLOCK AND it has a `pattern` AND
    (its enforcement.ci_checks is true OR its bundle sets ci_checks_default).

Usage:
    python scripts/enforce_bundles.py --team defaults FILE [FILE ...]
    git diff --name-only origin/main... | python scripts/enforce_bundles.py --team defaults --stdin

Exit 0 = clean. Exit 1 = at least one BLOCK rule matched. Exit 2 = load error.
"""
from __future__ import annotations

import argparse
import dataclasses
import pathlib
import re
import sys
from typing import Iterable, Optional

import yaml

DEPARTMENTS = ("architect", "security", "privacy", "finops")


class BundleLoadError(Exception):
    """Raised when a bundle cannot be loaded/parsed or a pin is unresolvable.

    The CLI maps this to exit code 2 — a load failure must fail the check, never
    silently pass as an empty rule set.
    """


@dataclasses.dataclass(frozen=True)
class CIRule:
    """A single CI-enforceable rule: a compiled regex + its bundle citation."""
    dept: str
    version: str
    rule_id: str
    title: str
    pattern: str
    phi: bool = False

    @property
    def citation(self) -> str:
        return f"{self.dept}/{self.version}/{self.rule_id}"

    def compiled(self) -> "re.Pattern[str]":
        try:
            return re.compile(self.pattern)
        except re.error as exc:  # a bad regex in a bundle is a load failure
            raise BundleLoadError(
                f"rule {self.citation} has an invalid pattern: {exc}"
            ) from exc


@dataclasses.dataclass(frozen=True)
class Violation:
    display_path: str
    line: int
    rule_id: str
    citation: str
    title: str
    phi: bool = False

    def format(self) -> str:
        return f"{self.display_path}:{self.line} [{self.citation}] {self.title}"


# ---------------------------------------------------------------------------
# PINS resolution
# ---------------------------------------------------------------------------

def load_pins(pins_path: pathlib.Path) -> dict:
    if not pins_path.exists():
        raise BundleLoadError(f"PINS.yaml not found at {pins_path}")
    try:
        data = yaml.safe_load(pins_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise BundleLoadError(f"PINS.yaml failed to parse: {exc}") from exc
    if not isinstance(data, dict) or "defaults" not in data:
        raise BundleLoadError("PINS.yaml missing required `defaults` block")
    return data


def resolve_versions(pins: dict, team: str) -> dict[str, str]:
    """team -> {dept: version}. Unlisted team falls back to `defaults`."""
    defaults = dict(pins.get("defaults") or {})
    teams = pins.get("teams") or {}
    resolved = dict(defaults)
    if team in teams and isinstance(teams[team], dict):
        resolved.update(teams[team])
    return resolved


# ---------------------------------------------------------------------------
# Rule loading + selection
# ---------------------------------------------------------------------------

def _is_ci_eligible(rule: dict, bundle_default: bool) -> bool:
    if rule.get("severity") != "BLOCK":
        return False
    if not rule.get("pattern"):
        return False
    enforcement = rule.get("enforcement") or {}
    opted_in = bool(enforcement.get("ci_checks", False))
    return opted_in or bundle_default


def select_ci_rules_from_file(
    rules_path: pathlib.Path,
    dept: str,
    version: str,
    *,
    force_all_block_patterns: bool = False,
) -> list[CIRule]:
    """Parse one rules.yaml and return the CI-eligible rules.

    `force_all_block_patterns` is a controlled override (used by the shipped
    reference bundles that predate the ci_checks key, and by tests): treat any
    BLOCK+pattern rule as CI-eligible regardless of the opt-in flag.
    """
    if not rules_path.exists():
        raise BundleLoadError(f"rules.yaml not found: {rules_path}")
    try:
        doc = yaml.safe_load(rules_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise BundleLoadError(f"{rules_path} failed to parse: {exc}") from exc
    if not isinstance(doc, dict):
        raise BundleLoadError(f"{rules_path} is not a mapping")
    meta = doc.get("metadata") or {}
    bundle_default = bool(meta.get("ci_checks_default", False)) or force_all_block_patterns
    out: list[CIRule] = []
    for rule in doc.get("rules") or []:
        if not isinstance(rule, dict):
            raise BundleLoadError(f"{rules_path}: a rule is not a mapping")
        if not _is_ci_eligible(rule, bundle_default):
            continue
        out.append(CIRule(
            dept=dept, version=version,
            rule_id=str(rule["id"]), title=str(rule.get("title", rule["id"])),
            pattern=str(rule["pattern"]), phi=bool(rule.get("phi", False)),
        ))
    return out


def load_ci_rules(
    bundles_root: pathlib.Path,
    resolved_versions: dict[str, str],
    *,
    force_all_block_patterns: bool = False,
) -> list[CIRule]:
    """Load CI-eligible rules for every resolved (dept, version). Fails closed."""
    rules: list[CIRule] = []
    for dept, version in resolved_versions.items():
        bundle_dir = bundles_root / dept / version
        if not bundle_dir.is_dir():
            raise BundleLoadError(
                f"unresolvable pin: {dept} -> {version} "
                f"(no directory {bundle_dir})"
            )
        rules.extend(select_ci_rules_from_file(
            bundle_dir / "rules.yaml", dept, version,
            force_all_block_patterns=force_all_block_patterns,
        ))
    return rules


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------

_TEXT_SUFFIXES = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rb", ".cs",
    ".yaml", ".yml", ".json", ".sql", ".sh", ".env", ".txt", ".md",
    ".tf", ".bicep", ".cfg", ".ini", ".toml", ".xml", ".html",
}


def _looks_textual(path: pathlib.Path) -> bool:
    if path.suffix.lower() in _TEXT_SUFFIXES:
        return True
    return path.suffix == ""  # extensionless (Dockerfile, Makefile) — try it


def scan_file(
    path: pathlib.Path,
    rules: Iterable[CIRule],
    *,
    display_path: Optional[str] = None,
) -> list[Violation]:
    """Apply every rule's regex to each line of `path`. Returns violations."""
    disp = display_path if display_path is not None else str(path)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeError):
        # An unreadable changed file is a finding, not a silent pass.
        return [Violation(disp, 0, "READ-ERROR", "enforcer/read", f"could not read {disp}")]
    compiled = [(r, r.compiled()) for r in rules]
    violations: list[Violation] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for rule, rx in compiled:
            if rx.search(line):
                violations.append(Violation(
                    display_path=disp, line=lineno, rule_id=rule.rule_id,
                    citation=rule.citation, title=rule.title, phi=rule.phi,
                ))
    return violations


# ---------------------------------------------------------------------------
# Orchestration / CLI
# ---------------------------------------------------------------------------

def write_result_json(
    path: pathlib.Path,
    *,
    pr_ref: str,
    violations: list["Violation"],
) -> None:
    """Write a legible result artifact. Pure stdlib json — no ledger, no Cosmos.

    Shape: {pr_ref, pass, violation_count, violations:[{bundle_ref,file,line,title,phi}]}
    """
    import json  # local import keeps the module's top-level dep surface minimal
    payload = {
        "pr_ref": pr_ref,
        "pass": len(violations) == 0,
        "violation_count": len(violations),
        "violations": [
            {
                "bundle_ref": v.citation,
                "file": v.display_path,
                "line": v.line,
                "rule_id": v.rule_id,
                "title": v.title,
                "phi": v.phi,
            }
            for v in violations
        ],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def run(
    changed_files: list[str],
    team: str,
    bundles_root: pathlib.Path,
    *,
    display_paths: Optional[dict[str, str]] = None,
    force_all_block_patterns: bool = False,
    result_path: Optional[pathlib.Path] = None,
    pr_ref: str = "",
    out=sys.stdout,
    err=sys.stderr,
) -> int:
    """Load rules, scan the changed files, print violations. Returns exit code.

    0 = clean, 1 = violations found, 2 = load error (fail closed).
    """
    display_paths = display_paths or {}
    try:
        pins = load_pins(bundles_root / "PINS.yaml")
        resolved = resolve_versions(pins, team)
        rules = load_ci_rules(
            bundles_root, resolved,
            force_all_block_patterns=force_all_block_patterns,
        )
    except BundleLoadError as exc:
        print(f"::error::bundle enforcement failed to load: {exc}", file=err)
        return 2

    if not rules:
        # No CI-eligible rules is a legitimate clean state ONLY when load
        # succeeded. It is logged so an all-empty config is visible, not silent.
        print("bundle-enforce: no CI-eligible rules selected (0 violations possible)", file=err)

    all_violations: list[Violation] = []
    for cf in changed_files:
        p = pathlib.Path(cf)
        if not p.exists() or not _looks_textual(p):
            continue
        disp = display_paths.get(cf, cf)
        all_violations.extend(scan_file(p, rules, display_path=disp))

    for v in all_violations:
        # GitHub Actions annotation + human-readable citation on one line.
        print(f"::error file={v.display_path},line={v.line}::{v.format()}", file=out)

    if result_path is not None:
        write_result_json(result_path, pr_ref=pr_ref, violations=all_violations)

    if all_violations:
        print(f"\nbundle-enforce: {len(all_violations)} BLOCK violation(s) — "
              f"merge must not proceed.", file=err)
        return 1
    return 0


def _read_stdin_files() -> list[str]:
    return [ln.strip() for ln in sys.stdin.read().splitlines() if ln.strip()]


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Bundle CI enforcer (ci_checks lane)")
    ap.add_argument("files", nargs="*", help="changed files to scan")
    ap.add_argument("--team", default="defaults",
                    help="team id for PINS resolution (default: defaults)")
    ap.add_argument("--stdin", action="store_true",
                    help="read newline-delimited changed files from stdin")
    ap.add_argument("--bundles-root", default=None,
                    help="path to standards-bundles/ (default: repo-relative)")
    ap.add_argument("--force-all-block-patterns", action="store_true",
                    help="treat every BLOCK+pattern rule as CI-eligible "
                         "(for reference bundles predating the ci_checks key)")
    ap.add_argument("--result-json", default=None,
                    help="write a bundle-enforce-result.json artifact to this path")
    ap.add_argument("--pr-ref", default="",
                    help="PR reference recorded in the result artifact")
    args = ap.parse_args(argv)

    if args.bundles_root:
        bundles_root = pathlib.Path(args.bundles_root)
    else:
        bundles_root = pathlib.Path(__file__).resolve().parents[1] / "standards-bundles"

    files = list(args.files)
    if args.stdin:
        files.extend(_read_stdin_files())

    return run(
        changed_files=files, team=args.team, bundles_root=bundles_root,
        force_all_block_patterns=args.force_all_block_patterns,
        result_path=pathlib.Path(args.result_json) if args.result_json else None,
        pr_ref=args.pr_ref,
    )


if __name__ == "__main__":
    raise SystemExit(main())
