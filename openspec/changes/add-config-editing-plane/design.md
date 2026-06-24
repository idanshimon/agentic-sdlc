# Design: config editing plane

## Context

The v0.7 four-plane architecture renders agents (Agent HQ), bundles (Standards
Plane), and prompts (Standards Plane) as first-class operator surfaces. Before
this change those surfaces were read-or-mock: the agent→bundle relationship was
declarative metadata no backend consumed, the Bundles page had no editor, the
Agents editor wrote to browser localStorage, and the prompt "edit" was a GitHub
deeplink. This change makes the relationship drive data and turns all three
surfaces into real editors that open governed PRs.

## Goals / Non-Goals

**Goals:**
- The agent→bundle subscription drives a queryable `bundle_refs` on every decision.
- Agents, bundles, and prompts are editable in-app; each save opens a governed PR.
- Edits never silently mutate running behaviour; the PR (and its merge) is the
  durable source of truth.
- The write path works in a stateless container with no git/gh/clone.
- A missing token or failed write fails honestly — never a fabricated PR URL.

**Non-Goals:**
- GitHub App auth (PAT today; App is future hardening).
- Live-applying bundle edits (PR-only by governance design).
- Per-team config repos.

## Decisions

1. **Agent→bundle resolution lives in `agent_bundles.py`, not inline in the
   pipeline.** It parses the agent frontmatter once, validates declared
   subscriptions against the real `standards-bundles/<dept>` directories (so a
   typo or a prose line like `all (read-only)` resolves to `[]` rather than a
   bogus ref), and exposes `bundles_for_stage(stage)`. The pipeline calls it at
   the two ledger write sites.

2. **One shared write-back core (`config_writer.py`) for all three editors.**
   Agents, bundles, and prompts differ only in their target path and labels; the
   branch/commit/PR mechanics are identical. A single `write_config_pr(rel_path,
   content, commit_message, pr_title, ...)` keeps the security boundary in one
   tested place.

3. **GitHub REST API, not git/gh subprocess.** The deployed orchestrator is a
   bare file tree (`COPY apps/orchestrator /app/orchestrator`) with no `.git`,
   no `git`, no `gh`. The REST path (GET base ref → POST branch → GET existing
   file sha → PUT contents → POST pull) needs only a token and works in a
   stateless container. The git-subprocess version returned `[Errno 2]` in the
   container and was abandoned after deploy verification.

4. **Path allowlist is the security boundary.** `_validate_path` normalizes the
   repo-relative path without touching the filesystem (the file need not exist
   locally) and refuses absolute paths, `..` escapes, and anything outside
   `.github/agents` / `standards-bundles` / `prompts`. Unit-tested directly.

5. **Bundles are PR-only; prompts/agents may hot-reload.** A `POST
   /api/config/reload` refreshes the agent/prompt caches so a demo sees the
   effect before merge. Bundles are deliberately excluded — live-editing the
   compliance posture would bypass committee review.

6. **Honest failure, never a fake.** `config_writer` raises `ConfigWriteError`
   on a missing token or any non-2xx GitHub response (including a clean
   `FileNotFoundError → ConfigWriteError` mapping so a missing binary can never
   surface as a 500). The endpoint maps that to a 422 and the UI shows "Saved
   locally — PR not opened". No code path fabricates a PR URL.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| PAT in the container is a broad credential | Scope to the platform repo (fine-grained: Contents + PRs write); rotate via the ACA secret with no redeploy. App auth tracked as future hardening. |
| Prompt draft never gets promoted | The draft opens a PR with `status: draft` + `supersedes: vN`; the catalog keeps resolving the published version until a human merges. Visible in the version-history UI. |
| Operator edits a bundle expecting live effect | The bundle editor shows a prominent "governed: opens a PR, never live" banner; the save returns the PR URL, not a success-applied state. |
| Write path abused to touch arbitrary files | Server-side allowlist + `..`/absolute refusal, unit-tested; the UI only ever sends paths under the three roots. |

## Open Questions

- Migrate config + delivery PATs to a single GitHub App installation? (Future
  hardening; the App path is already specced in `swap-deliver-ado-to-github` for
  delivery.)
