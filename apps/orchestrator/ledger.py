"""Compatibility shim for v0.6 → v0.7.

The orchestrator was written against an in-process `Ledger` class
(`apps/orchestrator/ledger.py` in v0.6). In v0.7 that logic was extracted
into the shared `ledger_core` package as `LedgerClient`.

Rather than churn every call site at the same time as the architecture
overhaul, this shim re-exports `LedgerClient` under the old `Ledger`
name and adds the small handful of method aliases the orchestrator
uses (`write_decision`, `delete_decision`).

Removal plan: once `apps/pipeline-doctor` and `apps/orchestrator` both
migrate to call `ledger_core.LedgerClient` directly with the v0.7
`write_entry` / `delete_entry` names, this file can be deleted.
"""
from __future__ import annotations

from ledger_core import InvariantWriteBlocked, LedgerClient, LedgerEntry

from .config import settings


class Ledger(LedgerClient):
    """Drop-in replacement for the v0.6 `Ledger` class.

    Differences from `LedgerClient`:
      * Zero-arg constructor that reads connection details from
        `orchestrator.config.settings`.
      * Method aliases: `write_decision` → `write_entry`,
        `delete_decision` → `delete_entry`. Both keep the original
        signatures so existing callers (and their tests) work
        unchanged.
    """

    def __init__(
        self,
        cosmos_endpoint: str | None = None,
        cosmos_db: str | None = None,
        ledger_container: str | None = None,
        runs_container: str | None = None,
    ) -> None:
        super().__init__(
            cosmos_endpoint=cosmos_endpoint or settings.cosmos_endpoint,
            cosmos_db=cosmos_db or settings.cosmos_db,
            ledger_container=ledger_container or settings.cosmos_ledger_container,
            runs_container=runs_container or settings.cosmos_runs_container,
        )

    async def write_decision(self, entry: LedgerEntry) -> LedgerEntry:
        """v0.6 alias for `write_entry`. May raise `InvariantWriteBlocked`."""
        return await self.write_entry(entry)

    async def delete_decision(self, entry_id: str, team_id: str) -> bool:
        """v0.6 alias for `delete_entry`."""
        return await self.delete_entry(entry_id, team_id)


__all__ = ["Ledger", "InvariantWriteBlocked"]
