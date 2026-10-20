# Bootstrap a self-propelled project: the intended user experience

Status: proposed product contract, not an available command or completed implementation. See the normative `project-bootstrap`, `goal-driven-development` and `operational-repair` capability specs. This walkthrough explains those contracts; it does not grant permissions.

## The promise

Describe the application and what success means, choose the foundation modules, and grant bounded authority. The result is three connected foundations:

1. An application with reviewed requirements and acceptance criteria.
2. A development loop that progresses through approved milestones.
3. A post-deployment loop that investigates incidents, performs permitted repairs and verifies recovery.

A scaffold, Markdown instructions or an impressive graph alone is not that result.

## 1. What the user says

> Start a private customer-support portal. Use the Team foundation. Customers can open tickets and upload attachments; staff can assign and resolve them. Break the work into reviewed milestones. Run unit, integration and browser tests where applicable. Agents can investigate failures, open fix PRs and address review findings. Preview deployment is automatic; production initially needs my approval. Monitor errors and availability after deployment. Authentication, database migrations and infrastructure changes always need their designated review. Record important decisions and independently verified outcomes. Stop for unclear product decisions, scope changes or exhausted repair limits.

The chosen application is illustrative. Real requirements must establish users, data, hosting and acceptance criteria. The assistant asks consequential missing questions, not an endless form about harmless defaults.

## 2. What the user reviews

Bootstrap presents a plan before applying it:

- **Product:** goals/non-goals, milestone backlog, dependencies and measurable acceptance.
- **Modules:** selected features and their resolved dependencies; omitted modules remain omitted.
- **Authority:** investigate/propose/repair/merge/deploy/runbook permissions per target and sensitive-change rules.
- **Footprint:** shared services reused, new application resources required, owning identities, permissions and cost categories.
- **Limits:** enforceable attempts, duration, concurrency, spend where supported, monitoring/evidence freshness and escalation destination.
- **Artifacts:** exact staged application/spec/test/workflow/instruction/monitoring/runbook changes, preserving unmanaged files.

Simple, Team and Governed are editable starting profiles. Governance strength, automation authority and infrastructure footprint are independent choices. Turning on a profile does not imply certification or consent to cloud provisioning.

## 3. What gets bootstrapped

The approved setup generates/adapts the application scaffold and specs; task backlog; agent instructions; selected tools; CI/review/repair/deployment workflows; tests and acceptance cases; scoped connection/deploy configuration; runtime instrumentation and external probes; recovery runbooks; effective-config and evidence references.

Credentials are configured through authorized secret mechanisms, never embedded in generated files. Where a capability or resource is unavailable, readiness says blocked/unconfigured with the missing prerequisite. It does not promise a tool that the selected runtime cannot call.

## 4. What proves it is ready

A small real change must travel through the selected path: task → PR → executed checks/review → preview → acceptance check → external health observation. If post-deployment repair is enabled, also prove signal → incident → eligible investigation dispatch in a safe test target.

The user receives exact run/build/probe references and a scope-specific readiness report. Generated only = staged. No deployment proof = not full-lifecycle ready. A deliberately narrower diagnosis-only setup may be ready for that narrower scope, but it is not described as autonomous delivery or self-healing.

## 5. What happens without the next human prompt

An enabled controller selects an approved task whose prerequisites are satisfied, claims it once, loads its goal/config/target/evidence, and dispatches the selected agent runtime. It records meaningful choices, produces the implementation PR, runs independent acceptance checks, addresses review findings within limits and follows the permitted release path.

A future run continues from durable task/evidence state; a model is not necessarily running continuously. The controller waits when no task is eligible. Product ambiguity, scope growth, repeated failure, unsupported tools or limits become explicit questions/blockers. Agents may suggest additional features, but cannot invent approved goals or weaken protected acceptance criteria to declare progress.

## 6. After release: attachment uploads fail

The external monitor/error source observes failures against a deployed build. The incident correlates app, environment, symptom, trace/log evidence and version. Duplicate signals converge on a bounded investigation rather than many competing PRs.

- **Code defect:** reproduce, add an appropriate regression, prepare a repair PR and run independent checks/review.
- **Configuration/runbook issue:** use only the separately authorized operational action.
- **Dependency outage, flake or unknown:** investigate/escalate; do not force every alert into a code patch.

The configured release policy decides the next step: proposed repair only; qualifying autonomous merge/deploy; or required human review. Sensitive work never inherits permission from an unrelated low-risk success. Initial project proofs keep human merge; later production automation needs its own explicit approval and exercised recovery path.

Deployment does not close the incident. Retest attachment upload against the new build and observe the defined health window. If it still fails or cannot be verified, remain unresolved and use authorized rollback/compensation or escalate. Record the actual outcome, not merely a requested action.

## 7. What the agents learn

Keep the storage API constraint as scoped knowledge; the streaming-versus-timeout choice as an attributed decision with alternatives; regression/deployment/retest as evidence; and the resulting approach as a candidate comparable precedent. A later reversal remains part of the history and can invalidate reuse.

Useful learning can propose better tests, runbooks or versioned instructions. Canonical policy and permission changes follow their review paths. Default learning does not retrain model weights, treat self-written success prose as truth, or authorize the agent to repeat the action in every environment.

## Required infrastructure

### Shared foundation, reused across projects

- Authenticated Mission Control and API.
- Scoped GitHub connection and approved model/agent surface.
- Durable event/work dispatch, command state and execution/reconciliation.
- Durable action/decision receipts plus evidence references.
- Identity, secrets, scoped access and independent monitoring for the foundation.

These are logical responsibilities, not a requirement for one server per item. GitHub workflows can perform execution; a small deployment may co-host other components. A supported minimal receipt backend need not be Cosmos. The exact topology must be specified and tested before claiming readiness.

### Per application

- Repository and runner/test capacity.
- Agent/model entitlement and policy-permitted access.
- Preview/production hosting and database/storage only as required by the application.
- Scoped deployment identity and secrets.
- Logs/error instrumentation plus external availability/health probes.
- Product/operations owners, acceptance cases and recovery procedures.

Sharing the foundation does not allow sharing application credentials or leaking data between repositories/teams.

### Optional, not mandatory dependencies

Doctor, custom decision-model hosting, vector retrieval, rich cross-repo analytics and authored graph generation. GPUs, Kubernetes and a vector database are not intrinsic prerequisites. Content Creator/Archify normally runs as authoring/build tooling, not an always-running service.

The resolved resource plan must show reused/new/missing resources, permissions, data/network/retention, cost categories, owner and teardown/disconnect actions. Dollar estimates require actual provider pricing/usage evidence; none is claimed in this draft.

## The user should always be able to answer

What are agents working on? What may they do next? Why did they choose this? What needs me? Which code/build was tested? Did the original problem stop? What did we learn? What happens if I pause or disconnect?

Those questions define the Mission Control workspace. Graphs explain the same evidence; they do not supply authority or manufacture completion.
