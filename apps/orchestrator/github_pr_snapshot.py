"""Fetch and verify exact GitHub pull-request head snapshots."""
from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any


class SnapshotError(RuntimeError):
    pass


@dataclass(frozen=True)
class PullRequestSnapshot:
    repo: str
    pr_number: int
    head_sha: str
    files: dict[str, str]


async def fetch_pr_snapshot(
    *, repo: str, pr_number: int, expected_head_sha: str,
    token: str, client: Any, max_file_bytes: int = 1_000_000,
) -> PullRequestSnapshot:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    base = f"https://api.github.com/repos/{repo}"
    pr = await client.get(f"{base}/pulls/{pr_number}", headers=headers)
    if pr.status_code != 200:
        raise SnapshotError(f"pull request read failed: HTTP {pr.status_code}")
    current_sha = str(pr.json().get("head", {}).get("sha", "")).lower()
    if current_sha != expected_head_sha.lower():
        raise SnapshotError("stale_head_sha")

    changed: list[dict] = []
    page = 1
    while True:
        response = await client.get(
            f"{base}/pulls/{pr_number}/files", headers=headers,
            params={"per_page": 100, "page": page},
        )
        if response.status_code != 200:
            raise SnapshotError(f"pull files read failed: HTTP {response.status_code}")
        items = response.json()
        changed.extend(items)
        if len(items) < 100:
            break
        page += 1

    files: dict[str, str] = {}
    for item in changed:
        if item.get("status") == "removed":
            continue
        path = item.get("filename", "")
        blob = await client.get(f"{base}/contents/{path}", headers=headers, params={"ref": current_sha})
        if blob.status_code != 200:
            raise SnapshotError(f"content read failed for {path}: HTTP {blob.status_code}")
        data = blob.json()
        if data.get("encoding") != "base64":
            raise SnapshotError(f"unsupported content encoding for {path}")
        raw = base64.b64decode(str(data.get("content", "")).replace("\n", ""), validate=True)
        if len(raw) > max_file_bytes:
            raise SnapshotError(f"file too large: {path}")
        try:
            files[path] = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SnapshotError(f"binary file unsupported: {path}") from exc
    return PullRequestSnapshot(repo, pr_number, current_sha, files)
