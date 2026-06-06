"""GitHub deliver stage — opens a PR on the configured target repo.

Replaces the v0.6 ADO path as the v0.7 default. ADO remains opt-in via
config.deliver_provider = "ado".

Responsibilities:
  1. Create a branch named `agentic-sdlc/run-<run_id>`
  2. Push codegen output to that branch
  3. Open a PR with decisions.md inline in the body
  4. Apply labels (agentic-sdlc, run/<run_id>, stage/<final_stage>)
  5. Assign reviewers per architect/<version>/reviewers.yaml
  6. Create a check run linking back to /telemetry?run_id=<run_id>
  7. Write a runtime ledger entry of kind "delivered"

Auth: GitHub App (not PAT). JWT signed with App private key, exchanged
for an installation access token per call.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

from ..decisions_md import render as render_decisions_md
from ..models import RunState
from ..github_app_client import GitHubAppClient

_logger = logging.getLogger("orchestrator.stages.deliver_github")


async def deliver_to_github(
    run: RunState,
    config: Any,
    ledger_client: Any = None,
) -> Dict[str, Any]:
    """Open a PR on the configured GH target repo.

    Args:
        run: completed RunState with cards/decisions/codegen output
        config: orchestrator settings (carries github_app config + target_repo)
        ledger_client: optional ledger writer (for the "delivered" entry)

    Returns:
        {pr_url, branch, gh_audit_xref}

    Raises:
        httpx.HTTPStatusError on GH API failure
    """
    target_repo = _resolve_target_repo(run.team_id, config)
    branch_name = f"agentic-sdlc/run-{run.run_id}"
    pr_title = f"agentic-sdlc: run {run.run_id} for team {run.team_id}"
    pr_body = _render_pr_body(run)
    labels = [
        "agentic-sdlc",
        f"run/{run.run_id}",
        f"stage/{run.current_stage.value if hasattr(run.current_stage, 'value') else run.current_stage}",
    ]

    gh_app = GitHubAppClient(
        app_id=config.github_app_id,
        private_key=config.github_app_private_key,
        installation_id=_resolve_installation_id(run.team_id, config),
    )
    token = await gh_app.get_installation_token()

    async with httpx.AsyncClient(
        base_url="https://api.github.com",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=30.0,
    ) as client:
        # 1. Get base branch SHA
        owner, repo = target_repo.split("/", 1)
        ref_resp = await client.get(f"/repos/{owner}/{repo}/git/refs/heads/main")
        ref_resp.raise_for_status()
        base_sha = ref_resp.json()["object"]["sha"]

        # 2. Create the branch (idempotent — if it exists, that's fine)
        create_ref_resp = await client.post(
            f"/repos/{owner}/{repo}/git/refs",
            json={"ref": f"refs/heads/{branch_name}", "sha": base_sha},
        )
        if create_ref_resp.status_code not in (201, 422):  # 422 = already exists
            create_ref_resp.raise_for_status()

        # 3. Commit codegen artifacts to the branch
        # NOTE: v0.7 demo: orchestrator's codegen output is treated as a single
        # decisions.md artifact attached to PR body. Real impl would commit
        # the multi-file codegen output via a tree + commit object dance.
        # For demo correctness, we ALWAYS commit a `RUN.md` artifact so the
        # branch has at least one commit to PR against.
        await _commit_run_artifact(client, owner, repo, branch_name, run, base_sha)

        # 4. Open the PR
        pr_resp = await client.post(
            f"/repos/{owner}/{repo}/pulls",
            json={
                "title": pr_title,
                "body": pr_body,
                "head": branch_name,
                "base": "main",
                "draft": False,
            },
        )
        if pr_resp.status_code == 422:
            # Already a PR for this branch — find and reuse
            existing = await client.get(
                f"/repos/{owner}/{repo}/pulls",
                params={"head": f"{owner}:{branch_name}", "state": "open"},
            )
            existing.raise_for_status()
            pr_data = existing.json()
            if not pr_data:
                pr_resp.raise_for_status()
            pr = pr_data[0]
        else:
            pr_resp.raise_for_status()
            pr = pr_resp.json()

        pr_url = pr["html_url"]
        pr_number = pr["number"]

        # 5. Apply labels
        await client.post(
            f"/repos/{owner}/{repo}/issues/{pr_number}/labels",
            json={"labels": labels},
        )

        # 6. Reviewer assignment is best-effort; skip on failure
        reviewers = _resolve_reviewers(run, config)
        if reviewers:
            try:
                await client.post(
                    f"/repos/{owner}/{repo}/pulls/{pr_number}/requested_reviewers",
                    json={"reviewers": reviewers[:5]},  # GH limits
                )
            except httpx.HTTPStatusError as e:
                _logger.warning("reviewer assignment failed (non-fatal): %s", e)

    gh_audit_xref = f"gh-pr-{pr_number}"

    # 7. Write the "delivered" ledger entry
    if ledger_client is not None:
        try:
            from ledger_core import LedgerEntry, Actor
            entry = LedgerEntry(
                team_id=run.team_id,
                actor=Actor(kind="agent", id="orchestrator-deliver"),
                decision=f"delivered run {run.run_id} as PR {pr_url}",
                rationale=(
                    f"deliver_provider=github; target={target_repo}; "
                    f"branch={branch_name}; reviewers={len(reviewers)}"
                ),
                run_id=run.run_id,
                runtime_kind="delivered",
                stage="deliver",
                bundle_refs=["architect/v0.1.0/SERVICE-CONTAINERIZED-001"],
                pr_url=pr_url,
                gh_audit_xref=gh_audit_xref,
                cost_usd=0.0,
            )
            await ledger_client.write_entry(entry)
        except Exception as e:
            _logger.warning("ledger write for delivered entry failed: %s", e)

    return {
        "pr_url": pr_url,
        "branch": branch_name,
        "gh_audit_xref": gh_audit_xref,
    }


async def _commit_run_artifact(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    branch: str,
    run: RunState,
    base_sha: str,
) -> str:
    """Commit a RUN.md artifact to the branch so the PR has content to review."""
    content = render_decisions_md(run)
    content_b64 = _b64(content)

    # Use the contents API for simplicity (single-file commit). For multi-file
    # codegen output, switch to tree + commit object dance.
    path = f".agentic-sdlc/runs/{run.run_id}/RUN.md"
    msg = f"agentic-sdlc: run {run.run_id} artifact"
    resp = await client.put(
        f"/repos/{owner}/{repo}/contents/{path}",
        json={
            "message": msg,
            "content": content_b64,
            "branch": branch,
        },
    )
    resp.raise_for_status()
    return resp.json()["commit"]["sha"]


def _b64(s: str) -> str:
    import base64
    return base64.b64encode(s.encode("utf-8")).decode("ascii")


def _render_pr_body(run: RunState) -> str:
    decisions_md = render_decisions_md(run)
    telemetry_url = ""  # filled in by config
    return (
        f"# Agentic-SDLC run `{run.run_id}`\n\n"
        f"**Team:** `{run.team_id}` · **Status:** {run.status}\n\n"
        f"This PR was authored by the agentic-sdlc orchestrator. Every decision "
        f"is recorded in the Decision Ledger and surfaced below.\n\n"
        f"---\n\n{decisions_md}\n\n"
        f"---\n\n"
        f"_Reviewer:_ verify that each decision aligns with the cited bundle "
        f"rule. PHI rules cannot be relaxed in this PR; if you need to "
        f"propose a rule change, open a separate PR on `standards-bundles/`."
    )


def _resolve_target_repo(team_id: str, config: Any) -> str:
    overrides = getattr(config, "delivery_overrides", {}) or {}
    team_cfg = overrides.get(team_id, {})
    return team_cfg.get("target_repo") or config.github_default_target_repo


def _resolve_installation_id(team_id: str, config: Any) -> int:
    overrides = getattr(config, "delivery_overrides", {}) or {}
    team_cfg = overrides.get(team_id, {})
    return int(team_cfg.get("installation_id") or config.github_app_installation_id)


def _resolve_reviewers(run: RunState, config: Any) -> list[str]:
    """v0.7 demo: empty list. Real impl reads architect/<version>/reviewers.yaml."""
    overrides = getattr(config, "delivery_overrides", {}) or {}
    team_cfg = overrides.get(run.team_id, {})
    reviewers = team_cfg.get("reviewers") or []
    return [str(r) for r in reviewers]
