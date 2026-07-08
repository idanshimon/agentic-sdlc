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

- [x] 0.1 `scripts/enforce_bundles.py` — stdlib + PyYAML only. `load_ci_rules(root, versions)` reads `standards-bundles/**/rules.yaml`, resolves versions via `PINS.yaml` (`defaults` fallback), selects `severity: BLOCK` + has `pattern` + (`ci_checks: true` OR bundle `ci_checks_default: true`).
- [x] 0.2 `scan_file(path, rules)` — apply each rule's compiled `pattern` per changed file, capture `file:line`, `<dept>/v<ver>/<rule-id>`, title. `run()` / `main()` exits non-zero on any violation.
- [x] 0.3 RED test: temp bundle fixture with a CI-enabled BLOCK rule → exit 1 + citation string (`test_violation_output_format_is_file_line_citation_title`, `test_run_returns_nonzero_on_violation`). Real security bundle catches SECRET-001 + PHI-001.
- [x] 0.4 GREEN test: clean file → exit 0, `pass: true` in the JSON artifact (`test_run_returns_zero_on_clean_tree`, `test_result_json_shape_on_clean`).
- [x] 0.5 **Safety/validation:** `import enforce_bundles` pulls NO `apps.orchestrator` module (`test_module_imports_no_orchestrator_cosmos_or_llm`, `test_only_stdlib_and_yaml_imported`). Fail-closed: malformed `rules.yaml` → non-zero, not empty-pass (`test_malformed_rules_yaml_raises_not_empty_pass`, `test_missing_bundle_dir_raises`, `test_unresolvable_pin_raises_bundle_error`).

## Phase 1 — `ci_checks` schema key + bundle opt-in

- [x] 1.1 `standards-bundles/BUNDLE-SCHEMA.md` — documented the optional `enforcement.ci_checks: <bool>` (default false) and bundle-level `metadata.ci_checks_default: <bool>`. Updated the optional-field list + added a bundle-metadata section.
- [x] 1.2 Set `ci_checks_default: true` on `security` and `privacy` bundle metadata; `architect`/`finops` remain per-rule opt-in. Rules without patterns are silently skipped by the CI lane (asserted).
- [x] 1.3 Test: `load_ci_rules('defaults')` returns exactly `{security/v0.1.0/PHI-001, security/v0.1.0/SECRET-001}` and excludes architect/finops (`test_real_bundles_select_expected_ci_ruleset_without_force`). Rule-id set locked (the drift guard).
- [x] 1.4 **Safety/validation:** drift test — selected rule-set derived ONLY from bundle files, no hardcoded list; adding a CI-enabled rule to a fixture bundle appears in output with zero script edits (`test_ci_ruleset_is_data_driven_not_hardcoded`).

## Phase 2 — GitHub Actions workflow (the surface)

- [x] 2.1 `.github/workflows/bundle-enforce.yml` — `on: pull_request`; checkout `fetch-depth: 0`; compute `git diff --name-only --diff-filter=ACM base...head`; `pip install pyyaml`; run `enforce_bundles.py --team defaults --stdin`. Non-zero exit fails the job. No `secrets.*`.
- [x] 2.2 Workflow writes + uploads `bundle-enforce-result.json` as a build artifact. Header comment states the check is advisory until added to branch-protection required checks.
- [x] 2.3 Test (workflow-lint): YAML parses, references no `secrets.`, scopes to the diff via `--stdin`, not the whole tree (`test_workflow_*`).
- [x] 2.4 **Safety/validation:** confirmed the workflow is the first under `.github/workflows/` and does not alter orchestrator/IDE behavior; a repo without the file is unaffected (`test_workflow_is_first_and_only_workflow` + documented in docs/CI-ENFORCEMENT.md).

## Phase 3 — Result artifact + docs (legibility)

- [x] 3.1 Enforcer writes `bundle-enforce-result.json` (`pr_ref`, `pass`, `violations[]` with `bundle_ref` + `file:line`). JSON shape tested for failing + clean runs; NO ledger/Cosmos import on the write path (`test_result_json_shape_*`, `test_write_result_json_uses_no_orchestrator_import`).
- [x] 3.2 `docs/CI-ENFORCEMENT.md` — the three enforcement lanes table (`pipeline_stages` / `ide_hooks` / `ci_checks`), the "advisory until required" step with exact branch-protection navigation, how the lane sits under `add-autonomous-review-loop` as the deterministic floor, and the "green check is necessary-not-sufficient" caveat.
- [x] 3.3 **Safety/validation:** doc-accuracy test — `docs/CI-ENFORCEMENT.md` names the real workflow file + script path; link-check asserts both exist (`test_ci_enforcement_doc_names_real_paths`).

## Phase 4 — Spec hygiene

- [x] 4.1 `openspec validate add-bundle-ci-enforcement --strict` → Valid.
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

- Unit: `load_ci_rules` selection (Phase 0/1), fail-closed on malformed bundle,
  PINS resolution + defaults fallback, no-orchestrator-import guard.
- Integration: enforcer over an injected violating diff → non-zero + citation;
  over a clean diff → zero + `pass: true` artifact.
- Workflow-lint: `bundle-enforce.yml` parses, references no secret, scopes to the
  diff.
- Doc-accuracy: `docs/CI-ENFORCEMENT.md` names existing script + workflow paths.
