# Fix Test Plan stage to receive decisions context

## Why

The TestPlan stage today receives only `architecture[:2000]` and produces
generic CRUD contract tests (POST 201, GET 200, 400, 404, DELETE 204) for
any PRD — including a streaming WebSocket vitals API where every test is
inapplicable. The 6-hour Phase A vs Phase B experiment in `experiments/`
documented this in 3 consecutive runs against the Patient Vitals Streaming
PRD: zero generated tests covered the actual architectural assertions
(WebSocket JWT validation, mTLS+OAuth vendor auth, HMAC tokenization,
p95/p99 latency, 99.95% uptime).

Root cause: `apps/orchestrator/_pipeline_stages.py` `stage_test_plan`
passes only `architecture` from the previous stage, with no Resolver
decisions context, no PRD excerpt, and no scenario hints. The stage
pattern-matches "architecture" → "REST API contract tests" and ships
generics regardless of input.

This is decoupled from any OpenSpec adoption — fixing it improves every
demo run today.

## What Changes

- `stage_test_plan` accepts decisions + prd_text alongside architecture
- TestPlan prompt is rewritten to require: each test cites the architectural
  assertion it verifies; tests use the actual domain language from
  decisions; no generic CRUD scaffolding
- Test names follow `test_<assertion_slug>` for grep-traceability
- One regression case added to `apps/orchestrator/eval/` (the new harness
  promoted from `experiments/`) that fails CI if test-spec coverage drops
  below 3/5 on the rubric

## Capabilities

### Modified Capabilities
- `pipeline`: TestPlan stage MUST consume decisions and PRD text; tests
  MUST reference the specific architectural assertions they verify

## Impact

- Affected files: `apps/orchestrator/_pipeline_stages.py`,
  `apps/orchestrator/prompt_library.py` (new test_plan variants),
  `apps/orchestrator/tests/test_stage_test_plan.py`
- No schema or API changes
- Migration: none — same SSE event shape

## Safety Impact

None. TestPlan output is informational; the change strictly improves what
gets shown to engineers reviewing PRs. PHI-class invariants are unaffected
(TestPlan does not read or write PHI).

## Non-Goals

- OpenSpec-shaped TestPlan (separate change `add-spec-shaped-testplan`,
  Tier 2)
- Tests that actually execute (still skeletons with `pytest.fail` body)
- Refactoring CodeGen consumption of TestPlan output

## Empirical evidence

`experiments/COMPARISON.md` — 3 Phase A runs, all produced identical
generic CRUD tests; rubric test-spec-coverage score = 1.0 across all runs.

## Rollback plan

Single commit; revert if rubric scores regress on existing fixture or any
demo run produces materially worse tests than the current generics. Low
risk — current state is so degraded that any concrete improvement is a net
gain.
