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

## 6. Open questions carried from the proposal

- **Q1** per-stage vs per-run job granularity — leaning per-stage.
- **Q2** custom deployment protection rule callback shape and timeout budget — confirm before
  committing Phase 2.
- **Q3** human endorsement before first injection of a promoted lesson — proposed default is
  required for `INVARIANT_CLASSES` only.
