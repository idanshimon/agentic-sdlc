"""ExecutionInputStore contract tests."""
from __future__ import annotations

import asyncio
import importlib
import os

import pytest


@pytest.fixture(autouse=True)
def _pinned_storage_config(monkeypatch):
    """Pin a concrete storage account and reload config + execution_store so
    both bind the SAME settings singleton. Guards against cross-module reload
    pollution (test_config_storage reloads config with different env). The
    module no longer has a hardcoded storage default, so without this the
    container-prefix integrity check would see an empty URL and fail."""
    monkeypatch.setenv("STORAGE_ACCOUNT_NAME", "stexample")
    monkeypatch.delenv("STORAGE_ACCOUNT_URL", raising=False)
    import apps.orchestrator.config as config
    importlib.reload(config)
    import apps.orchestrator.execution_store as es
    importlib.reload(es)
    yield
    # Restore real-env config for any later module.
    importlib.reload(config)


def _es():
    """Import the freshly-reloaded execution_store symbols inside a test."""
    import apps.orchestrator.execution_store as es
    return es.ExecutionInputStore, es.InputIntegrityError


def _settings():
    import apps.orchestrator.config as config
    return config.settings


class Download:
    def __init__(self, content: bytes): self.content = content
    async def readall(self): return self.content


class Blob:
    def __init__(self, name: str, store: dict[str, bytes]):
        self.name, self.store = name, store
        # Derive from the configured account so the store's container-prefix
        # integrity check (ref must start with <url>/<artifacts>/) is satisfied.
        s = _settings()
        self.url = f"{s.storage_account_url}/{s.storage_artifacts_container}/{name}"
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
    ExecutionInputStore, _ = _es()
    store = ExecutionInputStore(service=Service(), credential=object())
    ref, digest = run(store.put("run-1", b"synthetic PRD"))
    assert run(store.get(ref, digest)) == b"synthetic PRD"


def test_input_hash_mismatch_fails_closed():
    ExecutionInputStore, InputIntegrityError = _es()
    store = ExecutionInputStore(service=Service(), credential=object())
    ref, _ = run(store.put("run-2", b"synthetic PRD"))
    with pytest.raises(InputIntegrityError, match="hash mismatch"):
        run(store.get(ref, "0" * 64))
