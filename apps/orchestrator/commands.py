"""Pure idempotency and gate-version command guards."""
from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any

from fastapi import HTTPException, Request

from .auth import Principal
from .models import RunState


def command_key(principal: Principal, route: str, key: str) -> str:
    return f"{principal.subject}|{route}|{key}"


def request_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def begin_command(
    run: RunState, request: Request, principal: Principal, payload: Any,
    *, expected_gate_version: int | None,
) -> tuple[str, dict | None]:
    key = request.headers.get("idempotency-key", "").strip()
    if not key and principal.source == "disabled":
        # Explicit local/test compatibility. Authenticated deployments must send
        # caller-generated keys so retries remain stable across processes.
        key = f"dev-{request_hash(payload)}"
    if not key:
        raise HTTPException(400, "Idempotency-Key header is required")
    route = request.url.path
    record_key = command_key(principal, route, key)
    digest = request_hash(payload)
    existing = run.command_records.get(record_key)
    if existing:
        if existing["request_hash"] != digest:
            raise HTTPException(409, "idempotency_conflict")
        return record_key, existing.get("result")
    current_gate_version = int((run.pending_gate or {}).get("version", run.checkpoint_version))
    if expected_gate_version is not None and expected_gate_version != current_gate_version:
        raise HTTPException(409, "stale_gate_version")
    return record_key, None


def finish_command(run: RunState, record_key: str, payload: Any, result: dict) -> None:
    run.command_records[record_key] = {
        "request_hash": request_hash(payload),
        "result": result,
    }
    run.run_version += 1


async def cas_command(
    ledger, run_id: str, *, record_key: str, payload: Any, mutate,
    max_attempts: int = 4,
) -> dict:
    """Atomically apply a replay-safe command using Cosmos ETag replacement."""
    digest = request_hash(payload)
    for attempt in range(max_attempts):
        doc = await ledger.get_run(run_id)
        if doc is None:
            raise HTTPException(404, "run not found")
        etag = doc.get("_etag")
        if not etag:
            raise HTTPException(503, "authoritative run version unavailable")
        run = RunState.model_validate(doc)
        existing = run.command_records.get(record_key)
        if existing:
            if existing.get("request_hash") != digest:
                raise HTTPException(409, "idempotency_conflict")
            return existing.get("result") or {}
        result = mutate(run)
        finish_command(run, record_key, payload, result)
        try:
            await ledger.replace_run_strict(run, expected_etag=etag)
            return result
        except Exception:
            if attempt + 1 >= max_attempts:
                raise HTTPException(409, "concurrent_command_conflict")
            await asyncio.sleep(0)
    raise HTTPException(409, "concurrent_command_conflict")
