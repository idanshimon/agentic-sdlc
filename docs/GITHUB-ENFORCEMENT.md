# GitHub enforcement setup

Workflow files are not enforcement by themselves. Adoption is complete only when GitHub reports the required controls as active.

## Required repository controls

For the default branch:

- Activate a ruleset or branch protection.
- Require pull requests.
- Require `bundle-enforce`.
- Require build, unit-test, and security checks used by the adopting repository.
- Require CODEOWNERS review for governance-sensitive paths.
- Block force pushes and branch deletion.
- Enable merge queue when the repository's concurrency warrants it.

Actions:

- Restrict allowed Actions to GitHub-owned and explicitly approved publishers/repositories.
- Require immutable SHA pinning.
- Protect environments used for production delivery or merge.
- Give the review-loop workload only PR metadata/files, checks, comments, and bounded merge permissions.

Security:

- Enable secret scanning and push protection.
- Enable Dependabot security updates.
- Enable code scanning for the repository's languages.

## Verification

Run:

```bash
python scripts/verify_github_governance.py owner/repo
```

Exit codes:

- `0`: deterministic bundle check is required.
- `2`: workflow may exist, but enforcement is still advisory.

The report also shows ruleset count, branch protection, Actions policy, and security features. Unknown/403 results remain unknown and must not be reported as compliant.

## Current reference-repository posture (verified 2026-07-11)

The live read-only verifier reported:

- zero active rulesets
- no branch protection on `main`
- no required checks
- `bundle-enforce` advisory only
- Actions enabled for all actions
- immutable SHA policy not required
- secret scanning and push protection enabled
- Dependabot security updates disabled

These are live admin gaps. The repository now contains CODEOWNERS, pinned workflow actions, setup steps, and the verifier, but applying GitHub settings requires explicit repository-admin authorization and was not performed automatically.
