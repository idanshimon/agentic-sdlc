# Add DESCRIBES-vs-COMMITS semantics to the CI bundle enforcer

> **Status:** PROPOSED (filed 2026-08-18)
> **Capability:** bundle-ci-enforcement (MODIFIED), security bundle v0.1.0 (MODIFIED — `phi_locked` rule)
> **Severity:** Foundational — the CI enforcement lane had a 100% false-positive
> rate on this repository and blocked its own rule's test suite.

## Why

A repo-wide scan of the `ci_checks` lane produced **24 BLOCK violations, of which
zero were real leaks**:

| Class | Count |
|---|---|
| Test fixtures / demo fixtures / teaching UI | 23 |
| "Production" code | 1 |

The single production hit was `apps/orchestrator/_pipeline_stages.py:451` — the
prose string `title="Logging policy for MRN field unclear"` inside an
`AmbiguityCard`. It describes a governance question; it logs nothing.

The decisive finding: **PHI-001 blocked its own test suite.**
`apps/orchestrator/tests/test_phi001_context_scoped.py` lines 31-35 are the
quoted fixture strings that prove PHI-001 works, and PHI-001 flagged all five.

A rule that cannot survive its own tests is not strict, it is broken. And a gate
contributors know is wrong is worse than no gate: it teaches them that passing CI
is a matter of evasion rather than compliance. That is precisely the "paperwork of
assurance without the substance" this enforcement lane exists to prevent.

This surfaced only because an unrelated light-theme commit touched
`apps/ledger-insights-ui/src/app/phi/page.tsx`, pulling an already-on-`main` file
into the changed-files scan. The rule had been silently unenforced against these
paths.

## What changes

### 1. `scripts/enforce_bundles.py` — a new declarative rule field

`quoted_literal_exempt: bool` (default **false**). When enabled, a line is exempt
iff **every** occurrence of the rule's `context_pattern` (the sink) sits inside a
string literal.

This follows the existing `safe_wrapper_pattern` precedent: declarative semantics
expressed in the bundle, zero per-rule logic in the scanner.

### 2. `standards-bundles/security/v0.1.0/rules.yaml` — enable it on PHI-001

PHI-001 is `phi_locked: true`, which is why this proposal exists. The rule text,
severity, `pattern`, `context_pattern`, and `safe_wrapper_pattern` are unchanged.

## The load-bearing design decision

Two implementations were written. The first was wrong in the dangerous direction
and TDD caught it before it shipped.

**Rejected — "is the PHI token inside quotes?"** In a genuine leak the token is
almost always inside the quoted format string:

    `logger.info(f"patient {MRN} updated")`
                            ^^^ quoted, yet a REAL leak

Five tests failed, every one of them a real leak being wrongly exempted.

**Rejected — "sink quoted AND token quoted."** On
`logger.info(patient_id)  # see 'the docs'` the stray apostrophe in the comment
left the token "quoted", exempting a real leak.

**Chosen — "is the SINK quoted?"** The sink is what makes a line an act rather
than a description. **Any bare sink blocks**, decisively, regardless of how the
token is quoted.

    `logger.info(f"patient {MRN} updated")`     sink bare    -> BLOCKS
    `text: 'logger.info(f"patient {MRN}")'`     sink quoted  -> exempt

### Fails closed by construction

- No `context_pattern` → never exempt (no identifiable "act" to check).
- No sink found → not exempt.
- **Any** bare sink → not exempt.
- **Unterminated literal → not exempt.** Quote-stuffing cannot evade the gate.
- Off by default: no rule's blast radius changes without an explicit bundle edit.

### What it does NOT claim

This is not a proof of runtime safety. A string literal can still reach `eval()`
or a dynamic sink. The assertion is narrow and honest: *this line is not itself a
logging call.*

## Alternatives considered and rejected

**A path-scope / `exempt_paths` primitive.** Rejected: a general-purpose
suppression mechanism can excuse real violations, and with 24 findings it would
have been applied broadly on day one.

**A fingerprinted waiver ledger** (approvals, expiries, reason codes) — the
recommendation from an independent frontier-model review. Rejected on volume: a
waiver ledger is correct for a handful of genuine exceptions, but writing 24
waivers documents a broken mechanism instead of repairing it, and normalizes
"just file a waiver" as the response to a red gate. The same review's closing
recommendation — make the rule syntax-aware — is what this change implements.

**Rewriting the fixtures** to avoid the literal tokens. Rejected as governance
theater: splitting `"MR" + "N"` defeats the scanner while preserving the content,
and the PHI classifier demo page loses the very thing it teaches.

**Leaving it red.** Rejected: a permanently incorrect red gate destroys the
meaning of red. False positives are tolerable as incidents, not as steady state.

## Verification

- `scripts/tests/test_quoted_literal_exempt.py` — 19 tests, including 5
  adversarial evasion cases (unterminated quote, trailing quote after the match,
  comment-marker prefix, escaped quotes, literal closing before real code).
- Repo-wide PHI-001 findings: **15 → 1** (the remainder is prose inside a
  generated experiment artifact, not source).
- A real leak still blocks — verified against a synthetic
  `logger.info(f"patient {MRN} admitted")`.
- Full `scripts/tests/` suite: 76 passed.

## Out of scope — a separate pre-existing gap

PHI-001's `pattern` opens with `(?<![\w(])`, so a bare identifier immediately
after an opening paren is **never matched**:

    `logger.info(patient_id)`      NOT detected — and never has been
    `logger.info( patient_id )`    detected (the space breaks the lookbehind)

The lookbehind exists to stop `patient_id(` function calls from matching, but it
also blinds the rule to the most natural way to write the leak. This predates
this change and is unaffected by it. It is pinned by
`test_phi001_lookbehind_blind_spot_is_preexisting_not_caused_here` so it stays
visible and cannot regress silently. Fixing the pattern is a separate OpenSpec
change against a `phi_locked` rule.
