"""decisions.md builder — immutable per-run artifact, written to Blob 'decisions'.

Design refs (design.md §3 + §7 storage decoupling):
  * Human-readable companion to the typed ledger (Assessor never reads this file)
  * One blob per run_id, signature line per entry binds resolution to actor + ts
  * Immutability is enforced by writing only once at run completion and using a
    content-addressed blob name; we do NOT mutate existing blobs.
"""
from __future__ import annotations
import hashlib
import logging
from datetime import datetime, timezone

from azure.identity.aio import DefaultAzureCredential
from azure.storage.blob.aio import BlobServiceClient

from .config import settings
from .models import RunState

_logger = logging.getLogger("orchestrator.decisions_md")


def _sign(actor: str, resolution: str, ts: str) -> str:
    digest = hashlib.sha256(f"{actor}|{resolution}|{ts}|{settings.signer_identity}"
                            .encode()).hexdigest()[:16]
    return f"sig:{digest} by:{actor} at:{ts} signer:{settings.signer_identity}"


def render(run: RunState) -> str:
    """Render the markdown body for a run. See design.md §3 (immutable, signed)."""
    lines: list[str] = [
        f"# decisions.md — run {run.run_id}",
        f"_team: {run.team_id} · created: {run.created_at} · status: {run.status}_",
        "",
        "## Resolver decisions",
        "",
    ]
    cards_by_id = {c.card_id: c for c in run.cards}
    if not run.decisions:
        lines.append("_(no human gate decisions recorded)_")
    for d in run.decisions:
        card = cards_by_id.get(d.card_id or "")
        title = card.title if card else "(stage-level approval)"
        klass = card.ambiguity_class if card else "n/a"
        ts = datetime.now(timezone.utc).isoformat()
        lines += [
            f"### {title}",
            f"- class: `{klass}`",
            f"- decision: **{d.decision_kind}**",
            f"- note: {d.resolution_text or '_(none)_'}",
            f"- {_sign(d.actor, d.resolution_text, ts)}",
            "",
        ]
    lines += ["## Stage events", ""]
    for ev in run.events:
        lines.append(f"- [{ev.ts}] {ev.stage}/{ev.status} — {ev.message}")
    return "\n".join(lines) + "\n"


async def write_decisions_md(run: RunState) -> str:
    """Write once, return blob URL. Idempotent via run_id-keyed blob name."""
    body = render(run)
    blob_name = f"{run.run_id}/decisions.md"
    cred = DefaultAzureCredential()
    svc = BlobServiceClient(account_url=settings.storage_account_url, credential=cred)
    try:
        container = svc.get_container_client(settings.storage_decisions_container)
        try:
            await container.create_container()
        except Exception:
            pass
        blob = container.get_blob_client(blob_name)
        # overwrite=False enforces immutability semantics at the blob layer.
        await blob.upload_blob(body.encode("utf-8"), overwrite=False)
        url = blob.url
    except Exception as exc:
        _logger.warning("decisions.md upload failed (likely exists or perms): %s", exc)
        url = f"{settings.storage_account_url}/{settings.storage_decisions_container}/{blob_name}"
    finally:
        await svc.close()
        await cred.close()
    return url
