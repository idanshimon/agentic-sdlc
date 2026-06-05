# Tasks — add Standards Bundles plane

## Schema docs

- [ ] `standards-bundles/BUNDLE-SCHEMA.md` — full schema docs for rules/envelope/reviewers/PINS
- [ ] `standards-bundles/README.md` — overview, governance flow, deployment guidance

## Reference bundles (v0.1.0)

### security
- [ ] `standards-bundles/security/v0.1.0/rules.yaml` — PHI-001 through PHI-005, secret-scan rules, SBOM requirements
- [ ] `standards-bundles/security/v0.1.0/envelope.yaml` — explicitly empty (no auto-fixes allowed for security)
- [ ] `standards-bundles/security/v0.1.0/reviewers.yaml` — security_lead + privacy_dpo for HIGH
- [ ] `standards-bundles/security/v0.1.0/README.md` — rationale per rule

### architect
- [ ] `standards-bundles/architect/v0.1.0/rules.yaml` — allowed-stacks (Python 3.11+, Node 20+, FastAPI, Next.js), service patterns, deployment targets
- [ ] `standards-bundles/architect/v0.1.0/envelope.yaml` — provider-routing changes, retry counts within bounds
- [ ] `standards-bundles/architect/v0.1.0/reviewers.yaml` — architect_lead for MED/LOW, +security for HIGH
- [ ] `standards-bundles/architect/v0.1.0/README.md`

### privacy
- [ ] `standards-bundles/privacy/v0.1.0/rules.yaml` — HIPAA min-necessary, retention windows (7 years for clinical, 3 for ops), consent surfaces
- [ ] `standards-bundles/privacy/v0.1.0/envelope.yaml` — empty (privacy never auto-fixed)
- [ ] `standards-bundles/privacy/v0.1.0/reviewers.yaml` — privacy_dpo MUST be in HIGH
- [ ] `standards-bundles/privacy/v0.1.0/README.md`

### finops
- [ ] `standards-bundles/finops/v0.1.0/rules.yaml` — per-team monthly budget, $/decision ceilings, model selection rules
- [ ] `standards-bundles/finops/v0.1.0/envelope.yaml` — autopilot threshold tuning, retry-count tuning (LOW blast)
- [ ] `standards-bundles/finops/v0.1.0/reviewers.yaml` — finops_lead for LOW, +architect for MED
- [ ] `standards-bundles/finops/v0.1.0/README.md`

## PINS

- [ ] `standards-bundles/PINS.yaml` — defaults + sample team-overrides

## Code

- [ ] `packages/ledger-core/standards.py` — load_bundle(dept, version), get_pinned_version(team_id, dept), validate_rule_ref(ref)
- [ ] `apps/orchestrator/main.py` — refuse to start if any PINS.yaml entry is unresolvable

## Standards-change agent

- [ ] `.github/agents/standards-change.agent.md` — persona, tool allow-list (gh CLI scoped), bundle subscriptions
- [ ] `.github/agents/templates/adr.md.j2` — ADR template
- [ ] `.github/workflows/standards-change-on-pr-open.yml` — GitHub Actions workflow that invokes the agent on PR open against `standards-bundles/`

## Tests

- [ ] `tests/test_bundle_schema.py::test_rules_yaml_validates` — schema validation
- [ ] `tests/test_bundle_schema.py::test_envelope_yaml_validates`
- [ ] `tests/test_bundle_schema.py::test_reviewers_yaml_validates`
- [ ] `tests/test_bundle_schema.py::test_pins_yaml_validates`
- [ ] `tests/test_bundle_loader.py::test_load_bundle_by_dept_version`
- [ ] `tests/test_bundle_loader.py::test_get_pinned_version_falls_back_to_default`
- [ ] `tests/test_bundle_loader.py::test_validate_rule_ref_format`
- [ ] `tests/test_standards_change_agent.py::test_phi_change_classified_HIGH`
- [ ] `tests/test_standards_change_agent.py::test_threshold_tuning_classified_LOW`
- [ ] `tests/test_standards_change_agent.py::test_pattern_change_classified_MED`
- [ ] `tests/test_standards_change_agent.py::test_high_blast_assigns_3_reviewers_with_required_roles`

## Verification (definition of done)

- [ ] All four reference bundles load cleanly (validation passes)
- [ ] Orchestrator starts cleanly with default PINS
- [ ] Synthetic PR against a bundle triggers the agent → correct blast classification + reviewer set
- [ ] One real meta ledger entry exists from a simulated approved-PR merge
