# Working instructions for this foundation change

These instructions are subordinate to repository `AGENTS.md`, applicable pinned standards bundles and authorized project scope. They guide work on this draft; they do not grant permission to implement, publish, provision or change repository settings.

## Read before extending or implementing

1. Read `proposal.md`, `design.md`, `tasks.md`, `acceptance.md` and the capability specs affected by the task.
2. Inspect current source and the adjacent owning changes in design.md. Existing task counts and historical docs are not proof of implementation or deployment.
3. Record KEEP / SWAP / ADD / OUT. Build one acceptance-tested slice before expanding scope.

## Design and bootstrap discipline

- Design the minimum useful profile first. Do not make optional enterprise infrastructure a hidden dependency.
- Keep feature activation, action authority, security/governance, model routing, thresholds and UI preferences as separate controls.
- Require one resolved, versioned configuration contract with per-value provenance. UI, worker, server validation and generated instructions must agree on that effective configuration.
- Declare module dependencies, conflicts, permissions, resource footprint and supported disabled behavior. Reject unsupported combinations rather than silently falling back to a more privileged route.
- Generate only the selected modules' instruction/tool/agent/workflow artifacts from pinned templates. Stage and diff them before authorized apply. Preserve unmanaged instructions and existing CI.
- Never treat generated prompts, hidden buttons, profile names, model confidence or an authored diagram as enforcement.
- Keep required action receipts and identity isolation in the minimum foundation; make rich ledger hosting, custom decision models, Doctor, cross-repo analytics and presentation renderers optional where the selected requirements permit.
- Preserve existing mandatory requirements until an explicit owning-spec/policy change adapts them. A new Simple preset cannot silently repeal a pinned bundle.
- Expose units, ranges, ownership and failure semantics for thresholds. Mark unsupported/advisory limits honestly; never create inert knobs that look enforced.
- Disabling a module must stop new work, reconcile accepted work and retire owned schedules/credentials through a reviewed path. It must not erase audit evidence or imply unsupported cancellation.

## Model, graph and evidence discipline

- Prefer authoritative structured checks for facts and authorization; use typed models for bounded judgments and generative agents for investigation. Evaluate each separately.
- Resolve target scope before autonomy. Reuse precedent only under explicit compatibility policy. Human agreement is not measured production correctness.
- Keep source-grounded Archify explainers separate from live evidence projections and privileged commands. Reuse the app's theme/components and existing graph contracts.
- Treat Content Creator's synthetic mission-control showcase as a visual reference, not an authenticated production control surface.
- Preserve meaningful choices, presented alternatives, evidence references and concise attributed explanations; never fabricate internal model reasoning or execution receipts.
- Report proposed, authorized, dispatched, observed and independently verified states separately.

## Whole-lifecycle delivery contract

- Read `bootstrap-journey.md`. Bootstrap covers application/success criteria, continued development and post-deployment repair together; a generated scaffold is not completion.
- Capture approved goals, non-goals, acceptance criteria, task dependencies and action/target authority before enabling unattended development.
- Separate shared foundation infrastructure from each application's hosting/data/monitoring; show resources, owner, permissions and cost categories before apply.
- Prove bootstrap using executed CI, preview deployment, external health and an acceptance test. Mark disabled modules not enabled, pending infrastructure not ready and skipped checks not verified.
- Continue only eligible work in the approved backlog. Unknown product decisions, contradictory requirements, budgets and blockers pause or escalate; do not invent new goals.
- Production errors can trigger code repair, a permitted operational action or escalation. Auto-merge/auto-release requires explicit qualifying authority; proposal-only is a valid configured mode, not the only supported destination.
- Record intent, actual execution and independent outcome separately. Learning means governed knowledge/precedent/test/runbook improvement by default, not silent weight training or self-granted authority.

## App-owned OpenSpec and foundation acceptance

- Foundation tests and generated app tests are separate release obligations. App success cannot qualify an untested foundation.
- Bootstrap each app's own OpenSpec root/toolchain/workflow; preserve an existing app process and keep app requirements out of the foundation's own spec namespace.
- Link approved change/spec revision → requirement/scenario → task → tests → attempt/decision → PR/commit/build → acceptance. Revalidate affected evidence when the contract changes.
- Treat acceptance-authority creation and changes as governed artifacts. Useful agent-generated tests may count after applicable independent validation; do not let their author alone define success.
- Require applicable proposal/design/spec/tasks and test-first work for material changes. Use the explicit lightweight regression path for fixes restoring existing behavior; material behavior/security changes need a spec delta.
- Synchronize accepted app deltas into canonical specs and archive through the pinned supported process after applicable acceptance; verify readback and preserve stable evidence links. Do not infer production deployment or recovery from archive.
- Use the milestone gates in acceptance.md; parser success, zero discovered tests, skipped required checks and self-reported completion do not satisfy them.

## Required verification

- Add contract/failure tests before implementing producers and commands.
- Test the minimum profile with optional services absent; exercise config-only enable/disable and invalid dependency cases.
- Exercise duplicate delivery, ambiguous external completion, stale head/policy, target change, revocation and conflicting operators.
- Render and inspect every delivered graph view/theme; test keyboard, touch, reduced motion and a list equivalent.
- Run OpenSpec strict validation and the affected real suites. Verify external effects by exact-target readback when execution is authorized.
- Distinguish locally tested, live verified, implemented-but-unproven and blocked. A structurally valid specification is a draft contract, not a working dashboard.
