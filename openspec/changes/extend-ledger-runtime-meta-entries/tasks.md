# Tasks — extend ledger with runtime/meta entry types

## Code changes

- [ ] `packages/ledger-core/models.py` — add `entry_type` field, meta-only fields, runtime-only fields, model_validator
- [ ] `packages/ledger-core/models.py` — add `ReviewerAttribution` and `CanaryMetrics` sub-models
- [ ] `packages/ledger-core/cosmos.py` — update Cosmos indexing policy to include `/entry_type/?`, `/bundle_refs/[]/?`, `/blast_class/?`, `/agent_session_id/?`
- [ ] `packages/ledger-core/queries.py` — add `query_meta_by_bundle()`, `query_runtime_by_session()`, `find_precedent_by_bundle_ref()` helper queries
- [ ] `packages/ledger-core/__init__.py` — export the new types

## Test changes

- [ ] `packages/ledger-core/tests/test_models.py::test_runtime_entry_requires_run_id_or_session_id` — failing test first
- [ ] `packages/ledger-core/tests/test_models.py::test_meta_entry_requires_change_ticket_blast_reviewers` — failing test
- [ ] `packages/ledger-core/tests/test_models.py::test_meta_entry_rejects_run_id_or_stage` — failing test
- [ ] `packages/ledger-core/tests/test_models.py::test_v06_entry_auto_promotes_to_runtime` — backward compat test
- [ ] `packages/ledger-core/tests/test_queries.py::test_query_meta_by_bundle_returns_only_meta` — query separation test
- [ ] `packages/ledger-core/tests/test_queries.py::test_find_precedent_includes_meta_entries` — autopilot path test

## Documentation

- [ ] `docs/LEDGER-SCHEMA.md` — explain runtime vs meta, give examples of each
- [ ] Update `AGENTS.md` ledger contract section to reflect new schema

## Verification (definition of done)

- [ ] All new tests passing
- [ ] Cosmos indexing policy applied without runtime errors against existing data
- [ ] One runtime entry written successfully end-to-end via orchestrator
- [ ] One meta entry written successfully via standards-change-agent test fixture
- [ ] Query `entry_type = 'meta' AND 'security/v0.1.0/PHI-001' IN bundle_refs` returns expected entries
