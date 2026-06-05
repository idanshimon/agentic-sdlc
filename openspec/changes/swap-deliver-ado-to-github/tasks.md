# Tasks — swap deliver stage from ADO to GitHub

## Code

- [ ] `apps/orchestrator/stages/deliver_github.py` — new module
- [ ] `apps/orchestrator/stages/deliver_ado.py` — renamed from `deliver.py` (verbatim port)
- [ ] `apps/orchestrator/stages/__init__.py` — dispatch on `config.deliver_provider`
- [ ] `apps/orchestrator/config.py` — add `deliver_provider`, `github_app`, per-team delivery target overrides
- [ ] `apps/orchestrator/main.py` — startup validation: GH App credentials valid if provider=github

## GitHub App registration

- [ ] `deploy/scripts/register-github-app.sh` — wraps `gh api` for App creation; outputs install URL + manifest
- [ ] `apps/orchestrator/github_app_client.py` — JWT signing, installation token fetch, REST helpers
- [ ] `docs/GITHUB-APP-SETUP.md` — customer-side installation guide

## Tests

- [ ] `apps/orchestrator/tests/test_deliver_github.py::test_creates_branch_named_run_id`
- [ ] `apps/orchestrator/tests/test_deliver_github.py::test_pr_body_includes_decisions_md`
- [ ] `apps/orchestrator/tests/test_deliver_github.py::test_pr_labels_include_run_and_stage`
- [ ] `apps/orchestrator/tests/test_deliver_github.py::test_assigns_reviewers_from_architect_bundle`
- [ ] `apps/orchestrator/tests/test_deliver_github.py::test_writes_runtime_ledger_entry_with_pr_url`
- [ ] `apps/orchestrator/tests/test_deliver_github.py::test_idempotent_pr_per_run_id`
- [ ] `apps/orchestrator/tests/test_deliver_github.py::test_handles_rate_limit_with_retry_after`
- [ ] `apps/orchestrator/tests/test_deliver_github.py::test_falls_back_to_ado_when_provider_misconfigured`
- [ ] `apps/orchestrator/tests/test_dispatch.py::test_dispatches_to_github_when_provider_github`
- [ ] `apps/orchestrator/tests/test_dispatch.py::test_dispatches_to_ado_when_provider_ado`

## Verification (definition of done)

- [ ] All unit tests passing
- [ ] GH App registered on `idanshimon` user account, installed on `idanshimon/agentic-sdlc-target`
- [ ] One real PR exists on `idanshimon/agentic-sdlc-target` from a deployed orchestrator run
- [ ] `decisions.md` is visible in the PR body, formatted correctly
- [ ] Ledger entry for the delivered run has `pr_url` populated and `gh_audit_xref` set
