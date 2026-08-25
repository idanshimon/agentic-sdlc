# Adopt GitHub as the execution substrate and close the decision-record gaps

> **Status:** DRAFT (filed 2026-08-12)
> **Capabilities:** deployment (MODIFIED), pipeline (MODIFIED), ledger (MODIFIED),
> agent-hq-integration (MODIFIED), **agent-remediation (ADDED)**
> **Extends:** `redesign-decision-lifecycle-control-plane` (its delegate/retain boundary is the
> premise of this change, not a duplicate of it)
> **Severity:** Foundational — changes what this system *is*: a control plane above GitHub,
> not a parallel runtime beside it.

## Why

Two findings drive this change. Both are evidence, not opinion.

### Finding 1 — we already run on GitHub, partially, without having decided to

Three enforcement surfaces already execute on GitHub Actions today:

| Workflow | What it enforces | Runs with a secret? |
|---|---|---|
| `.github/workflows/bundle-enforce.yml` | deterministic review-scan subset on every PR | no — the un-bypassable floor |
| `.github/workflows/supply-chain-scan.yml` | `security/v0.2.0/SUPPLY-001`, syft/grype → SARIF | no |
| `.github/workflows/autonomous-review-loop.yml` | notifies the review-loop controller on PR events | yes (dispatch token) |

Alongside them: seven custom agents under `.github/agents/`, five hook scripts under
`.github/hooks/scripts/`, `CODEOWNERS`, and a `copilot-setup-steps.yml`. The repository is
already a GitHub-native governance artifact.

Critically, `bundle-enforce.yml` is not a token check: it invokes `scripts/enforce_bundles.py`,
which loads `standards-bundles/PINS.yaml`, resolves the team's pinned bundle versions
(`enforce_bundles.py:138-160`), loads the CI-eligible rules from each resolved
`<dept>/<version>/rules.yaml` (`:220-234`), and **fails closed** on a load error. Policy-as-code
already executes on GitHub Actions today, with no repository secret.

Meanwhile the orchestrator runs a second, parallel runtime on Azure Container Apps that
re-implements what GitHub already provides: job scheduling, containerised execution,
identity, artifact retention, and approval routing. We maintain both. Only one of them is
the customer's system of record.

`redesign-decision-lifecycle-control-plane` already ratified the boundary in prose:

> Delegate to GitHub: agent session research/planning/implementation; ephemeral or self-hosted
> runner environments; branches, commits, pull requests, reviews, checks, Actions, rulesets,
> CODEOWNERS, and merge queue.
> Retain in this control plane: cross-repository policy and autonomy posture; typed enterprise
> gates and hard-gate classes; decision-level audit and policy evidence; bounded
> review/remediation loops and escalation floors; cross-surface lineage.

That boundary was declared. It was never made structural. This change makes it structural:
**execution moves to GitHub; the control plane shrinks to exactly the governance surface
GitHub cannot express.**

### Finding 2 — an adversarial audit of our own code found four load-bearing gaps

`docs/overcut-adversarial-capability-comparison.md` audited every claimed governance advantage
against the implementation. The honest result:

**Real, and better than the competing platform:**

- Hard gate is enforced server-side. `apps/orchestrator/main.py:1861-1876` returns HTTP 409 when
  `approval_path == "bulk"` on a card whose `ambiguity_class` is in `HARD_GATE_CLASSES`. The
  floor is `INVARIANT_CLASSES = {"phi-classification", "auth-policy"}`
  (`packages/ledger-core/ledger_core/models.py:67`); env may extend it, never shrink it.
  A `curl` cannot rubber-stamp a PHI decision. This is classification-driven gating —
  structurally different from a confidence threshold, which a sufficiently confident agent clears.
- `autonomy_ref` records **why** each decision was autopiloted or gated, on every path:
  autopilot (`main.py:420-443`), human gate (`main.py:1907`), model-policy refusal (`main.py:769`).
- `gh_audit_xref` is populated at delivery (`apps/orchestrator/stages/deliver_github.py:144`).
- Precedent-gated autopilot is wired end to end — `find_precedent` (`main.py:413,433`) actually
  decides autopilot-vs-gate.

**Claimed but not shipped — these are the gaps this change closes:**

| # | Gap | Evidence |
|---|---|---|
| A | **No cross-run learning.** `accuracy_score` is `0.0` on all 229 live ledger entries. No compute site exists. `add-teaching-signal-feedback` is 42/56 tasks and 0% computing. | audit target 4 |
| B | **No rejected-alternatives capture.** The ledger persists `option_index` + `resolution_text` — the chosen option only. An auditor asking "why not the other option" cannot be answered from the record. | audit target 6 |
| C | **No per-run shared scratch store.** Zero `scratchpad` hits in the orchestrator. Every inter-stage handoff rides the stage payload — the documented truncation footgun. | audit target 3 |
| D | **`bundle_refs` is coarse and partly hardcoded.** Stamped from the stage's static subscription list (`main.py:475`), and `deliver_github.py:161` carries a literal `["architect/v0.1.0/SERVICE-CONTAINERIZED-001"]`. "The rule that decided this" is not recorded — only "the bundles this stage subscribes to". | audit target 2 |

Gap A is the most serious. A governed system whose learning loop is a schema with no
behaviour is claiming an assurance it does not provide.

### Why the two findings are one change

The gaps are precisely the things GitHub **cannot** do for us. If we move execution to GitHub
without closing them, we delegate the easy half and keep an incomplete control plane. The
retained surface must be complete before it is the only thing we own.

## What changes

### 1. GitHub becomes the execution substrate (`deployment`, `agent-hq-integration`)

Pipeline stage execution moves from the ACA orchestrator to GitHub Actions workflow runs,
authored as agentic workflow definitions committed to the repository. Concretely:

- Each pipeline stage becomes a job in a governed workflow. The workflow definition is a
  repository file, versioned in Git, reviewed under `CODEOWNERS` — not user-private automation.
- Agent execution uses the GitHub-hosted agent runtime with the repo's existing
  `.github/agents/*.agent.md` personas and `.github/hooks/` lifecycle hooks.
- Identity moves to OIDC federation to Azure. No stored service-principal secret for
  data-plane auth.
- Human approval routes through **Environments with required reviewers**, gated by a
  **custom deployment protection rule** that calls the control plane. This is the one GitHub
  primitive that can defer an approval decision to an external policy service.
- The control plane retains: hard-gate classification, autonomy posture, the Decision Ledger,
  precedent, standards bundles, and cross-repository reporting.

**What GitHub structurally cannot do, and therefore stays ours** — the load-bearing sentence
of this proposal:

> GitHub Environments gate on **who approves**. They cannot gate on **what class of thing is
> being decided**. There is no native primitive that says "if this proposed action is
> classified PHI-touching, require a named approver, and no confidence level bypasses it."
> Classification-driven, non-bypassable gating is our retained surface, and the custom
> deployment protection rule is the hook by which GitHub asks us for that verdict.

### 1a. Hybrid, not full rebase — three findings that bound the migration

Independent research into the GitHub substrate produced three constraints that change the shape
of this proposal from "move everything" to "move the execution lane, keep the governance lane."

**Constraint 1 — the native gate is weaker than it appears.** GitHub enables **administrator
bypass of environment protection rules by default**; it must be explicitly disabled. An
environment accepts **one approval out of up to six** configured reviewers, and cannot express an
N-of-M named-approver quorum. Custom deployment protection rules — the only conditional hook —
are **public preview**, require a GitHub App you build and host, are capped at six per
environment, and require Enterprise for private repositories. The gate is usable, but only when
hardened; hence the new hardening requirements in the deployment spec.

**Constraint 2 — approval waits exceed the substrate's limits.** A GitHub-hosted job is capped at
6 hours; an environment approval may wait 30 days; a total run 35 days. A standards committee
that takes six weeks to decide a `phi-classification` card exceeds all of them. This is decisive
and it is why the gate cannot be modelled as a paused job: **the run ends at the gate and a new
run resumes on approval, with the Decision Ledger as the continuity.**

**Constraint 3 — the market chose the same split.** Autonomous coding platforms (Devin,
Factory.ai, and peers) run their own sandboxes rather than CI, while Actions-acceleration vendors
(Blacksmith, Depot) prove Actions is an excellent substrate for the *deterministic* lane. The
convergent evidence supports a hybrid: deterministic and agent execution on GitHub; durable
governance, decision state, and long-horizon approvals off it.

**Regulatory backstop.** HIPAA §164.312(b) requires mechanisms that record *and examine* ePHI
activity; §164.316(b)(2)(i) requires six-year documentation retention; §164.312(c) requires
protection from improper alteration. EU AI Act Article 12 requires automatic lifecycle logging for
traceability, Article 14 requires effective human oversight with the ability to intervene or stop,
and Article 26 requires deployers to retain AI logs for at least six months. IEC 62304 Chapter 8
and SOC 2 CC8.1 require documented change control with traceable approval records.

Every one of these is a **control-plane obligation, independent of execution substrate**. Actions
log retention is measured in days and does not satisfy six-year retention. The Decision Ledger is
therefore not a component we could delegate to GitHub under any configuration — it is the
compliance artifact, and this is the strongest possible argument for keeping it.

**Known blockers to record now, not discover later:**

- The Copilot coding agent is **not available on data-residency deployments**. A customer
  requiring in-region processing cannot use that lane; the substrate decision must be made per
  customer, and the migration must not assume it.
- The agentic workflow toolchain is in **public preview**. (This supersedes an earlier
  research-stage characterization; see design §6.5.) The mitigation is unchanged: governance
  controls must not depend on unpinned preview features — hence the pinning-and-fallback
  requirement. Preview status is a reason to pin, not a reason to defer.
- Built-in threat detection is a **non-deterministic AI classifier**, not a rules engine. It is
  defense in depth, never the policy gate.

### 2. The ledger records the alternatives weighed, not only the choice (`ledger`) — gap B

`LedgerEntry` gains `rejected_options[]` and `decision_confidence`. At resolve time the
orchestrator persists every `ResolutionOption` the assessor produced, marking the selected one
and retaining the rest with their rationale. `AmbiguityCard.options` already carries them
(`apps/orchestrator/models.py:85`); today they are discarded at persist time.

### 3. Gate pauses carry a typed reason (`ledger`, `pipeline`)

`LedgerEntry` gains `gate_reason`, a closed enum:
`invariant_class | autonomy_tier | low_precedent | budget_exceeded | verification_failed | stalled | operator_requested`.

Today a gate opens and the reason is implicit in `autonomy_ref` free text. A typed reason makes
the operator feed answerable ("paused: invariant_class" and "paused: budget_exceeded" are
different human actions) and makes gate-cause reportable across repositories.

### 4. A run-scoped artifact store replaces payload-passing (`pipeline`) — gap C

A run-scoped, append-safe store for inter-stage data, backed by GitHub Actions artifacts under
the substrate. Stages write named entries and read them by name instead of threading everything
through the stage payload. This retires the payload-truncation failure class.

Explicitly **not** cross-run: this tier is ephemeral and dies with the run. Cross-run knowledge
is §5.

### 5. The teaching loop computes (`ledger`, `pipeline-doctor`) — gap A

`accuracy_score` gets a compute site. A bounded retrospective, scheduled on GitHub Actions,
samples completed runs and writes weighted `meta` ledger entries representing durable lessons.

Design constraints, chosen deliberately to be more conservative than a naive memory system:

- **Two-stage promotion.** A pattern observed once is *tentative* and is never injected into a
  prompt. It is promoted only when the same pattern recurs on a **separate run at the same
  stage**.
- **Asymmetric weighting.** A lesson that misleads loses more weight than a helpful one gains.
  A bad memory costs more than a missing one.
- **Decay for unread lessons**, and archival below a floor, with a tombstone recording why.
- **Random sampling, not most-recent**, to avoid recency bias.
- **Org-scoped, not workflow-scoped.** Lessons are keyed by `(ambiguity_class, slot_value_hash)`
  — the same key `find_precedent` already uses — so they cross runs, stages, and teams under
  the existing team partition. This is deliberately broader than a per-workflow memory.

Every promoted lesson is a ledger entry: append-only, attributable, and subject to the same
PHI rules as any other write.

### 6. `bundle_refs` becomes per-rule and honest (`standards-bundles`, `ledger`) — gap D

- The hardcoded `bundle_refs` at `deliver_github.py:161` is deleted.
- All seven stages stamp `bundle_refs`, not just the assessor.
- Where a specific rule was evaluated to reach a decision, that rule ID is recorded. Where only
  the subscription set is known, the entry says so rather than implying rule-level precision.

## KEEP / SWAP / ADD / OUT

### KEEP

- Four-plane architecture; the planes do not change, their hosting does.
- Append-only runtime/meta ledger and its typed schema.
- `INVARIANT_CLASSES` hard-lock and server-side gate enforcement (`main.py:1861-1876`).
- `autonomy_ref`, `gh_audit_xref`, precedent-gated autopilot — all verified wired.
- Standards bundles, prompt/version chain, custom agents, hooks, MCP, OpenSpec.
- The three existing GitHub enforcement workflows.

### SWAP

- ACA orchestrator as stage executor → GitHub Actions workflow runs.
- Stored service-principal secrets → OIDC federation.
- Bespoke approval UI as the only approval path → Environments + custom deployment protection
  rule calling the control plane for the classification verdict.
- Stage payload as the inter-stage channel → run-scoped artifact store.
- `accuracy_score` as an unpopulated field → a computed, weighted, decaying signal.
- Chosen-option-only persistence → alternatives-weighed persistence.

### ADD

- `rejected_options[]`, `decision_confidence`, `gate_reason` on `LedgerEntry`.
- Run budget limits: max stage retries, max total run minutes, idle timeout.
- Human interrupt on a live run (an operator can halt an in-flight agent stage).
- Repository identification for runs that do not already name their target repo.
- **Stacked-PR agent remediation** (`agent-remediation`): when a governed gate fails, the agent's
  work materializes as a separate pull request stacked on the triggering PR's branch, carrying its
  full evidence chain, never as a commit on a human's branch. This answers what the agent
  *produces* at a gate — which §1 establishes as a run boundary but does not otherwise specify.

### OUT

- Rebuilding anything GitHub already provides: runners, PRs, checks, rulesets, merge queue,
  agent session management.
- Multi-provider CI abstraction. We are deliberately GitHub-only; portability to GitLab or
  Azure DevOps is explicitly **not** a goal of this change.
- Changing canonical standards-bundle content.
- Mutating historical ledger entries. New fields default empty on existing rows.

## Risks and rollback

| Risk | Mitigation |
|---|---|
| A GitHub-hosted stage cannot pause for hours awaiting a human. | The gate is not a paused job. The run **ends** at the gate and a new run resumes on approval; the Decision Ledger is the continuity, not a held process. This is why the ledger stays ours. |
| Custom deployment protection rules are a narrow, preview-adjacent surface. | Isolate behind an adapter. If it regresses, the existing in-app approval path remains functional — the classification verdict is computed by the control plane either way. |
| Actions job limits (max minutes, retention) bound long stages. | Enforced explicitly as the §4 run budget, surfaced as `budget_exceeded` rather than an opaque timeout. |
| Moving execution loses the private-network posture. | Self-hosted runners inside the existing VNET remain available for stages that touch private endpoints. Decided per stage, not globally. |
| The teaching loop injects a wrong lesson. | Two-stage promotion, asymmetric penalty, decay, tombstones. A lesson is never injected while tentative. |
| A phased migration leaves two runtimes live. | Each stage migrates behind a flag with the ACA path intact until its GitHub equivalent is proven on a live run. Rollback is per-stage. |

## Open questions

1. **Q1 — Per-stage or per-run job granularity?** One job per stage gives natural checkpoints and
   per-stage rollback, at the cost of re-hydrating context each job. Leaning per-stage; the
   artifact store (§4) makes re-hydration cheap.
2. **Q2 — Does the custom deployment protection rule call the control plane synchronously, or
   does the control plane post its verdict back?** Webhook-plus-callback is the documented shape;
   confirm the timeout budget before committing.
3. **Q3 — Do promoted lessons require human endorsement before first injection?** Conservative
   answer is yes for `INVARIANT_CLASSES`, automatic for the rest. Proposed default: yes for
   invariant classes only.
