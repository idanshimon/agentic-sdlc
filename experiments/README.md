# Phase A vs Phase B Experiment

**Hypothesis:** OpenSpec-shaped artifacts (typed spec deltas with MUST/SHALL +
WHEN/THEN scenarios) emitted by the Architect/TestPlan/Deliver stages produce
more durable, traceable, regenerable, customer-readable outputs than free-form
prose.

## Method

- **Same PRD:** `samples/prds/patient-vitals-streaming.txt`
- **Same human input:** `experiments/fixtures/resolver-decisions.yaml` —
  fixed resolver responses so all runs see identical Gate-1 input
- **Same model routing:** Databricks-Anthropic for assessor/architect/test_plan/codegen
  (claude-sonnet-4-6); ingest stays as-is (just normalizes)
- **Same temperature:** 0.2 (orchestrator default)
- **N=3 runs per phase** to detect run-to-run variance vs phase variance

## Phase A — Baseline

Runs the orchestrator stages exactly as they ship today. No code changes.
Output: free-form prose architecture, free-form Given/When/Then test plan,
free-form code, prose decisions.md.

Stored at: `experiments/results/phase-a/run-{1,2,3}/`

## Phase B — OpenSpec-instrumented

Modified Architect, TestPlan, and Deliver stages emit OpenSpec-shaped artifacts:
- Architect produces `proposal.md` + `design.md` + `specs/<cap>/spec.md` (ADDED Requirements with MUST/SHALL + WHEN/THEN scenarios)
- TestPlan generates one test per scenario, mechanically (1:1 mapping)
- Deliver writes a real `openspec/changes/<run-id>-<slug>/` folder structure
- Ledger gains `entry_type=spec_delta` for each MUST clause shipped

Stored at: `experiments/results/phase-b/run-{1,2,3}/`

## Reflection

`experiments/RUBRIC.md` is written BEFORE Phase B build begins, so scoring is
not biased by what the Phase B output ends up looking like.

`experiments/COMPARISON.md` is the final side-by-side write-up.
