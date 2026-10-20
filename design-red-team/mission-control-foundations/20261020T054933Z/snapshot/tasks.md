# Implementation tasks

Status: DRAFT. All tasks below are future implementation/proof, not accomplished by writing this specification. Prior source inspection and local contract-test evidence are recorded in the project exploration docs. Milestones and owning-change dependencies are defined in design.md. Start with baseline + configuration contracts + one read-only repository; do not build all modules in parallel.

## 1. Baseline and owning-spec reconciliation

- [ ] 1.1 Reconcile source and task status in GitHub-substrate, target resolution, integrations, decision-workbench and Doctor changes; retain existing requirements rather than duplicate their implementation.
- [ ] 1.2 Choose the first approved test repo/application and classify the initial observe-only and repair target scopes; record KEEP/SWAP/ADD/OUT. [IA-01, AX-01]
- [ ] 1.3 Trace existing identity, ledger/evidence models, adapters, UI routes and graph components; record reuse versus net-new artifacts. [MC-02, GV-01]
- [ ] 1.4 Validate scope, owning-change cross-references and the complete requirement/scenario acceptance matrix before implementation. [IA-01]

## 2. Profile resolver and bootstrap contract

- [ ] 2.1 Specify versioned manifest/module/profile schemas and independent capability/authority/governance/model/budget/presentation axes; select concrete fields only after current loader discovery. [FC-01, FC-02]
- [ ] 2.2 Implement deterministic effective-config resolution, policy provenance/digest and invalid-key/range/conflict/dependency-cycle tests without auto-granting permissions. [FC-02, FC-03, FC-04]
- [ ] 2.3 Implement candidate Simple/Team/Governed presets plus organization-authored presets; ensure stricter security does not force greater autonomy or all infrastructure. [FC-01, FC-07]
- [ ] 2.4 Define the supported minimum receipt backend and preserve current mandatory requirements through explicit owning-spec adaptations; prove the minimal deployment with optional services absent. [FC-03, FC-07]
- [ ] 2.5 Build inspect/dry-run/staged generation from pinned templates for enabled instructions, agents, tools/MCP and workflows; preserve unmanaged content and produce an explicit diff. [FC-05]
- [ ] 2.6 Implement authorized apply/readback/readiness and configuration deactivation/drain paths; record config digests and incompatible-authority invalidation. [FC-06]
- [ ] 2.7 Validate config-only add/edit/disable/rename cases, repeat bootstrap idempotency, conflicting ownership and unsupported runtime knobs. [FC-01, FC-02, FC-03, FC-04, FC-05, FC-06, FC-07]

## 3. Scoped GitHub integration

- [ ] 3.1 Verify current product/enterprise capabilities and select the actual agent route and scoped connection identity; document native/bridged/unavailable/unverified limits. [GH-01]
- [ ] 3.2 Implement authenticated ingestion, stable event deduplication and source/commit/freshness normalization with rate-limit and out-of-order handling. [GH-02]
- [ ] 3.3 Implement backfill/reconciliation and authorized write adapters with ambiguous-completion readback. [GH-02, GH-03]
- [ ] 3.4 Verify revocation, least-privilege boundaries and actual required-check/publisher/bypass settings in the approved test repo without claiming local tests install them. [GH-01, GH-04]

## 4. Decision evidence and optional judgment routing

- [ ] 4.1 Join existing decision/work/session/action/PR/check/deployment identities and keep observed facts, suspected causes, chosen options and missing evidence distinct. [MC-02, MO-01, MO-02]
- [ ] 4.2 Define optional typed-model provider/question/answer/evidence/error/abstention contracts, separate explanation attribution and supported disabled-mode alternatives. [DM-01, DM-02]
- [ ] 4.3 Define budgeted open-ended investigation independent of known detectors, with an explicit off state and unconfirmed-concern handling. [DM-03]
- [ ] 4.4 Create held-out SDLC evaluation cases for rules, typed models and a generative baseline; preserve false-permission, unknown, error, coverage, timing and cost outcomes. No inference/provisioning without scope. [DM-04]
- [ ] 4.5 Validate authoritative-fact precedence, no confidence-based authorization and no sole self-judge. [DM-01, DM-02, DM-03, DM-04]

## 5. Target-aware authority and bounded execution

- [ ] 5.1 Close early target/risk/environment resolution and explicit precedent compatibility in owning delivery/substrate changes before cross-target automation. [AX-01]
- [ ] 5.2 Wire per-action envelopes and enforce supported retry/time/concurrency/spend/tool/data/egress limits using the effective config. [AX-02, FC-04]
- [ ] 5.3 Integrate existing lifecycle/idempotency/quarantine/merge-authorization decision functions with real dispatch, durable state and a running reconciler; demonstrate exact-head/policy invalidation. [AX-03, GH-03, GH-04]
- [ ] 5.4 Implement separate dispatch pause, revocation, cancellation request/acknowledgment and authorized compensation paths. [AX-04, FC-06]
- [ ] 5.5 Validate modified-verifier/workflow/publisher scenarios plus duplicate events, lost responses, target changes, budget exhaustion and independently trusted admission. [AX-01, AX-02, AX-03, AX-04, AX-05]

## 6. Mission Control operating workspace

- [ ] 6.1 Extend existing UI routes/theme with an attention-ranked queue, ownership/blocking reasons and truthful status/coverage. [MC-01]
- [ ] 6.2 Mount a shared decision workbench and command preview using authenticated server contracts and exact source links. [MC-02, MC-03]
- [ ] 6.3 Add scoped URL state, keyboard/touch access, list equivalents and reconnect recovery without duplicate command dispatch. [MC-04]
- [ ] 6.4 Browser-verify desktop/narrow screens, older-blocked-first ranking, actual filtered destinations, conflict handling and zero writes/inference during tours/selection. [MC-01, MC-02, MC-03, MC-04]

## 7. Graphs and Content Creator authoring

- [ ] 7.1 Define one evidence projection with source/version/status/freshness for architecture, execution and decision lineage; align it with the list/workbench. [GV-01]
- [ ] 7.2 Author and render a pinned Archify walkthrough via Content Creator, keeping generated presentation artifacts optional and separate from live authority. [GV-02]
- [ ] 7.3 Integrate appropriate existing live graph components, explicit Explore/Back/breadcrumbs/deep links and theme/reduced-motion behavior. [GV-03]
- [ ] 7.4 Validate sandbox/CSP/message-origin restrictions and prove generated showcase controls cannot approve actions or access credentials. [GV-04]
- [ ] 7.5 Render every delivered view/theme at actual desktop/mobile sizes, exercise interactions and inspect readable load-bearing arrows; preserve evidence and label illustrative traces. [GV-01, GV-02, GV-03, GV-04]

## 8. Memory outcomes and governed improvement

- [ ] 8.1 Implement scoped optional recall and precedent eligibility without altering immutable receipts; define sensitive-data retention/redaction/export rules. [MO-01, MO-04]
- [ ] 8.2 Ingest independent tests/retest/deployment/reversal/human-correction observations; keep agreement and operational correctness separate. [MO-02]
- [ ] 8.3 Implement reviewed promotion/demotion proposals with compatibility/sample checks and no self-issued authority or duplicated graduation evidence. [MO-03]
- [ ] 8.4 Validate stale/expired evidence, disconnected-repo export, unmeasured metrics and recall poisoning scenarios. [MO-01, MO-02, MO-03, MO-04]

## 9. First adoption proof and operational readiness

- [ ] 9.1 Run observe-only M1 against actual authorized repository evidence; prove absent optional modules do not block operation. [IA-01, FC-03, FC-07]
- [ ] 9.2 Run M2 real failure-to-fix-to-test-target-retest with human merge, plus explicit stale-head, duplicate-event, hard-human and target-change cases. [IA-02]
- [ ] 9.3 Record task resolution, human intervention, bounded resource use, verification coverage and rollback/revocation readiness; no permission graduation from the demo alone. [IA-03]
- [ ] 9.4 Publish operator/bootstrap/exit runbooks and named operational ownership; document pending M3/M4 rather than declaring production self-healing. [IA-04]
- [ ] 9.5 Validate with OpenSpec strict, relevant local suites, production-build browser checks and exact external readback; report local/live/unproven/blocked separately. [IA-01, IA-02, IA-03, IA-04]

## 10. Project intent bootstrap infrastructure and readiness

- [ ] 10.1 Normalize plain-language request into reviewed goals/non-goals, users/data/targets, milestone acceptance and bounded authority; preserve narrower selected scope. [PB-01]
- [ ] 10.2 Generate/adapt linked application specs/scaffold, backlog, tests, agent/workflow configuration and enabled monitoring/runbooks without clobbering existing artifacts. [PB-02]
- [ ] 10.3 Resolve shared/per-app/optional infrastructure, identities, permissions, data/network/retention, owner, usage/cost categories and exit actions; show reused/new/missing resources before authorized apply. [PB-03]
- [ ] 10.4 Implement durable setup/probe/handoff states and ambiguous creation reconciliation; demonstrate CI/review, preview, acceptance and external health plus signal-to-incident probe for enabled repair. [PB-04, PB-05]
- [ ] 10.5 Validate interrupted setup, generated-only false-ready refusal, absent monitoring identity, disabled modules and the scoped readiness report. [PB-01, PB-02, PB-03, PB-04, PB-05]

## 11. Goal driven continued development

- [ ] 11.1 Build an enabled controller over approved task/dependency/priority/target state with claims, concurrency and budgets; do not implement a second generic agent runtime. [GD-01, GD-03]
- [ ] 11.2 Wire requirement/task/decision/PR/check/release/acceptance lineage and protect independent acceptance criteria from author changes. [GD-02]
- [ ] 11.3 Implement product-question/scope-change escalation, versioned goal updates, separate suggested backlog and no-eligible-task waiting/completion. [GD-01, GD-04]
- [ ] 11.4 Validate continuation after restart, duplicated dispatch, failed task ceiling, changed goal and exhausted approved work. [GD-01, GD-02, GD-03, GD-04]

## 12. Post deployment incident repair and recovery

- [ ] 12.1 Connect approved external health/errors to authenticated redacted app/environment/build/symptom evidence; correlate duplicates/storms and prevent recursive repair loops. [OP-01]
- [ ] 12.2 Route code/configuration/runbook/dependency/flake/unknown cases with reproduction and appropriate independent tests; retain uncertain diagnosis explicitly. [OP-02]
- [ ] 12.3 Implement proposed-only, qualifying automatic release and human-required paths as separately selected current envelopes with trusted exact-state admission and rollout safeguards. [OP-03]
- [ ] 12.4 Verify original-symptom recovery and health observation window on the deployed build; implement tested scoped rollback/compensation or named escalation. [OP-04, OP-05]
- [ ] 12.5 Hand off independent incident outcomes to scoped knowledge/precedent and reviewable regression/runbook/instruction improvements; preserve reversions and prohibit self-granted authority. [OP-05, MO-05]
- [ ] 12.6 Validate app-down external detection, incident storm, dependency outage, unreproducible error, sensitive repair, no production authority, failed canary and missing/failed retest. [OP-01, OP-02, OP-03, OP-04, OP-05, MO-05]

## Rollback and release boundary

No implementation proceeds from this draft without scope approval. Each slice needs a rollback flag, action/evidence compatibility, actual absence tests for disabled modules and an in-flight-work disposition. Required checks remain independent of dashboard availability. No secret, cloud resource, model deployment, workflow or remote repository setting is changed by authoring this proposal.
