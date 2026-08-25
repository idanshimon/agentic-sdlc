# Design: adopt-github-native-execution-substrate

## 1. The mapping table — every competing feature lands on ours, or is explicitly declined

This is the requirement "every feature must map correctly to ours". No orphans: each row is
either mapped to a concrete artifact in this repository, or declined with a reason.

| # | Competing platform capability | Their mechanism | Our position today (file:line) | Disposition |
|---|---|---|---|---|
| 1 | Per-run inter-agent scratch | `scratchpad` tools; `append_scratchpad` is parallel-safe | **none** — stage payload only | **ADOPT** → §4 run-scoped artifact store |
| 2 | Cross-run memory | weighted memory, auto-injected into every agent, top-N by weight | `accuracy_score` declared, `0.0` on all 229 entries | **ADOPT + EXTEND** → §5; ours is org-scoped by `(ambiguity_class, slot_value_hash)`, theirs cannot cross workflows |
| 3 | Self-improvement retrospective | every N runs, random sample, sequential investigation | **none** | **ADOPT** → §5, scheduled on GitHub Actions |
| 4 | Alternatives weighed | `OrchestrationDecision.proposals` = full candidate set | `AmbiguityCard.options` presented (`models.py:85`), discarded at persist | **ADOPT** → `rejected_options[]` |
| 5 | Typed pause reason | `pendingReason` enum (6 values) | reason implicit in `autonomy_ref` free text | **ADOPT** → `gate_reason` enum (7 values) |
| 6 | Decision confidence | `confidence` float + `autoApprove.minConfidence` | absent on ledger | **ADOPT the field, DECLINE the gate** → see §2 |
| 7 | Runaway limits | `limits{maxSteps, maxRepeatsPerWorkflow, idleTimeoutHours, maxActiveInstances}` | per-stage timeout only | **ADOPT** → run budget, surfaced as `gate_reason=budget_exceeded` |
| 8 | Human interrupt on a live run | `exitCriteria.userSignals` — comment `/done` to end a session | pre-declared gates only | **ADOPT** → operator halt |
| 9 | Repo identification | `repo.identify` with confidence + `maxResults`/`minConfidence` | run assumes its repo | **ADOPT** → needed once GitHub is the substrate |
| 10 | Actor attribution on each step | `decidedBy` = EntryTrigger \| Rule \| Supervisor \| Human | `actor.kind` + `confidence_source` (`models.py:74,147`) | **ALREADY OURS** — no change |
| 11 | Why-this-was-gated | `pendingReason` on the decision | `autonomy_ref` on every path (`main.py:420-443,769,1907`) | **ALREADY OURS** — strengthened by row 5 |
| 12 | Human gate | `gates{name, gateCompletion, chatAgent}` + `autoApprove.minConfidence` | server-enforced 409 (`main.py:1861-1876`), `INVARIANT_CLASSES` floor (`models.py:67`) | **OURS IS STRONGER** — keep, see §2 |
| 13 | Policy expression | none — governance is RBAC + gates | versioned standards bundles, committee-reviewed, cited as `[dept/version/rule-id]` | **OURS IS STRONGER** — keep; fix coarseness (§6) |
| 14 | Precedent across decisions | none — memory is per-workflow/step | `precedent_refs` + `find_precedent` gates autopilot (`main.py:413,433`) | **OURS IS STRONGER** — keep |
| 15 | Immutable decision record | orchestration runtime rows + workspace audit trail | append-only ledger, Cosmos-persisted, `InvariantWriteBlocked` (`_legacy_v06.py:46`) | **OURS IS STRONGER** — keep |
| 16 | Workflow versioning | draft/committed, diff, restore, on workflows *and* orchestrations | Git + `CODEOWNERS` + OpenSpec | **PARITY** — Git is the stronger substrate; no change |
| 17 | Multi-agent coordination | `agent.session` coordinator + `delegate_to_sub_agent` | pipeline stages, fixed sequence | **DECLINE for now** — our stage graph is deliberately fixed; dynamic delegation is a separate change |
| 18 | Agent tool catalog | 41 tools, 9 categories | `.github/agents/*.agent.md` declare allowed tools | **DELEGATE TO GITHUB** — the agent runtime owns the tool surface |
| 19 | Provider-agnostic CI tools | one surface over GH Actions / GitLab / Bitbucket / ADO | GitHub-only | **DECLINE** — explicit non-goal; our infra is GitHub |
| 20 | Pluggable agent engine | `agentEngine: overcut \| claude` | per-stage provider config | **PARITY** — no change |
| 21 | Secrets vault | project-scoped vault | Managed Identity + Key Vault; OIDC after this change | **PARITY** — GitHub OIDC is the improvement |
| 22 | Repo semantic indexing | `semantic_code_search`, repository indexing | none | **DECLINE for now** — real gap, but not governance; file separately |
| 23 | Cost/token analytics | token usage analytics dashboards | `cost_usd`, `model_used` on every entry (`models.py:116-117`), `/telemetry` | **ALREADY OURS** |
| 24 | Multi-tenancy | workspaces / projects | `team_id` partition key (`models.py:108`), canonical team IDs | **ALREADY OURS** |
| 25 | Time-to-value | free tier, 18 importable playbooks, <10 min | PRD submit + deploy | **PARTIALLY ADDRESSED** — GitHub substrate removes the deploy step; playbook-equivalent is out of scope here |

Rows 1–9 are the additive scope of this change. Rows 10–16 and 23–24 are verified-existing and
must not regress. Rows 17, 19, 22 are declined with stated reasons.

## 2. The decision that defines the product: classification, not confidence

Row 6 and row 12 are the crux, and they resolve in opposite directions on purpose.

The competing platform gates on `autoApprove.minConfidence`. That is a **threshold on a scalar**.
Its failure mode is structural: a sufficiently confident agent clears any threshold. Confidence is
a property of the *actor*; it says nothing about the *stakes*.

We gate on `ambiguity_class ∈ INVARIANT_CLASSES` (`packages/ledger-core/ledger_core/models.py:67`).
That is a **classification of the subject matter**. `phi-classification` and `auth-policy` pause
regardless of how certain the agent is, and `apps/orchestrator/main.py:1861-1876` enforces it
server-side with an HTTP 409 that no client can talk its way past. `apps/orchestrator/config.py:115`
allows the set to be extended by environment and never shrunk.

Therefore:

- **We adopt `decision_confidence` as a recorded fact.** It is useful evidence, it belongs in the
  record, and reviewers should see it.
- **We decline confidence as a gating authority.** No configuration may make confidence sufficient
  to bypass an invariant class.

This is the one sentence a regulated customer needs: *confidence is recorded, classification decides.*

## 3. What GitHub can and cannot enforce

Grounding the infra decision honestly. This is the retained-surface justification.

**GitHub can enforce:**

| Need | Primitive |
|---|---|
| Only certain people may approve | Environments + required reviewers; `CODEOWNERS` |
| Certain checks must pass before merge | required status checks; rulesets; merge queue |
| Least-privilege agent credentials | `permissions:` blocks; scoped `GITHUB_TOKEN`; OIDC |
| Who did what, org-wide | audit log (+ streaming) |
| Build provenance | artifact attestations |
| Deterministic policy scan on every PR | Actions workflow with no secret — our `bundle-enforce.yml` already does this |
| Defer an approval to an external service | **custom deployment protection rules** |

**GitHub cannot enforce — this is the control plane's reason to exist:**

1. **Classification-driven gating.** Environments gate on *who approves*, never on *what class of
   thing is being decided*. There is no native expression of "if this action is PHI-touching,
   require a named approver, unbypassable."
2. **A per-decision rationale record.** Actions logs record what a job *did*, not why an agent
   *chose*. Nothing native holds `decision` + `rationale` + `bundle_refs` + `precedent_refs`.
3. **Precedent lineage across runs, repos, and time.** No native primitive links this decision to
   the prior decision it reused.
4. **Rule-versioned policy citation.** Rulesets are configuration, not versioned, reviewable,
   citable rule artifacts with `[dept/version/rule-id]` provenance.
5. **Durable pause-and-resume for human input.** Actions jobs are bounded. A run that waits days
   for a committee is not a paused job — which is exactly why the ledger, not a held process, is
   the unit of continuity.

The custom deployment protection rule is the seam: GitHub owns execution and asks us for the
verdict; we own the verdict and the record of it.

## 4. Migration shape

Per-stage, flag-gated, ACA path intact until each GitHub equivalent is proven on a live run.

1. **Phase 0 — non-executing prerequisites.** Ledger schema additions (§2/§3 of the proposal),
   artifact store, run budget. These ship on ACA first and are substrate-independent.
2. **Phase 1 — the leaf stage.** `review_scan` moves first: it is already deterministic, already
   has a GitHub equivalent in `bundle-enforce.yml`, and has no downstream consumer.
3. **Phase 2 — the gate.** Environments + custom deployment protection rule calling the control
   plane for the classification verdict. Proven against a `phi-classification` card: the 409
   behaviour must be observable through the GitHub approval path.
4. **Phase 3 — the generative stages.** `architect`, `test_plan`, `codegen` onto the GitHub agent
   runtime with existing `.github/agents/` personas.
5. **Phase 4 — decommission** the ACA stage executor once every stage has a proven GitHub run.
   The control plane API, ledger, and MCP server remain.

Rollback is per-stage: flip the flag; the ACA path is still there until Phase 4.

## 5. Verification obligations

Per repository `AGENTS.md`, a claim is not closed by passing tests. Each item below names the
proof required.

| Claim | Proof |
|---|---|
| Hard gate survives the migration | A `phi-classification` card, approved via the GitHub Environment path, is rejected when submitted as `bulk`. Observed 409, not a unit test. |
| Alternatives are persisted | Read a live ledger entry back from Cosmos; assert `rejected_options` is non-empty for a multi-option card. |
| Teaching loop computes | `accuracy_score != 0.0` on at least one live entry, with the retrospective run that produced it identified. This is the specific defect being closed. |
| Artifact store retires payload truncation | A stage handoff exceeding the prior payload limit completes. |
| `bundle_refs` is honest | No hardcoded rule ID remains in `deliver_github.py`; all seven stages stamp; entries distinguish rule-evaluated from subscription-set. |
| OIDC replaces stored secrets | No service-principal secret in the workflow; a live run authenticates to Azure by federated token. |
| Gate reason is typed | Every gate-opening entry carries a non-null `gate_reason`. |
| Agent never writes to a human branch | A live failed gate yields a stacked PR; the triggering head branch shows zero agent-authored commits. |
| Remediation evidence chain is complete | Open a live remediation PR; every link (triggering PR, gate, run URL, ledger id, rule citations) resolves. |
| Agent cannot close its own loop | An agent approval on an agent-authored PR leaves required review unsatisfied in the live repo. |
| Triggering PR unblocks automatically | Merging a live remediation re-evaluates the triggering PR's gates with no manual action. |

## 6. The authoring layer: agentic workflows as the stage-execution engine

§4 says stages move to GitHub Actions. It does not say how a stage is *authored*. Hand-writing
seven pipeline stages as raw Actions YAML — each with sandboxing, egress control, engine
selection, and a write path that the agent itself must not hold — is the kind of undifferentiated
work this change exists to stop doing.

The GitHub agentic-workflow toolchain is that authoring layer. A stage is a Markdown file with
YAML frontmatter; the toolchain compiles it to a committed `.lock.yml` that Actions executes. The
compiled artifact is a repository file under `CODEOWNERS` — which is exactly the deployment spec's
requirement that user-private automation must not be the canonical definition.

### 6.1 What the authoring layer provides, and therefore what we stop building

| Need | Provided by the authoring layer | Our former plan |
|---|---|---|
| Stage definition as a reviewable repo artifact | `.md` source + compiled `.lock.yml` pair | hand-written Actions YAML per stage |
| Agent sandbox + egress allowlist | container isolation behind the workflow firewall | task 6a.6, largely satisfied |
| Per-stage engine selection | `engine:` frontmatter | per-stage provider config in orchestrator env |
| Agent holds no write permission | agent job read-only; writes execute in a separate scoped job | task 6a.5, satisfied structurally |
| Mechanical write path | safe-output handlers, incl. pull-request creation and check runs | bespoke GitHub client code per stage |
| Per-run cost ceiling | per-run AI credit budget | part of §4 run budget |
| Inter-stage data | run-scoped artifact upload + restored context folders | §4 artifact store, cheaper |

### 6.2 The boundary, stated precisely

The authoring layer is an **execution** mechanism. It has no concept of subject-matter
classification, no durable decision record, and no cross-run precedent. Its own built-in threat
screening is a non-deterministic classifier — defense in depth, never a policy gate.

Therefore the split is exact and unchanged from §3:

> **Safe outputs are the mechanism by which a write happens. The control plane decides whether
> the write is permitted.** A safe-output handler that creates a pull request is plumbing. The
> verdict that a `phi-classification` decision requires a named human before that pull request may
> merge is ours, and there is no frontmatter key that expresses it.

Concretely, the remediation flow specified in `specs/agent-remediation/spec.md` composes both
planes: the agent job proposes, the safe-output job creates the stacked pull request, and the
control plane supplies the classification verdict and the quorum policy that decide whether it
may merge.

### 6.3 Q1 resolves: per-stage

The authoring layer's unit of composition is one workflow file. Stage jobs chain by declaring
dependencies, and a stage job can be gated on a control-plane job. This resolves **Q1 in favour of
per-stage granularity**, which was already the leaning; the artifact store makes re-hydration
cheap enough that the objection does not bind.

### 6.4 Q2 partially resolves

The authoring layer exposes manual approval routed through environment protection rules. That is
the seam the custom deployment protection rule attaches to, and it confirms the hook is a
first-class frontmatter concern rather than something bolted on. **The timeout budget remains
open** and still gates Phase 2.

### 6.5 Correction to a recorded blocker

The proposal's §1a records the toolchain as "a research-stage project whose own README has retired
releases over a billing defect." That characterization is stale: the toolchain is in public
preview with per-run credit budgeting. The **mitigation is unchanged and still required** — pin an
explicit version, keep the prior path behind a per-stage flag (tasks 6a.7, 6a.8, 7.1). Preview
status is a reason to pin, not a reason to defer.

### 6.6 What does not change

Constraint 2 is untouched and remains the load-bearing limit. A workflow run is an Actions run:
job and run duration caps apply, and a standards committee deliberating for weeks exceeds them.
The authoring layer is a per-run execution engine, not a durable workflow engine.

> The run **ends** at the gate. A new run resumes on approval. The Decision Ledger is the
> continuity.

This is the strongest available argument that the control plane is not redundant: the substrate
structurally cannot hold a governance gate open, and its log retention is measured in days against
a six-year obligation.

## 6.7 Correction from adversarial review: topology is not authorship

The first draft of `agent-remediation` treated the stacked pull request as the control that keeps
agent work attributable. An adversarial review defeated that in one move, and the correction is
worth stating plainly because it changes what we claim in front of a customer.

**A pull request's opener does not establish who wrote its contents.** An agent's patch can be
transplanted into a human-opened PR, or a human can open an empty PR that an agent then fills.
Either way the work is agent-produced and the rule that agents cannot approve agent-authored PRs
silently stops applying. Worse, a squash merge collapses commit identity so the durable history
may attribute the result to the merging human. Branch shape is not evidence.

The controls are therefore reassigned:

| Concern | Wrong control (first draft) | Correct control |
|---|---|---|
| Who wrote this | PR opener / branch topology | Attestation bound to the patch digest |
| May this merge | HTTP 409 from the API | Authorization for the exact resulting SHA, enforced at the ref |
| Is the gate trustworthy | Policy read from base revision | The whole evaluation boundary — policy, workflow, actions, verifier, collectors, publisher — from an immutable trusted revision |
| Is this bounded | Stack depth | Root-scoped budget (attempts, time, cost, changed surface) |
| Can it be reconstructed | `gh_audit_xref` triple | Immutable lifecycle events with parent/root ids and all SHAs |

Two consequences we should not soften:

1. **An API refusal is advisory unless it is bound to the merge.** The 409 remains correct and
   remains ours, but if any merge path — administrator, App, bot, merge queue — can route around
   it, "classification decides" is false. The gate has to live at the ref.
2. **The trust boundary is bigger than the policy.** An agent that cannot weaken the rule can
   still weaken the test that proves it. Protecting `rules.yaml` while leaving the verifier
   writable is a gate in name only.

**Stacked PRs are retained, with a demoted claim.** They materially improve review segregation —
human intent is one diff, agent remediation is another — and that is a real benefit worth keeping.
They are not proof of authorship and this spec no longer implies they are.

The honest customer sentence is now: *attestation says who wrote it, the ref says what may merge,
and the stack makes it reviewable.*

## 7. Open questions carried from the proposal

- **Q1** per-stage vs per-run job granularity — **RESOLVED: per-stage** (design §6.3).
- **Q2** custom deployment protection rule callback shape and timeout budget — **shape resolved**
  (environment-protection seam, design §6.4); **timeout budget remains open** and gates Phase 2.
- **Q3** human endorsement before first injection of a promoted lesson — proposed default is
  required for `INVARIANT_CLASSES` only.
