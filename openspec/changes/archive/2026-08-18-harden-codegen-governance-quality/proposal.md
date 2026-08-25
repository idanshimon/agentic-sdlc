# Proposal: harden codegen governance quality

> **Status:** SHIPPED (retroactive) — v0.7, orchestrator `ca-orchestrator-vnet--0000040`
> **Capabilities:** review-scan, standards-bundles, prompt-library
> **Commits:** b6cfca4, 17191bd, a13d4f5, 07b0155, 72e9f4b

## Why

With a real LLM wired into the pipeline (see `wire-real-llm-providers`), codegen
produces genuine code — and that exposed governance gaps that stub output never
did. Reviewing real delivered PRs by executing the generated code surfaced three
classes of defect the review-scan gate did not catch:

1. **PHI-001 was unusable for real healthcare code.** Its pattern matched patient
   identifier tokens (`MRN`, `patient_id`, `SSN`, `DOB`) *anywhere*, so it blocked
   every legitimate domain field (`patient_id: str`) and function parameter — 100%
   of real code — even though the rule's title, rationale, and test cases all
   target *cleartext logging*. The rule enforced its text, not its intent.

2. **Delivered test suites could not import.** The codegen prompt said "deploy as
   `app.py`", the tests prompt imported `from app import app`, but the deliver
   stage writes the implementation to `src/main.py`. Every delivered test suite
   died at collection with `ModuleNotFoundError: No module named 'app'`.

3. **Generated code shipped with missing imports.** Real generated files used
   names they never imported — `TestClient(app)` with no
   `from fastapi.testclient import TestClient`, `os.environ` with no `import os`
   (a service that NameErrors at startup), `time.time()` in a function with no
   `import time`. The review gate did not check that generated code even runs.

These are governance gaps, not polish. A reference design that ships PHI-leaking
or unrunnable code — or that blocks all legitimate healthcare code — is not
adoptable by a real team.

## KEEP / SWAP / ADD / OUT

### KEEP
- The deterministic BLOCK-rule scanner (`enforce_bundles`) and its shared use by
  the CI lane and the pipeline review (`review_verdict`).
- The versioned, resolver-selected prompt library.
- The hard-gate floor and PHI-locked rule semantics.

### SWAP
- PHI-001 blanket token match → context-scoped match (logging sink required,
  redaction wrappers exempt), enforcing the rule's documented intent.
- Codegen/tests prompts pointing at inconsistent module names → both aligned to
  the delivered `src/main.py` layout.

### ADD
- Generic, declarative `context_pattern` + `safe_wrapper_pattern` fields on bundle
  rules, matched identically by CI and the pipeline.
- A static-runnability gate in review-scan: syntax + undefined-name detection
  (symtable) so unrunnable generated code is a first-class BLOCK.

### OUT
- Full type-checking / linting of generated code (only runnability, i.e. "does it
  parse and do all names resolve", is in scope here).

## Verification

- 440 orchestrator tests pass (`test_phi001_context_scoped.py`,
  `test_static_runnability.py` added).
- Live end-to-end: run `ce754540` (eligibility), `093b44af` (vitals),
  `38340a6c` (platform/Neo4j) all passed review-scan (0 blockers) and opened real
  PRs (#6, #7, #10). The runnability gate verified to catch the real PR#12
  (`TestClient`), PR#12 `main.py` (`os`), and PR#6 (`time`) defects at the exact
  lines, with no false positives on builtins, comprehension locals, or
  forward-references.
