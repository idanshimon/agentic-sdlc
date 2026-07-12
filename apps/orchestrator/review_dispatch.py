"""Authenticated, replay-safe review-loop dispatch contract."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib

from pydantic import BaseModel, Field


class ReviewLoopDispatch(BaseModel):
    repo: str = Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
    pr_number: int = Field(gt=0)
    head_sha: str = Field(pattern=r"^[0-9a-fA-F]{40}$")


@dataclass(frozen=True)
class ReviewLoopIdentity:
    loop_id: str
    repo: str
    pr_number: int
    head_sha: str
    attempt: int = 1


def identity_for(dispatch: ReviewLoopDispatch) -> ReviewLoopIdentity:
    raw = f"{dispatch.repo.lower()}|{dispatch.pr_number}|{dispatch.head_sha.lower()}"
    loop_id = hashlib.sha256(raw.encode()).hexdigest()
    return ReviewLoopIdentity(
        loop_id=loop_id, repo=dispatch.repo, pr_number=dispatch.pr_number,
        head_sha=dispatch.head_sha.lower(),
    )


class ReviewLoopRegistry:
    """Process cache backed by deterministic IDs; durable store can replace it."""
    def __init__(self) -> None:
        self._items: dict[str, dict] = {}

    def get_or_create(self, identity: ReviewLoopIdentity, actor: str) -> tuple[dict, bool]:
        existing = self._items.get(identity.loop_id)
        if existing is not None:
            return existing, False
        record = {
            "loop_id": identity.loop_id,
            "repo": identity.repo,
            "pr_number": identity.pr_number,
            "head_sha": identity.head_sha,
            "attempt": identity.attempt,
            "actor": actor,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "disposition": "IN_PROGRESS",
        }
        self._items[identity.loop_id] = record
        return record, True
