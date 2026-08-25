# Tasks: add-security-bundle-v0.2.0

**Enforcement targets:** `scripts/enforce_bundles.py` (deterministic rules),
`scripts/enforce_supply_chain.py` + `.github/workflows/supply-chain-scan.yml`
(SUPPLY-001).

## Phase 1 — Author the bundle

- [x] 1.1 Extend `security/v0.1.0` beyond data handling: identity/access scope, supply-chain consequence, retention.
- [x] 1.2 Give every rule a rationale, an enforcement surface, and test cases.
- [x] 1.3 Mark rules with no regex form `requires_mechanism: true` and record `mechanism_status` honestly, so an inert rule is visibly inert rather than posing as a control.

## Phase 2 — Make SUPPLY-001 actually enforce

- [x] 2.1 `scripts/enforce_supply_chain.py` — read the SARIF, count findings by severity, block at or above the cutoff, and print the citation with counts.
- [x] 2.2 Wire `.github/workflows/supply-chain-scan.yml` and set `mechanism_status: implemented` only once the workflow existed. Verified: the referenced workflow file is present on disk.
- [x] 2.3 Fix the evidence half. Grype emitted empty `artifactLocation.uri` on every result, which Code Scanning rejected — so the gate blocked on findings a reviewer could not see. `scripts/normalize_grype_sarif.py` normalizes the URIs; the workflow uploads the normalized document.
- [x] 2.4 Prove enforcement end to end rather than assuming it. Observed in CI: 102 findings / 33 high → `BLOCKED`; after remediation → `1 finding: 1 medium` → `PASS — no findings at or above 'high'`.

## Phase 3 — Backfill the spec (2026-08-18)

- [x] 3.1 **Gap found during an OpenSpec audit:** this change had a proposal and no `specs/` directory at all — zero machine-checkable deltas — while SUPPLY-001 was already gating every merge in production. The rule shipped; the spec did not.
- [x] 3.2 Write `specs/standards-bundles/spec.md`: mechanism declaration, the blocking threshold, SARIF evidence publication, and the unenforceable-BLOCK-rule case.
- [x] 3.3 Verify each asserted behaviour against real code rather than assuming it. One claim was **wrong on first writing**: the spec said an unenforceable BLOCK rule fails the load. A probe bundle (one BLOCK rule, no pattern, no enforcement) **loaded without error** and yielded `[]` selected rules — `_is_ci_eligible` silently excludes it. The requirement was rewritten to specify exclusion, not load failure, with the reasoning recorded inline.
- [x] 3.4 `openspec validate --strict` passes.

## Phase 4 — Review

- [ ] 4.1 Reviewer approval per the `security` bundle roster.
- [ ] 4.2 Consider a follow-up change making "no pattern AND no declared mechanism" a hard load error. It cannot be a naive "BLOCK implies pattern" check, which would reject the legitimately mechanism-enforced rules.
