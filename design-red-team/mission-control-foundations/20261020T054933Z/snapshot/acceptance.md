# Acceptance and evidence plan

All scenarios below are specified, NOT executed. OpenSpec validation proves document structure only. Prior local contract tests do not establish these new integration scenarios or remote enforcement.

## Coverage matrix

Every requirement links to a capability spec, implementation task group and proposed verification target. Scenario identifiers are stable within each requirement; changes must preserve or explicitly supersede them. Test file names/routes remain implementation choices until source discovery.

## mission-control-workspace

- Spec: `specs/mission-control-workspace/spec.md`
- Task group: 6
- Proposed proof: UI pure projections, route/component tests, production-build browser command/reconnect tests.

- **MC-01 — Attention before chronology:** `MC-01-01`, `MC-01-02`.
- **MC-02 — Shared decision workbench:** `MC-02-01`.
- **MC-03 — Safe command interaction:** `MC-03-01`, `MC-03-02`.
- **MC-04 — Accessible accountable operation:** `MC-04-01`, `MC-04-02`.

## github-repository-control

- Spec: `specs/github-repository-control/spec.md`
- Task group: 3
- Proposed proof: Adapter contract tests plus approved test-repo API/readback and permission-revocation checks.

- **GH-01 — Scoped connection and capability inventory:** `GH-01-01`, `GH-01-02`.
- **GH-02 — Verified event and evidence ingestion:** `GH-02-01`, `GH-02-02`.
- **GH-03 — Authorized external commands:** `GH-03-01`, `GH-03-02`.
- **GH-04 — Actual admission enforcement:** `GH-04-01`, `GH-04-02`.

## governed-decision-routing

- Spec: `specs/governed-decision-routing/spec.md`
- Task group: 4
- Proposed proof: Typed-schema/provider tests and held-out evaluation; any inference separately authorized.

- **DM-01 — Typed judgment contract:** `DM-01-01`, `DM-01-02`.
- **DM-02 — Authority separate from model output:** `DM-02-01`, `DM-02-02`.
- **DM-03 — Recognition and discovery distinction:** `DM-03-01`, `DM-03-02`.
- **DM-04 — Independent routing evaluation:** `DM-04-01`, `DM-04-02`.

## autonomy-action-execution

- Spec: `specs/autonomy-action-execution/spec.md`
- Task group: 5
- Proposed proof: Existing authorization/lifecycle suites plus real worker/reconciler and target-repo failure injection.

- **AX-01 — Target before authority:** `AX-01-01`, `AX-01-02`.
- **AX-02 — Bounded transition envelopes:** `AX-02-01`, `AX-02-02`.
- **AX-03 — Durable command lifecycle:** `AX-03-01`, `AX-03-02`.
- **AX-04 — Revocation cancellation and recovery:** `AX-04-01`, `AX-04-02`.
- **AX-05 — Protect the evaluation path:** `AX-05-01`.

## decision-memory-outcomes

- Spec: `specs/decision-memory-outcomes/spec.md`
- Task group: 8
- Proposed proof: Recall/scope/projector contracts and persistence/retention/export round trips.

- **MO-01 — Scoped memory and precedent:** `MO-01-01`, `MO-01-02`.
- **MO-02 — Observed outcomes and honest metrics:** `MO-02-01`, `MO-02-02`.
- **MO-03 — Governed learning and promotion:** `MO-03-01`, `MO-03-02`.
- **MO-04 — Retention and portability:** `MO-04-01`, `MO-04-02`.

## evidence-graph-views

- Spec: `specs/evidence-graph-views/spec.md`
- Task group: 7
- Proposed proof: Shared projection tests, pinned renderer outputs and browser sweeps for every view/theme.

- **GV-01 — One evidence projection:** `GV-01-01`, `GV-01-02`.
- **GV-02 — Archify and live graph boundary:** `GV-02-01`, `GV-02-02`.
- **GV-03 — Exploration interaction and render proof:** `GV-03-01`, `GV-03-02`.
- **GV-04 — Presentation isolation:** `GV-04-01`, `GV-04-02`.

## foundation-configuration

- Spec: `specs/foundation-configuration/spec.md`
- Task group: 2
- Proposed proof: Resolver/bootstrap contracts, exact generated diff, absent-service tests and authorized remote readback.

- **FC-01 — Composable profiles and independent controls:** `FC-01-01`, `FC-01-02`.
- **FC-02 — Deterministic effective configuration:** `FC-02-01`, `FC-02-02`.
- **FC-03 — Dependency resolved activation:** `FC-03-01`, `FC-03-02`.
- **FC-04 — Enforced threshold semantics:** `FC-04-01`, `FC-04-02`.
- **FC-05 — Reproducible instruction bootstrap:** `FC-05-01`, `FC-05-02`, `FC-05-03`.
- **FC-06 — Safe configuration change and deactivation:** `FC-06-01`, `FC-06-02`.
- **FC-07 — Minimum accountable foundation:** `FC-07-01`, `FC-07-02`.

## incremental-adoption

- Spec: `specs/incremental-adoption/spec.md`
- Task group: 9
- Proposed proof: Existing-pipeline inventory, controlled M1/M2 evidence and operator exit/recovery exercise.

- **IA-01 — Existing pipeline assessment:** `IA-01-01`.
- **IA-02 — One complete repair proof:** `IA-02-01`, `IA-02-02`.
- **IA-03 — Graduation by action and target:** `IA-03-01`.
- **IA-04 — Cost ownership and exit:** `IA-04-01`, `IA-04-02`.

## project-bootstrap

- Spec: `specs/project-bootstrap/spec.md`
- Task group: 10
- Proposed proof: executed integration/failure tests with durable state and exact external readback; fixtures alone do not prove deployed behavior.

- **PB-01 — Approved project intent:** `PB-01-01`, `PB-01-02`.
- **PB-02 — Three connected foundations:** `PB-02-01`, `PB-02-02`.
- **PB-03 — Resource and permission plan:** `PB-03-01`, `PB-03-02`.
- **PB-04 — Executed scope-specific readiness:** `PB-04-01`, `PB-04-02`, `PB-04-03`.
- **PB-05 — Durable setup and handoff:** `PB-05-01`, `PB-05-02`.

## goal-driven-development

- Spec: `specs/goal-driven-development/spec.md`
- Task group: 11
- Proposed proof: executed integration/failure tests with durable state and exact external readback; fixtures alone do not prove deployed behavior.

- **GD-01 — Approved eligible work selection:** `GD-01-01`, `GD-01-02`.
- **GD-02 — Requirement-to-acceptance development loop:** `GD-02-01`, `GD-02-02`.
- **GD-03 — Durable bounded continuation:** `GD-03-01`, `GD-03-02`.
- **GD-04 — Product change and milestone control:** `GD-04-01`, `GD-04-02`.

## operational-repair

- Spec: `specs/operational-repair/spec.md`
- Task group: 12
- Proposed proof: executed integration/failure tests with durable state and exact external readback; fixtures alone do not prove deployed behavior.

- **OP-01 — External incident evidence:** `OP-01-01`, `OP-01-02`.
- **OP-02 — Diagnosis before intervention:** `OP-02-01`, `OP-02-02`.
- **OP-03 — Policy-permitted automatic release:** `OP-03-01`, `OP-03-02`, `OP-03-03`.
- **OP-04 — Original-symptom recovery proof:** `OP-04-01`, `OP-04-02`.
- **OP-05 — Authorized recovery and learning handoff:** `OP-05-01`, `OP-05-02`.

## decision-memory-outcomes — learning extension

- Spec: `specs/decision-memory-outcomes/spec.md`
- Task group: 8 and 12
- Proposed proof: executed integration/failure tests with durable state and exact external readback; fixtures alone do not prove deployed behavior.

- **MO-05 — Learning is governed improvement:** `MO-05-01`, `MO-05-02`.

## Critical release matrix

- Minimal profile with Cosmos/Doctor/custom model hosting/render services absent: operate and create durable action receipts through the supported minimal backend.
- Simple plus stricter security; Governed plus observe-only: independent controls remain independent.
- Unknown key/range, dependency cycle, organization-policy conflict and unsupported runtime limit: reject before apply.
- Repeat bootstrap and handwritten instruction conflict: stable managed output; no clobbering or silent permission expansion.
- Enable/disable a module during accepted work: stop new dispatch, retain observation/reconciliation, expose actual cancellation result.
- Missing/reordered/duplicated webhook; API rate limit; accepted write with lost response: no duplicate repair or healthy-empty lie.
- Sandbox history proposed for production; changed head/base/policy: incompatible authority/precedent cannot transfer.
- High-confidence prohibited recommendation; poisoned repo/log/memory instruction: no authorization bypass.
- Agent modifies verifier/publisher/workflow instead of fixing code: independent governance review required by policy.
- Created PR without tests; merged PR without deployment/retest; logging-only Doctor mutation: no applied/verified claim.
- iframe approval message; out-of-scope selection; tour completion: no privileged action or scope leak.
- Every graph view/theme and list equivalent: same evidence, readable arrows, keyboard/touch, no fabricated flow.
- Provider unexecuted or billing unavailable: not measured, not zero/perfect.

## Whole-lifecycle acceptance additions

- Plain-language request with missing product/data decisions: ask or stage explicit assumptions; do not dispatch unattended work before approved intent.
- Greenfield project plus existing pipeline: generate linked specs/tests/backlog/development/operations without replacing functioning adopter CI.
- Shared-versus-per-app resource plan: named identities, ownership, network/data/retention, readiness and real cost categories; no invented estimates or silent provisioning.
- Generated files without CI/preview/monitoring proof: not full-lifecycle ready. Narrow profiles retain their explicit narrower readiness scope.
- Approved backlog ends, blocks or changes mid-task: wait/escalate/revalidate; no infinite feature invention or protected-test weakening.
- Application down or incident storm: external detection and bounded correlated investigation, not self-report-only or duplicate repairs.
- Dependency outage and uncertain diagnosis: no forced code patch or fabricated root cause.
- Qualifying automatic release, human-required repair and proposal-only: prove each distinct policy outcome in an approved target; first integration proof remains human-merged.
- Successful deploy with failing/unknown original-symptom retest: unresolved; exercise authorized recovery or escalation.
- Later reversal or proposed instruction improvement: preserve negative evidence; reviewed knowledge/precedent update, no silent weight training or authority expansion.

## Evidence record for each executed proof

Record requirement/scenario, config/profile/template/policy versions, commit/build, target scope, actor, expected refusal or success, actual result, external IDs/readback, limitations and timestamp. Preserve raw failures. A screenshot alone cannot prove backend authorization; a backend unit test alone cannot prove operator usability. Privacy/redaction applies to all evidence artifacts.

## Exit criteria by milestone

M0: owning-change contracts, profile resolver/schema and protocol reviewed. M1: live read-only evidence and safe UI/graphs; no write claim. M2: complete bounded repair and original-task test-target verification including failure cases. M3: independently demonstrated limited admission with explicit policy approval. M4: separately approved operational/multi-repo extension. Passing any milestone is not universal production certification.
