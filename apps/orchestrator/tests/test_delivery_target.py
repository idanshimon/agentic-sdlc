"""Tests for delivery-target resolution and recording (tasks 1.1-1.6).

Both defects here are the same shape as everything else in this codebase's
recent history: the system knew something and did not record it as a fact, or
depended on something it never declared.
"""
from __future__ import annotations

import pytest

from orchestrator.stages.deliver_github import (
    DeliveryTargetUnresolved,
    _resolve_target_repo,
)


class _Cfg:
    def __init__(self, default="", overrides=None):
        self.github_default_target_repo = default
        self.delivery_overrides = overrides or {}


# --- resolution order --------------------------------------------------------

def test_team_override_wins():
    cfg = _Cfg(default="org/fallback", overrides={"team-a": {"target_repo": "org/chosen"}})
    assert _resolve_target_repo("team-a", cfg) == "org/chosen"


def test_falls_back_to_declared_default():
    cfg = _Cfg(default="org/fallback")
    assert _resolve_target_repo("team-a", cfg) == "org/fallback"


def test_blank_override_falls_through_rather_than_delivering_nowhere():
    cfg = _Cfg(default="org/fallback", overrides={"team-a": {"target_repo": "   "}})
    assert _resolve_target_repo("team-a", cfg) == "org/fallback"


def test_values_are_stripped():
    cfg = _Cfg(overrides={"team-a": {"target_repo": "  org/chosen  "}})
    assert _resolve_target_repo("team-a", cfg) == "org/chosen"


# --- the failure that used to be an AttributeError --------------------------

def test_no_target_anywhere_raises_a_typed_error():
    with pytest.raises(DeliveryTargetUnresolved):
        _resolve_target_repo("team-a", _Cfg())


def test_the_error_names_the_team_the_order_and_the_key_to_set():
    """The operator reading this is usually not who wrote the config."""
    with pytest.raises(DeliveryTargetUnresolved) as e:
        _resolve_target_repo("team-cardiology", _Cfg())
    msg = str(e.value)
    assert "team-cardiology" in msg
    assert "delivery_overrides" in msg
    assert "GITHUB_DEFAULT_TARGET_REPO" in msg
    assert "owner/repo" in msg


def test_missing_config_attribute_does_not_crash_with_attributeerror():
    """A config object lacking the field entirely must still fail cleanly."""
    class _Bare:
        pass

    with pytest.raises(DeliveryTargetUnresolved):
        _resolve_target_repo("team-a", _Bare())


def test_there_is_no_builtin_default_target():
    """Delivering generated code somewhere plausible that nobody chose is worse
    than refusing to deliver. The reference repo stays tenant-neutral."""
    from orchestrator.config import Settings

    assert Settings().github_default_target_repo == ""


# --- the destination is a queryable fact -------------------------------------

def test_ledger_entry_carries_target_repo_as_a_typed_field():
    from ledger_core import Actor, LedgerEntry

    e = LedgerEntry(
        team_id="t", actor=Actor(kind="agent", id="orchestrator-deliver"),
        decision="delivered", rationale="r", run_id="run-1",
        runtime_kind="delivered", target_repo="org/product",
    )
    assert e.target_repo == "org/product"


def test_unknown_destination_is_none_not_empty_string():
    """`None` (never recorded) must stay distinguishable from `""`."""
    from ledger_core import Actor, LedgerEntry

    e = LedgerEntry(
        team_id="t", actor=Actor(kind="agent", id="x"), decision="d",
        rationale="r", run_id="1", runtime_kind="delivered",
    )
    assert e.target_repo is None


def test_preexisting_entries_still_parse():
    from ledger_core import Actor, LedgerEntry

    e = LedgerEntry(
        team_id="t", actor=Actor(kind="agent", id="x"), decision="d",
        rationale="r", run_id="1", runtime_kind="delivered", target_repo="org/p",
    )
    legacy = {k: v for k, v in e.model_dump().items() if k != "target_repo"}
    assert LedgerEntry(**legacy).target_repo is None


def test_destination_survives_serialization():
    from ledger_core import Actor, LedgerEntry

    e = LedgerEntry(
        team_id="t", actor=Actor(kind="agent", id="x"), decision="d",
        rationale="r", run_id="1", runtime_kind="delivered", target_repo="org/p",
    )
    assert LedgerEntry(**e.model_dump()).target_repo == "org/p"
