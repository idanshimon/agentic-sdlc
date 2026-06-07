# Phase A Reflection — written BEFORE Phase B build

**Authored:** 2026-06-06, after Phase A v2 results in hand, BEFORE Phase B
build started or Phase B run executed. Locking these observations in early
so the Phase B build doesn't get unconsciously biased toward the gaps I
already saw.

---

## What Phase A actually produced

Three runs of the live orchestrator pipeline against the Patient Vitals
Streaming PRD, with five fixed Resolver decisions applied identically across
all runs.

| Run | Cards | Gating | Decisions | Tokens | $ | Wall |
|-----|------:|-------:|----------:|-------:|--:|-----:|
| 1   |    8  |     5  |      5   | 16,037 | $0.2167 | 182.5s |
| 2   |    7  |     5  |      5   | 15,065 | $0.2019 | 166.6s |
| 3   |    8  |     5  |      5   | 15,506 | $0.2114 | 185.9s |
| Σ   |       |        |          | 46,608 | $0.6300 | 535.0s |

Run-to-run cost variance: **7.4%**. That's the noise floor for this PRD +
this model + 0.2 temperature.

## Bug surfaced and isolated (but kept in the comparison)

The default Databricks provider caps `max_tokens=4096`. The Assessor prompt
asks for 5–8 cards × ~250 tokens each (with options + rationale +
downstream_impact), which routinely truncates into invalid JSON. The
orchestrator's fallback path then ships **2 hard-coded cards with empty
`options[]`**, which makes resolver decisions land as `"accept: (no options)"`
and the Architect (correctly) refuses to hallucinate without real input.

The harness applies a runtime-only `max_tokens=8192` patch that affects
Phase A AND Phase B identically. The deployed orchestrator code is unchanged.

This is itself a Phase A finding. The prose-pipeline has a fragility — a
single LLM-call truncation triggers a silent cascade that destroys the
downstream artifact. Phase B (typed schemas, structural validation) is
intended to surface that earlier.

## Per-dimension Phase A scoring (per RUBRIC.md)

### 1. Traceability density

**Phase A score: 4 (mean across 3 runs).**

Architect prompt explicitly asks for "cite which decision drove each bullet"
and the model honors it. Every bullet carries a `*(Decision: …)*` tag in
parens. Run-1 has 5/5 decisions cited; run-2 has 5/5; run-3 has 5/5.
Score is 4 not 5 because the citations are paraphrases ("WebSocket JWT
auth"), not stable IDs — refactoring the decision text would orphan the
citation silently. No back-link to card_id.

### 2. Test-spec coverage

**Phase A score: 1 (catastrophic).**

Across all 3 runs, TestPlan emits 5 generic CRUD contract tests (POST 201,
GET 200, 400, 404, DELETE 204). **Zero overlap with architectural
assertions.** None of:

- WebSocket JWT validation before HTTP 101
- mTLS + OAuth client_credentials vendor auth
- HMAC-SHA256 deterministic PHI tokenization
- p95 latency budget at WebSocket boundary
- 99.95% monthly uptime SLO

are tested. The TestPlan stage gets `architecture[:2000]` only — no PRD
context, no decisions, no scenarios. It pattern-matches the word
"architecture" to "REST API contract tests" and produces something useless.

This is a real gap in the orchestrator, not a comparison artifact.

### 3. Regeneration stability

**Phase A score: 2.**

All three architecture.md outputs are coherent and decision-anchored, but
the decomposition differs substantially:

- Run 1: WebSocket API Gateway → Vendor Connector Layer → PHI De-id Sidecar
- Run 2: Vendor Connector Layer → WebSocket Ingest Gateway → FHIR Normalization Service
- Run 3: Vendor WebSocket Gateway → Internal Auth Server → PHI Tokenization Service

Same decisions resolved, but three different architectural shapes. Naming
varies, ordering varies, responsibility splits vary. Eyeballing the diff,
normalized Levenshtein is in the 30–60% range across pairs. Not catastrophic
— each is internally consistent — but a customer comparing two runs would
see "different architectures" not "the same architecture rephrased."

### 4. Customer readability

**Phase A score: pending blind read after Phase B.**

Subjective — will randomize one run from each phase and ask Idan to pick.
Phase A architecture is genuinely well-written prose: cites decisions
inline, uses domain language ("HIPAA Safe Harbor 18 identifiers", "FHIR R4
Observation"), structures into logical sections. It's not bad. The question
is whether typed structure beats good prose for the specific job of
"customer ships this to their CISO."

### 5. Validator-grade structural correctness

**Phase A score: 1 (by definition).**

Phase A output is free-form Markdown with no spec headers. `openspec
validate` would reject it instantly. This dimension is biased toward
Phase B by construction; the interesting question is whether Phase B can
*actually* hit 4 or 5.

### 6. Cost / latency

**Phase A baseline: $0.21/run, 178s/run, 15.5k tokens/run.**

This is the floor we're comparing Phase B against. Hypothesis: Phase B's
tighter schema costs +20–50% in tokens (longer prompts demanding structure).
If Phase B exceeds 2× cost without compensating dimension wins, it's a
worse pipeline.

## What Phase B has to do to win

Per the rubric: ≥1.0 mean delta on at least 3 of (Traceability, Test-spec,
Regen, Readability), within 2× cost, and validator-grade ≥4.

The two dimensions where Phase A is wide-open for displacement:

1. **Test-spec coverage (Phase A = 1).** Mechanical scenario→test mapping
   is the highest-leverage move. If Phase B's TestPlan reads the spec
   instead of the architecture and emits one pytest function per `####
   Scenario:`, it almost can't help winning.
2. **Regen stability (Phase A = 2).** If Phase B produces structurally
   identical specs (same Requirements in possibly different order), the
   regen score should jump to 4+.

Where Phase A is strong and Phase B has to prove its worth:

3. **Customer readability (Phase A = good prose).** Spec deltas are not
   prose. They're typed. Whether they read better is a real question, not
   a foregone conclusion. Some customers prefer prose; some prefer typed
   contracts. Idan's blind read decides.
4. **Cost (Phase A = $0.21/run).** Phase B prompt has to demand structure,
   cite decisions by ID, write proposal+design+spec — that's more
   instructions, more output, more $. The question is whether the gain
   justifies the spend.

## What I'm specifically watching for during Phase B build

**Honesty checks I'm pre-committing to:**

1. If Phase B's first run can't validate with `openspec validate --strict`,
   I do NOT silently hand-fix the spec to make the rubric pass. The
   validator score reports the unfixed state. Hand-fixing means the
   pipeline isn't actually emitting valid OpenSpec; the test fails.

2. If the Phase B prompt has to be 3× longer to get useful structure, I
   note that as a pragmatic finding, not a "but the prompt could be
   shorter someday." Customers see today's cost.

3. If Phase B regen stability is *worse* than Phase A (because typed
   schemas amplify small wording differences), I report it. Surprising
   results are signal.

4. If TestPlan in Phase B can't actually reverse-derive concrete tests
   from MUST clauses (because the model needs more context than just
   the scenarios), I note that as "spec→test isn't fully mechanical;
   needs a generator pass."

## Locked-in observations

- Phase A pipeline ships free-form prose end-to-end
- TestPlan is decoupled from decisions (only sees architecture text)
- Architect honors decision-citation requests in its prompt
- Run-to-run cost variance is small (7.4%); content variance is large
- The orchestrator's silent-fallback paths are real production bugs that
  spec-shape MIGHT catch via Pydantic validation, MIGHT NOT

Now: build Phase B.
