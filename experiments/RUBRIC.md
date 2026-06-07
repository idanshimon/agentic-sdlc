# Scoring Rubric — Phase A (baseline) vs Phase B (OpenSpec-shaped)

**Authored:** 2026-06-06, BEFORE Phase A results examined and BEFORE Phase B
build started. This is the fairness contract for the experiment — by writing
the metrics down first, I forfeit the ability to post-hoc rationalize whichever
artifact ends up looking subjectively nicer.

---

## What we're measuring

Six dimensions, each scored 1-5 per phase across all 3 runs (so each phase has
6 × 3 = 18 cell scores). Per-cell scoring rule below each dimension. Final
phase score per dimension is the mean across the 3 runs.

A dimension is "decisive for OpenSpec" only if Phase B beats Phase A by ≥ 1.0
points on the mean. Cosmetic wins (< 1.0) don't count — model variance run-to-
run is real.

---

## 1. Traceability density

> "Given an architectural assertion, can I find the gating decision that drove it?"

How many of the resolved Resolver decisions are explicitly cited in the Architect
output, divided by the total number of resolved decisions. Ideal: 1.0.

**Per-cell scoring (pure mechanical count):**
- 5 — Every resolved decision cited verbatim or by stable ID
- 4 — Every decision cited but as paraphrase, not verbatim
- 3 — ≥ 80 % of decisions cited (paraphrase OK)
- 2 — ≥ 50 % cited
- 1 — < 50 % cited

Phase A counts free-form prose mentions. Phase B counts MUST/SHALL clauses
that explicitly reference a decision (e.g. via `[decision-3]` or
`[card-id]`). The Phase B prompt MUST require these citations; otherwise the
test isn't fair.

---

## 2. Test-spec coverage

> "How many architectural assertions have a corresponding test?"

Count of architectural assertions with a 1:1 mapping to a generated test, divided
by total architectural assertions.

**Per-cell scoring:**
- 5 — 100 % of assertions have a test, mapping is explicit (line-level)
- 4 — 100 % have a test, mapping is implicit (must reverse-engineer)
- 3 — 75-99 % have a test
- 2 — 50-74 % have a test
- 1 — < 50 % have a test

Phase A: I'll grep the test_plan output for verbal echoes of assertions in
architecture.md. Phase B: I'll match each generated test back to the
`### Requirement: <Name>` it claims to verify (Phase B prompt MUST require
this back-reference; otherwise the test isn't fair).

---

## 3. Regeneration stability

> "If I run the pipeline twice on the same input, do I get the same artifact?"

Levenshtein distance between architecture.md from run-1 vs run-2, normalized by
mean length.

**Per-cell scoring (single number per phase, not per run):**
- 5 — < 5 % normalized distance (essentially identical)
- 4 — 5-15 %
- 3 — 15-30 %
- 2 — 30-60 %
- 1 — > 60 % (every run looks different)

We expect Phase A to drift heavily — free-form prose generation at temperature
0.2 still varies. Phase B's hypothesis is that constraining output to typed
structure (the same MUST/SHALL clauses, just maybe re-ordered) will yield
substantially less drift.

If Phase B doesn't beat Phase A here, **the spec-shape value is in
human-readability, not in regeneration**. That's still a real result.

---

## 4. Customer readability (blind read)

> "If I (as the user, blind to which is which) had to ship one of these to
> Kapil tomorrow morning, which lands harder?"

Idan reads architecture.md from one Phase A run + one Phase B run side-by-side
without labels (I'll randomize). Picks one. 1-5 score on:

- 5 — Phase B clearly preferred ("I'd ship this")
- 4 — Phase B mildly preferred
- 3 — Tie / either is fine
- 2 — Phase A mildly preferred
- 1 — Phase A clearly preferred ("Phase B is structure for structure's sake")

This is the only subjective metric. It's what the customer's CISO actually
experiences, so it counts.

---

## 5. Validator-grade structural correctness

> "Does the artifact survive `openspec validate --strict`?"

**Per-cell scoring:**
- 5 — `openspec validate <change> --strict` exits 0 with no warnings
- 4 — Validates, with warnings
- 3 — Validates only after one minor structural fix (filename, header)
- 2 — Validates only after multiple structural fixes
- 1 — Cannot be made to validate (semantically wrong-shape)

Phase A is structurally guaranteed to fail (it's free-form prose). Score = 1.
Phase B has to *actually validate* — the test isn't "does it look like a
spec," it's "does the OpenSpec CLI accept it."

This dimension is biased toward Phase B by construction. The interesting
question is HOW HARD it is to make Phase B output validate. If we need
heavy post-processing, the cost-of-shape is real.

---

## 6. Cost / latency

> "What does the spec-shape cost in tokens and seconds?"

Mean of `total_tokens` and `total_cost_usd` across the 3 runs per phase.

**Reporting shape:** absolute numbers, not 1-5. We'll see whether Phase B's
tighter output schema costs more (longer prompts) or less (more deterministic,
shorter responses). Hypothesis is +20-50 % token cost for Phase B in exchange
for the structural gains.

If Phase B costs more than 2× and the structural gains aren't decisive
elsewhere, that's a signal the experiment is recommending a worse pipeline.

---

## Pass / fail

OpenSpec-shaped Phase B is recommended IF:

1. Wins by ≥ 1.0 on at least 3 of (Traceability, Test-spec coverage,
   Regeneration stability, Customer readability), AND
2. Cost / latency is within 2× of Phase A, AND
3. Validator-grade is 4 or 5 on Phase B (no point shipping output that
   doesn't actually validate).

OpenSpec-shaped Phase B is rejected IF:

1. Loses on Customer readability (hardest signal — if Idan prefers prose, that's
   the customer's real experience), OR
2. Cost > 3× Phase A with marginal gains elsewhere, OR
3. Validator-grade ≤ 2 (we couldn't actually make the artifact OpenSpec-valid).

A mixed result ("structure helps Architect, doesn't help TestPlan") is also
expected and useful — surfaces it as an additive layer on a subset of stages
rather than a wholesale rewrite.

---

## What this rubric explicitly is NOT measuring

- **Long-term drift correction.** "Spec → Code drift detection by Pipeline
  Doctor" is the next experiment. Out of scope here.
- **Cross-customer reuse.** Capability sharing across HCA / Cigna is a 6-month
  hypothesis, not a 6-hour one.
- **Plan Mode-as-Resolver.** Different axis entirely.
- **Workshop-day demo polish.** Both phases get judged on artifact substance,
  not slide presentation.

---

## Scoring spreadsheet

```
                              Phase A          Phase B          Δ
                              run1 run2 run3   run1 run2 run3   (mean)
1. Traceability density        ?    ?    ?      ?    ?    ?     ?
2. Test-spec coverage          ?    ?    ?      ?    ?    ?     ?
3. Regeneration stability      ?              ?                 ?
4. Customer readability        (single blind read score)        ?
5. Validator-grade            (1)            (?)                ?
6. Tokens / USD               ($?, ?tok)     ($?, ?tok)         ?×
```

Filled in `experiments/COMPARISON.md` after both phases run.
