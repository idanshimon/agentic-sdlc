# Proposal: swap deliver stage from ADO to GitHub

> **Status:** PARTIALLY SHIPPED (2026-06-23) — reconciled with implementation
> **Capability:** pipeline
> **Related:** master-v07-four-plane-architecture, add-config-editing-plane

> **Reconciliation note (2026-06-23).** This proposal was authored as a DRAFT
> describing a GitHub App auth design. What actually shipped is real GitHub-PR
> delivery via the Git Data API authenticated by a **PAT** (`DELIVER_GH_TOKEN`),
> not a GitHub App. The spec deltas have been updated to match shipped reality:
> token auth (App is future hardening), the "never fabricate a PR URL" guarantee
> (the core of the work — it replaced two `Math.random()` demo URLs and a
> `dev.azure.com` fallback that all 404'd), repo resolution + empty-repo
> bootstrap, and atomic multi-artifact commits. NOT yet shipped from the original
> draft: GitHub App auth, reviewer assignment from `reviewers.yaml`,
> `gh_audit_xref` on delivered entries, and per-team provider overrides — these
> remain in the spec as forward design and their tasks stay unchecked.

## Why

v0.6's deliver stage targeted Azure DevOps because HCA Nashville's reference
deployment lived in ADO. v0.7 makes GitHub the default delivery target,
matching the rest of the agent-hq-integration story (issues from chat
bridges land as GH Issues, coding agent opens GH PRs, etc.).

ADO support is preserved as opt-in via a `deliver_provider` config flag for
customers like HCA who have committed to ADO. No regression for them.

## What changes

A new module `apps/orchestrator/stages/deliver_github.py` parallel to
the existing `deliver.py` (which becomes `deliver_ado.py`). The pipeline
state machine reads `config.deliver_provider` and dispatches to the right
implementation.

### deliver_github.py responsibilities

1. Open or update a PR on the configured target repo
   (`<org>/<repo>` configurable per team via `config.delivery.<team>.target_repo`).
2. Push the codegen output to a branch named `agentic-sdlc/run-<run_id>`.
3. Attach `decisions.md` (rendered from ledger entries for this run) to the PR body.
4. Add labels: `agentic-sdlc`, `run/<run_id>`, `stage/<final_stage>`.
5. Assign reviewers per `architect/v0.1.0/reviewers.yaml` matching the run's bundle subscriptions.
6. Create a check run that links back to `/telemetry?run_id=<run_id>`.

### Auth model

GitHub App, not PAT. The orchestrator deployment registers a private GitHub App
with permissions: `contents: write`, `pull-requests: write`, `checks: write`,
`metadata: read`. App credentials stored as Container App secrets.

Per-org installation: customers self-host the App on their org and provide
the installation ID. Orchestrator config carries `github_app.installation_id`
per team.

### Telemetry

Each PR creation writes a runtime ledger entry of kind `delivered` with
`pr_url` populated, plus a `gh_audit_xref` field set to the GH App's audit
session ID. Compliance can join our ledger entries to the GH audit log.

## Why this design

**Branch-per-run, not branch-per-task.** Each pipeline run produces ONE PR
on ONE branch. Allows clean rollback (close PR, delete branch) and clean
audit (decisions.md is per-run).

**GitHub App, not PAT.** App tokens are scoped, rotatable, audited by GitHub
Enterprise as `actor:Copilot`-adjacent events. PATs are user-scoped and
unauditable in the same way.

**`decisions.md` attached to PR body, not as a separate file.** Reviewers
see the decision rationale immediately. Renderer at
`apps/orchestrator/decisions_md.py` is preserved verbatim from v0.6.

## Risks and rollback

| Risk | Mitigation | Rollback |
|---|---|---|
| GH App installation fails on customer org | Self-deploy doc walks through install; orchestrator refuses to start without valid installation | Switch `deliver_provider` to `ado`, redeploy |
| PR rate limits hit during canary period | Orchestrator implements 1-PR-per-run-id idempotency + retry-after honoring | Disable per-team via config flag |
| Branch protection blocks orchestrator merges | Orchestrator never merges; only opens PR for human/Copilot review | N/A — design assumes human review |

## Test targets

- Unit: 8 cases for `deliver_github.py` (PR creation, branch naming, reviewer assignment, decisions.md attachment)
- Integration: against a test target repo, verify PR opens with correct labels + body
- E2E: full pipeline run completes → PR exists on `idanshimon/agentic-sdlc-target`
