"""merge_pr — the net-new GitHub merge primitive for the autonomous review loop.

deliver_pr.py only OPENS pull requests; swap-deliver-ado-to-github states the
orchestrator never merges. Tier-A auto-merge (add-autonomous-review-loop) needs
a real `PUT /repos/{repo}/pulls/{n}/merge`, and it must be
BRANCH-PROTECTION-AWARE: a merge blocked by required checks / reviews / a
conflict MUST escalate explicitly, never report a silent success. A silent
no-op would violate the never-silent-merge invariant.

The HTTP client is injectable so the whole primitive is testable with zero real
GitHub; in production it falls back to httpx.AsyncClient.
"""
from __future__ import annotations

import dataclasses
import logging
import os
from typing import Any, Optional

_logger = logging.getLogger(__name__)

_GH_API = os.environ.get("GITHUB_API_BASE", "https://api.github.com").rstrip("/")


@dataclasses.dataclass
class MergeResult:
    merged: bool
    sha: Optional[str] = None
    escalate: bool = False
    reason: str = ""


async def merge_pull_request(
    *,
    repo: str,
    pr_number: int,
    token: str,
    client: Any = None,
    merge_method: str = "merge",
    commit_title: Optional[str] = None,
    expected_head_sha: Optional[str] = None,
) -> MergeResult:
    """Merge a PR via the REST API. Branch-protection-aware, fail-loud.

    Returns MergeResult. On any non-success the result carries escalate=True and
    a human-readable reason — the loop controller turns that into a
    `loop_escalated` ledger entry rather than pretending the merge happened.

    Status handling (GitHub PR-merge API):
      * 200 -> merged (sha in body)
      * 405 -> not mergeable / blocked by branch protection -> ESCALATE
      * 409 -> head modified / conflict -> ESCALATE
      * 401/403 -> auth / permission -> ESCALATE
      * anything else -> ESCALATE (fail closed)
    """
    if not token:
        return MergeResult(
            merged=False, escalate=True,
            reason="no GitHub token configured (set DELIVER_GH_TOKEN / GH_TOKEN) "
                   "— refusing to claim a merge that did not happen",
        )

    url = f"{_GH_API}/repos/{repo}/pulls/{pr_number}/merge"
    payload: dict[str, Any] = {"merge_method": merge_method}
    if expected_head_sha:
        payload["sha"] = expected_head_sha
    if commit_title:
        payload["commit_title"] = commit_title
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    owns_client = client is None
    if owns_client:
        import httpx
        client = httpx.AsyncClient(timeout=30.0)

    try:
        resp = await client.put(url, json=payload, headers=headers)
    except Exception as exc:  # network / transport failure -> escalate, never silent
        _logger.exception("merge_pull_request transport error: %s", exc)
        return MergeResult(merged=False, escalate=True,
                           reason=f"merge request failed to send: {exc}")
    finally:
        if owns_client:
            try:
                await client.aclose()
            except Exception:
                pass

    status = getattr(resp, "status_code", 0)
    body = _safe_json(resp)

    if status == 200:
        return MergeResult(merged=True, sha=body.get("sha"), escalate=False,
                           reason="merged")

    if status == 405:
        return MergeResult(
            merged=False, escalate=True,
            reason=f"not mergeable — blocked by branch protection or failing "
                   f"required checks: {body.get('message', 'Method Not Allowed')}",
        )
    if status == 409:
        return MergeResult(
            merged=False, escalate=True,
            reason=f"merge conflict / head modified: {body.get('message', 'Conflict')}",
        )
    if status in (401, 403):
        return MergeResult(
            merged=False, escalate=True,
            reason=f"auth/permission denied ({status}): {body.get('message', '')}",
        )

    # Fail closed on anything unexpected.
    return MergeResult(
        merged=False, escalate=True,
        reason=f"unexpected merge response {status}: {body.get('message', '')}",
    )


def _safe_json(resp: Any) -> dict:
    try:
        data = resp.json()
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}
