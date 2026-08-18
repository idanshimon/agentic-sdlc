# Tasks: add-describes-vs-commits-enforcement

**Test targets:** `scripts/tests/test_quoted_literal_exempt.py` (new),
`scripts/tests/test_enforce_bundles.py` (regression). Run with
`.venv/bin/python -m pytest scripts/tests/ -q`.

## Phase 0 — Prove the defect is real and measure it

- [x] 0.1 Scan the full repo (not just changed files) through the `ci_checks` lane and count findings by class. Result: 24 BLOCK violations — 23 fixtures/tests, 1 prose string in `_pipeline_stages.py:451`.
- [x] 0.2 Confirm zero are real leaks by reading every flagged line.
- [x] 0.3 Confirm PHI-001 blocks its own test suite (`test_phi001_context_scoped.py:31-35`).

## Phase 1 — RED: encode the distinction as failing tests first

- [x] 1.1 `test_real_logging_call_still_blocks_when_exemption_is_on` — the load-bearing test. A real leak must never be exempted.
- [x] 1.2 Regression tests for each real false-positive line (demo page placeholder, UI fixture, prose AmbiguityCard, test dict fixture, PHI-001's own fixture).
- [x] 1.3 Adversarial tests: unterminated quote, trailing quote after the match, comment-marker prefix, escaped quotes, literal closing before real code.
- [x] 1.4 `test_default_is_off` — absent the flag, blast radius is unchanged.
- [x] 1.5 Run RED. **5 failures, all real-leaks-wrongly-exempted.** First implementation (token-position) was unsafe.

## Phase 2 — GREEN: sink-position semantics

- [x] 2.1 `_is_inside_string_literal(line, index)` — quote-state scan; escaped quotes do not delimit; unterminated literal returns False (fails closed).
- [x] 2.2 `_describes_rather_than_commits(line, ctx, rx)` — exempt iff EVERY sink occurrence is inside a literal.
- [x] 2.3 Remove the token-quoted clause after `logger.info(patient_id)  # see 'the docs'` exposed it as unsafe (a stray apostrophe exempted a real leak). Bare sink is decisive alone.
- [x] 2.4 `quoted_literal_exempt` field on `CIRule`, default False; wired through `select_ci_rules_from_file`.
- [x] 2.5 Full suite green — 76 passed.

## Phase 3 — Enable on PHI-001 (phi_locked — requires this proposal)

- [x] 3.1 Set `quoted_literal_exempt: true` on PHI-001 with inline rationale. Rule text, severity, and all three patterns unchanged.
- [x] 3.2 Re-scan repo-wide: **15 PHI-001 findings → 1** (prose in a generated experiment artifact, not source).
- [x] 3.3 Verify a real leak still blocks against a synthetic `logger.info(f"patient {MRN} admitted")`.
- [x] 3.4 Dogfood: fix the enforcer's own docstring examples, which tripped the rule they document.

## Phase 4 — Record the pre-existing gap found along the way

- [x] 4.1 Pin the `(?<![\w(])` lookbehind blind spot in a named test so it stays visible and cannot regress silently.
- [ ] 4.2 File a separate OpenSpec change to fix the lookbehind (out of scope here — `phi_locked`, and orthogonal to this change).

## Phase 5 — Review

- [ ] 5.1 Reviewer approval per the security bundle's declared roster (required: this modifies a `phi_locked` rule).
- [ ] 5.2 Confirm `bundle-enforce` passes on the PR.
