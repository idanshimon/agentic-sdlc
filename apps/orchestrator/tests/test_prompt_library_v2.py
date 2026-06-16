"""Phase 2 backend resolver tests.

Covers openspec spec ADDED Requirements:
  1. YAML storage shape + frontmatter validation
  2. Inheritance walk (team → persona → global)
  3. Ledger entry chain shape
  4. Legacy entry render path (in test_legacy_entry_render, separate file)
  5. PromptCatalog.get_prompts_owned_by
  6. PromptCatalog.get_versions
  7. Image-bake contract (verified by Phase 7 integration, not here)
  8. Published prompts are immutable (enforced by CI/GitHub Action, not loader)

Also covers Phase 2.5 migration regression: byte-identical templates
between YAML files and the existing dataclass strings.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from orchestrator.prompt_library_v2 import (
    PromptCatalog,
    PromptFile,
    PromptValidationError,
    ResolveResult,
    load_prompts,
)


# ---------------------------------------------------------------------------
# 2.5 — Migration regression: YAML files match dataclass strings byte-exact
# ---------------------------------------------------------------------------

def test_migrated_yaml_matches_dataclass_strings():
    """The 6 YAML files under prompts/global/ MUST contain the exact same
    template strings as the constants in prompt_library.py. Drift here is
    a silent change to model behavior — caught at unit-test time."""
    from orchestrator import prompt_library
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    base = repo_root / "prompts" / "global"
    pairs = [
        ("ingest",      prompt_library.INGEST_PROMPT),
        ("assessor",    prompt_library.ASSESSOR_PROMPT),
        ("architect",   prompt_library.ARCHITECT_PROMPT),
        ("test_plan",   prompt_library.TEST_PLAN_PROMPT),
        ("codegen",     prompt_library.CODEGEN_PROMPT),
        ("review_scan", prompt_library.REVIEW_SCAN_PROMPT),
    ]
    for stage, expected in pairs:
        yaml_path = base / stage / "v1.yaml"
        assert yaml_path.exists(), f"missing YAML for {stage} at {yaml_path}"
        doc = yaml.safe_load(yaml_path.read_text())
        assert doc["template"] == expected, (
            f"DRIFT for stage={stage}: YAML template doesn't match "
            f"prompt_library.{stage.upper()}_PROMPT. "
            f"YAML first 80 = {doc['template'][:80]!r}; "
            f"dataclass first 80 = {expected[:80]!r}"
        )


# ---------------------------------------------------------------------------
# 2.6 — Loader validates frontmatter + path/scope consistency
# ---------------------------------------------------------------------------

def _write_prompt(path: Path, **overrides) -> None:
    """Helper: write a valid YAML prompt with optional field overrides."""
    base = {
        "prompt_id": "assessor-global",
        "version": "v1",
        "status": "published",
        "scope": "global",
        "owner_persona": "pm",
        "stage": "assessor",
        "model_compat_notes": "Test fixture",
        "effective_from": "2026-06-16T00:00:00Z",
        "superseded_by": None,
        "git_sha": "test123",
        "authored_by": "test@hermes",
        "reason": "fixture",
        "template": "Test prompt body",
    }
    base.update(overrides)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(base, sort_keys=False))


def test_loader_loads_valid_global_prompts(tmp_path):
    """A well-formed prompts/global/<stage>/v1.yaml loads cleanly."""
    _write_prompt(tmp_path / "global" / "assessor" / "v1.yaml")
    catalog = load_prompts(tmp_path)
    versions = catalog.get_versions("assessor", "global")
    assert len(versions) == 1
    assert versions[0].prompt_id == "assessor-global"
    assert versions[0].version == "v1"


def test_loader_fails_on_missing_required_field(tmp_path):
    """openspec spec Requirement 1, scenario 2: missing required field aborts."""
    _write_prompt(tmp_path / "global" / "assessor" / "v1.yaml")
    # Now corrupt it
    bad = yaml.safe_load((tmp_path / "global" / "assessor" / "v1.yaml").read_text())
    del bad["owner_persona"]
    (tmp_path / "global" / "assessor" / "v1.yaml").write_text(yaml.safe_dump(bad))
    with pytest.raises(PromptValidationError, match="validation failed"):
        load_prompts(tmp_path)


def test_loader_fails_on_path_scope_mismatch(tmp_path):
    """A file under global/ that claims scope=team is rejected — paths
    and frontmatter must agree."""
    _write_prompt(
        tmp_path / "global" / "assessor" / "v1.yaml",
        scope="team",  # mismatch with /global/ path
    )
    with pytest.raises(PromptValidationError, match="contradicts path-implied scope"):
        load_prompts(tmp_path)


def test_loader_fails_on_empty_directory(tmp_path):
    """Empty prompts/ aborts startup — fail-fast over silent fallback."""
    (tmp_path / "global").mkdir()
    with pytest.raises(PromptValidationError, match="empty"):
        load_prompts(tmp_path)


def test_loader_fails_on_missing_root(tmp_path):
    """Missing prompts/ aborts startup."""
    missing = tmp_path / "does_not_exist"
    with pytest.raises(PromptValidationError, match="does not exist"):
        load_prompts(missing)


# ---------------------------------------------------------------------------
# 2.7 — Resolver inheritance walk
# ---------------------------------------------------------------------------

def test_resolve_global_only(tmp_path):
    """Only global exists → resolve returns global with chain=[team:no, persona:no, global:yes]"""
    _write_prompt(tmp_path / "global" / "assessor" / "v1.yaml", template="GLOBAL")
    catalog = load_prompts(tmp_path)
    result = catalog.resolve(stage="assessor", model="claude-sonnet", team="cardiology")
    assert result.template == "GLOBAL"
    assert [(s.scope, s.matched) for s in result.chain] == [
        ("team", False), ("persona", False), ("global", True),
    ]
    assert result.matched_step.scope == "global"


def test_resolve_team_overrides_global(tmp_path):
    """openspec spec scenario: team override beats global."""
    _write_prompt(tmp_path / "global" / "assessor" / "v1.yaml", template="GLOBAL")
    _write_prompt(
        tmp_path / "team" / "cardiology" / "assessor" / "v1.yaml",
        scope="team", template="CARDIOLOGY",
        prompt_id="assessor-team-cardiology",
    )
    catalog = load_prompts(tmp_path)
    result = catalog.resolve(stage="assessor", model="claude-sonnet", team="cardiology")
    assert result.template == "CARDIOLOGY"
    chain = [(s.scope, s.matched) for s in result.chain]
    assert chain[0] == ("team", True)
    # The other two should be in the chain marked not-matched but with
    # "skipped" reasoning (we don't bother looking at them once team wins)
    assert chain[1][1] is False
    assert chain[2][1] is False


def test_resolve_missing_team_falls_through_to_global(tmp_path):
    """openspec spec scenario: missing team override falls through to global."""
    _write_prompt(tmp_path / "global" / "assessor" / "v1.yaml", template="GLOBAL")
    catalog = load_prompts(tmp_path)
    result = catalog.resolve(stage="assessor", model="claude-sonnet", team="finance")
    assert result.template == "GLOBAL"
    assert result.matched_step.scope == "global"


def test_resolve_persona_overrides_global_when_no_team(tmp_path):
    """If no team but persona has an override, persona wins."""
    _write_prompt(tmp_path / "global" / "assessor" / "v1.yaml", template="GLOBAL")
    _write_prompt(
        tmp_path / "persona" / "pm" / "assessor" / "v1.yaml",
        scope="persona", template="PERSONA-PM",
        prompt_id="assessor-persona-pm",
    )
    catalog = load_prompts(tmp_path)
    result = catalog.resolve(stage="assessor", model="claude-sonnet", team=None)
    assert result.template == "PERSONA-PM"
    assert result.matched_step.scope == "persona"


def test_resolve_full_3level_hierarchy(tmp_path):
    """All three scopes exist → team wins, chain reflects what was considered."""
    _write_prompt(tmp_path / "global" / "assessor" / "v1.yaml", template="GLOBAL")
    _write_prompt(
        tmp_path / "persona" / "pm" / "assessor" / "v1.yaml",
        scope="persona", template="PERSONA",
        prompt_id="assessor-persona-pm",
    )
    _write_prompt(
        tmp_path / "team" / "cardiology" / "assessor" / "v1.yaml",
        scope="team", template="TEAM",
        prompt_id="assessor-team-cardiology",
    )
    catalog = load_prompts(tmp_path)
    result = catalog.resolve(stage="assessor", model="claude-sonnet", team="cardiology")
    assert result.template == "TEAM"
    assert result.matched_step.scope == "team"


def test_resolve_raises_on_missing_global(tmp_path):
    """If no prompt exists at any scope, resolve raises — orchestrator
    refuses to silent-fallback to a hardcoded default. The error tells
    operators exactly which stage is missing."""
    _write_prompt(
        tmp_path / "global" / "ingest" / "v1.yaml",
        stage="ingest", prompt_id="ingest-global",
    )  # different stage from the one we ask for
    catalog = load_prompts(tmp_path)
    with pytest.raises(PromptValidationError, match="no published prompt found"):
        catalog.resolve(stage="assessor", model="claude-sonnet")


# ---------------------------------------------------------------------------
# Catalog query API (Requirements 5, 6)
# ---------------------------------------------------------------------------

def test_get_prompts_owned_by(tmp_path):
    """Filter by persona: openspec spec Requirement 5 scenario."""
    _write_prompt(tmp_path / "global" / "ingest" / "v1.yaml",
                  owner_persona="pm", stage="ingest", prompt_id="ingest-global")
    _write_prompt(tmp_path / "global" / "assessor" / "v1.yaml",
                  owner_persona="pm", stage="assessor", prompt_id="assessor-global")
    _write_prompt(tmp_path / "global" / "architect" / "v1.yaml",
                  owner_persona="architect", stage="architect", prompt_id="architect-global")
    catalog = load_prompts(tmp_path)
    pm_prompts = catalog.get_prompts_owned_by("pm")
    assert len(pm_prompts) == 2
    assert {p.stage for p in pm_prompts} == {"ingest", "assessor"}
    architect_prompts = catalog.get_prompts_owned_by("architect")
    assert len(architect_prompts) == 1


def test_get_versions_newest_first(tmp_path):
    """openspec spec Requirement 6: get_versions returns newest first."""
    _write_prompt(tmp_path / "global" / "assessor" / "v1.yaml", version="v1")
    _write_prompt(tmp_path / "global" / "assessor" / "v2.yaml", version="v2")
    _write_prompt(tmp_path / "global" / "assessor" / "v10.yaml", version="v10")
    catalog = load_prompts(tmp_path)
    versions = catalog.get_versions("assessor", "global")
    assert [p.version for p in versions] == ["v10", "v2", "v1"]


# ---------------------------------------------------------------------------
# Chain shape for ledger integration
# ---------------------------------------------------------------------------

def test_chain_serializes_to_ledger_friendly_dict(tmp_path):
    """Phase 3 wires this into LedgerEntry.prompt_resolution_path —
    so chain_as_list() output must be JSON-serializable shape."""
    import json
    _write_prompt(tmp_path / "global" / "assessor" / "v1.yaml",
                  git_sha="abc123", owner_persona="pm")
    catalog = load_prompts(tmp_path)
    result = catalog.resolve(stage="assessor", model="claude-sonnet")
    serialized = json.dumps(result.chain_as_list())  # must not raise
    parsed = json.loads(serialized)
    assert len(parsed) == 3
    matched = next(s for s in parsed if s["matched"])
    assert matched["scope"] == "global"
    assert matched["git_sha"] == "abc123"
    assert matched["owner_persona"] == "pm"
