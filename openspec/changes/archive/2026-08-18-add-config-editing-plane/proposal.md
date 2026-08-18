# Proposal: config editing plane — governed PR write-back for agents, bundles, prompts

> **Status:** SHIPPED (2026-06-23)
> **Capability:** config-editing-plane
> **Related:** add-agent-hq-integration, add-standards-bundles, add-multi-persona-prompt-library, master-v07-four-plane-architecture

## Why

The Agents, Bundles, and Prompt Library surfaces rendered configuration that
the pipeline reads, but the relationship was display-only and the editors were
mocks:

1. Every agent under `.github/agents/*.agent.md` declared `bundle_subscriptions:`
   (e.g. architect → [architect, security]), but **no backend code read it**.
   `bundle_refs` was never stamped on a ledger entry, so the agent→bundle
   relationship shown in the UI did not drive any behaviour.
2. The Bundles page was **read-only** — there was no way to edit a bundle at all
   (the root of the operator report "changing the bundle did nothing").
3. The Agents editor saved to **browser localStorage only** — edits never
   reached `.github/agents/*.md`, the repo, or the orchestrator.
4. The Prompt Library "edit" path was a GitHub deeplink, not an in-app editor.

This change closes the loop on both ends: the agent→bundle relationship now
drives data, and all three config surfaces (agents, bundles, prompts) became
real editors that open a governed PR against the file the pipeline reads.

## What changes

### #2 — agent→bundle wiring (the relationship drives data)

- `apps/orchestrator/agent_bundles.py` parses `.github/agents/*.agent.md`,
  validates declared `bundle_subscriptions` against the real bundle directories,
  and exposes `bundles_for_stage(stage)`.
- `LedgerEntry.bundle_refs` is stamped at both decision write sites (autopilot
  and per-card approve) with the deciding agent's bundle subscriptions, so every
  decision is attributed to the bundles that governed it — queryable, not
  cosmetic.

### #3 — governed editing plane (real PRs, never live mutation)

- `apps/orchestrator/config_writer.py` — shared PR write-back core using the
  **GitHub REST API over HTTPS** (Contents + Pulls). Writes are confined to an
  allowlist of config roots (`.github/agents`, `standards-bundles`, `prompts`);
  any path escaping those is refused.
- Three endpoints: `POST /api/config/{agents,bundles,prompts}/save` — each opens
  a PR on the config file and returns the PR URL.
- `POST /api/config/reload` — hot-reload of the agent/prompt caches for
  prompts/agents only (so a demo sees the effect before merge); bundles are
  PR-only and never hot-reloaded.
- UI: the Agents editor saves via PR (was localStorage), the Bundles page gains
  an "Edit rules" editor (was read-only), and the Prompt Library gains an in-app
  editor that composes the next draft version (`vN+1`, status: draft) and opens
  a PR.

### Auth + honesty

- Token from `GH_TOKEN` / `GITHUB_TOKEN` / `CONFIG_GH_TOKEN` (a repo-scoped PAT
  or fine-grained token with Contents + Pull-requests write). When no token is
  configured, the save endpoint returns a clean 422 and the UI shows "Saved
  locally — PR not opened" — it NEVER fabricates a PR URL or reports a fake
  success.

## Why REST, not git/gh subprocess

The first implementation shelled `git`/`gh` from the orchestrator. Deploy
verification proved this can never work in the container: it is a bare file tree
(`COPY`, no `.git`, no `git`, no `gh`), so a real save returned
`[Errno 2] No such file or directory`. The GitHub REST API needs no binaries and
no working clone — only a token — which is the correct architecture for a
stateless container. Verified end-to-end against real GitHub (a live PR opened +
closed via the REST path).

## Impact

- New: `apps/orchestrator/agent_bundles.py`, `apps/orchestrator/config_writer.py`
- Modified: `apps/orchestrator/main.py` (3 save endpoints + reload),
  `apps/orchestrator/models.py` (`bundle_refs`), `apps/orchestrator/_pipeline_stages.py`
- UI: `agents/page.tsx`, `bundles/page.tsx`, `prompts/page.tsx`,
  `components/domain/versioned-editor.tsx`, `lib/api/orchestrator.ts`
- Deployment: `GH_TOKEN` Container App secret on the orchestrator

## Safety Impact

- Bundles are PR-only by design. Live-editing the compliance standards would
  bypass committee review, which is the entire governance story. A bundle edit
  takes effect only after the PR merges.
- The write allowlist (`.github/agents`, `standards-bundles`, `prompts`) means
  the editor cannot be tricked into writing arbitrary repo files; absolute paths
  and `..` escapes are refused server-side.
- No fabricated success: a missing token or a failed PR yields an honest error,
  never a fake PR URL.

## Non-goals

- GitHub App auth (the delivery and config tokens are PATs today; App-based auth
  is a future hardening, tracked separately).
- Per-team or per-customer config repos (single platform repo for config edits).
- Automatic promotion of prompt drafts to published (the draft opens a PR; a
  human promotes + merges).
