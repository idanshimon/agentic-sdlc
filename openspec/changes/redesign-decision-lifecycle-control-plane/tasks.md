# Tasks: redesign-decision-lifecycle-control-plane

## 0. Grounding and specification

- [x] Inspect current repo, live runtime UI, GitHub agentic surfaces, current GitHub docs, and Customer Hub workflow/gate discussions.
- [x] Record KEEP / SWAP / ADD / OUT in the proposal.
- [x] Author proposal, design, tasks, and spec delta.
- [x] Validate with `openspec validate redesign-decision-lifecycle-control-plane --strict`.

## 1. Live artifact contract

- [x] RED: add pure projection tests for architecture, test plan, implementation, generated tests, decisions document, delivery references, newest-event-wins, and empty input.
- [x] GREEN: implement the event artifact projector.
- [x] Update `RunArtifactsPanel` to use projected live artifacts and render implementation/tests separately.
- [x] Verify no emitted artifact is labeled pending.

## 2. Terminal outcome UX

- [x] RED: add pure classifier tests for failed event, failed-without-event, review-policy failure, and delivery-not-opened.
- [x] GREEN: implement terminal outcome classification.
- [x] Add a prominent run outcome panel above stage progress and diagnostics.
- [x] Provide an explicit next action: inspect blocker, review policy evidence, retry/replay, or open delivery configuration.

## 3. Run-scoped Decisions registry

- [x] RED: add tests for Decisions query parsing and serialization.
- [x] GREEN: implement URL-backed filter helpers.
- [x] Pass `run` query scope to `useDecisions`.
- [x] Initialize all table filters from URL state without weakening server-side team scope.
- [x] Add `View decisions` deep link on run detail.

## 4. Delivery quality fix

- [x] RED: add an orchestrator test proving `tests/test_main.py` receives `test_code`, not markdown `test_plan`.
- [x] GREEN: update delivery artifact extraction and file mapping.
- [x] Preserve legacy safety: runs without `test_code` omit the executable test file rather than misrepresent markdown as Python.

## 5. Verification

- [x] Run targeted UI tests.
- [x] Run full UI Vitest suite (99 passing).
- [x] Run `pnpm tsc --noEmit`.
- [x] Run production UI build.
- [x] Run targeted orchestrator delivery test.
- [x] Run full orchestrator suite (356 passing; 2 pre-existing warnings).
- [x] Re-run strict OpenSpec validation.
- [x] Browser-verify run-scoped Decisions: scope renders, degraded read is explicit, and no-data is not misreported. Populated failed-run visual verification still requires reachable live services.

## 6. Plain-language decision activity feed

- [x] Replace the phase-chip lifecycle grid with a human-readable activity feed keyed off ledger entries.
- [x] Classify each entry as agent decision, human decision, autopilot reuse, teaching signal (feedback/flag/pause), delivery, or review-loop convergence.
- [x] Render one plain-language sentence per row (who, what, when) and a learning-event count.
- [x] Deep-link each row to `#decision-<id>`; expand + scroll the table row on hash focus.
- [x] RED/GREEN: unit-test the classifier and sentence builder against representative ledger shapes.
- [x] Verify locally against live ledger data before deploy.

## Follow-on, not required for the first slice

- [ ] Derived lifecycle API joining ledger/run/GitHub evidence.
- [ ] Shared decision workbench used at runtime and in registry detail.
- [ ] Attention queue with owner, deadline, risk, and autonomy posture.
- [ ] Stage rail expandable into inputs, prompt/agent/model, outputs, checks, cost, and GitHub evidence.
- [ ] Saved enterprise views and cross-repository posture.
