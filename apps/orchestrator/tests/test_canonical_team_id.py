"""canonical_team_id — the one spelling of a team id across the stack.

Regression guard for KI-1 Bug B: the UI team selector submitted bare slugs
("cardiology") while token scoping + backend defaults use the "team-" prefix,
so a run's decisions landed in a partition the dashboard token couldn't read
and the Decisions view was silently empty.
"""
from __future__ import annotations

import pytest

from apps.orchestrator.org_model import canonical_team_id


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("cardiology", "team-cardiology"),
        ("Cardiology", "team-cardiology"),
        ("  cardiology  ", "team-cardiology"),
        ("team-cardiology", "team-cardiology"),   # already canonical — idempotent
        ("TEAM-CARDIOLOGY", "team-cardiology"),
        ("team-demo", "team-demo"),
        ("finance", "team-finance"),
        ("care team", "team-care-team"),           # whitespace collapses to hyphen
        ("care_team", "team-care-team"),           # underscore collapses to hyphen
        ("*", "*"),                                # list wildcard passes through
        ("__org__", "__org__"),                    # org-scope sentinel passes through
        ("", ""),                                  # empty passes through
    ],
)
def test_canonical_team_id(raw, expected):
    assert canonical_team_id(raw) == expected


def test_canonical_team_id_is_idempotent():
    once = canonical_team_id("cardiology")
    assert canonical_team_id(once) == once == "team-cardiology"
