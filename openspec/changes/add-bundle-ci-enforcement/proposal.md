# Proposal: bundle enforcement as a GitHub-native required check (ci_checks lane)

> **Status:** DRAFT (2026-07-08)
> **Capability:** bundle-ci-enforcement (NEW)
> **Motivation:** A cloud Coding Agent that opens a PR directly on a repository
>   never runs the orchestrator pipeline and never runs an IDE Copilot session.
>   Today the standards bundles enforce on exactly those two surfaces
>   (`pipeline_stages`, `ide_hooks`) — so an un-orchestrated agent PR is enforced
>   by neither. This change adds the missing GitHub-native enforcement surface: a
>   fail-closed required status check that applies the bundle floor to the diff of
>   any PR, whatever opened it.

## Why

The standards-bundles plane is the system's source of truth for what is
allowed. A rule declares where it is enforced:

```yaml
enforcement:
  pipeline_stages: [codegen, review-scan]   # runs inside the orchestrator
  ide_hooks: [pre-tool-use, post-tool-use]  # runs inside a Copilot IDE/CLI session
```

Both surfaces are **actor-mediated**: they fire only when a change flows through
the orchestrator, or through an IDE/CLI Copilot session that loads the hooks.
Neither fires on a pull request opened directly on the repository by a cloud
Coding Agent (or by a human pushing a branch, or an external automation). That
PR — an agent's "black box" output arriving straight as a Git object — is
precisely the un-orchestrated case that today reaches the merge button having
been checked by no bundle surface at all.

The reference design already documents the intended remedy but has not built it.
`add-standards-bundles` says the standards-change agent blocks merge via a
"GitHub branch protection rule with custom check," and its spec asserts "branch
protection rules MUST block the merge" — but that is scoped to bundle-*authoring*
PRs (changes to `standards-bundles/` itself), not to *product* PRs that must
obey the bundles. There is no workflow in the repo (`.github/workflows/` does not
exist) that runs the bundle rules against an ordinary code PR as a status check.

The gap is a missing **enforcement surface**, not a missing rule. The bundles
already carry machine-checkable rules (`pattern` + `severity: BLOCK`, with
`phi: true` markers and `test_cases`). What is missing is a third enforcement
lane, alongside `pipeline_stages` and `ide_hooks`, that runs those same rules
in GitHub CI and fails closed:

```
enforcement:
  pipeline_stages: [...]   # orchestrator            (exists)
  ide_hooks: [...]         # Copilot IDE/CLI          (exists)
  ci_checks: true          # GitHub required status    (THIS CHANGE)
```

This is the deterministic floor the `add-autonomous-review-loop` change needs
underneath it. That loop's controller is orchestrator-hosted and Cosmos-backed;
it triggers on `pull_request.opened` and dispatches heavyweight remediation. A
plain, always-on, dependency-free required check is a different tool for a
different job: it cannot be bypassed by an agent that skips the orchestrator, it
needs no services to run, and it gives a GitHub-native audience the red-X-on-the-PR
signal that reads instantly as "governed." The loop is the smart layer; this is
the dumb, un-bypassable floor. They compose.

## What Changes

Four additive pieces. No existing pipeline stage, IDE hook, bundle, or ledger
entry changes behavior. Repositories that do not adopt the workflow are
unaffected.

### 1. A standalone bundle enforcer runnable with zero orchestrator

- A new script `scripts/enforce_bundles.py` that loads the resolved bundles
  from `standards-bundles/**` (honoring `PINS.yaml` for the team the repo maps
  to, falling back to `defaults`), selects every rule with `severity: BLOCK` and
  a `pattern`, and applies them to a set of changed files (the PR diff).
- It depends only on the Python standard library plus PyYAML. It does NOT import
  the orchestrator, does NOT read Cosmos, and does NOT call an LLM. It is the
  deterministic subset of `review-scan` — the pattern-matchable rules only.
- Exit `0` when no BLOCK rule matches; exit non-zero when any does, printing each
  violation as `file:line [<dept>/v<ver>/<rule-id>] <title>`.

### 2. A `ci_checks` enforcement key in the bundle schema

- `BUNDLE-SCHEMA.md` and the rule schema gain an optional
  `enforcement.ci_checks: <bool>` (default `false`). A rule opts into the CI lane
  by setting it `true`. This keeps the enforcement surface a first-class,
  declared property of each rule — consistent with `pipeline_stages` and
  `ide_hooks` — rather than an implicit "all BLOCK rules run in CI" assumption.
- The enforcer runs a rule in CI when `severity: BLOCK` AND the rule has a
  `pattern` AND (`ci_checks: true` OR the bundle's `ci_checks_default: true`).

### 3. A GitHub Actions workflow that runs the enforcer as a required check

- A new `.github/workflows/bundle-enforce.yml` that triggers on
  `pull_request`, computes the changed files against the base branch, and runs
  `scripts/enforce_bundles.py` over them. A non-zero exit fails the check.
- The workflow only *reports* until a human marks it a **required status check**
  under branch protection. That final step — documented, not automated here — is
  what converts the workflow from advisory into control. The proposal is explicit
  that "a workflow exists" is not "a gate exists."

### 4. Ledger note + docs so the CI lane is legible and audited

- `docs/CI-ENFORCEMENT.md` documenting the lane, the required-check step, how it
  relates to `pipeline_stages`/`ide_hooks`, and how it sits under the autonomous
  review loop.
- When the enforcer runs in CI it emits a machine-readable result artifact
  (`bundle-enforce-result.json`: `pr_ref`, `violations[]` with bundle refs,
  `pass`/`fail`) so a later ledger-ingest step (out of scope here) can file a
  `runtime` entry. This change does not write to the ledger directly (CI has no
  Cosmos credential by design); it produces the artifact a trusted ingest path
  can consume.

## Capabilities

### New Capabilities

- `bundle-ci-enforcement`: A GitHub-native, orchestrator-independent enforcement
  surface that applies the `severity: BLOCK` bundle rules to a pull request's
  diff as a fail-closed required status check, covering PRs (notably cloud
  Coding Agent PRs) that never traverse the pipeline or an IDE hook.

### Modified Capabilities

- None. This change is purely additive. It references the `standards-bundles`
  schema and the `autonomous-review-loop` floor but modifies neither. The
  optional `enforcement.ci_checks` key is an additive field; bundles that omit it
  behave exactly as today.

## Impact

- **Affected specs (new):** `bundle-ci-enforcement`.
- **Composes (does not modify):** `add-standards-bundles` (consumes its
  `rules.yaml`/`PINS.yaml`; adds the `ci_checks` enforcement key), `add-pipeline-doctor`
  (unchanged — envelope auto-fix is a separate surface), `add-autonomous-review-loop`
  (this is the deterministic floor beneath that loop; the loop's remediation runs
  above a passing/failing CI gate), `swap-deliver-ado-to-github` (the PRs this
  gate checks are the real PRs that change opens).
- **Affected code:** new `scripts/enforce_bundles.py`; new
  `.github/workflows/bundle-enforce.yml` (first workflow in the repo — the repo
  has no `.github/workflows/` today); `standards-bundles/BUNDLE-SCHEMA.md`
  (documents the new optional `ci_checks` key); new `docs/CI-ENFORCEMENT.md`.
- **Config:** none required to keep current behavior. Adopting repos add the
  workflow and (separately, by a human) the required-check branch-protection rule.

## Safety Impact

- **Fail-closed by construction.** The enforcer exits non-zero on any BLOCK
  match; the workflow fails on non-zero. A parse error in a bundle or a missing
  bundle MUST fail the check, never pass silently (an enforcement surface that
  fails open is worse than none).
- **No secrets, no data plane.** The enforcer runs on the diff text only. It
  reads no PHI, needs no Cosmos credential, and writes nothing to the ledger
  directly. This is deliberate: a CI job broadly triggerable by any PR must not
  hold a data-plane secret.
- **Does not replace the PHI floor.** PHI rules (`phi: true`) remain BLOCK on the
  orchestrator and IDE surfaces. Adding them to the CI lane strengthens coverage
  but MUST NOT be read as permission to relax the orchestrator/loop PHI floor —
  the autonomous-review-loop's `tier_floor_phi` escalation is unchanged and
  authoritative for merge decisions.
- **A green check is necessary, not sufficient.** The CI lane enforces only the
  pattern-matchable subset. It does not judge business logic or non-pattern
  rules; those remain the job of the orchestrator review stage and human review.
  The docs MUST state this so a green check is never mistaken for full review.

## Non-goals

- Not building the ledger-ingest path (the CI job emits an artifact; wiring it to
  a `runtime` entry is a separate change that owns the trusted credential).
- Not making the orchestrator review-scan obsolete. The CI lane is the
  deterministic floor; review-scan remains the richer, LLM-assisted verdict.
- Not auto-configuring branch protection. Marking the check required is a
  deliberate human/admin action, by design.
- Not per-line PHI detection beyond the existing bundle `pattern`s. The enforcer
  runs the rules that exist; authoring better patterns is bundle-authoring work.
