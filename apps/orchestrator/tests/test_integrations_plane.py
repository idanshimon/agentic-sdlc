"""Tests for the integrations plane — registry, provenance, provider seam.

Spec: openspec/changes/add-enterprise-integrations-plane/specs/integrations-plane/spec.md
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from apps.orchestrator import integrations as I
from apps.orchestrator import planning_providers as PP
from apps.orchestrator import work_items as W

SECRET = "ghp_THIS_IS_A_FAKE_TEST_TOKEN_0123456789"


def _write(tmp_path: Path, body: str) -> str:
    p = tmp_path / "integrations.yaml"
    p.write_text(body)
    return str(p)


GOOD = """
integrations:
  - id: code-host
    kind: code_host
    provider: github
    display_name: GitHub
    base_url: https://api.github.com
    identity: delivery-bot
    scopes: [repo, workflow]
    token_env: TEST_GH_TOKEN
    target_repo: acme/platform
  - id: planning
    kind: planning_tracker
    provider: aha
    display_name: Planning tracker
    base_url: https://example.example/api/v1
    identity: planning-reader
    scopes: [read]
    token_env: TEST_PLANNING_TOKEN
    item_url_template: https://example.example/features/{ref}
    item_api_template: https://example.example/api/v1/features/{ref}
"""


# --- Requirement: opt-in, fails safe when absent ------------------------------

def test_default_singleton_is_opt_in_not_auto_loaded(tmp_path, monkeypatch):
    """The repo's config/*.example template must never be auto-discovered, and a
    load from a scratch cwd must stay unloaded. This is the posture guarantee:
    deploying the image changes nothing."""
    monkeypatch.delenv("INTEGRATIONS_PATH", raising=False)
    paths = [str(p) for p in I._candidate_paths()]
    assert not any("example" in p for p in paths), paths
    assert not any("config/" in p for p in paths), paths

    monkeypatch.chdir(tmp_path)
    reg = I.load_integrations()
    assert reg.loaded is False
    assert reg.integrations == ()


def test_absent_registry_reports_unconfigured_not_error(tmp_path, monkeypatch):
    monkeypatch.delenv("INTEGRATIONS_PATH", raising=False)
    monkeypatch.chdir(tmp_path)
    view = I.load_integrations().redacted()
    assert view["loaded"] is False
    assert view["integrations"] == []
    assert view["error"] == ""


def test_env_path_takes_precedence(tmp_path, monkeypatch):
    path = _write(tmp_path, GOOD)
    monkeypatch.setenv("INTEGRATIONS_PATH", path)
    assert str(I._candidate_paths()[0]) == path


@pytest.mark.parametrize(
    "body",
    [
        "integrations: [[[",            # unparseable
        "- just\n- a\n- list\n",        # top level not a mapping
        "integrations: 5\n",            # integrations not a list
    ],
)
def test_malformed_registry_degrades_loudly_never_half_applied(tmp_path, body):
    reg = I.load_integrations(_write(tmp_path, body))
    assert reg.loaded is False
    assert reg.error
    assert reg.integrations == ()


# --- Requirement: credentials referenced, never stored or returned ------------

def test_inline_credential_is_refused_at_load(tmp_path):
    reg = I.load_integrations(_write(tmp_path, f"""
integrations:
  - id: bad
    kind: code_host
    provider: github
    token: {SECRET}
"""))
    assert reg.get("bad") is None
    assert reg.rejected
    reason = reg.rejected[0]["reason"]
    assert "token" in reason
    assert SECRET not in reason  # the refusal must not echo the value


def test_inline_credential_refusal_does_not_take_down_siblings(tmp_path):
    reg = I.load_integrations(_write(tmp_path, f"""
integrations:
  - id: bad
    kind: code_host
    provider: github
    api_key: {SECRET}
  - id: planning
    kind: planning_tracker
    provider: jira
    token_env: TEST_PLANNING_TOKEN
"""))
    assert reg.loaded is True
    assert reg.get("bad") is None
    assert reg.get("planning") is not None


def test_credential_presence_reported_without_disclosure(tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_GH_TOKEN", SECRET)
    monkeypatch.setenv("TEST_PLANNING_TOKEN", SECRET)
    reg = I.load_integrations(_write(tmp_path, GOOD))
    view = reg.redacted()
    assert view["integrations"][0]["credential_present"] is True
    import json
    blob = json.dumps(view)
    assert SECRET not in blob
    assert "TEST_GH_TOKEN" in blob  # the NAME is fine; the value is not


def test_missing_env_var_means_unconfigured(tmp_path, monkeypatch):
    monkeypatch.delenv("TEST_GH_TOKEN", raising=False)
    monkeypatch.delenv("TEST_PLANNING_TOKEN", raising=False)
    reg = I.load_integrations(_write(tmp_path, GOOD))
    assert reg.get("code-host").credential_present is False
    assert reg.get("code-host").status == "unconfigured"


# --- Requirement: honest status ----------------------------------------------

def test_declared_but_unprobed_is_configured_not_verified(tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_GH_TOKEN", SECRET)
    reg = I.load_integrations(_write(tmp_path, GOOD))
    item = reg.get("code-host")
    assert item.status == "configured"
    assert item.redacted()["verified"] is False


def test_registry_can_never_mint_verified(tmp_path, monkeypatch):
    """Nothing in the loader may produce `verified` — that word belongs to a
    real probe result only."""
    monkeypatch.setenv("TEST_GH_TOKEN", SECRET)
    monkeypatch.setenv("TEST_PLANNING_TOKEN", SECRET)
    reg = I.load_integrations(_write(tmp_path, GOOD))
    assert all(i.status != "verified" for i in reg.integrations)


def test_probe_without_credential_returns_unknown_not_verified():
    item = I.Integration(id="x", kind="code_host", provider="github", token_env="NOPE_MISSING")
    res = asyncio.run(PP.probe_integration(item))
    assert res.status == "unknown"
    assert res.ok is False


def test_probe_of_unimplemented_provider_returns_unknown(monkeypatch):
    monkeypatch.setenv("TEST_TOK", SECRET)
    item = I.Integration(id="x", kind="planning_tracker", provider="generic", token_env="TEST_TOK")
    monkeypatch.setattr(PP, "get_provider", lambda _i: None)
    res = asyncio.run(PP.probe_integration(item))
    assert res.status == "unknown"


# --- Requirement: provider seam, one shape, no writes -------------------------

def test_unknown_provider_is_refused_at_load(tmp_path):
    reg = I.load_integrations(_write(tmp_path, """
integrations:
  - id: mystery
    kind: planning_tracker
    provider: notarealtracker
    token_env: TEST_TOK
  - id: fine
    kind: planning_tracker
    provider: jira
    token_env: TEST_TOK
"""))
    assert reg.get("mystery") is None
    assert "notarealtracker" in reg.rejected[0]["reason"]
    assert reg.get("fine") is not None


def test_unknown_kind_is_refused(tmp_path):
    reg = I.load_integrations(_write(tmp_path, """
integrations:
  - id: weird
    kind: teleporter
    provider: github
"""))
    assert reg.get("weird") is None


def test_every_planning_provider_exposes_the_same_shape():
    """Adding a provider must not change any consumer."""
    for name, provider in PP._PLANNING_PROVIDERS.items():
        assert isinstance(provider, PP.PlanningProvider), name
        assert hasattr(provider, "resolve") and hasattr(provider, "probe"), name


def test_no_provider_exposes_a_write_path():
    """This capability is read-only toward planning systems."""
    for provider in list(PP._PLANNING_PROVIDERS.values()) + list(PP._CODE_HOST_PROVIDERS.values()):
        for attr in dir(provider):
            if attr.startswith("_"):
                continue
            assert not attr.startswith(PP.FORBIDDEN_METHOD_PREFIXES), (
                f"{type(provider).__name__}.{attr} looks like a write path"
            )


def test_duplicate_ids_are_rejected(tmp_path):
    reg = I.load_integrations(_write(tmp_path, """
integrations:
  - id: dup
    kind: planning_tracker
    provider: jira
    token_env: A
  - id: dup
    kind: planning_tracker
    provider: aha
    token_env: B
"""))
    assert len(reg.integrations) == 1
    assert any(r["reason"] == "duplicate id" for r in reg.rejected)


# --- Requirement: work-item provenance ---------------------------------------

def test_provenance_absent_is_none_and_non_blocking():
    assert W.normalize_ref(None, None) is None
    assert W.normalize_ref("aha", "   ") is None
    assert W.ledger_fields(None) == {}


def test_unconfigured_planning_system_records_a_claim_not_verified():
    ref = W.normalize_ref("aha", "E-1042", registry=I.IntegrationsRegistry())
    assert ref.verification == "claimed"
    assert ref.source_ref == "E-1042"
    assert "no planning-tracker integration configured" in ref.reason


def test_configured_tracker_still_only_claims_until_fetched(tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_PLANNING_TOKEN", SECRET)
    reg = I.load_integrations(_write(tmp_path, GOOD))
    ref = W.normalize_ref("planning", "E-1042", registry=reg)
    # A rendered deep link is NOT verification.
    assert ref.url == "https://example.example/features/E-1042"
    assert ref.verification == "claimed"


def test_malformed_ref_is_unverifiable_but_does_not_raise():
    ref = W.normalize_ref("aha", "not a valid ref!! <script>")
    assert ref.verification == "unverifiable"
    assert ref.reason


def test_successful_resolution_marks_verified():
    ref = W.normalize_ref("aha", "E-1042")
    out = W.apply_resolution(ref, W.WorkItem(id="E-1042", item_type="epic", title="Claims intake"))
    assert out.verification == "verified"
    assert out.title == "Claims intake"
    assert out.reason == ""


def test_failed_resolution_does_not_fail_the_run():
    ref = W.normalize_ref("aha", "E-1042")
    out = W.apply_resolution(ref, None, error="tracker unreachable")
    assert out.verification == "unverifiable"
    assert out.reason == "tracker unreachable"
    assert out.source_ref == "E-1042"  # provenance survives the failure


def test_ledger_fields_carry_provenance_when_present():
    ref = W.normalize_ref("aha", "E-1042")
    fields = W.ledger_fields(ref)
    assert fields["work_item"]["source_ref"] == "E-1042"
    assert fields["work_item"]["verification"] == "claimed"


def test_resolve_returns_none_when_no_api_template_configured():
    item = I.Integration(id="p", kind="planning_tracker", provider="generic", token_env="T")
    assert asyncio.run(PP.resolve_work_item(item, "E-1")) is None
