# Tasks: harden-codegen-governance-quality

> **Status: 100% shipped in v0.7** (orchestrator `--0000040`). All sections complete.

## 1 — Context-scoped PHI-001

- [x] 1.1 Add `context_pattern` + `safe_wrapper_pattern` to `CIRule` + `matches_line()` in `scripts/enforce_bundles.py` *(commit 17191bd)*
- [x] 1.2 Parse the new fields in `select_ci_rules_from_file` *(commit 17191bd)*
- [x] 1.3 Rewrite `security/v0.1.0` PHI-001 rule to context-scoped form + update test_cases *(commit 17191bd)*
- [x] 1.4 Share the matcher in `review_verdict._scan_text` so CI and pipeline agree *(commit 17191bd)*
- [x] 1.5 Tests: `test_phi001_context_scoped.py` incl. a contract test against the rule's own test_cases *(commit 17191bd)*
- [x] 1.6 Document the rule fields in `standards-bundles/security/v0.1.0/README.md` *(commit a13d4f5)*

## 2 — Delivered-layout prompt alignment

- [x] 2.1 codegen-tests v2: import `from main import app` (not `from app`) *(commit 07b0155)*
- [x] 2.2 codegen v2: deliver as `src/main.py` (not `app.py`) *(commit 07b0155)*
- [x] 2.3 Supersede codegen-tests v1 → v2 *(commit 07b0155)*
- [x] 2.4 Add "imports must be complete" instruction to both prompts *(commit 72e9f4b)*

## 3 — Static runnability gate

- [x] 3.1 PHI-safe codegen prompt v2 so generated code passes the security gate *(commit b6cfca4)*
- [x] 3.2 Add `_static_runnability_blockers()` to `build_review_verdict` — v1 (allowlist) *(commit 07b0155)*
- [x] 3.3 Rewrite to symtable-based undefined-name detection (module + function scope) *(commit 72e9f4b)*
- [x] 3.4 Tests: `test_static_runnability.py` incl. false-positive guards *(commit 72e9f4b)*
- [x] 3.5 Fix pre-existing `test_clean_code_yields_pass_verdict` fixture that referenced an undefined helper *(commit 72e9f4b)*

## Delta from original plan

There was no prior openspec change for codegen quality — this is entirely
retroactive, authored after the defects were found by executing delivered PRs.
Section 3 (runnability gate) went beyond "fix the prompt": the durable fix is a
governance check that statically proves generated code runs, so the same defect
class cannot recur regardless of model behavior.
