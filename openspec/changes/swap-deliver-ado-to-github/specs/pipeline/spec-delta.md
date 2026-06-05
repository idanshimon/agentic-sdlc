# Spec delta — capability: pipeline (deliver-stage subset)

## Modified

### Deliver stage

The deliver stage now dispatches on `config.deliver_provider` to one of:
- `deliver_github` (default, NEW)
- `deliver_ado` (opt-in, ported verbatim from v0.6)

Both implementations share the same input/output contract:
- Input: completed run state + ledger entries + codegen output
- Output: a PR (or ADO PR) URL + a runtime ledger entry of kind `delivered`

### Branch naming

Branch name is `agentic-sdlc/run-<run_id>` (was `feature/<run_id>` in v0.6).
This makes filtered queries (`branch:agentic-sdlc/*`) trivial.

### PR body

Includes the rendered `decisions.md` content directly (was attached file in
v0.6 ADO path). Renderer unchanged from v0.6 (`decisions_md.py` ported verbatim).

### Reviewer assignment

Reviewers are now assigned from `standards-bundles/architect/v<n>/reviewers.yaml`
matching the run's bundle subscriptions. If multiple bundles apply, union of
required roles is used.

## Added

### GitHub App auth

A GitHub App is the auth boundary. PAT-based deploy is explicitly unsupported.
App credentials stored as Container App secrets, retrieved via Managed Identity
+ Key Vault. App installation is per-customer-org.

### gh_audit_xref ledger field

The runtime ledger entry of kind `delivered` carries a `gh_audit_xref` field
set to the GH audit session ID for the PR creation, allowing compliance to
join our ledger to GH's `actor:Copilot` audit log.

## Constraints

- `deliver_github` requires `github_app.installation_id` to be set per team
  in config; orchestrator refuses startup otherwise.
- `deliver_ado` remains supported but is opt-in.
- Mixed deployments (some teams GH, some ADO) are supported via per-team
  config overrides.
