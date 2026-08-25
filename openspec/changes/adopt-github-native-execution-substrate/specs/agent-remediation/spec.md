# Spec delta: adopt-github-native-execution-substrate / agent-remediation

> **Capability:** `agent-remediation` (NEW)
>
> The deployment spec establishes that a run **ends** at a governed gate and a new run resumes on
> approval. It does not say what the agent *produces* at that moment, nor how agent-authored work
> is kept attributable.
>
> **Revision note (adversarial review).** An earlier draft of this capability treated the stacked
> pull request as the authorship control. That was wrong, and the correction is load-bearing:
>
> > **Branch topology is not authorship.** A pull request's opener does not establish who authored
> > its contents. Stacking is a review-segregation practice; the authorship control is a
> > cryptographic attestation bound to the patch, and the enforcement control is a merge
> > chokepoint on a protected ref. Where this spec previously implied stacking proves provenance,
> > it now requires attestation to prove it and retains stacking for reviewability only.
>
> This spec is written against the failure modes, not the happy path.

## ADDED Requirements

### Requirement: A governed ref MUST reject any update not authorized for the exact resulting SHA

A governed ref MUST reject every update unless the control plane has issued an authorization
naming the exact resulting commit SHA, the gate instance, the classification, and the policy
bundle digest.

A verdict returned by an API is advisory unless it is bound to the merge itself. An HTTP refusal
that a merge path can route around is not an enforcement surface. Every merge path — direct push,
API merge, administrator, GitHub App, bot, and merge queue — MUST be subject to the same
authorization, and administrator bypass MUST be disabled and tested rather than assumed.

Required status checks MUST be bound to the expected publishing app identity and to the exact head
SHA, so that a check of the same name published by another identity does not satisfy the gate.

#### Scenario: an unauthorized merge is rejected at the ref

- **GIVEN** a remediation whose resulting merge SHA has no control-plane authorization
- **WHEN** a merge to the governed ref is attempted by any path, including an administrator
- **THEN** the ref update MUST be rejected
- **AND** the rejection MUST be recorded as a `runtime` ledger entry

#### Scenario: authorization does not transfer to a different SHA

- **GIVEN** an authorization issued for merge SHA `A`
- **WHEN** the resulting merge SHA is `B` because the base branch moved
- **THEN** the ref update MUST be rejected
- **AND** the prior authorization MUST NOT be reusable

#### Scenario: a spoofed check does not satisfy the gate

- **GIVEN** a required check bound to a specific publishing app identity
- **WHEN** a check with the same name is published by a different identity
- **THEN** the gate MUST remain unsatisfied

### Requirement: Authorship MUST be derived from attestation, never from pull-request metadata

The actor recorded for a remediation MUST be derived from a verifiable attestation bound to the
patch. Pull-request opener, commit author and committer fields, commit trailers, branch names, and
labels MUST NOT be treated as authorship evidence.

Every agent-produced patch MUST carry an attestation identifying the initiating principal, the
agent identity, the workflow run, the source revision, the toolchain, and a digest of the patch
itself. A branch carrying commits whose provenance is unverifiable, or mixed across principals
without attestation, MUST fail closed.

Without this, the review-independence rule below is defeated by relabeling: an agent's patch
transplanted into a human-opened pull request is indistinguishable from human work, and the agent
has closed its own loop while appearing not to.

#### Scenario: a transplanted agent patch is still recognized as agent-authored

- **GIVEN** a patch produced by an agent and attested
- **WHEN** it is cherry-picked into a pull request opened by a human principal
- **THEN** the decision record MUST attribute the patch to the agent identity from its attestation
- **AND** the human-review requirement for agent-authored work MUST still apply

#### Scenario: unverifiable provenance fails closed

- **GIVEN** a remediation branch containing a commit with no valid attestation
- **WHEN** merge authorization is evaluated
- **THEN** authorization MUST be refused
- **AND** the outcome MUST record `gate_reason: verification_failed`

### Requirement: The evaluation trust boundary MUST resolve from an immutable trusted revision

Everything that determines a gate's outcome MUST resolve from a revision the evaluated change
cannot modify. This includes the policy definition, the gate workflow definition, referenced
actions, the verifier and evidence-collection code, and the component that publishes check
results. Referenced actions MUST be pinned by digest.

Protecting the policy alone is insufficient. A trusted policy evaluated by instrumentation the
change controls is not a trusted gate: an agent that cannot weaken the rule can still weaken the
test that proves the rule, or the collector that reports the result.

Where a change modifies any part of this boundary, that modification MUST itself be gated as a
standards change and MUST NOT influence its own evaluation.

#### Scenario: a change cannot weaken the test that judges it

- **GIVEN** a remediation whose diff modifies the verifier or the gate workflow definition
- **WHEN** the governed gate evaluates that remediation
- **THEN** the evaluation MUST use the trusted revision's verifier and workflow
- **AND** the modification MUST be routed as a standards change

#### Scenario: trust-boundary resolution failure is fail-closed

- **GIVEN** a governed gate whose policy or verifier cannot be resolved from the trusted revision
- **WHEN** the gate evaluates
- **THEN** the gate MUST fail closed and MUST NOT report success
- **AND** the outcome MUST record `gate_reason: verification_failed`

### Requirement: A gate instance MUST admit at most one active remediation, bound by compare-and-swap

Each gate instance MUST permit at most one active remediation at a time, and both creation and
merge authorization MUST be conditioned on an immutable state tuple captured at decision time.

The tuple MUST include the repository identity, the root gate instance, the parent pull request
and its head SHA, the target base SHA, and the policy bundle digest. Merge authorization MUST be a
compare-and-swap against that tuple.

Any change to the tuple — a force-push to the parent, a moved base branch, a rebase after
approval, or a rotated policy bundle — MUST invalidate both the authorization and the recorded
approvals. Concurrent workers observing the same failure MUST NOT be able to open sibling
remediations, which would break the linear stack the reviewability argument depends on.

#### Scenario: concurrent remediation workers cannot create siblings

- **GIVEN** two workers observing the same failed gate instance
- **WHEN** both attempt to create a remediation
- **THEN** exactly one MUST succeed
- **AND** the other MUST be refused against the existing active remediation

#### Scenario: a force-push after approval invalidates the decision

- **GIVEN** an approved remediation authorized against parent head SHA `A`
- **WHEN** the parent branch is force-pushed to SHA `B`
- **THEN** the authorization and its approvals MUST be invalidated
- **AND** merge MUST be refused until re-evaluated against `B`

#### Scenario: policy rotation during review invalidates authorization

- **GIVEN** an authorization bound to policy bundle digest `D1`
- **WHEN** the team's pinned bundle rotates to `D2` before merge
- **THEN** the authorization MUST be invalidated

### Requirement: Human review MUST be independent, and approval MUST bind to the exact merge result

Required review MUST be satisfied only by distinct, eligible human principals who are independent
of the agent's operator and of the remediation requester. An agent principal's approval MUST NOT
count on work attributed to an agent by attestation.

Approval MUST bind to the exact patch and the exact resulting merge SHA. Any material change to
either MUST invalidate it. Approval delegated through a shared account, a bot, or group membership
that resolves back to the requester MUST NOT count.

For a remediation attributed to an `INVARIANT_CLASSES` decision, the approval set MUST additionally
satisfy the quorum declared in `standards-bundles/<dept>/<version>/reviewers.yaml`, evaluated by
the control plane. A GitHub Environment accepts one approval out of up to six configured reviewers
and cannot express an N-of-M named-approver quorum, so the Environment MUST NOT be treated as the
quorum authority.

#### Scenario: an agent approval does not satisfy required review

- **GIVEN** a remediation attributed to an agent by attestation
- **WHEN** an agent principal approves it
- **THEN** the required human review MUST remain unsatisfied

#### Scenario: approval does not survive a material change

- **GIVEN** a remediation approved at patch digest `P1`
- **WHEN** the patch changes to `P2`
- **THEN** the approval MUST be invalidated and merge MUST be refused

#### Scenario: quorum is evaluated by the control plane, not the Environment

- **GIVEN** a remediation for a `phi-classification` decision whose bundle requires two approvers
- **WHEN** one eligible human approval is recorded and the Environment reports approved
- **THEN** merge authorization MUST be refused for insufficient quorum

### Requirement: Remediation MUST be transactionally quarantined until both records reconcile

A remediation pull request MUST be created in a non-mergeable quarantine state and MUST become
eligible only after an idempotent reconciliation confirms that the control-plane record and the
repository state agree.

GitHub and the ledger cannot be updated atomically, and webhook delivery is not a transaction.
Failing delivery closed is insufficient on its own: a created pull request whose ledger write
failed is an actionable orphan, and a ledger entry whose pull request creation failed points at
nothing. All operations MUST carry idempotency keys so that retries do not produce duplicate
remediations or duplicate re-evaluation records.

A reconciler MUST run independently of webhook delivery and MUST detect orphaned, duplicated,
missing, reordered, and post-verification-edited records, blocking the affected ref until resolved.

#### Scenario: a remediation whose ledger write failed is not mergeable

- **GIVEN** a remediation pull request created while its ledger write failed
- **WHEN** merge is attempted
- **THEN** it MUST remain non-mergeable in quarantine
- **AND** the reconciler MUST surface it as an orphan

#### Scenario: retried delivery does not duplicate a remediation

- **GIVEN** a remediation delivery that is retried after an ambiguous failure
- **WHEN** the retry executes with the same idempotency key
- **THEN** exactly one remediation pull request MUST exist

#### Scenario: out-of-order events do not produce an impossible history

- **GIVEN** a merge event delivered before the corresponding creation event
- **WHEN** the reconciler processes them
- **THEN** the recorded history MUST remain causally consistent

### Requirement: Remediation MUST be bounded by a root-scoped budget, not by stack depth

Remediation MUST be bounded by a budget computed across the root gate instance, covering attempts,
elapsed time, cost, and cumulative changed surface.

Depth MUST be descriptive metadata only and MUST NOT be the enforcement mechanism. Depth is
derived, caller-influenced data: five sibling attempts evade a depth limit of one, and reopening
under a new root resets it. Opening a new pull request, moving repositories, or relabeling
authorship MUST NOT reset the budget.

Exhaustion MUST halt and open a gate with `gate_reason: budget_exceeded`, surfacing "the agent
cannot satisfy this gate" as an explicit governance event.

#### Scenario: sibling attempts consume the same root budget

- **GIVEN** a root gate instance with a budget of two remediation attempts
- **AND** two attempts already recorded at depth one
- **WHEN** a third attempt is requested at any depth
- **THEN** it MUST be refused with `gate_reason: budget_exceeded`

#### Scenario: reopening does not reset the budget

- **GIVEN** an exhausted root gate instance
- **WHEN** a remediation is attempted under a newly created pull request for the same root
- **THEN** the budget MUST remain exhausted

### Requirement: Remediation MUST be delivered as a stacked pull request for reviewability

Agent remediation MUST be delivered as a pull request based on the triggering pull request's head
branch, and MUST NOT be pushed directly to that branch.

This requirement exists for **review segregation**: human intent stays one reviewable diff and
agent remediation is another, which is materially easier to review and to reason about. It MUST
NOT be represented as proof of authorship — authorship is established by attestation, and merge is
controlled at the ref. A squash merge collapses commit identity, and the durable history may
attribute the result to the merging human; the attestation and the ledger, not the branch
topology, carry the authorship claim.

#### Scenario: remediation is based on the triggering head branch

- **GIVEN** a failed governed gate on a pull request
- **WHEN** remediation is delivered
- **THEN** it MUST be a pull request based on that pull request's head branch
- **AND** no direct push to that branch MUST occur

#### Scenario: authorship survives a squash merge

- **GIVEN** a remediation merged by squash, collapsing commit identity
- **WHEN** the decision record is read
- **THEN** the agent attribution MUST still be derivable from the patch attestation

### Requirement: The remediation pull request MUST carry one durable reference, not duplicated evidence

The remediation pull request body MUST carry a machine-managed immutable reference to its ledger
entry and a concise human-readable reason. The complete evidence chain MUST live in the ledger and
in signed check output.

Duplicating the evidence chain as prose in a mutable pull-request body turns editable text into a
compliance record: it goes stale, invites automated rewriting, and produces false incidents when a
human edits it. Linkage MUST be established through stable identifiers and repository metadata
rather than through prose fields, and MUST be verifiable in both directions.

#### Scenario: the body reference resolves to the decision record

- **GIVEN** a remediation pull request
- **WHEN** its body reference is resolved
- **THEN** it MUST identify exactly one `LedgerEntry`
- **AND** that entry MUST identify this pull request

#### Scenario: an edited body does not invalidate the audit chain

- **GIVEN** a human edits the human-readable portion of a remediation body
- **WHEN** the audit chain is verified
- **THEN** verification MUST rely on the durable identifiers, not the prose
- **AND** the change MUST NOT be reported as a compliance incident

### Requirement: Gate re-evaluation MUST follow the merged head SHA through the normal gate path

When a remediation merges into the triggering pull request's head branch, the governed gate MUST
re-evaluate the new exact head SHA through the ordinary trusted gate workflow, causally linked to
the merge event by an idempotency key.

The audit-significant property is that the new head SHA is evaluated — not that a distinct rerun
mechanism exists. A parallel rerun subsystem MUST NOT be built, because it would be a second
evaluation path with its own trust boundary to defend.

A gate that clears only when a human remembers to act is a convention, not an enforcement surface.

#### Scenario: the merged head SHA is evaluated

- **GIVEN** a remediation that merges into the triggering head branch
- **WHEN** the branch head becomes SHA `C`
- **THEN** the governed gate MUST evaluate SHA `C` with no manual action
- **AND** the evaluation MUST be recorded as a `runtime` ledger entry

#### Scenario: duplicate merge events produce one evaluation

- **GIVEN** a merge webhook delivered twice
- **WHEN** re-evaluation is triggered
- **THEN** exactly one evaluation record MUST exist for that head SHA

## MODIFIED Requirements

### Requirement: The ledger MUST record remediation as immutable events, not a denormalized summary

The ledger MUST record the remediation lifecycle as immutable events with stable parent and root
identifiers, sufficient to reconstruct what happened without reading the repository.

Each event MUST carry the repository identity, the root and parent gate instance identifiers, the
relevant SHAs (parent head, target base, evaluated, and resulting merge), the merge method, the
policy bundle digest, the reviewer-eligibility snapshot, the patch digest, and an idempotency key.
Lifecycle events MUST include created, attested, approved, head-changed, merge-authorized, merged,
re-evaluated, superseded, and abandoned.

A triple of triggering pull request, remediation pull request, and depth cannot support a
reconstruction claim: pull-request numbers are not globally unique, depth is derived and
forgeable, force-push and rebase history is absent, and abandoned or superseded attempts are
invisible. `gh_audit_xref` MAY be generated from these events as a denormalized convenience, but
MUST NOT be the system of record.

#### Scenario: the stack reconstructs from events alone

- **GIVEN** a remediation stack including one abandoned attempt and one force-push
- **WHEN** the ledger events are read without reading the repository
- **THEN** the parent and root lineage MUST be reconstructable
- **AND** the abandoned attempt and the force-push MUST both be present

#### Scenario: depth is descriptive, not authoritative

- **GIVEN** a ledger event whose recorded depth conflicts with its parent lineage
- **WHEN** the stack is reconstructed
- **THEN** the parent edges MUST be authoritative
- **AND** the conflict MUST be surfaced as an integrity finding
