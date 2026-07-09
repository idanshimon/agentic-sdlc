"""KI-1 Bug B regression guard: a run's team_id must match the dashboard team.

The /api/run endpoint partitions every decision under `team_id`. It used to
default to a hardcoded "cardiology", while the dashboard's LEDGER_MCP_TOKEN maps
to "team-demo" — so decisions landed in a partition the dashboard could not
read and the Decisions view looked empty (KI-1 Bug B).

The default is now driven by the LEDGER_TEAM_ID env var (fallback "team-demo"),
which the bicep sets to the same team the token is scoped to. These tests lock
that so the divergence can't silently return.
"""
from __future__ import annotations

import importlib
import os
from unittest.mock import patch


def _team_default(reload: bool = False) -> str:
    """Resolve the create_run team_id Form default the way FastAPI would."""
    from apps.orchestrator import main
    if reload:
        importlib.reload(main)
    import inspect
    sig = inspect.signature(main.create_run)
    form = sig.parameters["team_id"].default
    # Starlette Form stores default_factory / default on the FieldInfo-like obj.
    factory = getattr(form, "default_factory", None)
    if callable(factory):
        return factory()
    return getattr(form, "default", None)


def test_default_team_is_not_the_old_hardcoded_cardiology():
    # The regression: "cardiology" diverged from the dashboard token's team.
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("LEDGER_TEAM_ID", None)
        assert _team_default() != "cardiology"


def test_default_team_falls_back_to_team_demo():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("LEDGER_TEAM_ID", None)
        assert _team_default() == "team-demo"


def test_default_team_follows_ledger_team_id_env():
    # Whatever the deploy sets LEDGER_TEAM_ID to (to match the token), runs use it.
    with patch.dict(os.environ, {"LEDGER_TEAM_ID": "team-cardiology"}, clear=False):
        assert _team_default() == "team-cardiology"
