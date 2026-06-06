# finops/v0.1.0

FinOps bundle — per-team budgets, cost-per-decision ceilings, autopilot
confidence thresholds, model selection.

## Auto-fix envelope

Pipeline Doctor MAY auto-fix:
- Autopilot thresholds (range [0.70, 0.95], max delta 0.05 per run)
- Cost-per-decision ceilings (range [0.01, 1.00], max delta 0.05 per run)

Both require 7-14 days of persistent drift signal AND non-PHI scope.

Auto-fix is FORBIDDEN on:
- BUDGET-MONTHLY-001 (budget changes always require human approval)

## Rule index

| ID | Title | Severity |
|---|---|---|
| BUDGET-MONTHLY-001 | Per-team monthly LLM budget ceiling | WARN |
| COST-PER-DECISION-001 | Cost-per-decision ceiling per stage | WARN |
| AUTOPILOT-THRESHOLD-AUTH | Autopilot threshold for auth-policy | WARN |
| AUTOPILOT-THRESHOLD-NAMING | Autopilot threshold for naming-convention | WARN |
| MODEL-SELECTION-001 | Approved model selections | WARN |
