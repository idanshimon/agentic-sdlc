"""deliver_pr — open a REAL GitHub PR with the artifacts a pipeline run produced.

This replaces the old stage_deliver behaviour, which either (demo runs) emitted
two random Math.random() PR numbers at a repo that doesn't exist, or (real runs)
fell back to a fabricated dev.azure.com URL when the MCP push wasn't configured.
Both produced 404 links. Per "no fakes in production": this module opens a real
PR or returns nothing — never an invented URL.

Mechanism: the GitHub Git Data API, so all run artifacts land in ONE commit:
  1. GET base branch HEAD sha + its tree sha
  2. POST a blob per file                       (git/blobs)
  3. POST a tree referencing the blobs           (git/trees, base_tree=<base>)
  4. POST a commit pointing at the tree          (git/commits)
  5. POST a new branch ref at that commit         (git/refs)
  6. POST a pull request                          (pulls)

Target repo: DELIVER_TARGET_REPO ("owner/repo"). Delivery PRs carry generated
application code, so they MUST go to a separate target repo — never the platform
repo. When DELIVER_TARGET_REPO is unset, delivery is considered not configured
and open_delivery_pr returns ok=False with a clear reason (the caller surfaces an
honest "no delivery backend configured" event, not a fake URL).

Auth: reuses config_writer._token() (GH_TOKEN / GITHUB_TOKEN / CONFIG_GH_TOKEN).
"""
from __future__ import annotations

import base64
import logging
import os
from dataclasses import dataclass, field
from typing import Optional

import httpx

from .config_writer import _token

_logger = logging.getLogger("orchestrator.deliver_pr")

_API = "https://api.github.com"
# Explicit target wins; otherwise a convention default is derived from the token
# owner at call time (see _resolve_target_repo). "owner/repo".
_TARGET_REPO = os.environ.get("DELIVER_TARGET_REPO", "").strip()
_DEFAULT_REPO_NAME = os.environ.get("DELIVER_DEFAULT_REPO_NAME", "agentic-sdlc-delivery").strip()
_BASE_BRANCH = os.environ.get("DELIVER_BASE_BRANCH", "main")
_DRY_RUN = os.environ.get("DELIVER_DRY_RUN", "").lower() in ("1", "true", "yes")
# Allow auto-creating the deliveries repo when missing (needs a token with repo
# creation rights). Off by default; the demo enables it.
_AUTO_CREATE = os.environ.get("DELIVER_AUTO_CREATE", "").lower() in ("1", "true", "yes")


def _delivery_token() -> Optional[str]:
    """Token for delivery PRs. Prefers a delivery-specific token so it can be
    scoped/rotated independently of the config-editor token, then falls back to
    the shared GH_TOKEN chain."""
    for var in ("DELIVER_GH_TOKEN", "DELIVERY_GH_TOKEN"):
        val = os.environ.get(var)
        if val and val.strip():
            return val.strip()
    return _token()  # GH_TOKEN / GITHUB_TOKEN / CONFIG_GH_TOKEN


@dataclass
class DeliverResult:
    ok: bool
    pr_url: Optional[str]
    branch: Optional[str]
    reason: str  # human-readable; on failure this is why (surfaced to the operator)
    files: list[str] = field(default_factory=list)


def delivery_configured() -> bool:
    """True when a delivery backend can be resolved (a token is present; the repo
    is either explicit or will be derived/auto-created)."""
    return bool(_delivery_token())


async def _token_owner(client: httpx.AsyncClient) -> Optional[str]:
    """The login of the authenticated token (for the convention default repo)."""
    r = await client.get(f"{_API}/user")
    if r.status_code == 200:
        return r.json().get("login")
    return None


async def _resolve_target_repo(client: httpx.AsyncClient) -> Optional[str]:
    """Pick the delivery repo: explicit DELIVER_TARGET_REPO wins; otherwise
    <token-owner>/<default-name>. Returns 'owner/repo' or None if undeterminable."""
    if _TARGET_REPO:
        return _TARGET_REPO
    owner = await _token_owner(client)
    if not owner:
        return None
    return f"{owner}/{_DEFAULT_REPO_NAME}"


async def _ensure_repo(client: httpx.AsyncClient, repo: str) -> tuple[bool, str]:
    """Ensure `repo` exists with a base branch to PR against. Creates it (when
    DELIVER_AUTO_CREATE) and seeds an initial README commit if empty.
    Returns (ok, reason)."""
    owner, name = repo.split("/", 1)
    r = await client.get(f"{_API}/repos/{repo}")
    if r.status_code == 404:
        if not _AUTO_CREATE:
            return False, (f"delivery repo {repo} does not exist (set "
                           f"DELIVER_AUTO_CREATE=1 to create it automatically, "
                           f"or create it manually)")
        # Create under the authed user. (Org repos would need a different endpoint.)
        rc = await client.post(f"{_API}/user/repos", json={
            "name": name, "private": True, "auto_init": True,
            "description": "agentic-sdlc pipeline delivery PRs",
        })
        if rc.status_code not in (200, 201):
            return False, f"could not create repo {repo}: HTTP {rc.status_code} {rc.text[:160]}"
    elif r.status_code != 200:
        return False, f"could not read repo {repo}: HTTP {r.status_code} {r.text[:160]}"

    # Ensure the base branch has at least one commit (empty repo → seed README).
    rb = await client.get(f"{_API}/repos/{repo}/git/refs/heads/{_BASE_BRANCH}")
    if rb.status_code == 200:
        return True, "ready"
    if rb.status_code in (404, 409):
        readme = base64.b64encode(
            b"# agentic-sdlc deliveries\n\nGenerated pull requests from pipeline "
            b"runs land here. Each run opens a branch `agentic/<run-id>` with the "
            b"produced code, tests, architecture, and decision record.\n"
        ).decode()
        rs = await client.put(f"{_API}/repos/{repo}/contents/README.md", json={
            "message": "chore: initialize deliveries repo",
            "content": readme, "branch": _BASE_BRANCH,
        })
        if rs.status_code in (200, 201):
            return True, "initialized"
        return False, f"could not initialize base branch: HTTP {rs.status_code} {rs.text[:160]}"
    return False, f"could not read base branch: HTTP {rb.status_code} {rb.text[:160]}"


async def open_delivery_pr(
    *,
    run_id: str,
    team_id: str,
    files: list[dict],          # [{"path": "...", "content": "..."}]
    title: str,
    body: str,
) -> DeliverResult:
    """Push `files` to a new branch on DELIVER_TARGET_REPO and open a PR.

    Returns DeliverResult(ok=True, pr_url=...) on success. On any
    misconfiguration or failure returns ok=False with a reason — and NEVER a
    fabricated URL. The caller decides how to surface the failure.
    """
    branch = f"agentic/{run_id[:8]}"
    file_paths = [f["path"] for f in files]

    token = _delivery_token()
    if not token:
        return DeliverResult(
            ok=False, pr_url=None, branch=None,
            reason="no GitHub token configured (set DELIVER_GH_TOKEN or GH_TOKEN) "
                   "— cannot open a real PR",
            files=file_paths,
        )

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    try:
        async with httpx.AsyncClient(headers=headers, timeout=60.0) as client:
            # 0. resolve the target repo (explicit, or <owner>/<default-name>)
            repo = await _resolve_target_repo(client)
            if not repo:
                return DeliverResult(
                    ok=False, pr_url=None, branch=None,
                    reason="could not resolve a delivery repo (set DELIVER_TARGET_REPO, "
                           "or check the token is valid so the default owner/agentic-sdlc-"
                           "delivery can be derived)",
                    files=file_paths,
                )
            repo_base = f"{_API}/repos/{repo}"

            if _DRY_RUN:
                return DeliverResult(
                    ok=True, pr_url=None, branch=branch,
                    reason=f"DRY-RUN: would push {len(files)} files to {repo}@{branch} and open a PR",
                    files=file_paths,
                )

            # 0b. ensure the repo exists + has a base branch to PR against
            ok, why = await _ensure_repo(client, repo)
            if not ok:
                return DeliverResult(
                    ok=False, pr_url=None, branch=None, reason=why, files=file_paths,
                )

            # 1. base ref → commit sha → tree sha
            r = await client.get(f"{repo_base}/git/refs/heads/{_BASE_BRANCH}")
            if r.status_code != 200:
                return DeliverResult(
                    ok=False, pr_url=None, branch=None,
                    reason=f"could not read base branch {_BASE_BRANCH!r} on "
                           f"{repo}: HTTP {r.status_code} {r.text[:160]}",
                    files=file_paths,
                )
            base_commit_sha = r.json()["object"]["sha"]
            rc = await client.get(f"{repo_base}/git/commits/{base_commit_sha}")
            if rc.status_code != 200:
                return DeliverResult(
                    ok=False, pr_url=None, branch=None,
                    reason=f"could not read base commit: HTTP {rc.status_code} {rc.text[:160]}",
                    files=file_paths,
                )
            base_tree_sha = rc.json()["tree"]["sha"]

            # 2. blob per file
            tree_entries = []
            for f in files:
                rb = await client.post(f"{repo_base}/git/blobs", json={
                    "content": f["content"], "encoding": "utf-8",
                })
                if rb.status_code not in (200, 201):
                    return DeliverResult(
                        ok=False, pr_url=None, branch=None,
                        reason=f"blob create failed for {f['path']!r}: "
                               f"HTTP {rb.status_code} {rb.text[:160]}",
                        files=file_paths,
                    )
                tree_entries.append({
                    "path": f["path"], "mode": "100644", "type": "blob",
                    "sha": rb.json()["sha"],
                })

            # 3. tree on top of the base tree
            rt = await client.post(f"{repo_base}/git/trees", json={
                "base_tree": base_tree_sha, "tree": tree_entries,
            })
            if rt.status_code not in (200, 201):
                return DeliverResult(
                    ok=False, pr_url=None, branch=None,
                    reason=f"tree create failed: HTTP {rt.status_code} {rt.text[:160]}",
                    files=file_paths,
                )
            new_tree_sha = rt.json()["sha"]

            # 4. commit
            rcm = await client.post(f"{repo_base}/git/commits", json={
                "message": f"agentic-sdlc run {run_id[:8]} (team {team_id})",
                "tree": new_tree_sha, "parents": [base_commit_sha],
            })
            if rcm.status_code not in (200, 201):
                return DeliverResult(
                    ok=False, pr_url=None, branch=None,
                    reason=f"commit create failed: HTTP {rcm.status_code} {rcm.text[:160]}",
                    files=file_paths,
                )
            new_commit_sha = rcm.json()["sha"]

            # 5. branch ref
            rr = await client.post(f"{repo_base}/git/refs", json={
                "ref": f"refs/heads/{branch}", "sha": new_commit_sha,
            })
            if rr.status_code not in (200, 201):
                # 422 = ref exists; update it instead so re-runs don't hard-fail.
                ru = await client.patch(f"{repo_base}/git/refs/heads/{branch}", json={
                    "sha": new_commit_sha, "force": True,
                })
                if ru.status_code not in (200, 201):
                    return DeliverResult(
                        ok=False, pr_url=None, branch=None,
                        reason=f"branch ref create/update failed: "
                               f"HTTP {rr.status_code}/{ru.status_code} {rr.text[:120]}",
                        files=file_paths,
                    )

            # 6. PR (tolerate "already exists" — return the existing one)
            rp = await client.post(f"{repo_base}/pulls", json={
                "title": title, "head": branch, "base": _BASE_BRANCH, "body": body,
            })
            if rp.status_code in (200, 201):
                pr_url = rp.json().get("html_url")
            elif rp.status_code == 422 and "A pull request already exists" in rp.text:
                # find the open PR for this head
                rl = await client.get(f"{repo_base}/pulls", params={
                    "head": f"{repo.split('/')[0]}:{branch}", "state": "open",
                })
                arr = rl.json() if rl.status_code == 200 else []
                pr_url = arr[0]["html_url"] if arr else None
                if not pr_url:
                    return DeliverResult(
                        ok=False, pr_url=None, branch=branch,
                        reason=f"PR exists for {branch} but could not be resolved",
                        files=file_paths,
                    )
            else:
                return DeliverResult(
                    ok=False, pr_url=None, branch=branch,
                    reason=f"PR create failed: HTTP {rp.status_code} {rp.text[:160]}",
                    files=file_paths,
                )

    except Exception as exc:
        _logger.exception("delivery PR failed for run %s", run_id)
        return DeliverResult(
            ok=False, pr_url=None, branch=branch,
            reason=f"delivery error: {exc}",
            files=file_paths,
        )

    _logger.info("opened delivery PR for run %s: %s", run_id, pr_url)
    return DeliverResult(ok=True, pr_url=pr_url, branch=branch,
                         reason=f"Opened PR on {repo}", files=file_paths)
