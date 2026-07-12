"""ExecutionInputStore contract tests."""
from __future__ import annotations

import asyncio

import pytest

from apps.orchestrator.execution_store import ExecutionInputStore, InputIntegrityError


class Download:
    def __init__(self, content: bytes): self.content = content
    async def readall(self): return self.content


class Blob:
    def __init__(self, name: str, store: dict[str, bytes]):
        self.name, self.store = name, store
        self.url = f"https://stagenticab9963.blob.core.windows.net/artifacts/{name}"
    async def upload_blob(self, content, **kwargs): self.store[self.name] = bytes(content)
    async def download_blob(self): return Download(self.store[self.name])


class Container:
    def __init__(self): self.store: dict[str, bytes] = {}
    async def create_container(self): return None
    def get_blob_client(self, name): return Blob(name, self.store)


class Service:
    def __init__(self): self.container = Container()
    def get_container_client(self, name): return self.container


def run(coro): return asyncio.run(coro)


def test_input_round_trip_verifies_hash():
    store = ExecutionInputStore(service=Service(), credential=object())
    ref, digest = run(store.put("run-1", b"synthetic PRD"))
    assert run(store.get(ref, digest)) == b"synthetic PRD"


def test_input_hash_mismatch_fails_closed():
    store = ExecutionInputStore(service=Service(), credential=object())
    ref, _ = run(store.put("run-2", b"synthetic PRD"))
    with pytest.raises(InputIntegrityError, match="hash mismatch"):
        run(store.get(ref, "0" * 64))
