# Spec delta: add-autonomous-review-loop / autonomous-review-loop

## ADDED Requirements

### Requirement: A review FAIL verdict MUST be routed to bounded codegen remediation

The system MUST dispatch a remediation task to the codegen agent when
`review-scan` returns `status: FAIL` on a pull request in an opted-in
repository (Tier A or B), carrying the structured blockers (check, bundle rule,
detail, file:line) as the remediation contract, and MUST record a
`review_remediation` runtime ledger entry for the attempt. The remediation MUST
resolve only the cited blockers and MUST cite the same bundle rule it satisfies.

#### Scenario: a FAIL verdict on a Tier-B repo dispatches remediation

- **GIVEN** a pull request on a repo configured Tier B with a `review-scan` verdict `status: FAIL` citing `security/v0.1.0/SECRET-001`
- **WHEN** the review loop processes the verdict
- **THEN** a remediation task MUST be dispatched to codegen with that blocker as its contract
- **AND** a `review_remediation` ledger entry MUST be written with `attempt: 1`, the blocker in `blockers_in`, and `actor.kind: agent`
- **AND** the remediation commit MUST land on the same PR branch

#### Scenario: a FAIL verdict on an unlisted repo does not remediate

- **GIVEN** a pull request on a repo absent from `repo_autonomy.yaml` (Tier C by default)
- **WHEN** the review loop processes a `FAIL` verdict
- **THEN** the system MUST NOT dispatch remediation
- **AND** the system MUST post the verdict as an advisory PR comment
- **AND** no `review_remediation` entry MUST be written

### Requirement: The loop MUST be bounded by a hard attempt ceiling and escalate on exhaustion

The review→remediate→re-review loop MUST stop after at most
`REVIEW_LOOP_MAX_ATTEMPTS` remediation attempts (default 3). On exhaustion with
a still-failing verdict, the system MUST write a `loop_escalated` entry with
reason `max_attempts` and MUST NOT merge. The env MAY lower the ceiling but a
configuration permitting unbounded attempts MUST be rejected.

#### Scenario: loop exhausts attempts and escalates without merging

- **GIVEN** a Tier-A pull request whose review-scan still returns `FAIL` after 3 remediation attempts
- **WHEN** the loop reaches attempt 3's failing re-review
- **THEN** the system MUST write a `loop_escalated` entry with `escalation_reason: max_attempts` and the unresolved blockers
- **AND** the pull request MUST NOT be merged
- **AND** the escalation MUST surface in the operator escalation inbox

#### Scenario: loop converges and records a terminal PASS

- **GIVEN** a Tier-A pull request whose review-scan returns `FAIL` then `PASS` after one remediation
- **WHEN** the re-review returns `PASS`
- **THEN** the system MUST write a `loop_converged` entry with `attempts: 1` and `merged: true`
- **AND** the merge MUST NOT occur without that terminal ledger entry

### Requirement: Auto-merge without a human MUST be permitted only for Tier-A repositories

The system MUST merge a converged pull request automatically without human
action only when the pull request's repository is configured Tier A. A Tier-B
repository MUST run the loop to `PASS` and then await an explicit human merge.
A Tier-C (or unlisted) repository MUST NOT be merged by the loop under any
verdict.

#### Scenario: Tier-A converged PR auto-merges

- **GIVEN** a converged `PASS` pull request on a Tier-A repo with no PHI or deny blockers in its history
- **WHEN** the loop reaches the terminal PASS
- **THEN** the system MUST merge the pull request without human action
- **AND** the `loop_converged` entry MUST record `merged: true` and `repo_tier: A`

#### Scenario: Tier-B converged PR awaits human merge

- **GIVEN** a converged `PASS` pull request on a Tier-B repo
- **WHEN** the loop reaches the terminal PASS
- **THEN** the system MUST NOT merge automatically
- **AND** the pull request MUST be presented for an explicit human merge via `POST /api/review-loops/{id}/merge`
- **AND** the `loop_converged` entry MUST record `merged: false` until the human merges

### Requirement: PHI, auth, and explicit-deny blockers MUST force human escalation regardless of tier

The system MUST escalate to a human, and MUST NOT auto-remediate or auto-merge,
whenever a pull request carries a blocker citing a rule with `phi: true`, an
auth-policy rule, or an explicit-deny pattern — independent of the repository's
tier, env configuration, or attempt count. This floor MUST be enforced both
when loading `repo_autonomy.yaml` (an unsafe Tier-A assignment is refused) and
at loop runtime (a PHI/deny blocker forces escalation even if the tier says
otherwise).

#### Scenario: a PHI blocker on a Tier-A repo forces escalation

- **GIVEN** a Tier-A pull request whose review-scan returns `FAIL` citing `security/v0.1.0/PHI-001`
- **WHEN** the loop processes the verdict
- **THEN** the system MUST NOT dispatch autonomous remediation for that blocker
- **AND** the system MUST write a `loop_escalated` entry with `escalation_reason: tier_floor_phi`
- **AND** the pull request MUST NOT be merged

#### Scenario: config granting Tier A to a PHI-touching repo is refused at load

- **GIVEN** a `repo_autonomy.yaml` assigning Tier A to a repo with a `phi: true` blocker in its last-30-day history
- **WHEN** the repo-autonomy config is loaded
- **THEN** the loader MUST raise `RepoTierUnlockError`
- **AND** the repo MUST fall back to an escalation-forcing posture rather than a half-applied Tier A

### Requirement: A repository absent from configuration MUST default to advisory (Tier C)

The system MUST treat any repository not explicitly listed in
`repo_autonomy.yaml` as Tier C (advisory): the loop MAY run and post its verdict
as a PR comment but MUST NOT remediate, merge, or otherwise change repository
state. Deploying the image MUST NOT change any repository's behavior until a
human explicitly graduates it in configuration.

#### Scenario: deploying the image leaves every repo advisory

- **GIVEN** a fresh deploy with no `repo_autonomy.yaml` present
- **WHEN** a pull request is opened on any repository
- **THEN** every repository MUST be treated as Tier C
- **AND** the loop MUST NOT remediate or merge any pull request
- **AND** `GET /api/config/repo-autonomy` MUST report the bootstrap (all-advisory) posture

### Requirement: Every loop hop MUST be an auditable ledger entry with a structured citation

The system MUST record each remediation attempt, convergence, and escalation as
a runtime ledger entry (`review_remediation`, `loop_converged`,
`loop_escalated`) carrying a structured, grep-able autonomy citation of the form
`reviewloop/<tier>/<repo>/<action>[@attempt=N]:<reason>`. These entries MUST be
queryable by the existing compliance query surface without a loop-specific code
branch.

#### Scenario: a converged loop is reconstructable from the ledger alone

- **GIVEN** a pull request that failed, remediated once, then passed and merged on a Tier-A repo
- **WHEN** an auditor queries the ledger for that PR reference
- **THEN** the entries MUST include one `review_remediation` (attempt 1) and one `loop_converged` (merged true)
- **AND** each entry MUST carry a `reviewloop/A/<repo>/...` structured citation
- **AND** the compliance query MUST return them without a loop-specific branch

### Requirement: The autonomous loop MUST be observable in the operator UI

The system MUST present in-flight and recent review loops in the operator
dashboard, showing for each loop the real pull-request link, the repository tier,
the attempt timeline, the terminal state, and a link from every hop to its
ledger entry. Escalations MUST surface as a first-class list with the
unresolved blockers and the pull request.

#### Scenario: an operator watches a loop without being in the merge path

- **GIVEN** an in-flight review loop on a Tier-A repo
- **WHEN** the operator opens the `/review-loop` page
- **THEN** the page MUST show the PR link, tier badge, and the review→remediate→review timeline
- **AND** each hop MUST link to its ledger entry and the real GitHub PR or commit
- **AND** the operator MUST NOT be required to act for the loop to proceed
