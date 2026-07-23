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


# Payload keys that can carry large generated-code / document strings. These are
# needed live (in-memory) for the deliver stage but must not bloat the durable
# run doc, which is re-PUT on every event. Cap length in the persisted snapshot.
_LARGE_PAYLOAD_KEYS = frozenset({
    "code", "app_code", "test_code", "architecture", "test_plan",
    "impl", "tests", "content", "decisions_md", "diff", "patch",
})
_MAX_PERSISTED_STR = 2000  # chars kept per large field in the durable doc


def _trim_run_doc_payloads(doc: dict) -> None:
    """Mutate a serialized run doc in place: replace oversized event-payload
    strings with a short head + a length/hash marker so the durable snapshot
    stays small. Idempotent and defensive — never raises on unexpected shapes.
    """
    import hashlib

    events = doc.get("events")
    if not isinstance(events, list):
        return
    for ev in events:
        if not isinstance(ev, dict):
            continue
        payload = ev.get("payload")
        if not isinstance(payload, dict):
            continue
        for key, val in list(payload.items()):
            if (
                key in _LARGE_PAYLOAD_KEYS
                and isinstance(val, str)
                and len(val) > _MAX_PERSISTED_STR
            ):
                digest = hashlib.sha256(val.encode("utf-8")).hexdigest()[:12]
                payload[key] = val[:_MAX_PERSISTED_STR]
                payload[f"{key}__truncated"] = {
                    "full_len": len(val), "sha256_12": digest,
                }


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
    async def write_entry_strict(self, entry: LedgerEntry) -> LedgerEntry:
        """Persist an entry and surface failures for command/outbox workflows."""
        if entry.entry_type == "runtime" and entry.ambiguity_class in INVARIANT_CLASSES:
            existing = await self._find_invariant(entry.ambiguity_class, entry.slot_value_hash or "")
            if existing is not None and entry.decision_kind == "swap":
                raise InvariantWriteBlocked(
                    f"invariant precedent exists for {entry.ambiguity_class}/{entry.slot_value_hash}: "
                    f"{existing.get('resolution_text')!r}"
                )
        doc = entry.model_dump(mode="json", exclude_none=False)
        doc["id"] = entry.id
        await self._ledger.upsert_item(doc)
        return entry

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
        """Most recent precedent matching (team, class, slot_hash). Used by autopilot.

        NOTE (2026-06-20): the query intentionally does NOT use `SELECT TOP 1`.
        Empirically (debug probe against live Cosmos), `SELECT TOP 1 ... ORDER BY`
        with a partition-scoped async `query_items` returned an EMPTY iterator
        even when matching rows existed — the same WHERE + ORDER BY without TOP
        returned the rows fine. This silently killed the teaching loop: an
        operator's swap precedent was never matched, so autopilot always re-gated.
        We fetch ordered rows and take the first (most recent) in Python instead.
        """
        q = (
            "SELECT * FROM c "
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
                return from_legacy_v06_dict(item)  # first row = most recent
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
    async def save_run_cas(self, run) -> dict:
        """Refresh the authoritative ETag and conditionally replace the snapshot."""
        current = await self.get_run(run.run_id)
        if current is None or not current.get("_etag"):
            raise RuntimeError("authoritative run version unavailable")
        authoritative = type(run).model_validate(current)
        incoming = run.model_dump(mode="json")
        # Never erase replay/concurrency state committed by another command.
        incoming["command_records"] = authoritative.command_records | run.command_records
        incoming["decision_outbox"] = authoritative.decision_outbox or run.decision_outbox
        incoming["run_version"] = max(authoritative.run_version, run.run_version)
        incoming["checkpoint_version"] = max(authoritative.checkpoint_version, run.checkpoint_version)
        # Keep the persisted doc small: real codegen embeds ~9KB app + ~9KB test
        # strings (under code/app_code/test_code) plus architecture/test_plan in
        # EVERY event payload, and the whole run doc is re-PUT on every event.
        # Left unbounded the doc balloons (66KB+ and climbing) until the async
        # driver task starves/dies mid-review_scan and the run is reaped as
        # FAILED with no exception. Trim oversized payload strings out of the
        # DURABLE snapshot only — the live in-memory run keeps them for the
        # deliver stage during the run.
        _trim_run_doc_payloads(incoming)
        return await self.replace_run_strict(incoming, expected_etag=current["_etag"])

    async def save_run(self, doc) -> None:
        """Save a serialized run state. Accepts a dict OR a pydantic model.

        Phase 6.3 fix (2026-06-17): callers were passing RunState pydantic
        objects directly. dict(model) returns a dict but values stay as
        pydantic objects + enums + datetimes, which the Cosmos SDK can
        serialize partially but fails on nested pydantic objects
        (StageEvent inside events list) with "Object of type X is not
        JSON serializable". The save_run() except-Exception then swallows
        the error silently, leaving the appearance of success while the
        Cosmos doc stays at its original state.

        This was responsible for:
          - 8 zombie runs that "cleanup" failed to fix (admin endpoint
            silently no-op'd the upsert)
          - Phase 6.1 per-event saves never actually landed in Cosmos
            (every event "saved" but the doc stayed at the ingest snapshot)
          - The /api/runs list showing 0 runs after pod restart because
            in-memory _runs was empty and Cosmos had no fresh writes

        Fix: detect pydantic models and call model_dump(mode="json")
        which serializes enums to their string values + datetimes to
        ISO strings + nested pydantic objects to plain dicts. Dicts
        passed in continue to work unchanged.

        Also: log the actual error message (not just "Run save failed: %s")
        so future silent-failure regressions surface in App Insights.
        """
        try:
            # Auto-serialize pydantic models (RunState in particular)
            if hasattr(doc, "model_dump"):
                doc = doc.model_dump(mode="json")
            else:
                doc = dict(doc)
            doc["id"] = doc.get("run_id") or doc.get("id")
            if not doc["id"]:
                raise ValueError("save_run: doc must have run_id or id")
            await self._runs.upsert_item(doc)
        except Exception as exc:
            _logger.warning(
                "Run save failed (id=%s): %s: %s",
                (doc.get("id") if isinstance(doc, dict) else "?"),
                type(exc).__name__,
                exc,
            )

    async def create_run_strict(self, doc) -> dict:
        """Create a run and surface persistence/conflict failures to the caller."""
        if hasattr(doc, "model_dump"):
            payload = doc.model_dump(mode="json")
        else:
            payload = dict(doc)
        payload["id"] = payload.get("run_id") or payload.get("id")
        if not payload["id"]:
            raise ValueError("create_run_strict: doc must have run_id or id")
        return await self._runs.create_item(payload)

    async def replace_run_strict(self, doc, *, expected_etag: str) -> dict:
        """Conditionally replace a run; stale ETags remain observable conflicts."""
        if hasattr(doc, "model_dump"):
            payload = doc.model_dump(mode="json")
        else:
            payload = dict(doc)
        payload["id"] = payload.get("run_id") or payload.get("id")
        if not payload["id"]:
            raise ValueError("replace_run_strict: doc must have run_id or id")
        try:
            from azure.core import MatchConditions
            return await self._runs.replace_item(
                item=payload["id"], body=payload,
                etag=expected_etag, match_condition=MatchConditions.IfNotModified,
            )
        except ImportError:  # pragma: no cover - azure-core ships with cosmos
            return await self._runs.replace_item(
                item=payload["id"], body=payload, etag=expected_etag,
            )

    async def create_review_loop_strict(self, record: dict) -> dict:
        payload = dict(record)
        payload["id"] = payload["loop_id"]
        payload["run_id"] = payload["loop_id"]
        payload["document_type"] = "review_loop"
        return await self._runs.create_item(payload)

    async def save_review_loop_strict(self, record: dict, *, expected_etag: str) -> dict:
        payload = dict(record)
        payload["id"] = payload["loop_id"]
        payload["run_id"] = payload["loop_id"]
        payload["document_type"] = "review_loop"
        try:
            from azure.core import MatchConditions
            return await self._runs.replace_item(
                item=payload["id"], body=payload, etag=expected_etag,
                match_condition=MatchConditions.IfNotModified,
            )
        except ImportError:  # pragma: no cover
            return await self._runs.replace_item(
                item=payload["id"], body=payload, etag=expected_etag,
            )

    async def get_review_loop(self, loop_id: str) -> Optional[dict]:
        try:
            return await self._runs.read_item(item=loop_id, partition_key=loop_id)
        except CosmosResourceNotFoundError:
            return None

    async def list_review_loops(self, limit: int = 100) -> list[dict]:
        query = (
            "SELECT TOP @n * FROM c WHERE c.document_type = 'review_loop' "
            "ORDER BY c.created_at DESC"
        )
        out: list[dict] = []
        async for item in self._runs.query_items(
            query=query, parameters=[{"name": "@n", "value": limit}],
        ):
            out.append(item)
        return out

    async def query_nonterminal_runs(self, limit: int = 100) -> list[dict]:
        """Return restart candidates; callers acquire a conditional lease before work."""
        query = (
            "SELECT TOP @n * FROM c WHERE "
            "(NOT IS_DEFINED(c.document_type) OR c.document_type != 'review_loop') "
            "AND c.status IN ('running','awaiting_gate')"
        )
        out: list[dict] = []
        async for item in self._runs.query_items(
            query=query,
            parameters=[{"name": "@n", "value": limit}],
        ):
            out.append(item)
        return out

    async def get_run(self, run_id: str) -> Optional[dict]:
        try:
            return await self._runs.read_item(item=run_id, partition_key=run_id)
        except CosmosResourceNotFoundError:
            return None
        except Exception as exc:
            _logger.warning("Run read failed: %s", exc)
            return None
