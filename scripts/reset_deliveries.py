#!/usr/bin/env python3
"""reset_deliveries.py — clean the agentic-sdlc deliveries repo between demos.

Closes every OPEN pull request whose head branch starts with `agentic/` and
deletes that branch, returning the deliveries repo to a clean slate. Leaves
`main` and any non-agentic branches/PRs untouched.

Safe by construction:
  - only touches branches matching the `agentic/` prefix (pipeline output)
  - never deletes the base branch
  - dry-run by default; pass --apply to actually close/delete
  - reads the token from a file or env, never a command-line arg

Usage:
    # preview what would be reset (no changes):
    python scripts/reset_deliveries.py --token-file /tmp/ghtok/delivery

    # actually reset:
    python scripts/reset_deliveries.py --token-file /tmp/ghtok/delivery --apply

    # target a different repo / token source:
    DELIVER_TARGET_REPO=owner/repo DELIVER_GH_TOKEN=ghp_... \
        python scripts/reset_deliveries.py --apply
"""
from __future__ import annotations

import argparse
import os
import sys

import httpx

API = "https://api.github.com"
BRANCH_PREFIX = "agentic/"


def _token(token_file: str | None) -> str:
    if token_file:
        with open(token_file) as fh:
            return fh.read().strip()
    for var in ("DELIVER_GH_TOKEN", "DELIVERY_GH_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"):
        v = os.environ.get(var)
        if v and v.strip():
            return v.strip()
    sys.exit("no token: pass --token-file or set DELIVER_GH_TOKEN")


def main() -> None:
    ap = argparse.ArgumentParser(description="Reset agentic-sdlc deliveries repo")
    ap.add_argument("--repo", default=os.environ.get("DELIVER_TARGET_REPO", "idanshimon/agentic-sdlc-delivery"))
    ap.add_argument("--token-file", default=None)
    ap.add_argument("--apply", action="store_true", help="actually close/delete (default: dry-run)")
    args = ap.parse_args()

    token = _token(args.token_file)
    h = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    base = f"{API}/repos/{args.repo}"
    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"[{mode}] resetting {args.repo} (branches matching {BRANCH_PREFIX!r})\n")

    with httpx.Client(headers=h, timeout=30) as c:
        # 1. close open PRs whose head is an agentic/ branch
        closed = 0
        page = 1
        while True:
            r = c.get(f"{base}/pulls", params={"state": "open", "per_page": 100, "page": page})
            r.raise_for_status()
            prs = r.json()
            if not prs:
                break
            for pr in prs:
                ref = pr.get("head", {}).get("ref", "")
                if ref.startswith(BRANCH_PREFIX):
                    print(f"  PR #{pr['number']:>4}  {ref:30}  {pr['title'][:50]}")
                    if args.apply:
                        c.patch(f"{base}/pulls/{pr['number']}", json={"state": "closed"})
                    closed += 1
            page += 1

        # 2. delete agentic/ branches
        deleted = 0
        page = 1
        while True:
            r = c.get(f"{base}/branches", params={"per_page": 100, "page": page})
            r.raise_for_status()
            branches = r.json()
            if not branches:
                break
            for b in branches:
                name = b["name"]
                if name.startswith(BRANCH_PREFIX):
                    print(f"  branch    {name}")
                    if args.apply:
                        c.delete(f"{base}/git/refs/heads/{name}")
                    deleted += 1
            page += 1

    verb = "closed" if args.apply else "would close"
    verb2 = "deleted" if args.apply else "would delete"
    print(f"\n{verb} {closed} PR(s), {verb2} {deleted} branch(es).")
    if not args.apply:
        print("(dry-run — re-run with --apply to make changes)")


if __name__ == "__main__":
    main()
