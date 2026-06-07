# Tasks — add-pipeline-eval-harness

## 1. Port harness to apps/orchestrator/eval/

- [ ] 1.1 Create `apps/orchestrator/eval/__init__.py`,
      `eval/runner.py`, `eval/score_rubric.py`, `eval/RUBRIC.md`
- [ ] 1.2 Refactor `runner.py` to accept `Fixture` objects:
      `(prd_path, decisions_path, expected_scores_path)` parameterized over
      stage-overrides, model, temperature, N
- [ ] 1.3 Carry over the `max_tokens=8192` provider patch from the
      experiment harness as opt-in (`runner_config.allow_max_tokens_override`)
      because the deployed orchestrator's 4096 default truncates Assessor
      JSON; document the patch's rationale alongside the orchestrator
      `_call()` signature
- [ ] 1.4 Validation: `pytest apps/orchestrator/eval/tests/` green,
      one-shot run on Patient Vitals fixture reproduces the scores from
      `experiments/SCORES.json` within ±0.5 per dimension

## 2. Fixtures with deterministic baselines

- [ ] 2.1 `eval/fixtures/patient-vitals/{prd.txt, decisions.yaml}`
      copied from `experiments/`
- [ ] 2.2 `eval/fixtures/patient-vitals/baseline.json` — a frozen N=3
      score snapshot of Phase A as the regression baseline
- [ ] 2.3 Validation: `pytest apps/orchestrator/eval/test_baselines.py`
      verifies fixtures are wellformed (PRD non-empty, fixture parses,
      baseline.json schema matches)

## 3. CI integration

- [ ] 3.1 New GH Actions step `eval-rubric-regression` triggered on PRs
      touching `_pipeline_stages.py`, `prompt_library.py`,
      `apps/orchestrator/eval/fixtures/*`, or any prompt file
- [ ] 3.2 Step runs `python -m apps.orchestrator.eval.runner --fixture
      patient-vitals --n 1 --threshold-from baseline.json`
- [ ] 3.3 Fail when any dimension regresses by more than the thresholds
      in `eval/thresholds.yaml`
- [ ] 3.4 Validation: deliberate-regression test PR (revert any one of
      the Phase B improvements on the spec-shaped branch) is rejected
      by CI

## 4. Documentation + ledger

- [ ] 4.1 `apps/orchestrator/eval/README.md` — how to run, how to add a
      new fixture, how to interpret scores
- [ ] 4.2 Update `AGENTS.md` to reference the eval harness as the
      regression gate for stage-prompt edits
- [ ] 4.3 Validation: `meta` ledger entry on merge declaring the new
      capability and the `pipeline-eval-harness` spec
