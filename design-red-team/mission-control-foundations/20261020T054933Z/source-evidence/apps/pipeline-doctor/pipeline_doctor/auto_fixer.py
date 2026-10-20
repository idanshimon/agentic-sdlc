"""Auto-fix applier — within bounded envelopes.

Takes a validated AutoFixProposal (passed envelope check) and:
  1. Writes a runtime ledger entry of kind "auto_fix"
  2. Optionally applies the change to the live config (post-MVP)
  3. Returns the entry id for downstream traceability

For v0.7 demo: the "applies the change to the live config" step is a stub
that logs the proposed mutation. Real config application is post-MVP and
requires an in-memory config registry that the orchestrator reads from.

The IMPORTANT thing — recording the decision in the ledger — works fully.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Optional

from ledger_core import LedgerEntry, Actor, LedgerClient

from .models import AutoFixProposal, EnvelopeCheck

_logger = logging.getLogger("pipeline_doctor.auto_fixer")


class AutoFixer:
    """Applies validated auto-fixes to the live system + writes ledger entries."""

    def __init__(self, ledger: LedgerClient, dry_run: bool = False):
        self._ledger = ledger
        self._dry_run = dry_run

    async def apply(
        self,
        proposal: AutoFixProposal,
        envelope_check: EnvelopeCheck,
        team_id: str,
        actor_id: str = "pipeline-doctor",
    ) -> Optional[str]:
        """Apply an auto-fix that has already passed envelope validation.

        Returns the ledger entry id, or None if dry_run.
        Raises ValueError if envelope_check.allowed is False.
        """
        if not envelope_check.allowed:
            raise ValueError(
                f"AutoFixer.apply called on disallowed proposal: "
                f"{[v.reason for v in envelope_check.violations]}"
            )

        rationale = self._build_rationale(proposal, envelope_check)

        entry = LedgerEntry(
            team_id=team_id,
            actor=Actor(kind="agent", id=actor_id, display_name="Pipeline Doctor"),
            decision=(
                f"auto-fix applied: {proposal.field_path} "
                f"{proposal.current_value!r} -> {proposal.proposed_value!r}"
            ),
            rationale=rationale,
            run_id="doctor-{}".format(datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")),
            runtime_kind="auto_fix",
            bundle_refs=[proposal.bundle_ref],
            cost_usd=0.0,  # Doctor itself does not invoke an LLM in the apply path
        )

        if self._dry_run:
            _logger.info("DRY-RUN: would apply auto-fix %s", proposal.id)
            _logger.info("DRY-RUN: would write entry %s", entry.id)
            return None

        # Write the ledger entry first, BEFORE applying the actual config change.
        # Reason: if we crash between apply and write, the system has changed
        # without an audit trail. The ledger entry is the audit; it MUST exist.
        await self._ledger.write_entry(entry)

        # Apply the config change.
        # In v0.7 demo this is a logged stub. Real impl writes to a config
        # registry the orchestrator reads from.
        self._apply_config_change(proposal)

        _logger.info("auto-fix applied: %s (entry_id=%s)", proposal.id, entry.id)
        return entry.id

    def _build_rationale(
        self, proposal: AutoFixProposal, envelope_check: EnvelopeCheck,
    ) -> str:
        return (
            f"Pipeline Doctor auto-fix.\n\n"
            f"Triggered by: {proposal.triggered_by}\n"
            f"Bundle: {proposal.bundle_ref}\n"
            f"Rule: {proposal.rule_id}\n"
            f"Field: {proposal.field_path}\n"
            f"Change: {proposal.current_value!r} -> {proposal.proposed_value!r}\n\n"
            f"Rationale: {proposal.rationale}\n\n"
            f"Envelope check: ALLOWED. {len(envelope_check.violations)} violations "
            f"raised, all resolvable.\n\n"
            f"Expected impact: {proposal.expected_impact or 'no specific prediction'}"
        )

    def _apply_config_change(self, proposal: AutoFixProposal) -> None:
        # v0.7 demo: log the proposed mutation. Real impl: write to config registry.
        _logger.info(
            "STUB apply: %s.%s : %r -> %r",
            proposal.bundle_ref,
            proposal.field_path,
            proposal.current_value,
            proposal.proposed_value,
        )
