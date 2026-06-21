"""config_writer — governed PR write-back for the editing plane (#3).

The Agents / Bundles / Prompts editors are real config edits to files that the
pipeline reads. Per the four-plane governance model, an edit must NOT silently
mutate running behaviour — it goes through a PR so the owning committee reviews
it (CODEOWNERS already gates these paths). This module is the shared core every
editor's save endpoint calls.

Implementation: the **GitHub REST API over HTTPS** (httpx). This is the correct
approach for a stateless container — the deployed orchestrator is a bare file
tree (COPY, no .git / git / gh), so the earlier git-subprocess approach could
never work there. REST needs only a token:

  1. GET base branch HEAD sha            (git/refs/heads/<base>)
  2. POST a new branch ref off that sha  (git/refs)
  3. GET existing file sha if present    (contents/<path>?ref=<base>)
  4. PUT file content on the new branch   (contents/<path>)
  5. POST a pull request                  (pulls)
  6. POST labels                          (issues/<n>/labels)  [best-effort]

Auth: a token from GH_TOKEN / GITHUB_TOKEN / CONFIG_GH_TOKEN with `repo` scope
(or a fine-grained token with Contents:write + Pull requests:write). When no
token is configured the writer raises a clean ConfigWriteError so the endpoint
returns an honest 422 ("PR write-back not wired here") — never a 500 or a
fabricated success.

Safety: writes are confined to an allowlist of config roots (.github/agents,
standards-bundles, prompts). A path escaping those via '..' or an absolute path
is refused — the editor cannot be tricked into writing arbitrary repo files.

Bundles are PR-only (no live apply) by design — live-editing the compliance
standards would bypass committee review, which is the whole governance story.
"""
from __future__ import annotations

import base64
import logging
import os
import re
from dataclasses import dataclass
from typing import Optional

import httpx

_logger = logging.getLogger("orchestrator.config_writer")

# owner/repo to open PRs on. Default to the canonical repo.
_TARGET_REPO = os.environ.get("CONFIG_TARGET_REPO", "idanshimon/agentic-sdlc")
_BASE_BRANCH = os.environ.get("CONFIG_BASE_BRANCH", "main")
_DRY_RUN = os.environ.get("CONFIG_WRITE_DRY_RUN", "").lower() in ("1", "true", "yes")

# Only these roots may be written by the editing plane. Anything else is refused.
_ALLOWED_ROOTS = (".github/agents", "standards-bundles", "prompts")

_API = "https://api.github.com"


class ConfigWriteError(Exception):
    """Raised when a config write/PR cannot be completed."""


@dataclass
class ConfigWriteResult:
    ok: bool
    pr_url: Optional[str]
    branch: str
    path: str
    dry_run: bool
    message: str


def _token() -> Optional[str]:
    """Resolve a GitHub token from the environment, or None if unconfigured."""
    for var in ("CONFIG_GH_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"):
        val = os.environ.get(var)
        if val and val.strip():
            return val.strip()
    return None


def _validate_path(rel_path: str) -> str:
    """Confirm rel_path is a clean repo-relative path under an allowed config
    root. Returns the normalized path. Refuses absolute paths and '..' escapes."""
    if rel_path.startswith("/"):
        raise ConfigWriteError(f"absolute paths not allowed: {rel_path!r}")
    # Normalize without touching the filesystem (the file may not exist locally).
    parts: list[str] = []
    for seg in rel_path.split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            raise ConfigWriteError(f"path escapes repo root: {rel_path!r}")
        parts.append(seg)
    norm = "/".join(parts)
    if not any(norm.startswith(root) for root in _ALLOWED_ROOTS):
        raise ConfigWriteError(
            f"path {rel_path!r} not under an allowed config root "
            f"({', '.join(_ALLOWED_ROOTS)})"
        )
    return norm


def _slug(s: str, maxlen: int = 40) -> str:
    s = re.sub(r"[^a-zA-Z0-9._-]+", "-", s).strip("-").lower()
    return s[:maxlen] or "edit"


async def _gh(
    client: httpx.AsyncClient, method: str, path: str, **kw
) -> httpx.Response:
    """Call the GitHub API, raising ConfigWriteError with a useful message on
    any non-2xx response (callers decide which statuses are tolerable first)."""
    resp = await client.request(method, path, **kw)
    return resp


async def write_config_pr(
    rel_path: str,
    content: str,
    commit_message: str,
    pr_title: str,
    pr_body: str = "",
    labels: Optional[list[str]] = None,
    branch_prefix: str = "config-edit",
) -> ConfigWriteResult:
    """Write `content` to `rel_path` on a new branch and open a PR via the
    GitHub REST API. Returns the PR URL. Raises ConfigWriteError on any failure
    (caller maps to HTTP 422)."""
    norm = _validate_path(rel_path)
    branch = f"{branch_prefix}/{_slug(commit_message)}-{os.urandom(3).hex()}"
    labels = labels or ["config-edit"]

    if _DRY_RUN:
        _logger.info("DRY-RUN write_config_pr path=%s branch=%s", norm, branch)
        return ConfigWriteResult(
            ok=True, pr_url=None, branch=branch, path=norm, dry_run=True,
            message=f"DRY-RUN: would write {norm} and open PR {pr_title!r}",
        )

    token = _token()
    if not token:
        raise ConfigWriteError(
            "no GitHub token configured (set GH_TOKEN with repo scope as a "
            "container secret) — PR write-back is not wired in this environment"
        )

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    repo_base = f"{_API}/repos/{_TARGET_REPO}"

    async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
        # 1. base branch HEAD sha
        r = await _gh(client, "GET", f"{repo_base}/git/refs/heads/{_BASE_BRANCH}")
        if r.status_code != 200:
            raise ConfigWriteError(
                f"could not read base branch {_BASE_BRANCH!r}: "
                f"HTTP {r.status_code} {r.text[:200]}"
            )
        base_sha = r.json()["object"]["sha"]

        # 2. create the new branch ref
        r = await _gh(client, "POST", f"{repo_base}/git/refs", json={
            "ref": f"refs/heads/{branch}", "sha": base_sha,
        })
        if r.status_code not in (200, 201):
            raise ConfigWriteError(
                f"could not create branch {branch!r}: "
                f"HTTP {r.status_code} {r.text[:200]}"
            )

        # 3. existing file sha (PUT requires it when updating an existing file)
        existing_sha: Optional[str] = None
        r = await _gh(client, "GET", f"{repo_base}/contents/{norm}",
                      params={"ref": _BASE_BRANCH})
        if r.status_code == 200:
            existing_sha = r.json().get("sha")
        elif r.status_code not in (404,):
            raise ConfigWriteError(
                f"could not check existing file: HTTP {r.status_code} {r.text[:200]}"
            )

        # 4. PUT the file content on the new branch
        put_body = {
            "message": commit_message,
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            "branch": branch,
        }
        if existing_sha:
            put_body["sha"] = existing_sha
        r = await _gh(client, "PUT", f"{repo_base}/contents/{norm}", json=put_body)
        if r.status_code not in (200, 201):
            raise ConfigWriteError(
                f"could not write file {norm!r}: HTTP {r.status_code} {r.text[:200]}"
            )

        # 5. open the PR
        r = await _gh(client, "POST", f"{repo_base}/pulls", json={
            "title": pr_title,
            "head": branch,
            "base": _BASE_BRANCH,
            "body": pr_body or commit_message,
        })
        if r.status_code not in (200, 201):
            raise ConfigWriteError(
                f"could not open PR: HTTP {r.status_code} {r.text[:200]}"
            )
        pr = r.json()
        pr_url = pr.get("html_url")
        pr_number = pr.get("number")

        # 6. labels — best-effort; a label failure must not fail the PR
        if pr_number and labels:
            try:
                await _gh(client, "POST",
                          f"{repo_base}/issues/{pr_number}/labels",
                          json={"labels": labels})
            except Exception as exc:  # pragma: no cover - best effort
                _logger.warning("label add failed (non-fatal): %s", exc)

    _logger.info("opened config PR via REST: %s (%s)", pr_url, norm)
    return ConfigWriteResult(
        ok=True, pr_url=pr_url, branch=branch, path=norm, dry_run=False,
        message=f"Opened PR for {norm}",
    )
