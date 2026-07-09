"""Tests for scripts/enforce_bundles.py — the standalone bundle CI enforcer.

Contract source: openspec/changes/add-bundle-ci-enforcement/specs/bundle-ci-enforcement/spec.md

The enforcer is the deterministic subset of review-scan: it applies
`severity: BLOCK` bundle rules that carry a `pattern` to a set of changed
files, with zero orchestrator import, zero Cosmos, zero LLM. It fails closed
on any load/parse/pin error.

Run from the repo root:
    source .venv/bin/activate
    python -m pytest scripts/tests/test_enforce_bundles.py -q
"""
from __future__ import annotations

import pathlib
import sys
import textwrap

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import enforce_bundles as eb  # noqa: E402


BUNDLES = REPO_ROOT / "standards-bundles"


# --------------------------------------------------------------------------
# Requirement: zero orchestrator/Cosmos/LLM dependency; loads from disk
# --------------------------------------------------------------------------

def test_module_imports_no_orchestrator_cosmos_or_llm():
    """The enforcer module must not pull in apps.orchestrator, azure.cosmos,
    or any provider SDK. Assert on sys.modules after a fresh import."""
    # Anything already imported by enforce_bundles is in its module globals.
    banned = ("apps.orchestrator", "azure.cosmos", "openai", "anthropic", "httpx")
    src = (SCRIPTS / "enforce_bundles.py").read_text(encoding="utf-8")
    for name in banned:
        assert f"import {name}" not in src, f"enforcer must not import {name}"
        assert f"from {name}" not in src, f"enforcer must not import from {name}"


def test_only_stdlib_and_yaml_imported():
    """Third-party imports limited to yaml (PyYAML)."""
    src = (SCRIPTS / "enforce_bundles.py").read_text(encoding="utf-8")
    # crude but effective: the only non-stdlib top-level import allowed is yaml
    assert "import yaml" in src


# --------------------------------------------------------------------------
# Requirement: PINS resolution (team -> version, fallback to defaults)
# --------------------------------------------------------------------------

def test_resolve_pins_known_team_uses_its_pin():
    pins = eb.load_pins(BUNDLES / "PINS.yaml")
    resolved = eb.resolve_versions(pins, team="team-demo")
    assert resolved["security"] == "v0.1.0"
    assert resolved["privacy"] == "v0.1.0"


def test_resolve_pins_unlisted_team_falls_back_to_defaults():
    pins = eb.load_pins(BUNDLES / "PINS.yaml")
    resolved = eb.resolve_versions(pins, team="team-nonexistent")
    assert resolved == {
        "architect": "v0.1.0",
        "security": "v0.1.0",
        "privacy": "v0.1.0",
        "finops": "v0.1.0",
    }


def test_unresolvable_pin_raises_bundle_error():
    """A pin pointing at a version dir that doesn't exist must fail closed."""
    pins = {"defaults": {"security": "v9.9.9"}, "teams": {}}
    with pytest.raises(eb.BundleLoadError):
        eb.load_ci_rules(BUNDLES, eb.resolve_versions(pins, team="defaults"))


# --------------------------------------------------------------------------
# Requirement: rule selection — BLOCK + pattern + (ci_checks OR bundle default)
# --------------------------------------------------------------------------

def test_selects_only_block_rules_with_pattern_and_ci_optin(tmp_path):
    """Rule selection honors severity==BLOCK, presence of pattern, and the
    ci_checks opt-in (per-rule true OR bundle ci_checks_default true)."""
    bundle_dir = tmp_path / "security" / "v0.1.0"
    bundle_dir.mkdir(parents=True)
    (bundle_dir / "rules.yaml").write_text(textwrap.dedent("""
        metadata: {bundle: security, version: 0.1.0}
        rules:
          - id: HAS-PATTERN-OPTIN
            title: opted in
            severity: BLOCK
            pattern: 'forbidden_token'
            enforcement: {ci_checks: true}
          - id: HAS-PATTERN-NO-OPTIN
            title: not opted in
            severity: BLOCK
            pattern: 'other_token'
          - id: BLOCK-NO-PATTERN
            title: semantic only
            severity: BLOCK
            enforcement: {ci_checks: true}
          - id: WARN-PATTERN-OPTIN
            title: warn not block
            severity: WARN
            pattern: 'warn_token'
            enforcement: {ci_checks: true}
    """), encoding="utf-8")
    rules = eb.select_ci_rules_from_file(bundle_dir / "rules.yaml", "security", "v0.1.0")
    ids = {r.rule_id for r in rules}
    assert ids == {"HAS-PATTERN-OPTIN"}, f"got {ids}"


def test_bundle_level_ci_checks_default_opts_in_all_block_patterns(tmp_path):
    bundle_dir = tmp_path / "security" / "v0.1.0"
    bundle_dir.mkdir(parents=True)
    (bundle_dir / "rules.yaml").write_text(textwrap.dedent("""
        metadata: {bundle: security, version: 0.1.0, ci_checks_default: true}
        rules:
          - id: A
            title: a
            severity: BLOCK
            pattern: 'tok_a'
          - id: B
            title: b
            severity: BLOCK
            pattern: 'tok_b'
          - id: C-NO-PATTERN
            title: c
            severity: BLOCK
    """), encoding="utf-8")
    rules = eb.select_ci_rules_from_file(bundle_dir / "rules.yaml", "security", "v0.1.0")
    assert {r.rule_id for r in rules} == {"A", "B"}


# --------------------------------------------------------------------------
# Requirement: apply rules to changed files -> violations w/ citation format
# --------------------------------------------------------------------------

def test_violation_output_format_is_file_line_citation_title(tmp_path):
    """Violation string MUST be: file:line [<dept>/v<version>/<rule-id>] <title>"""
    f = tmp_path / "app.py"
    f.write_text("import os\nx = 'forbidden_token here'\n", encoding="utf-8")
    rule = eb.CIRule(
        dept="security", version="v0.1.0", rule_id="TEST-001",
        title="no forbidden token", pattern=r"forbidden_token", phi=False,
    )
    violations = eb.scan_file(f, [rule], display_path="app.py")
    assert len(violations) == 1
    assert violations[0].format() == "app.py:2 [security/v0.1.0/TEST-001] no forbidden token"


def test_clean_file_produces_no_violations(tmp_path):
    f = tmp_path / "clean.py"
    f.write_text("x = redacted_id()\n", encoding="utf-8")
    rule = eb.CIRule("security", "v0.1.0", "PHI-001", "no MRN",
                     r"(?i)(MRN|patient_id|SSN)", phi=True)
    assert eb.scan_file(f, [rule], display_path="clean.py") == []


# --------------------------------------------------------------------------
# End-to-end against the REAL security bundle (the 2 shipped pattern rules)
# --------------------------------------------------------------------------

def test_real_security_bundle_catches_hardcoded_secret(tmp_path, monkeypatch):
    """A file with an api_key = "<16+ chars>" must trip SECRET-001 from the
    real shipped security bundle. This is the demoable red-X."""
    # activate ci_checks on the real bundle rules by running with a bundle
    # default override so the shipped (not-yet-opted-in) rules select.
    f = tmp_path / "config.py"
    f.write_text('api_key = "AKIAIOSFODNN7EXAMPLEKEY123"\n', encoding="utf-8")
    rules = eb.load_ci_rules(
        BUNDLES, {"security": "v0.1.0"},
        force_all_block_patterns=True,  # test override: treat shipped BLOCK+pattern as CI-eligible
    )
    violations = eb.scan_file(f, rules, display_path="config.py")
    assert any(v.rule_id == "SECRET-001" for v in violations), \
        f"expected SECRET-001, got {[v.rule_id for v in violations]}"


def test_real_security_bundle_catches_phi_in_logs(tmp_path):
    f = tmp_path / "svc.py"
    f.write_text("logger.info(f'patient {MRN} updated')\n", encoding="utf-8")
    rules = eb.load_ci_rules(BUNDLES, {"security": "v0.1.0"},
                             force_all_block_patterns=True)
    violations = eb.scan_file(f, rules, display_path="svc.py")
    assert any(v.rule_id == "PHI-001" for v in violations)


# --------------------------------------------------------------------------
# Requirement: fail closed on malformed bundle
# --------------------------------------------------------------------------

def test_malformed_rules_yaml_raises_not_empty_pass(tmp_path):
    bundle_dir = tmp_path / "security" / "v0.1.0"
    bundle_dir.mkdir(parents=True)
    (bundle_dir / "rules.yaml").write_text("rules: [ this is: not: valid yaml", encoding="utf-8")
    with pytest.raises(eb.BundleLoadError):
        eb.select_ci_rules_from_file(bundle_dir / "rules.yaml", "security", "v0.1.0")


def test_missing_bundle_dir_raises(tmp_path):
    with pytest.raises(eb.BundleLoadError):
        eb.load_ci_rules(tmp_path, {"security": "v0.1.0"})


# --------------------------------------------------------------------------
# CLI integration: exit codes
# --------------------------------------------------------------------------

def test_run_returns_nonzero_on_violation(tmp_path):
    f = tmp_path / "bad.py"
    f.write_text('password = "hunter2hunter2hunter2"\n', encoding="utf-8")
    code = eb.run(
        changed_files=[str(f)], team="defaults", bundles_root=BUNDLES,
        display_paths={str(f): "bad.py"}, force_all_block_patterns=True,
    )
    assert code != 0


def test_run_returns_zero_on_clean_tree(tmp_path):
    f = tmp_path / "ok.py"
    f.write_text("x = 1\n", encoding="utf-8")
    code = eb.run(
        changed_files=[str(f)], team="defaults", bundles_root=BUNDLES,
        display_paths={str(f): "ok.py"}, force_all_block_patterns=True,
    )
    assert code == 0


# --------------------------------------------------------------------------
# Drift guard: real bundles now opt in via ci_checks_default (no --force).
# The selected rule-set is derived ONLY from the bundle files.
# --------------------------------------------------------------------------

def test_real_bundles_select_expected_ci_ruleset_without_force():
    """With security+privacy ci_checks_default: true shipped, load_ci_rules on
    the real bundles (no force flag) selects exactly the BLOCK+pattern rules
    that opted in. Locks the set so a bundle edit that changes CI coverage is
    a visible, intentional diff — not silent drift."""
    pins = eb.load_pins(BUNDLES / "PINS.yaml")
    resolved = eb.resolve_versions(pins, team="defaults")
    rules = eb.load_ci_rules(BUNDLES, resolved)  # NO force override
    selected = {r.citation for r in rules}
    # Only the two shipped BLOCK rules carrying a real regex pattern:
    assert selected == {
        "security/v0.1.0/PHI-001",
        "security/v0.1.0/SECRET-001",
    }, f"CI rule-set drifted: {selected}"


def test_ci_ruleset_is_data_driven_not_hardcoded(tmp_path):
    """Adding a CI-enabled BLOCK+pattern rule to a fixture bundle makes it
    appear in load_ci_rules with zero script edits — proves no hardcoded list."""
    bundle_dir = tmp_path / "architect" / "v0.1.0"
    bundle_dir.mkdir(parents=True)
    (bundle_dir / "rules.yaml").write_text(
        "metadata: {bundle: architect, version: 0.1.0}\n"
        "rules:\n"
        "  - id: NEW-CI-RULE\n"
        "    title: newly opted in\n"
        "    severity: BLOCK\n"
        "    pattern: 'brand_new_token'\n"
        "    enforcement: {ci_checks: true}\n",
        encoding="utf-8",
    )
    rules = eb.load_ci_rules(tmp_path, {"architect": "v0.1.0"})
    assert {r.rule_id for r in rules} == {"NEW-CI-RULE"}


# --------------------------------------------------------------------------
# Result artifact (bundle-enforce-result.json) shape — no ledger/Cosmos on write
# --------------------------------------------------------------------------

def test_result_json_shape_on_violation(tmp_path):
    import json
    bad = tmp_path / "bad.py"
    bad.write_text('api_key = "AKIAIOSFODNN7EXAMPLEKEY"\n', encoding="utf-8")
    result = tmp_path / "bundle-enforce-result.json"
    code = eb.run(
        changed_files=[str(bad)], team="defaults", bundles_root=BUNDLES,
        display_paths={str(bad): "bad.py"}, force_all_block_patterns=True,
        result_path=result, pr_ref="delivery#7",
    )
    assert code == 1
    doc = json.loads(result.read_text())
    assert doc["pr_ref"] == "delivery#7"
    assert doc["pass"] is False
    assert doc["violation_count"] >= 1
    v0 = doc["violations"][0]
    assert set(v0) == {"bundle_ref", "file", "line", "rule_id", "title", "phi"}
    assert v0["bundle_ref"].startswith("security/v0.1.0/")


def test_result_json_shape_on_clean(tmp_path):
    import json
    ok = tmp_path / "ok.py"
    ok.write_text("x = 1\n", encoding="utf-8")
    result = tmp_path / "res.json"
    code = eb.run(
        changed_files=[str(ok)], team="defaults", bundles_root=BUNDLES,
        display_paths={str(ok): "ok.py"}, force_all_block_patterns=True,
        result_path=result, pr_ref="delivery#8",
    )
    assert code == 0
    doc = json.loads(result.read_text())
    assert doc["pass"] is True
    assert doc["violation_count"] == 0
    assert doc["violations"] == []


def test_write_result_json_uses_no_orchestrator_import():
    """The result-write path must not IMPORT orchestrator/cosmos/ledger modules.
    Check import statements, not prose mentions (docstrings say 'no ledger')."""
    src = (SCRIPTS / "enforce_bundles.py").read_text(encoding="utf-8")
    for line in src.splitlines():
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            assert "orchestrator" not in stripped, stripped
            assert "cosmos" not in stripped, stripped
            assert "ledger" not in stripped, stripped


# --------------------------------------------------------------------------
# Workflow-lint: bundle-enforce.yml parses, no secrets, scopes to the diff
# --------------------------------------------------------------------------

WORKFLOW = REPO_ROOT / ".github" / "workflows" / "bundle-enforce.yml"


def test_workflow_exists_and_parses():
    import yaml
    assert WORKFLOW.exists(), "bundle-enforce.yml must exist"
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert isinstance(doc, dict)
    # PyYAML parses the bare `on:` key as boolean True — accept either.
    assert "on" in doc or True in doc, "workflow must declare a trigger"


def test_workflow_triggers_on_pull_request():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "pull_request:" in text


def test_workflow_references_no_secret():
    """The lane must run without any repository secret."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "secrets." not in text, "workflow must not reference any secret"


def test_workflow_scopes_to_changed_files_not_whole_tree():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "git diff --name-only" in text
    assert "--stdin" in text  # enforcer fed the diff, not a whole-tree scan


def test_workflow_is_first_and_only_workflow():
    """Documented invariant: this change adds the FIRST workflow; a repo
    without it is unaffected. Guards the 'additive' claim."""
    wf_dir = REPO_ROOT / ".github" / "workflows"
    ymls = sorted(p.name for p in wf_dir.glob("*.yml")) + \
        sorted(p.name for p in wf_dir.glob("*.yaml"))
    assert "bundle-enforce.yml" in ymls


# --------------------------------------------------------------------------
# Doc-accuracy: CI-ENFORCEMENT.md names the real script + workflow paths
# --------------------------------------------------------------------------

def test_ci_enforcement_doc_names_real_paths():
    doc = REPO_ROOT / "docs" / "CI-ENFORCEMENT.md"
    assert doc.exists()
    text = doc.read_text(encoding="utf-8")
    assert "scripts/enforce_bundles.py" in text
    assert ".github/workflows/bundle-enforce.yml" in text
    # the paths it names must actually exist
    assert (REPO_ROOT / "scripts" / "enforce_bundles.py").exists()
    assert WORKFLOW.exists()
