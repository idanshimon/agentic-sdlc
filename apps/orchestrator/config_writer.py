"""config_writer — governed PR write-back for the editing plane (#3).

The Agents / Bundles / Prompts editors are real config edits to files that the
pipeline reads. Per the four-plane governance model, an edit must NOT silently
mutate running behaviour — it goes through a PR so the owning committee reviews
it (CODEOWNERS already gates these paths). This module is the shared core every
editor's save endpoint calls.

Reuses the proven `gh` pattern from pipeline-doctor/change_proposer.py:
  write file → branch → commit → push → `gh pr create` → return PR URL.

Safety: writes are confined to an allowlist of config roots (.github/agents,
standards-bundles, prompts). A path escaping those is refused — the editor
cannot be tricked into writing arbitrary repo files.

Bundles are PR-only (no live apply) by design — live-editing the compliance
standards would bypass committee review, which is the whole governance story.
Prompts/agents may additionally hot-reload the running orchestrator (separate
endpoint) so a demo gets instant feedback without pretending it skipped the PR.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_logger = logging.getLogger("orchestrator.config_writer")

_REPO_ROOT = Path(os.environ.get("CONFIG_REPO_ROOT", Path(__file__).resolve().parents[2]))

# Only these roots may be written by the editing plane. Anything else is refused.
_ALLOWED_ROOTS = (".github/agents", "standards-bundles", "prompts")

# Where to open the PR. Default = current repo (gh infers from origin).
_TARGET_REPO = os.environ.get("CONFIG_TARGET_REPO")  # "owner/repo" or None
_BASE_BRANCH = os.environ.get("CONFIG_BASE_BRANCH", "main")
_DRY_RUN = os.environ.get("CONFIG_WRITE_DRY_RUN", "").lower() in ("1", "true", "yes")


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


def _validate_path(rel_path: str) -> Path:
    """Resolve rel_path against the repo root, refusing anything outside the
    allowed config roots or escaping via '..'."""
    if rel_path.startswith("/"):
        raise ConfigWriteError(f"absolute paths not allowed: {rel_path!r}")
    target = (_REPO_ROOT / rel_path).resolve()
    try:
        rel = target.relative_to(_REPO_ROOT)
    except ValueError:
        raise ConfigWriteError(f"path escapes repo root: {rel_path!r}")
    if not any(str(rel).startswith(root) for root in _ALLOWED_ROOTS):
        raise ConfigWriteError(
            f"path {rel_path!r} not under an allowed config root "
            f"({', '.join(_ALLOWED_ROOTS)})"
        )
    return target


def _slug(s: str, maxlen: int = 40) -> str:
    s = re.sub(r"[^a-zA-Z0-9._-]+", "-", s).strip("-").lower()
    return s[:maxlen] or "edit"


async def _run(cmd: list[str], cwd: Path) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        *cmd, cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    return proc.returncode or 0, out.decode().strip(), err.decode().strip()


async def write_config_pr(
    rel_path: str,
    content: str,
    commit_message: str,
    pr_title: str,
    pr_body: str = "",
    labels: Optional[list[str]] = None,
    branch_prefix: str = "config-edit",
) -> ConfigWriteResult:
    """Write `content` to `rel_path`, open a PR, return the PR URL.

    Steps (all via git/gh in the repo working tree):
      1. validate the path is under an allowed config root
      2. create a branch off the base
      3. write the file + commit
      4. push + `gh pr create`
    Raises ConfigWriteError on any failure (caller maps to HTTP 4xx/5xx).
    """
    target = _validate_path(rel_path)
    branch = f"{branch_prefix}/{_slug(commit_message)}-{os.urandom(3).hex()}"
    labels = labels or ["config-edit"]

    if _DRY_RUN:
        _logger.info("DRY-RUN write_config_pr path=%s branch=%s", rel_path, branch)
        return ConfigWriteResult(
            ok=True, pr_url=None, branch=branch, path=rel_path, dry_run=True,
            message=f"DRY-RUN: would write {rel_path} and open PR {pr_title!r}",
        )

    # 1. fresh branch off the base
    rc, _, err = await _run(["git", "checkout", "-B", branch, _BASE_BRANCH], _REPO_ROOT)
    if rc != 0:
        raise ConfigWriteError(f"git checkout failed: {err}")

    # 2. write the file (create parent dirs)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")

    # 3. stage + commit
    rc, _, err = await _run(["git", "add", str(target)], _REPO_ROOT)
    if rc != 0:
        raise ConfigWriteError(f"git add failed: {err}")
    rc, _, err = await _run(["git", "commit", "-m", commit_message], _REPO_ROOT)
    if rc != 0:
        raise ConfigWriteError(f"git commit failed: {err}")

    # 4. push + open PR
    rc, _, err = await _run(["git", "push", "-u", "origin", branch], _REPO_ROOT)
    if rc != 0:
        raise ConfigWriteError(f"git push failed: {err}")

    cmd = ["gh", "pr", "create", "--base", _BASE_BRANCH, "--head", branch,
           "--title", pr_title, "--body", pr_body or commit_message]
    for lab in labels:
        cmd.extend(["--label", lab])
    if _TARGET_REPO:
        cmd.extend(["--repo", _TARGET_REPO])
    rc, out, err = await _run(cmd, _REPO_ROOT)
    if rc != 0:
        raise ConfigWriteError(f"gh pr create failed: {err}")

    pr_url = out.strip().splitlines()[-1] if out else None
    _logger.info("opened config PR: %s (%s)", pr_url, rel_path)
    return ConfigWriteResult(
        ok=True, pr_url=pr_url, branch=branch, path=rel_path, dry_run=False,
        message=f"Opened PR for {rel_path}",
    )
