# Add pipeline eval harness as first-class repo capability

## Why

The 6-hour Phase A vs Phase B experiment in `experiments/` produced an
eval harness that empirically scored two pipeline variants on a fixed
PRD across 6 dimensions. The harness is now the most durable artifact
from that work — every future v0.8/v0.9/v1 question ("does GPT-4.1 beat
Sonnet for Architect?", "does the Foundry route win on PHI cards?",
"does the spec-shaped Architect actually help?") can run through this
loop in hours rather than days.

The harness lives at `experiments/` today, structured for one-off use.
To benefit subsequent stage-prompt or routing changes it needs to:

- Live alongside the orchestrator code as a first-class repo capability
- Run in CI as a regression gate
- Be reusable beyond the Patient Vitals fixture (multiple PRDs, multiple
  stages, multiple variants)
- Carry deterministic fixtures so scores compare apples-to-apples

## What Changes

- New top-level path `apps/orchestrator/eval/`:
  - `eval/runner.py` — port of `experiments/run_phase_a.py` minus the
    research scaffolding, parameterised on (PRD, fixture, stage-overrides)
  - `eval/score_rubric.py` — port of `experiments/score_rubric.py`
  - `eval/fixtures/patient-vitals/{prd.txt, decisions.yaml, expected.json}`
  - `eval/fixtures/<other PRDs over time>`
  - `eval/RUBRIC.md` — promoted from `experiments/RUBRIC.md`, version-pinned
- CI step `eval-rubric-regression` runs against every PR that touches
  `_pipeline_stages.py`, `prompt_library.py`, or any `eval/fixtures/*`
- Fail thresholds per dimension stored in `eval/thresholds.yaml` (initially
  generous; tightened as baseline stabilises)
- `experiments/` stays for one-off research; the production harness is the
  one in `apps/orchestrator/eval/`

## Capabilities

### New Capabilities
- `pipeline-eval-harness`: first-class evaluation surface with
  deterministic fixtures, mechanical rubric scoring, and CI regression
  gates for stage-prompt or routing changes

## Impact

- New files under `apps/orchestrator/eval/` (~600 lines ported from `experiments/`)
- New CI workflow step ~3 min wall-clock per PR (model latency dominates)
- Cosmos quota: zero (harness uses file-shimmed ledger)
- LLM cost per CI run: ~$0.20-0.65 depending on N (start with N=1 in CI,
  N=3 on nightly)

## Safety Impact

The harness exercises real LLM providers with a sample PRD, no PHI. Per
AGENTS.md PHI rules: sample PRDs in fixtures must use synthetic identifiers
only (`PT-DEMO-0001`, `1900-01-01`). No production data ever flows through
the eval harness.

## Non-Goals

- Replacing `apps/orchestrator/tests/` (unit tests stay)
- Auto-promoting prompt variants based on rubric scores (that's the
  prompt-library bundle work, deferred)
- Multi-model comparison out of the box (added later when we need it)

## Empirical evidence

`experiments/COMPARISON.md` — the harness scored Phase A vs Phase B on
all 6 rubric dimensions; the structure proved reusable and the rubric
distinguished real signal from cosmetic differences.

## Rollback plan

Single change introducing new directory; revert by deleting if it proves
flaky in CI. No production code path depends on it.
