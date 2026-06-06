#!/usr/bin/env bash
# deploy/scripts/05-publish-to-github.sh
# Creates idanshimon/agentic-sdlc on GitHub (personal account, NOT EMU) and pushes.
#
# Pattern from cust/hca/agentic-sdlc memory:
#   - idanshimon (personal) account is the target — EMU account blocks personal repo creation
#   - commit author MUST use noreply email (GH007 push privacy block on gmail)
set -euo pipefail

REPO="${REPO:-idanshimon/agentic-sdlc}"
VISIBILITY="${VISIBILITY:-private}"  # start private; flip to public when ready

# 1. Ensure we are signed in as idanshimon (personal), not idanshimon_microsoft
gh auth status 2>&1 | head -10
echo
CURRENT=$(gh auth status 2>&1 | grep "Active account: true" -B 1 | head -1 | awk '{print $NF}')
echo "Active GH account: $CURRENT"
if [[ "$CURRENT" != "idanshimon" ]]; then
  echo "Switching to idanshimon (personal) account..."
  gh auth switch --user idanshimon
fi

# 2. Create repo if missing
if ! gh repo view "$REPO" --json name 2>/dev/null; then
  echo "Creating $REPO ($VISIBILITY)..."
  gh repo create "$REPO" --$VISIBILITY \
    --description "Governed agentic SDLC reference design — four planes (Standards / Pipeline / Decision Ledger / Agent HQ Runtime). Successor to agentic-sdlc-reference (v0.6)." \
    --source=. --remote=origin
else
  echo "Repo $REPO already exists, will push to it"
  if ! git remote get-url origin >/dev/null 2>&1; then
    git remote add origin "https://github.com/$REPO.git"
  fi
fi

# 3. Push commits
echo
echo "Pushing to origin/main..."
git push -u origin main

# 4. Restore work account (idanshimon_microsoft) for normal operations
echo
echo "Restoring idanshimon_microsoft as active account..."
gh auth switch --user idanshimon_microsoft 2>/dev/null || true

echo
echo "=== Done ==="
echo "View at: https://github.com/$REPO"
