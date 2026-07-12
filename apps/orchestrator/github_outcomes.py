"""Publish idempotent GitHub check/comment outcomes for an exact PR head."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PublishedOutcome:
    check_id: int | None
    check_url: str | None
    comment_id: int | None
    comment_url: str | None


async def publish_review_outcome(
    *, client: Any, repo: str, pr_number: int, head_sha: str,
    token: str, disposition: str, summary: str,
) -> PublishedOutcome:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    conclusion = {
        "MERGED": "success", "PASSED_AWAITING_MERGE": "neutral",
        "ADVISORY": "neutral", "ESCALATED": "action_required", "FAILED": "failure",
    }.get(disposition)
    check = await client.post(
        f"https://api.github.com/repos/{repo}/check-runs", headers=headers,
        json={
            "name": "agentic-sdlc/review-loop", "head_sha": head_sha,
            "status": "completed" if conclusion else "in_progress",
            **({"conclusion": conclusion} if conclusion else {}),
            "output": {"title": disposition, "summary": summary[:65535]},
        },
    )
    if check.status_code not in (200, 201):
        raise RuntimeError(f"check publication failed: HTTP {check.status_code}")
    check_data = check.json()

    marker = f"<!-- agentic-sdlc-review-loop:{head_sha} -->"
    comments = await client.get(
        f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments",
        headers=headers, params={"per_page": 100},
    )
    existing = next((c for c in comments.json() if marker in c.get("body", "")), None) if comments.status_code == 200 else None
    body = f"{marker}\n## Agentic SDLC review: {disposition}\n\n{summary}"
    if existing:
        comment = await client.patch(existing["url"], headers=headers, json={"body": body})
    else:
        comment = await client.post(
            f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments",
            headers=headers, json={"body": body},
        )
    if comment.status_code not in (200, 201):
        raise RuntimeError(f"comment publication failed: HTTP {comment.status_code}")
    comment_data = comment.json()
    return PublishedOutcome(
        check_data.get("id"), check_data.get("html_url"),
        comment_data.get("id"), comment_data.get("html_url"),
    )
