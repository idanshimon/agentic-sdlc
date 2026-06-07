# Spec delta — fix-test-plan-decisions-context

## MODIFIED Requirements

### Requirement: TestPlan stage receives decisions and PRD context
The TestPlan stage MUST consume the Resolver-resolved decisions and the
PRD text alongside the upstream architecture, and the generated tests MUST
reference the specific architectural assertions and decisions they verify
rather than ship generic REST/CRUD scaffolding.

#### Scenario: Streaming PRD does not produce CRUD tests
- **WHEN** TestPlan runs on a PRD whose architecture references WebSocket,
  event streaming, or non-REST transport
- **THEN** the generated tests do not contain bare HTTP-status-code
  contract tests (e.g. plain "POST returns 201", "DELETE returns 204")
  unless those status codes appear in the resolved decisions

#### Scenario: Each test cites an architectural assertion or decision
- **WHEN** TestPlan emits a generated test
- **THEN** the test name or its docstring references at least one named
  architectural assertion (component name, decision keyword, or
  Requirement title) that appears in the upstream architecture or
  decisions context

#### Scenario: Decisions context is propagated through the SSE driver
- **WHEN** an orchestrator run reaches the TestPlan stage
- **THEN** `stage_test_plan` is invoked with both `prd_text` and
  `decisions` arguments populated from the current `RunState`, not
  `None` defaults

### Requirement: Eval-harness regression gate on TestPlan quality
The orchestrator repository MUST carry a CI-wired eval harness that
re-runs the Patient Vitals fixture and fails the build if the
test-spec-coverage rubric score for the TestPlan output drops below 3
(out of 5).

#### Scenario: CI fails on TestPlan regression
- **WHEN** a PR modifies `_pipeline_stages.stage_test_plan`,
  `prompt_library.py` TestPlan variants, or any prompt-library entry
  whose stage is `test_plan`
- **THEN** the CI pipeline runs the eval harness on the Patient Vitals
  fixture and the build fails if the test-spec-coverage score is < 3
