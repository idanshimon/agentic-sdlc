# Design: bundle-ci-enforcement

## Context

The four-plane reference design enforces standards on two actor-mediated
surfaces. A rule's `enforcement` block names them:

- `pipeline_stages` — evaluated inside the orchestrator as a run flows through
  its stages (`assessor`, `codegen`, `review-scan`, …).
- `ide_hooks` — evaluated inside a Copilot IDE/CLI session via `pre-tool-use` /
  `post-tool-use` hooks.

Both require the change to pass through a component the system controls. A pull
request opened directly on the repository by a cloud Coding Agent passes through
neither: it is a Git object created by an external actor, reviewed (today) only
if a human or the orchestrator happens to look. The `add-autonomous-review-loop`
change adds a `pull_request.opened` hook that dispatches the orchestrator's
review loop — but that path is heavyweight (Cosmos-backed controller,
remediation dispatch) and orchestrator-hosted. There is no lightweight,
dependency-free, always-on check that runs the bundle rules against the PR diff
and fails closed.

This change adds that third surface — `ci_checks` — as a GitHub Actions required
status check. It is the deterministic floor: the pattern-matchable subset of the
bundle rules, run in CI, with no orchestrator and no data plane.

The design deliberately reuses what exists and is explicit about what is new:

- **Reuses:** the bundle files (`standards-bundles/**/rules.yaml`,
  `PINS.yaml`, `envelope.yaml`) exactly as authored; the `severity`/`pattern`/
  `phi`/`test_cases` fields; the `<dept>/v<ver>/<rule-id>` citation format.
- **Net-new:** a bundle loader that runs outside the orchestrator process; the
  `enforcement.ci_checks` schema key; the first GitHub Actions workflow in the
  repo; a diff-scoped rule applicator; the fail-closed-on-parse-error posture.

## Goals / Non-Goals

**Goals:**
- Enforce the `severity: BLOCK` bundle rules on any PR's diff, independent of the
  orchestrator and IDE surfaces.
- Fail closed: a violation, a bundle parse error, or a missing bundle blocks the
  check. Never pass silently.
- Zero data-plane footprint: no Cosmos, no LLM, no secret. Runs on diff text.
- Give a GitHub-native audience an un-bypassable, legible signal (a required
  check red X) that maps to a cited bundle rule.
- Be the deterministic floor the autonomous review loop runs above.

**Non-Goals:**
- Not replacing `review-scan`. The CI lane runs only pattern-matchable rules; the
  richer LLM verdict stays in the orchestrator.
- Not writing to the Decision Ledger from CI. The job emits an artifact a trusted
  ingest path can later file; CI holds no ledger credential.
- Not auto-configuring branch protection. Marking the check *required* is a
  deliberate admin action — documented, not automated.
- Not solving non-pattern rules (e.g. "PHI at rest must use CMK" is an
  architecture assertion, not a diff pattern). Those remain orchestrator/human.

## Decisions

1. **Enforcement is a declared per-rule property, not an implicit "all BLOCK
   runs in CI."** A rule opts into the CI lane via `enforcement.ci_checks: true`
   (or the bundle sets `ci_checks_default: true`). This mirrors how
   `pipeline_stages` and `ide_hooks` already work — enforcement surface is
   explicit and auditable per rule — and prevents a rule authored for
   orchestrator-only semantics from silently gaining a CI failure mode.

2. **The enforcer is a standalone script, not an orchestrator entrypoint.**
   `scripts/enforce_bundles.py` imports only stdlib + PyYAML. It re-reads the
   bundle YAML directly rather than importing `apps/orchestrator`. Rationale: the
   CI lane must run with zero services and zero orchestrator dependencies, and
   must not drag the orchestrator's import graph (Cosmos clients, provider SDKs)
   into a PR-triggered job. The small duplication of "load and select rules" is
   the price of an un-bypassable, dependency-free floor. A shared pure-Python
   `bundle_rules` reader MAY later be factored into `packages/` and imported by
   both; that refactor is out of scope and must not add orchestrator deps.

3. **Diff-scoped, not whole-tree.** The enforcer checks only the files changed in
   the PR (computed by the workflow as `git diff --name-only base...head`),
   matching `review-scan`'s diff semantics and keeping the check fast and
   relevant. A rule with no `pattern` is skipped by the CI lane (nothing to match
   deterministically) — those rules are the orchestrator's job.

4. **Fail-closed on every ambiguity.** Missing bundle directory, YAML parse
   error, unresolvable pin, or an unreadable rule all exit non-zero with a
   diagnostic. An enforcement surface that fails open on its own
   misconfiguration is worse than absent, because it manufactures false
   assurance. This mirrors the orchestrator's "refuse to start on unresolvable
   pin" posture.

5. **PINS resolution reuses the bundle contract.** The workflow passes a
   `--team <team_id>` (or `--defaults`) to the enforcer; the enforcer resolves
   versions through `PINS.yaml` exactly as the orchestrator does, so the CI lane
   enforces the *same version* a team's pipeline runs. A repo→team mapping is a
   workflow input (env or a small `ci-team.txt`), defaulting to `defaults`.

6. **The check is advisory until made required — and the design says so out
   loud.** Adding `bundle-enforce.yml` makes the check *run*; it blocks merges
   only once an admin adds it to the branch-protection required-checks set. The
   docs and the proposal both state this explicitly, because the entire point of
   the CI lane is the distinction between a workflow (reports) and a gate
   (blocks). Shipping the workflow while implying it gates would reproduce the
   exact "distributing config is not enforcing it" error this work exists to fix.

7. **No ledger write from CI; emit an artifact instead.** The job writes
   `bundle-enforce-result.json` (pass/fail + cited violations + pr_ref) as a
   build artifact. A separate, trusted change can ingest that into a `runtime`
   ledger entry. CI deliberately holds no Cosmos credential — a broadly
   PR-triggerable job must not.

## Risks / Trade-offs

| Risk | Mitigation | Rollback |
|---|---|---|
| Rule-loading logic duplicated between the enforcer and the orchestrator drifts over time | Both read the SAME `rules.yaml`; the enforcer adds no rule semantics, only selects `BLOCK`+`pattern`+`ci_checks`. A shared pure-Python reader is a documented later refactor. A drift test asserts the enforcer's selected rule-set matches the bundle files. | Remove the workflow; bundles and orchestrator unaffected. |
| A green CI check is mistaken for full review | Docs state the lane enforces only the pattern-matchable subset; a green check is necessary-not-sufficient. The check name is explicit (`bundle-enforce (deterministic floor)`). | N/A — documentation posture. |
| Regex `pattern`s produce false positives on a PR diff and block a legitimate change | Rules are the SAME ones already enforced on the orchestrator/IDE surfaces, so CI adds no new false-positive surface beyond what bundles already assert. A repo can scope adoption (only add the required check once its bundle patterns are trusted). | Un-require the check; fix the pattern via normal bundle-authoring review. |
| The workflow is added but never made required, giving false assurance | The proposal and docs make the required-check step a first-class, explicit instruction; the workflow's own comment states it does not gate until required. | N/A — the risk is *not* completing setup; docs address it. |
| CI job pulls the orchestrator's heavy import graph | Enforcer imports only stdlib + PyYAML by construction; a test asserts `import scripts.enforce_bundles` pulls no `apps.orchestrator` module. | N/A — enforced by test. |
| Bundle parse error silently passes the PR | Fail-closed decision (#4): any load error exits non-zero. A test feeds a malformed bundle and asserts non-zero exit. | N/A — enforced by test. |

## Open Questions

- **Repo→team mapping source.** A `ci-team.txt` file in the repo root vs a
  workflow env var vs deriving from the org's PINS. Recommendation: start with a
  workflow env `BUNDLE_TEAM` defaulting to `defaults`; promote to a checked-in
  `ci-team.txt` if per-repo pinning is needed. Decide before Phase 2.
- **`ci_checks_default` at bundle vs rule granularity.** Whether the security
  bundle should default all its BLOCK rules into CI (`ci_checks_default: true`)
  or require per-rule opt-in. Recommendation: security + privacy default-on
  (their BLOCK rules are exactly the non-negotiables you want on every surface);
  architect + finops per-rule opt-in. Confirm with bundle owners.
- **Shared reader refactor.** Whether to factor a pure-Python `bundle_rules`
  reader into `packages/` now (imported by both enforcer and orchestrator) or
  defer until a second consumer justifies it. Recommendation: defer; keep the
  enforcer standalone until the drift test shows real divergence pressure.
