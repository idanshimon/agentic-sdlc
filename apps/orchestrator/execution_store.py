"""Durable PRD input storage with content-hash verification.

Raw input is stored in the existing artifacts Blob container, never in decision
ledger entries. The reference is persisted on RunState for restart recovery.
"""
from __future__ import annotations

import hashlib

from azure.identity.aio import DefaultAzureCredential
from azure.storage.blob.aio import BlobServiceClient

from .config import settings


class InputIntegrityError(RuntimeError):
    pass


class ExecutionInputStore:
    def __init__(self, *, service=None, credential=None) -> None:
        self._credential = credential
        self._service = service

    async def put(self, run_id: str, content: bytes) -> tuple[str, str]:
        digest = hashlib.sha256(content).hexdigest()
        blob_name = f"{run_id}/input/prd"
        cred = self._credential or DefaultAzureCredential()
        service = self._service or BlobServiceClient(
            account_url=settings.storage_account_url, credential=cred,
        )
        try:
            container = service.get_container_client(settings.storage_artifacts_container)
            try:
                await container.create_container()
            except Exception:
                pass
            blob = container.get_blob_client(blob_name)
            await blob.upload_blob(content, overwrite=False, metadata={"sha256": digest})
            return blob.url, digest
        finally:
            if self._service is None:
                await service.close()
            if self._credential is None:
                await cred.close()

    async def get(self, ref: str, expected_sha256: str) -> bytes:
        cred = self._credential or DefaultAzureCredential()
        service = self._service or BlobServiceClient(
            account_url=settings.storage_account_url, credential=cred,
        )
        try:
            # ref is the canonical blob URL produced by put().
            prefix = f"{settings.storage_account_url.rstrip('/')}/{settings.storage_artifacts_container}/"
            if not ref.startswith(prefix):
                raise InputIntegrityError("input reference is outside the configured artifacts container")
            blob_name = ref[len(prefix):]
            container = service.get_container_client(settings.storage_artifacts_container)
            blob = container.get_blob_client(blob_name)
            stream = await blob.download_blob()
            content = await stream.readall()
            actual = hashlib.sha256(content).hexdigest()
            if actual != expected_sha256:
                raise InputIntegrityError(
                    f"input hash mismatch: expected {expected_sha256}, received {actual}"
                )
            return content
        finally:
            if self._service is None:
                await service.close()
            if self._credential is None:
                await cred.close()
