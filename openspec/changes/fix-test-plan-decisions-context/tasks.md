# Tasks — fix-test-plan-decisions-context

## 1. TestPlan stage signature + prompt

- [x] 1.1 Extend `stage_test_plan(run, prd_text=None, decisions=None)` —
      backward-compatible defaults so existing callers work
- [x] 1.2 Update `main.py` SSE driver to pass `prd_text` (cached on run)
      and `run.decisions` to TestPlan
- [x] 1.3 Rewrite TestPlan system prompt: require architectural-assertion
      citations per test, ban generic-CRUD scaffolding when the PRD shows
      streaming/event-driven patterns
- [x] 1.4 Validation: prompt run on Patient Vitals fixture must produce
      tests that name `WebSocket`, `mTLS`, `OAuth`, `HMAC`, or other
      decision-grounded terms (regex check in test) — verified empirically
      via `experiments/results/phase-a-fixed/run-1/test_plan.md`

## 2. Prompt library variants

- [ ] 2.1 Add 6 TestPlan variants to `prompt_library.py` (one per provider
      shape per AOAI/Anthropic/Databricks pair)
- [ ] 2.2 Each variant carries `model_compat_notes` documenting the
      provider-specific framing differences
- [ ] 2.3 Validation: `pytest apps/orchestrator/tests/test_prompt_library.py`
      green

## 3. Eval-harness regression case

- [ ] 3.1 Promote `experiments/run_phase_a.py` + `score_rubric.py` to
      `apps/orchestrator/eval/` (separate change `add-pipeline-eval-harness`
      may ship first)
- [ ] 3.2 Add fixture: `apps/orchestrator/eval/fixtures/patient-vitals/`
      with PRD + canonical resolver decisions
- [ ] 3.3 CI step: `pytest apps/orchestrator/eval/test_test_plan_regression.py`
      fails if test-spec-coverage rubric score < 3 on Patient Vitals
- [ ] 3.4 Validation: harness run on the fix produces test-spec-coverage
      ≥ 3 (target 4-5)

## 4. Documentation + ledger

- [ ] 4.1 Update `apps/orchestrator/README.md` TestPlan section
- [ ] 4.2 Validation: `meta` ledger entry on merge documenting the prompt
      change and pre/post rubric scores
