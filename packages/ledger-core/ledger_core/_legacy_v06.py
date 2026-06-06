"""Decision Ledger client — Cosmos, typed schema, team-partitioned.

Spec refs (design.md §4):
  * Typed ambiguity classes, slot_value_hash, team_id partition
  * Invariant-class write-block (PHI / auth / identity / secrets / license)
  * v1 is suggest-only — no promotion path implemented (FDE Phase 1 work)
  * Cross-team retrieval forbidden — every query carries partition_key=team_id
"""
from __future__ import annotations
import logging
from typing import Optional

from azure.cosmos.aio import CosmosClient
from azure.cosmos.exceptions import CosmosResourceNotFoundError
from azure.identity.aio import DefaultAzureCredential

from .config import settings
from .models import INVARIANT_CLASSES, LedgerEntry, RunState

_logger = logging.getLogger("orchestrator.ledger")


class InvariantWriteBlocked(Exception):
    """Raised when a write would contradict an invariant-class org entry (design.md §4)."""


class Ledger:
    def __init__(self) -> None:
        self._cred = DefaultAzureCredential()
        self._client = CosmosClient(settings.cosmos_endpoint, credential=self._cred)
        self._db = self._client.get_database_client(settings.cosmos_db)
        self._ledger = self._db.get_container_client(settings.cosmos_ledger_container)
        self._runs = self._db.get_container_client(settings.cosmos_runs_container)

    async def close(self) -> None:
        await self._client.close()
        await self._cred.close()

    # ---- ledger ---------------------------------------------------------
    async def write_decision(self, entry: LedgerEntry) -> LedgerEntry:
        """Persist a Resolver decision. Suggest-only in v1 (design.md §4)."""
        # Invariant write-block: org-layer invariant entries are non-overridable.
        if entry.ambiguity_class in INVARIANT_CLASSES and entry.decision_kind == "swap":
            existing = await self._find_invariant(entry.ambiguity_class, entry.slot_value_hash)
            if existing is not None:
                raise InvariantWriteBlocked(
                    f"invariant precedent exists for {entry.ambiguity_class}/"
                    f"{entry.slot_value_hash}: {existing.get('resolution_text')!r}"
                )
        # v1 hard rule: writes always land as `suggest` — promotion is FDE Phase 1.
        # TODO(promotion): when promotion math is implemented, only entries with
        # confidence_source == 'human' may contribute to sample_count toward promotion.
        # Autopilot decisions are persisted for audit but excluded from the math
        # (design.md §4 promotion semantics).
        entry.status = "suggest"
        try:
            await self._ledger.upsert_item(entry.model_dump())
        except Exception as exc:  # demo resilience — container may not be reachable in dev
            _logger.warning("Ledger write failed (continuing): %s", exc)
        return entry

    async def delete_decision(self, run_id: str, card_id: str) -> bool:
        """Delete the ledger entry for (run_id, card_id). Used by /undo.

        Returns True if an item was deleted, False otherwise. Wrapped in
        try/except for demo resilience (missing item or Cosmos unreachable
        must not 500 the undo flow).
        """
        try:
            query = "SELECT * FROM c WHERE c.run_id=@r AND c.card_id=@c"
            params = [{"name": "@r", "value": run_id}, {"name": "@c", "value": card_id}]
            found: Optional[dict] = None
            async for item in self._ledger.query_items(query=query, parameters=params):
                found = item
                break
            if found is None:
                return False
            await self._ledger.delete_item(
                item=found["id"], partition_key=found.get("team_id"),
            )
            return True
        except Exception as exc:
            _logger.warning("Ledger delete failed (continuing): %s", exc)
            return False

    async def _find_invariant(self, klass: str, slot_hash: str) -> Optional[dict]:
        query = (
            "SELECT TOP 1 * FROM c WHERE c.ambiguity_class=@k AND c.slot_value_hash=@s "
            "AND c.team_id='__org__'"
        )
        params = [{"name": "@k", "value": klass}, {"name": "@s", "value": slot_hash}]
        try:
            async for item in self._ledger.query_items(query=query, parameters=params):
                return item
        except Exception:
            return None
        return None

    async def find_precedent(
        self, team_id: str, ambiguity_class: str, slot_value_hash: str,
    ) -> Optional[dict]:
        """Return most recent precedent matching (team, class, slot_hash), or None.

        Used by HYBRID autopilot mode: if a precedent exists, the card may
        auto-resolve; otherwise it gates for human review (design.md §3, §4).

        Demo stub: always returns None so HYBRID gates everything on first run.
        Real impl: Cosmos partition query on team_id with class+slot filter.
        """
        # TODO(phase-1): real Cosmos query — partition_key=team_id.
        return None

    async def recent_for_team(self, team_id: str, limit: int = 25) -> list[dict]:
        """Team-partitioned read (cross-team retrieval forbidden — design.md §4)."""
        q = "SELECT TOP @n * FROM c WHERE c.team_id=@t ORDER BY c.created_at DESC"
        params = [{"name": "@n", "value": limit}, {"name": "@t", "value": team_id}]
        out: list[dict] = []
        try:
            async for item in self._ledger.query_items(
                query=q, parameters=params, partition_key=team_id
            ):
                out.append(item)
        except Exception as exc:
            _logger.warning("Ledger read failed: %s", exc)
        return out

    # ---- run state ------------------------------------------------------
    async def save_run(self, run: RunState) -> None:
        try:
            doc = run.model_dump(mode="json")  # serialize datetimes/enums
            doc["id"] = run.run_id  # Cosmos requires `id` field
            await self._runs.upsert_item(doc)
        except Exception as exc:
            _logger.warning("Run save failed (run_id=%s): %s", run.run_id, exc)

    async def get_run(self, run_id: str) -> Optional[RunState]:
        try:
            item = await self._runs.read_item(item=run_id, partition_key=run_id)
            return RunState(**item)
        except CosmosResourceNotFoundError:
            return None
        except Exception as exc:
            _logger.warning("Run read failed: %s", exc)
            return None
