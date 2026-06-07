# Spec delta — add-pipeline-eval-harness

## ADDED Requirements

### Requirement: Pipeline eval harness exists as a first-class repo capability
The repository MUST carry an evaluation harness under
`apps/orchestrator/eval/` that runs the orchestrator pipeline against
deterministic PRD fixtures and scores the output against a published
rubric, with at least one canonical fixture (Patient Vitals Streaming)
and at least five mechanical rubric dimensions.

#### Scenario: Harness runs end-to-end on a fixture
- **WHEN** a developer runs `python -m apps.orchestrator.eval.runner
  --fixture patient-vitals --n 1`
- **THEN** the runner executes the full pipeline (ingest → assessor →
  resolver → architect → test_plan → codegen → review_scan → deliver)
  and writes a `scores.json` containing numeric scores per rubric
  dimension along with raw artifacts under `eval/results/<run_id>/`

#### Scenario: Rubric scoring is mechanical and reproducible
- **WHEN** the harness scores two artifact directories that have
  identical content
- **THEN** it MUST produce identical numeric scores (no LLM call inside
  the scorer; all dimensions other than blind-read-readability are
  computed by deterministic parsers and string distance metrics)

### Requirement: CI regresses on rubric-score drops
The CI pipeline MUST run the eval harness against the Patient Vitals
fixture on every PR that modifies `_pipeline_stages.py`,
`prompt_library.py`, or any file under `apps/orchestrator/eval/fixtures/`,
and MUST fail the build if any rubric dimension regresses below the
threshold defined in `apps/orchestrator/eval/thresholds.yaml`.

#### Scenario: Regression PR is rejected
- **WHEN** a PR introduces a stage-prompt change that drops the
  test-spec-coverage rubric score below 3 on the Patient Vitals fixture
- **THEN** the CI step `eval-rubric-regression` exits non-zero and the
  PR is blocked from merging until the score recovers or thresholds are
  explicitly relaxed via a paired bundle change

#### Scenario: Non-regressing PR passes CI
- **WHEN** a PR modifies a stage prompt without affecting rubric scores
  (e.g. typo fix, comment edit)
- **THEN** the CI step runs to completion within ~3 minutes and exits
  with success

### Requirement: Fixtures carry frozen baselines for comparability
Each fixture under `apps/orchestrator/eval/fixtures/<name>/` MUST include
a `baseline.json` with N=3 reference scores captured at fixture
inception, so regressions are measured against a stable reference rather
than a moving target.

#### Scenario: Baseline is referenced by CI thresholds
- **WHEN** CI runs the eval harness against fixture `<name>`
- **THEN** the rubric scores are compared against the values in
  `fixtures/<name>/baseline.json`, not against any external service or
  prior CI run
