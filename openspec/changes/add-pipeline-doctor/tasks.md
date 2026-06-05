# Tasks — add Pipeline Doctor agent

## Code

- [ ] `apps/pipeline-doctor/pyproject.toml` (deps: pydantic, pyyaml, httpx, gh CLI wrapper, packages/ledger-core)
- [ ] `apps/pipeline-doctor/pipeline_doctor/__init__.py`
- [ ] `apps/pipeline-doctor/pipeline_doctor/models.py` — DriftSignal, AutoFixProposal, ChangeProposal, EnvelopeCheck, EnvelopeViolation
- [ ] `apps/pipeline-doctor/pipeline_doctor/drift_detector.py` — 5 signal detectors (autopilot rejection, cost-per-decision, class drift, unused rule, phi violation)
- [ ] `apps/pipeline-doctor/pipeline_doctor/envelope_validator.py` — load+validate against bundle envelope.yaml, hard-code PHI block
- [ ] `apps/pipeline-doctor/pipeline_doctor/auto_fixer.py` — apply within envelope, write runtime ledger entry
- [ ] `apps/pipeline-doctor/pipeline_doctor/change_proposer.py` — open PR via gh CLI, render ADR from template
- [ ] `apps/pipeline-doctor/pipeline_doctor/main.py` — entrypoint (parse args, run detectors, dispatch fixes/proposals)
- [ ] `apps/pipeline-doctor/templates/adr.md.j2` — Jinja2 ADR template
- [ ] `apps/pipeline-doctor/Dockerfile` — Python 3.11 slim, gh CLI installed
- [ ] `apps/pipeline-doctor/README.md`

## Tests

- [ ] `tests/test_envelope_validator.py::test_phi_rules_always_blocked` — failing test first
- [ ] `tests/test_envelope_validator.py::test_within_bounds_passes`
- [ ] `tests/test_envelope_validator.py::test_outside_bounds_fails_with_violation_detail`
- [ ] `tests/test_envelope_validator.py::test_deny_rule_pattern_blocked`
- [ ] `tests/test_drift_detector.py::test_autopilot_rejection_rate_threshold` (each of 5 signals → tests)
- [ ] `tests/test_drift_detector.py::test_cost_per_decision_baseline_comparison`
- [ ] `tests/test_drift_detector.py::test_class_drift_unprecedented`
- [ ] `tests/test_drift_detector.py::test_bundle_rule_unused_30d`
- [ ] `tests/test_drift_detector.py::test_phi_class_violation_immediate_signal`
- [ ] `tests/test_auto_fixer.py::test_writes_runtime_ledger_entry` — agent attribution correct
- [ ] `tests/test_auto_fixer.py::test_emits_notification_on_apply`
- [ ] `tests/test_auto_fixer.py::test_rate_limits_per_dept_per_week`
- [ ] `tests/test_change_proposer.py::test_pr_body_renders_with_adr`
- [ ] `tests/test_change_proposer.py::test_pr_assigns_correct_reviewers`
- [ ] `tests/test_change_proposer.py::test_blast_class_in_pr_label`
- [ ] `tests/test_main.py::test_dry_run_emits_signals_no_writes` — full integration with synthetic ledger
- [ ] `tests/test_main.py::test_real_run_with_synthetic_ledger_produces_one_autofix_and_one_proposal`

## Deployment

- [ ] `infra/main.bicep` — add Container Job resource for `pipeline-doctor`, hourly schedule
- [ ] `deploy/scripts/build-pipeline-doctor.sh` — `az acr build` wrapper

## Custom agent file

- [ ] `.github/agents/pipeline-doctor.agent.md` — persona, tools allow-list, bundle subscriptions

## Verification (definition of done)

- [ ] All unit tests passing
- [ ] Integration test against synthetic ledger fixture produces: 1 auto-fix entry + 1 change-proposal PR draft
- [ ] Live in dev RG: Container Job runs hourly, ledger gets entries, no errors in logs for 24 hours
- [ ] One real auto-fix exists in the ledger from a real drift signal
- [ ] One real change-proposal PR exists on `standards-bundles/<dept>` (can be on a private fork for the demo)
