# Design: Agentic Mission Control foundations

## Context

The local baseline is `main` at `f9b0233`. Prior exploration lives in `docs/github-first-adoption-direction.md` and `docs/github-first-decision-integration.md`. This is a customer-neutral design composition, not a production implementation audit.

The existing system already separates Standards / Pipeline / Ledger+Doctor / Agent runtime. Current local code includes alternatives and gate reasons, read-time precedent scoring, exact-state merge authorization, evaluation-path classification and remediation lifecycle functions. Local contract tests in the prior exploration passed; none prove remote GitHub settings or a working end-to-end GitHub-only repair loop.

## Goals / Non-Goals

**Goals:**
- Give a repository owner one understandable operating workspace over agent activity, decisions, blockers and outcomes.
- Adopt GitHub-native execution where its current documented and authenticated behavior satisfies the contract.
- Gradually add agentic behavior to existing CI/CD as well as new projects.
- Use decision models for suitable judgments without equating probability with permission.
- Deliver beautiful, interactive explanations and real evidence graphs without fabricating live activity.
- Make target scope, identity, budgets, failure handling and verification first-class.

**Non-Goals:**
- Rebuild GitHub PR/check/session infrastructure or migrate every stage immediately.
- Adopt every Content Creator renderer as an application dependency.
- Let a model change its own rules, evaluation oracle, credentials or autonomy tier.
- Claim full production self-healing from a successful PR or a logging stub.

## Decisions

### D1 — Evolve the existing application, not another Mission Control product

The initial host is the existing Ledger Insights application and its server-enforced contracts. Route/layout changes are proposed only after inventorying existing pages. Operator navigation follows tasks: Operate / Decide / Explore / Govern / Configure, not internal service names. The initial page is an attention queue; graphs are coordinated exploration views, not mandatory navigation for every action.

Rejected alternative: build a separate generic dashboard/runtime and synchronize everything twice. It would duplicate identity, policy and evidence ownership.

### D2 — GitHub executes; our decision contracts govern the integration

Use a GitHub App installation as the default connection candidate: selected repositories, short-lived installation credentials and separately reviewed permission expansion. Verify enterprise constraints before selecting the final integration. Personal tokens are not the default production design. Reads, PR creation, repairs, merge and deployment have distinct permissions.

A connector normalizes external events and observations; a durable action service validates user/workload identity and current envelope; a worker performs supported external commands; a reconciler reads back actual state. API names and hosting topology are intentionally not frozen yet. Provider APIs remain versioned adapters. Every feature is classified native, bridged, unavailable or unverified for the actual installation/license/policy.

The control plane can span multiple repos, but release one repo first. GitHub remains authoritative for PRs/checks/deployments. Ledger entries are authoritative records of project decisions, not an alternative forge database. A check is enforced only when the target ref actually requires a trusted publisher's result and bypass posture is known.

### D3 — Treat work as a correlated evidence graph

Candidate domain objects: repository connection, application/target, work item, execution/session reference, decision, action command, verification result, policy version and outcome observation. These are logical contracts, not promises of new database tables. Reuse stable existing identifiers before adding fields.

Lineage joins source event → task → session/attempt → decision → command → PR/commit/check → deployment → original-task retest. Preserve source IDs, event/observation time, commit/artifact digests, policy digest and freshness. Unknown or stale evidence stays visibly unknown/stale. All tenant/repository filters constrain server-authorized scope.

The UI derives lifecycle state over immutable events. Missing verification is never inferred from approval or terminal success. Commands use authenticated actors, idempotency and expected-version preconditions; state conflict is an actionable result.

### D4 — Separate four kinds of intelligence/control

1. Deterministic extraction/checks for authoritative structured facts, identity, arithmetic, policy and exact-state comparisons.
2. Typed decision models for bounded evidence judgments, such as code defect versus flaky test versus infrastructure versus unknown. Persist question/options/schema/model version and evidence references; model probabilities remain model outputs, not measured correctness.
3. Generative investigation for unfamiliar failures, multi-step tool work and explanations. Open-ended periodic investigation is independent of known detector alarms; an `unknown` label alone does not discover new concerns.
4. Authorization/admission for what may happen. Models advise; reviewed policy and applicable independent evidence determine authority.

A typed model is an application-level tool/service candidate, not an assumed replacement for Copilot's backend. It may offer no generated explanation. Any explanation generated elsewhere is separately attributed, not invented as the decision model's reasoning. Do not deploy/train a decision model in this phase. Benchmark rules, typed models and an appropriate generative baseline on held-out SDLC cases before routing real work.

### D5 — Scope autonomy before reasoning can authorize work

Resolve repository/application, target environment and policy-defined target/risk class before the first autonomy decision. The current precedent lookup and class-history projection are target-blind; the delivery target resolves too late. Reconcile this in `add-per-run-delivery-target` and substrate work rather than adding a second lookup.

An envelope identifies action class, protected scope, roles/identity, policy digest, budgets, tool/data/egress bounds, time horizon and human requirements. Unknown scope cannot inherit production-affecting authority. A target class is a candidate reuse dimension, not proof that all production services are equivalent. Explicit compatibility policy determines legitimate cross-repo precedent reuse.

Autonomy is per transition: diagnose, propose, dispatch, repair, approve, merge, deploy or execute a runbook. Promotion is a reviewed policy change supported by independent outcomes; demotion/revocation must be immediate for new commands. In-flight cancellation can be requested, acknowledged, unsupported or completed; a stop button does not establish rollback.

### D6 — Use the existing remediation contracts, then prove integration

`merge_authorization.py`, `evaluation_path.py`, `attestation.py` and `remediation_lifecycle.py` provide useful local contracts. They do not install remote protections, independently mint production attestations or guarantee a running reconciler. Wire and test their real boundaries before declaring a loop safe.

Persist intent before dispatch, perform the authorized operation, reconcile its exact external target and record observed result. On ambiguous completion, reconcile before retry. Draft/quarantined work remains non-mergeable until records agree. Independent admission protects not just standards, but the workflow, verifier, collector, publisher, pins and ownership path that turn standards into a verdict.

Operational runbooks and code repairs are different executors. Recovery, canary verification and rollback each require their own authority and acceptance criteria. Production operations are deferred until a bounded test-target proof exists.

### D7 — Context memory, precedent and outcomes remain distinct

Runtime memory supports investigation. The decision ledger preserves attributable choices and evidence. Eligible precedent supports comparable decisions; it is not a permission token. Outcomes are observations of tests, deployment/recovery, reversions and human corrections with explicit coverage.

Current `accuracy.py` projects agreement using replay history. Human agreement is not escaped-defect rate, causal benefit or production correctness. No self-written success claim or repeated copy of one case can manufacture graduation evidence. Missing/unmeasured values are not numeric zero in product metrics. Retention/deletion/redaction policy must reconcile immutable audit needs with access and data obligations; secret-bearing content must not become permanent memory.

### D8 — Archify explains; live graphs explore; neither grants authority

Content Creator's pinned Archify integration renders authored typed JSON to interactive HTML. Use it for architecture/flow explanations, guided chapters and portable walkthroughs. It does not discover architecture from source or supply a production control backend. Its output is optional generated content, not runtime policy.

Existing data-driven graph components remain candidates for live decision lineage and execution topology. Reuse the app's current theme and source projection; do not replace every graph just to match a presentation renderer. The Content Creator orbital mission-control template is a showcase reference with synthetic telemetry and local gate interaction; its Approve button is not a backend-authorized command.

Graph nodes have stable IDs, source/status/version and links to the same inspector as list rows. Single click explains without moving the camera; explicit Explore descends with Back/breadcrumbs and URL state. Controls, keyboard/touch, reduced motion, selection and readable arrows/labels must be verified at delivery size. A textual/list equivalent remains usable.

Embed generated artifacts with sandbox/CSP and strict origin/schema validation. Do not give an iframe repository tokens or accept approval messages from it. View/selection messages may update local focus; real actions go through first-party authorization and an explicit intent preview.

### D9 — The decision workbench is the center, not a decorative graph

A selected task answers: what happened; observed facts versus suspected cause; recommended action and alternatives; policy/permission; affected target and downstream consequence; checks/verification; who owns the next step. Raw evidence is linked. No private internal model thought is required or fabricated.

Core verbs: investigate, request fix, request re-review, approve a specific eligible action, reject with reason, pause new dispatch, request cancellation, open the PR and inspect evidence. Expose only implemented/supported actions, with meaningful unavailable reasons. Explicit retry distinguishes rerun checks, repeat investigation and create another repair attempt. Batch approval is deferred until per-item authority/conflict semantics are proven.

A dashboard decision can be durable across days without holding an Actions job open; resume is a new run revalidating current state. The ledger provides decision continuity, not a guarantee that any runtime checkpoint can be resumed universally.

### D10 — One bounded existing-pipeline repair is the first product slice

Milestones:
- **M0:** reconcile baseline/source/task status, prove read-only repository inventory and decision/evidence contracts, define failure-case fixture and policy envelope.
- **M1:** connect one approved repo, show real CI/PR evidence plus attention-first decisions and a source-grounded Archify explainer. Read-only.
- **M2:** real failure → diagnosis → fix PR → independent tests/review → bounded repair → human merge → test-target retest. Link existing ledger contracts throughout.
- **M3:** reviewed low-risk admission envelope with remote enforcement proof; scoped memory/precedent and outcome evaluation.
- **M4:** multi-repo/application dependency scope and governed operational runbooks, canary/rollback and open-ended discovery.

Architecture/graph polish is part of M1/M2, not a substitute for actual command execution. All milestones are planned. M0 grounding completed during drafting is recorded separately from unchecked implementation tasks.

### D11 — Composable foundation profiles, not a universal enterprise installation

Candidate starter presets are **Simple** (one repo, CI visibility, diagnosis/fix PR and human merge), **Team** (shared decisions, bounded repair, configurable review/security integration and outcome visibility), and **Governed** (versioned policy overlays, stronger identity/separation, audit/export/retention and protected change paths). These are editable starting points, not compliance certifications or an ordered autonomy ladder. A simple team can still demand strong security; a heavily governed team can still run observe-only. Add organization-authored presets through the same validated schema.

Configure independent axes: capability activation, automation authority, security/governance policy, model/routing policy, budgets/thresholds and presentation. Show the resolved effective config and provenance per value. UI visibility has no enforcement meaning. Autonomy and governance are not one slider.

The smallest foundation has scoped identity, bounded commands, truthful status and a durable action receipt. It need not deploy Cosmos, the Doctor, custom model hosting, cross-repo analytics or committee review. The rich ledger backend is replaceable/optional as an infrastructure choice; accountable records for consequential actions are not optional. Existing project obligations remain active until their owning specifications are explicitly adapted—this draft does not silently disable existing invariant rules.

Use one versioned configuration manifest (candidate filename `.agentic/foundation.yaml`, not yet selected as an implemented API) with schema/profile/module versions and an effective config digest. Deterministic precedence: platform safety contract → applicable organization-required policy → repository configuration → constrained per-task overrides; profile defaults fill unspecified values and may not override higher authority. Bootstrap cannot import policy merely because untrusted repository text asks it to. Existing bundle precedence remains authoritative within that subsystem.

Each module declares capabilities, dependencies, conflicts, required permissions, resource footprint, data retention and readiness probes. State distinguishes disabled, enabled-unconfigured, ready, degraded and blocked; a permission failure is never rendered as disabled or healthy. Reject unresolved dependencies, cycles, unsupported config and prohibited combinations before applying changes. Never auto-grant permissions to satisfy a dependency.

Examples: typed decision models off → supported rules/generative route or explicit unsupported task, not hidden model hosting. Doctor off → no Doctor worker/schedule/model calls. Authored graphs off → list/workbench remain functional and no renderer service required. Repo memory off → new runs receive no cross-run memory injection; immutable action history is not erased. Mandatory organizational scanning cannot be switched off by a repo preset. Enabling multi-repo authority requires target-aware policy and corresponding scope verification.

Thresholds declare names, units, range, owner and fail behavior: attempt/time/concurrency/spend budgets; evidence freshness; minimum independent samples; decision-model abstention; reviewed autonomy evaluation criteria. Measured correctness, agreement and model probability stay separate. A knob that lacks provider support or runtime enforcement is unavailable/advisory, never shown as a working limit. Hard blocks remain hard blocks; user configuration cannot turn confidence into permission. Relaxing organization policy uses its approval path; making a local limit stricter may use a narrower authorized path.

Bootstrap is inspect → select profile/modules → preview dependency/permission/resource diff → generate staged artifacts → validate → authorized apply → read back actual settings → readiness report. Generate only enabled capabilities' instructions, custom-agent/tool/MCP configuration and workflow templates from pinned templates plus the effective manifest. Keep generated files traceable to template/config versions. Preserve handwritten instructions via managed blocks or separate files; refuse conflicting ownership. Provide dry-run and idempotent regeneration, never silently overwrite existing pipeline/security settings or deploy cloud resources. Exclude credentials from all artifacts.

Generated prompts communicate policy but do not enforce it. The same effective config must drive server validation, worker routing, enabled routes and probes. Unavailable runtime features cannot be activated by writing optimistic instructions. Record the resolved profile/config/policy digests on decisions and commands; config changes invalidate affected prior authority and precedent eligibility as specified by compatibility rules.

Disable is a lifecycle operation: stop new dispatch, reconcile/drain or explicitly cancel accepted work, preserve receipts, revoke unused permissions/credentials and retire owned resources through a reviewed plan. Hiding a page or deleting a workflow is not successful deactivation. Test the minimal preset with enterprise modules actually absent, not merely hidden; add config-only enable/disable/rename cases and rejection tests to prevent silent coupling.

### D12 — Bootstrap is a three-loop operating contract

The primary journey in `bootstrap-journey.md` starts with a plain-language project request, not an invented CLI command. Normalize it to an approved project intent: users/use cases, goals/non-goals, milestone acceptance, target/deployment/data constraints, owner, selected profile/modules and per-action authority. Missing consequential product choices produce explicit questions or reviewable assumptions; never silent product invention.

Compile that intent into linked application specs/scaffold, a dependency-aware backlog, agent instructions, tests, build/review/deployment workflows, runtime monitoring, runbooks and infrastructure plan. Existing projects preserve working artifacts and receive a reviewed additive diff. Include unit/integration/browser tests where applicable, owned acceptance scenarios and independent evaluation paths; an author cannot silently weaken the acceptance oracle to finish a task.

Bootstrap states are intent captured → plan awaiting approval → artifacts staged → applying authorized setup → probing → ready or blocked/degraded. Disabled modules are not enabled, and unprovisioned optional services do not become false blockers for a smaller profile. Readiness records carry effective config/versions and actual evidence: a small real change passes CI/review, deploys to preview, passes an acceptance check, and is seen by an external health probe. Monitoring enabled for repairs additionally needs signal-to-incident dispatch proof. File generation is only staged; full-lifecycle ready is not reported while deployment or monitoring proof is missing. A scaffold-only/diagnosis-only profile may be ready for its explicitly narrower declared scope, never silently upgraded to full-lifecycle ready.

### D13 — Continued development has goals and a stopping condition

A scheduler/controller selects only approved eligible backlog tasks under dependencies, priority, leases/concurrency and budget. It dispatches reasoning/code work to the selected supported runtime rather than assuming the model permanently runs. A later run reloads goal/task/config/evidence state before acting. Development self-propulsion requires an enabled controller and execution capacity; agent instructions alone cannot provide it.

Each task traces approved requirement → implementation/review → exact-head checks → permitted merge/release → acceptance result. Record material choices/options and actual outcomes. Missing product choices, scope growth, conflicting acceptance, unavailable tools and repeated failures block or escalate. Tasks cannot approve themselves by altering protected tests or acceptance criteria. If no eligible task remains, the controller waits or reports milestone completion; it does not generate endless feature work. Suggestions beyond the approved goal enter a separate proposed backlog for review.

### D14 — Post-deployment repair includes release and recovery proof

External monitoring feeds authenticated, redacted, deduplicated incidents associated with application, environment, deployed commit/build, symptom, affected operation and available trace/log evidence. Avoid alert storms and recursive repair triggers using incident correlation, cooldown/concurrency limits and attempt budgets. Foundation monitoring is separate from the application it watches.

Classify a suspected code defect, test flake, configuration issue, capacity/dependency failure or unknown; keep symptom/cause/confirmed fact distinct. Code repairs produce a regression and proposed PR. Operational remediation uses separately authorized runbooks; infrastructure/database/security changes obey their own action/target rules. Unreproducible or ambiguous failures may stay investigation-only. Do not assume every alert should produce code.

Support three selected outcomes: prepare a proposed repair, deploy a qualifying repair autonomously, or escalate for required human authority. Automatic merge/release only occurs inside the explicit current envelope after independent checks, trusted admission and rollout protection. The initial integration proof uses human merge; automatic production release is a later separately approved proof, not permanently excluded from the product.

A merged/deployed change is not recovered service. Verify the original symptom on the deployed build, intended health criterion and configured observation window. Failed or unavailable verification remains unresolved; choose scoped rollback/compensation or escalation according to policy, never claim recovery from a green build. Deployment itself must support and test the selected recovery plan before autonomous production release.

### D15 — Infrastructure is a resolved plan, not one compulsory stack

The bootstrap plan separates:

- **Shared foundation:** authenticated Mission Control/API; scoped GitHub connection; durable event/work dispatch and execution/reconciliation; durable action/decision receipts and evidence references; identity/secrets; independent health/alerts for the foundation. Multiple logical responsibilities may share a deployment, and GitHub workflows may supply execution. A controller may be event-driven rather than a permanently running agent process.
- **Per application:** repository, model/agent entitlement, runner/test capacity, preview/production hosting, application database/storage as needed, scoped deploy identities, logs/error reporting and external health probes. Isolate app data and credentials even when sharing the foundation.
- **Optional modules:** rich cross-repo ledger/analytics, Doctor, typed-model hosting, semantic/vector retrieval, authored graph generation and advanced operational detectors. Neither Kubernetes nor GPUs nor a dedicated vector database is intrinsically required. Content Creator/Archify is build-time/presentation tooling unless an explicit integration adds an isolated rendering service.

Each selected resource/capability has provider/placement, owning identity/team, permission scope, data/network/retention needs, usage limit, supported readiness probe, cost category, lifecycle/exit action and whether provisioned, reused or still required. No invented dollar estimates. A connection or agent subscription is not proof of permission to run every selected surface; verify actual features/policy/entitlements. Show footprint/cost deltas for profiles before authorization; never silently provision cloud resources or require the entire canonical deployment for Simple mode.

Optional model/provider loss disables its route or uses an explicit approved fallback. Shared foundation outage does not remove existing admission requirements. Credentials expire/revoke independently; queue state, accepted commands and evidence must survive the declared restart/recovery tests.

## Existing-change composition and ownership

- `adopt-github-native-execution-substrate`: execution authoring, identity and gate integration. This change supplies operator-facing composition and proof slices; do not duplicate stage migration.
- `add-per-run-delivery-target`: early target resolution and precedent scope; required before cross-target autonomy.
- `redesign-decision-lifecycle-control-plane` and `redesign-decisions-and-run-drilldown`: reuse lifecycle/workbench/source projections and existing routes; evolve rather than fork.
- `add-enterprise-integrations-plane`: connection inventory/config/provenance; reconcile GitHub App and health contracts there.
- `add-autonomy-control-surface` / `add-graduated-autonomy-tier2`: posture and class policy; reconcile transition/target scope there.
- `add-self-heal-cowork`, archived autonomous-review-loop and current remediation source: reuse boundaries without silently converting human approval into unrestricted autonomy.
- `compute-accuracy-score-projection`, replay and teaching-feedback changes: distinguish existing agreement projection from proposed outcome-based graduation.
- `add-pipeline-doctor`: `_apply_config_change` logs a stub while recording applied language. Correct the claim/execution boundary before presenting real self-healing.

Task checkboxes in older drafts can be stale. Each implementation claim needs source + execution evidence; do not rewrite neighboring changes wholesale during this sketch.

## Risks / Trade-offs

- Powerful dashboard becomes a credential aggregation target: installation scoping, separation of duties, short-lived credentials, revocation, egress and audited commands.
- Two external stores disagree: durable intents, quarantine, idempotency and periodic reconciliation, not webhook delivery assumptions.
- Models confidently misclassify: abstention/disagreement paths, authoritative-fact precedence, held-out evaluation and protected authorization floor.
- Beautiful diagrams imply unearned health: visible source/freshness/coverage and measured motion only; authored walkthroughs labeled illustrative.
- Excess scope: first repo first, explicit M0–M4 gates, keep existing pipeline, retire duplicate responsibility after verified replacement.
- Cost/runaway loops: enforced per-task and installation budgets, concurrency limits, visible unmeasured usage and controlled retries.
- Retention/privacy tension: policy-defined raw-evidence retention and redacted audit references; define legal/security ownership before production capture.

## Rollback / Failure Posture

Read-only rollout first; additive schema fields with compatibility tests; no ledger rewrites. Disable individual agent patterns and revoke dispatch authority independently of read access. Required checks remain active through dashboard outages. An unreachable decision service prevents new privileged actions; GitHub evidence reads can be degraded/stale without becoming passing policy. Restore the prior executor only behind the same authority contract; rollback is not permission to bypass gates. Reconcile accepted in-flight commands and export a pending-work record when disconnecting.

## Open Questions

- Which GitHub agent surface actually exposes the required trigger, follow-up, model choice and cost/identity controls under the adopter's current plan/policy? Verify before choosing cloud agent vs CLI vs Agentic Workflows.
- Is a GitHub App supported by the first adopter's enterprise/hosting posture? Which permissions and identity provider are approved?
- Which logical contracts require new fields versus joins over existing ledger/external references?
- What exact target compatibility rules prevent false precedent transfer without starving legitimate reuse?
- Who owns production risk acceptance, evidence retention and rollback authority?
- Which typed-model tasks show a measured benefit over rules or a generative baseline on this workload?
- What discovery schedule/budget is appropriate after known-failure repair is proven?

No cloud provisioning, model inference, renderer integration or repository write authorization is granted by this draft.
