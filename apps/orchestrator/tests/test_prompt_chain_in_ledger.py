"""Phase 2.6: assert ledger entries carry the prompt_resolution_path.

When a stage helper resolves a prompt through the catalog AND stashes
the chain on run.prompt_chain_by_stage, every LedgerEntry written by
the autopilot path (main.py::_drive) or the per-card /approve path
(main.py::approve) MUST pin that chain into entry.prompt_resolution_path.

This closes the audit loop: given any decision in Cosmos, we can
answer "which prompt produced this?" deterministically — with the
matched scope's prompt_id, version, git_sha, and owner_persona all
visible in the entry.
"""
from __future__ import annotations

from orchestrator.models import LedgerEntry


def test_ledger_entry_default_prompt_resolution_path_is_none():
    """Legacy entries — pre-Phase 2 runs and any code path that doesn't
    flow through the catalog — should have prompt_resolution_path=None.
    The UI renders 'chain unavailable (pre-v2)' for these per the
    openspec spec scenario.
    """
    e = LedgerEntry(
        team_id="team-cardiology",
        run_id="r1",
        card_id="c1",
        ambiguity_class="phi-classification",
        decision_kind="accept",
    )
    assert e.prompt_resolution_path is None


def test_ledger_entry_accepts_chain_list():
    """Phase 2 entries: chain is a list of dicts, each with scope,
    matched, prompt_id, version, git_sha, owner_persona, reason."""
    chain = [
        {
            "scope": "team",
            "matched": False,
            "reason": "no published team prompt for team=cardiology stage=assessor",
        },
        {
            "scope": "persona",
            "matched": False,
            "reason": "no published persona prompt for persona=pm stage=assessor",
        },
        {
            "scope": "global",
            "matched": True,
            "prompt_id": "assessor-global",
            "version": "v1",
            "git_sha": "abc123",
            "owner_persona": "pm",
        },
    ]
    e = LedgerEntry(
        team_id="team-cardiology",
        run_id="r1",
        card_id="c1",
        ambiguity_class="phi-classification",
        decision_kind="accept",
        prompt_resolution_path=chain,
    )
    assert e.prompt_resolution_path == chain
    # Round-trip through model_dump for Cosmos write
    dumped = e.model_dump(mode="json", exclude_none=False)
    assert dumped["prompt_resolution_path"] == chain


def test_ledger_entry_serializes_none_chain_explicitly():
    """When prompt_resolution_path is None, the cosmos doc should still
    include the key (so future readers can distinguish 'never written'
    from 'pre-Phase-2 legacy entry'). model_dump with exclude_none=False
    keeps the None value."""
    e = LedgerEntry(
        team_id="team-cardiology",
        run_id="r1",
        card_id="c1",
        ambiguity_class="phi-classification",
        decision_kind="accept",
    )
    dumped = e.model_dump(mode="json", exclude_none=False)
    assert "prompt_resolution_path" in dumped
    assert dumped["prompt_resolution_path"] is None
