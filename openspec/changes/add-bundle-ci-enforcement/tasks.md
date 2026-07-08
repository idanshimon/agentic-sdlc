# Tasks: add-bundle-ci-enforcement

Phased so an early slice is demonstrable before the full lane is wired. Each
phase ends green (its tests pass) before the next starts. YOU are the CI — this
repo has no pre-existing `.github/workflows/`; run the enforcer and its suite
locally. This change ADDS the first workflow, but its own tests run locally.

**Test targets:** `scripts/tests/test_enforce_bundles.py` (new). Run with
`python3 -m pytest scripts/tests/test_enforce_bundles.py -q`.

## Phase 0 — Standalone enforcer (the demonstrable core)

Goal: `scripts/enforce_bundles.py` loads the real bundles, applies BLOCK+pattern
rules to a file set, exits non-zero with cited violations. Proven green on the
current repo and red on an injected violation. This is the demo asset.

- [ ] 0.1 `scripts/enforce_bundles.py` — stdlib + PyYAML only. `load_rules(team) -> list[Rule]` reads `standards-bundles/**/rules.yaml`, resolves versions via `PINS.yaml` (`defaults` fallback), selects `severity: BLOCK` + has `pattern` + (`ci_checks: true` OR bundle `ci_checks_default: true`).
- [ ] 0.2 `check_files(rules, paths) -> list[Violation]` — apply each rule's compiled `pattern` per changed file, capture `file:line`, `<dept>/v<ver>/<rule-id>`, title. `main()` exits non-zero on any violation.
- [ ] 0.3 RED test: an injected file with a `patient_id` cleartext-log line trips `security/v0.1.0/PHI-001` (only if that rule is CI-enabled in Phase 1); until then, seed a temp bundle fixture with a CI-enabled BLOCK rule and assert exit 1 + citation string.
- [ ] 0.4 GREEN test: the enforcer over the repo's current `definitions`/sample files (no CI-enabled rule matching) exits 0 and writes `pass: true`.
- [ ] 0.5 **Safety/validation:** test that `import scripts.enforce_bundles` pulls NO `apps.orchestrator` module and opens no network socket (assert via `sys.modules` inspection + monkeypatched socket). Fail-closed test: a malformed `rules.yaml` fixture yields non-zero exit, not empty-pass.

## Phase 1 — `ci_checks` schema key + bundle opt-in

- [ ] 1.1 `standards-bundles/BUNDLE-SCHEMA.md` — document the optional `enforcement.ci_checks: <bool>` (default false) and bundle-level `ci_checks_default: <bool>`. Update the rules.yaml schema block and the required/optional field lists.
- [ ] 1.2 Set `ci_checks_default: true` on `security` and `privacy` bundle metadata (per design recommendation); leave `architect`/`finops` per-rule opt-in. Confirm each selected rule has a real `pattern` (rules without patterns are silently skipped by the CI lane — assert this).
- [ ] 1.3 Test: `load_rules('defaults')` returns exactly the security+privacy BLOCK-with-pattern rules and excludes architect/finops rules that did not opt in. Lock the selected rule-id set with an explicit assertion (the drift guard).
- [ ] 1.4 **Safety/validation:** drift test — the enforcer's selected rule-set is derived ONLY from the bundle files (no hardcoded rule list in the script). Assert by adding a temp CI-enabled rule to a fixture bundle and seeing it appear in `load_rules` output without touching the script.

## Phase 2 — GitHub Actions workflow (the surface)

- [ ] 2.1 `.github/workflows/bundle-enforce.yml` — `on: pull_request`; checkout with `fetch-depth: 0`; compute `git diff --name-only origin/${{ github.base_ref }}...HEAD`; `pip install pyyaml`; run `python3 scripts/enforce_bundles.py --team "${BUNDLE_TEAM:-defaults}" --files <changed>`. Non-zero exit fails the job. No `secrets.*` referenced.
- [ ] 2.2 Workflow uploads `bundle-enforce-result.json` as a build artifact. Header comment states the check is advisory until added to branch protection required checks.
- [ ] 2.3 Test (workflow-lint): validate the YAML parses and references no `secrets.`; assert the run step passes `--files` scoped to the diff, not the whole tree.
- [ ] 2.4 **Safety/validation:** confirm the workflow is the first under `.github/workflows/` and does not alter any orchestrator/IDE behavior; a repo without the file is unaffected (documented + asserted by absence).

## Phase 3 — Result artifact + docs (legibility)

- [ ] 3.1 Enforcer writes `bundle-enforce-result.json` (`pr_ref`, `pass`, `violations[]` with `bundle_ref` + `file:line`). Test the JSON shape for both a failing and a clean run; assert NO ledger/Cosmos import on the write path.
- [ ] 3.2 `docs/CI-ENFORCEMENT.md` — the three enforcement lanes table (`pipeline_stages` / `ide_hooks` / `ci_checks`), the "advisory until required" step with the exact branch-protection navigation, how the lane sits under `add-autonomous-review-loop` as the deterministic floor, and the "green check is necessary-not-sufficient" caveat.
- [ ] 3.3 **Safety/validation:** doc-accuracy test — `docs/CI-ENFORCEMENT.md` names the real workflow file and the real script path; a link-check asserts both exist. Re-run the full suite green.

## Phase 4 — Spec hygiene

- [ ] 4.1 `openspec validate add-bundle-ci-enforcement --strict` → Valid.
- [x] 4.2 Cross-reference this change from `add-autonomous-review-loop/design.md` + `add-autonomous-review-loop/proposal.md` (the loop's deterministic floor) and `add-standards-bundles/proposal.md` (the `ci_checks` enforcement key). Do NOT modify their spec deltas — reference only. **DONE 2026-07-08** — prose-only cross-refs added; no spec deltas touched.

## Rollback plan

- The change is additive and opt-in. To roll back: delete
  `.github/workflows/bundle-enforce.yml` (the check stops running), delete
  `scripts/enforce_bundles.py`, and revert the `ci_checks`/`ci_checks_default`
  keys in `BUNDLE-SCHEMA.md` + the two bundle metadatas. No orchestrator stage,
  IDE hook, ledger entry, or existing bundle rule changes behavior, so removal
  restores the exact prior state.
- If a required check must be removed urgently: an admin un-checks
  `bundle-enforce` from branch protection — merges are immediately unblocked
  without touching the workflow or bundles.

## Test targets (summary, for strict config)

- Unit: `load_rules` selection (Phase 0/1), fail-closed on malformed bundle,
  PINS resolution + defaults fallback, no-orchestrator-import guard.
- Integration: enforcer over an injected violating diff → non-zero + citation;
  over a clean diff → zero + `pass: true` artifact.
- Workflow-lint: `bundle-enforce.yml` parses, references no secret, scopes to the
  diff.
- Doc-accuracy: `docs/CI-ENFORCEMENT.md` names existing script + workflow paths.
