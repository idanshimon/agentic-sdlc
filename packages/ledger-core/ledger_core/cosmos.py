"""Cosmos client for the Decision Ledger.

Exposes the LedgerClient class — used by the orchestrator, Pipeline Doctor,
and Decision Ledger MCP server.
"""
from __future__ import annotations
import logging
from typing import List, Optional

from azure.cosmos.aio import CosmosClient
from azure.cosmos.exceptions import CosmosResourceNotFoundError
from azure.identity.aio import DefaultAzureCredential

from .models import (
    INVARIANT_CLASSES,
    LedgerEntry,
    from_legacy_v06_dict,
)

_logger = logging.getLogger("ledger_core.cosmos")


class InvariantWriteBlocked(Exception):
    """Raised when a write would contradict an invariant-class org entry."""


class LedgerClient:
    """Async Cosmos-backed ledger client. v0.7 schema with runtime/meta entries."""

    def __init__(
        self,
        cosmos_endpoint: str,
        cosmos_db: str,
        ledger_container: str = "decision-ledger",
        runs_container: str = "pipeline-runs",
    ):
        self._cred = DefaultAzureCredential()
        self._client = CosmosClient(cosmos_endpoint, credential=self._cred)
        self._db = self._client.get_database_client(cosmos_db)
        self._ledger = self._db.get_container_client(ledger_container)
        self._runs = self._db.get_container_client(runs_container)

    async def close(self) -> None:
        await self._client.close()
        await self._cred.close()

    # ---- writes -----------------------------------------------------------
    async def write_entry(self, entry: LedgerEntry) -> LedgerEntry:
        """Persist a ledger entry. Validates schema per entry_type."""
        if entry.entry_type == "runtime" and entry.ambiguity_class in INVARIANT_CLASSES:
            existing = await self._find_invariant(
                entry.ambiguity_class, entry.slot_value_hash or "",
            )
            if existing is not None and entry.decision_kind == "swap":
                raise InvariantWriteBlocked(
                    f"invariant precedent exists for {entry.ambiguity_class}/"
                    f"{entry.slot_value_hash}: {existing.get('resolution_text')!r}"
                )
        try:
            doc = entry.model_dump(mode="json", exclude_none=False)
            doc["id"] = entry.id  # Cosmos requires `id`
            await self._ledger.upsert_item(doc)
        except Exception as exc:
            _logger.warning("Ledger write failed (continuing): %s", exc)
        return entry

    async def delete_entry(self, entry_id: str, team_id: str) -> bool:
        try:
            await self._ledger.delete_item(item=entry_id, partition_key=team_id)
            return True
        except CosmosResourceNotFoundError:
            return False
        except Exception as exc:
            _logger.warning("Ledger delete failed: %s", exc)
            return False

    # ---- reads ------------------------------------------------------------
    async def query_recent_for_team(
        self,
        team_id: str,
        limit: int = 25,
        entry_type: Optional[str] = None,
    ) -> List[LedgerEntry]:
        """Team-partitioned read; optional filter by entry_type."""
        if entry_type:
            q = (
                "SELECT TOP @n * FROM c "
                "WHERE c.team_id=@t AND c.entry_type=@et "
                "ORDER BY c.created_at DESC"
            )
            params = [
                {"name": "@n", "value": limit},
                {"name": "@t", "value": team_id},
                {"name": "@et", "value": entry_type},
            ]
        else:
            q = (
                "SELECT TOP @n * FROM c WHERE c.team_id=@t "
                "ORDER BY c.created_at DESC"
            )
            params = [
                {"name": "@n", "value": limit},
                {"name": "@t", "value": team_id},
            ]
        out: List[LedgerEntry] = []
        try:
            async for item in self._ledger.query_items(
                query=q, parameters=params, partition_key=team_id
            ):
                out.append(from_legacy_v06_dict(item))
        except Exception as exc:
            _logger.warning("Ledger read failed: %s", exc)
        return out

    async def query_meta_by_bundle(
        self,
        bundle_dept: str,
        version_prefix: Optional[str] = None,
        limit: int = 50,
    ) -> List[LedgerEntry]:
        """Cross-team query for meta entries affecting a bundle dept."""
        # Use ARRAY_CONTAINS with a STARTSWITH-like pattern; Cosmos supports STARTSWITH
        q = (
            "SELECT TOP @n * FROM c "
            "WHERE c.entry_type='meta' "
            "AND EXISTS(SELECT VALUE r FROM r IN c.bundle_refs WHERE STARTSWITH(r, @bd)) "
            "ORDER BY c.created_at DESC"
        )
        bd = f"{bundle_dept}/"
        if version_prefix:
            bd = f"{bundle_dept}/{version_prefix}"
        params = [
            {"name": "@n", "value": limit},
            {"name": "@bd", "value": bd},
        ]
        out: List[LedgerEntry] = []
        try:
            async for item in self._ledger.query_items(
                query=q, parameters=params, enable_cross_partition_query=True
            ):
                out.append(from_legacy_v06_dict(item))
        except Exception as exc:
            _logger.warning("Meta query failed: %s", exc)
        return out

    async def query_runtime_by_session(
        self,
        agent_session_id: str,
        limit: int = 100,
    ) -> List[LedgerEntry]:
        """All ledger entries from a specific GH audit session."""
        q = (
            "SELECT TOP @n * FROM c "
            "WHERE c.agent_session_id=@s "
            "ORDER BY c.created_at DESC"
        )
        params = [
            {"name": "@n", "value": limit},
            {"name": "@s", "value": agent_session_id},
        ]
        out: List[LedgerEntry] = []
        try:
            async for item in self._ledger.query_items(
                query=q, parameters=params, enable_cross_partition_query=True
            ):
                out.append(from_legacy_v06_dict(item))
        except Exception as exc:
            _logger.warning("Session query failed: %s", exc)
        return out

    async def find_precedent(
        self,
        team_id: str,
        ambiguity_class: str,
        slot_value_hash: str,
    ) -> Optional[LedgerEntry]:
        """Most recent precedent matching (team, class, slot_hash). Used by autopilot."""
        q = (
            "SELECT TOP 1 * FROM c "
            "WHERE c.team_id=@t "
            "AND c.ambiguity_class=@k "
            "AND c.slot_value_hash=@s "
            "AND c.entry_type='runtime' "
            "ORDER BY c.created_at DESC"
        )
        params = [
            {"name": "@t", "value": team_id},
            {"name": "@k", "value": ambiguity_class},
            {"name": "@s", "value": slot_value_hash},
        ]
        try:
            async for item in self._ledger.query_items(
                query=q, parameters=params, partition_key=team_id
            ):
                return from_legacy_v06_dict(item)
        except Exception as exc:
            _logger.warning("Precedent lookup failed: %s", exc)
        return None

    async def _find_invariant(
        self, klass: str, slot_hash: str,
    ) -> Optional[dict]:
        q = (
            "SELECT TOP 1 * FROM c "
            "WHERE c.ambiguity_class=@k AND c.slot_value_hash=@s "
            "AND c.team_id='__org__'"
        )
        params = [
            {"name": "@k", "value": klass},
            {"name": "@s", "value": slot_hash},
        ]
        try:
            async for item in self._ledger.query_items(
                query=q, parameters=params, enable_cross_partition_query=True
            ):
                return item
        except Exception:
            return None
        return None

    # ---- run state --------------------------------------------------------
    async def save_run(self, doc: dict) -> None:
        """Save a serialized run state. Caller passes a dict (e.g. RunState.model_dump)."""
        try:
            doc = dict(doc)
            doc["id"] = doc.get("run_id") or doc.get("id")
            if not doc["id"]:
                raise ValueError("save_run: doc must have run_id or id")
            await self._runs.upsert_item(doc)
        except Exception as exc:
            _logger.warning("Run save failed: %s", exc)

    async def get_run(self, run_id: str) -> Optional[dict]:
        try:
            return await self._runs.read_item(item=run_id, partition_key=run_id)
        except CosmosResourceNotFoundError:
            return None
        except Exception as exc:
            _logger.warning("Run read failed: %s", exc)
            return None
