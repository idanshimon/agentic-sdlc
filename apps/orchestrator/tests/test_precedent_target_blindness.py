"""Regression guards for the Q2 finding: autonomy is decided target-blind.

These tests pin facts about the CURRENT system, established by reading the
source while answering Q2 (see `design.md` in this change).

They are deliberately written to FAIL when the finding is fixed. Each carries
the follow-up in its message, so closing the gap updates the guard rather than
silently deleting the evidence that motivated it.

The finding: at the moment the system decides "may an agent resolve this alone",
nothing in the run knows where the resulting code will land. Autonomy is granted
without knowledge of the blast radius of the decision being authorised.
"""
from __future__ import annotations

import inspect
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MAIN = REPO_ROOT / "apps" / "orchestrator" / "main.py"
COSMOS = REPO_ROOT / "packages" / "ledger-core" / "ledger_core" / "cosmos.py"
DELIVER = REPO_ROOT / "apps" / "orchestrator" / "stages" / "deliver_github.py"


def test_precedent_lookup_is_target_blind():
    """`find_precedent` keys on (team, class, slot_hash) — no target."""
    src = COSMOS.read_text()
    body = src[src.index("async def find_precedent"):]
    body = body[: body.index("\n    async def ", 10)] if "\n    async def " in body[10:] else body

    assert "c.team_id=@t" in body and "c.ambiguity_class=@k" in body
    assert "target_repo" not in body, (
        "find_precedent now considers the delivery target — good. Update this "
        "guard and the Q2 finding in design.md, which records that it did not."
    )


def test_accuracy_projection_cannot_see_the_target():
    """`query_class_history` uses an explicit column list that omits target_repo.

    A scorer cannot partition by a field it never selects.
    """
    src = COSMOS.read_text()
    body = src[src.index("async def query_class_history"):]
    select = body[body.index("SELECT"): body.index("ORDER BY")]

    assert "c.ambiguity_class" in select
    assert "target_repo" not in select, (
        "query_class_history now selects the delivery target — good. The "
        "accuracy projection can partition by blast radius; update this guard."
    )


def test_no_precedent_forming_entry_stamps_the_target():
    """Only the deliver-stage entry records target_repo, and it is written
    AFTER every gate decision has already been made."""
    src = MAIN.read_text()
    assert "LedgerEntry(" in src
    assert src.count("target_repo") == 0, (
        "main.py now references target_repo. If precedent-forming entries stamp "
        "it, the Q2 window has been closed — update this guard. If they do not, "
        "check that the reference is not creating a partial attribution, which "
        "would be worse than none."
    )


def test_the_target_is_resolved_after_the_decision():
    """THE finding. `_resolve_target_repo` is called inside the deliver stage;
    the autopilot decision happens during resolution, many stages earlier."""
    src = DELIVER.read_text()
    call = src.index("target_repo = _resolve_target_repo(")
    definition = src.index("def _resolve_target_repo(")
    assert call < definition, "sanity: the call precedes the definition in this module"

    main_src = MAIN.read_text()
    assert "_resolve_target_repo" not in main_src, (
        "main.py now resolves the delivery target. If it resolves at RUN "
        "CREATION, the Q2 finding is fixed and this guard should be replaced "
        "with one asserting the target is known before the first gate decision."
    )


def test_the_window_is_still_open():
    """No built-in default target means one deployment, one target, so precedent
    has not yet accumulated across differing blast radii.

    This is the condition that keeps the fix a schema addition rather than a
    data migration. When it changes, the cost of Q2 changes with it.
    """
    from orchestrator.config import Settings

    assert Settings().github_default_target_repo == "", (
        "a default delivery target is now configured. If runs are delivering to "
        "more than one target, precedent is accumulating under a target-blind "
        "key and CANNOT be split retroactively — see Q2 in design.md. Fix the "
        "keying before this history grows."
    )
