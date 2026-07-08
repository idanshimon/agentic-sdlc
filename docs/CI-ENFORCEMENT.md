# CI Enforcement — the third bundle enforcement lane (`ci_checks`)

Standards bundles declare **where** each rule is enforced. There are three
enforcement surfaces; this doc covers the third.

| Lane | Where it runs | Trigger | Covers |
|---|---|---|---|
| `pipeline_stages` | inside the orchestrator | a pipeline run reaches the stage | actor-mediated — only orchestrated changes |
| `ide_hooks` | inside a Copilot IDE/CLI session | `pre-tool-use` / `post-tool-use` | actor-mediated — only IDE/CLI sessions that load the hooks |
| **`ci_checks`** | **GitHub Actions, on the PR** | **any `pull_request`** | **un-orchestrated PRs too** — a cloud Coding Agent's PR, a human branch push, an external automation |

The first two are **actor-mediated**: they only fire when a change flows through
the orchestrator or an instrumented IDE session. A pull request opened directly
on the repository — an agent's black-box output arriving straight as a Git
object — is enforced by neither. The `ci_checks` lane closes that gap with a
fail-closed required status check.

## What it is

- **Script:** [`scripts/enforce_bundles.py`](../scripts/enforce_bundles.py) —
  the deterministic subset of the `review-scan` agent. stdlib + PyYAML only.
  **No orchestrator import, no Cosmos, no LLM call.**
- **Workflow:** [`.github/workflows/bundle-enforce.yml`](../.github/workflows/bundle-enforce.yml)
  — triggers on `pull_request`, computes changed files vs the base, runs the
  enforcer over exactly those files. Requires **no repository secret**.
- **Tests:** [`scripts/tests/test_enforce_bundles.py`](../scripts/tests/test_enforce_bundles.py)
  — run `python -m pytest scripts/tests/test_enforce_bundles.py -q`.

## Which rules run in CI

A rule runs in the CI lane **only when all three hold**:

1. `severity: BLOCK`
2. it declares a machine-checkable `pattern`
3. either its `enforcement.ci_checks: true` **or** its bundle sets
   `metadata.ci_checks_default: true`

Everything else is skipped by CI — a semantic BLOCK rule with no `pattern`
(e.g. `HIPAA-MIN-NEC-001` "no `SELECT *` on PHI tables") cannot be judged by a
regex and is left to `pipeline_stages` / `ide_hooks` / the autonomous review
loop. As of v0.1.0 the CI lane covers exactly:

- `security/v0.1.0/PHI-001` — patient identifiers in cleartext logs
- `security/v0.1.0/SECRET-001` — service-principal secrets in source

This is deliberately narrow. **A green `bundle-enforce` check is necessary, not
sufficient** — it proves the two deterministic rules did not trip; it does NOT
prove the semantic standards were met. That is precisely why the autonomous
review loop (`openspec/changes/add-autonomous-review-loop`) sits above this lane:
the CI floor is the dumb, un-bypassable base; the loop is the smart layer that
enforces the rules a regex cannot. **Neither alone covers the standard.**

## Making it a merge gate (it is advisory by default)

Adding the workflow does **not** by itself block merges — it reports an ordinary
check. To turn it into a gate:

1. Repo **Settings → Branches → Branch protection rules**
2. Add or edit the rule for the protected branch (e.g. `main`)
3. Enable **Require status checks to pass before merging**
4. Search for and add **`bundle-enforce`** to the required set
5. Save

To remove the gate urgently, un-check `bundle-enforce` from the required set —
merges unblock immediately without touching the workflow or bundles.

## Local usage

```bash
# scan explicit files
python scripts/enforce_bundles.py --team defaults path/to/changed.py

# scan a PR's diff
git diff --name-only --diff-filter=ACM origin/main...HEAD \
  | python scripts/enforce_bundles.py --team defaults --stdin

# write the JSON result artifact
python scripts/enforce_bundles.py --team defaults --stdin \
  --result-json bundle-enforce-result.json --pr-ref "delivery#7" < changed.txt
```

Exit codes: `0` clean · `1` at least one BLOCK rule matched · `2` load error
(missing bundle dir, unparseable `rules.yaml`, unresolvable pin). The enforcer
**fails closed** — a load error is never treated as an empty rule set that passes.

## Where to install it

Per the two-stream model, this workflow belongs on **both**:

- **`agentic-sdlc`** (the engine repo) — dogfood; also closes this repo's own
  previously-missing CI.
- **the delivery repo** (where the factory's produced PRs land) — demonstrates
  that the dark factory's output is gated before it can merge.
