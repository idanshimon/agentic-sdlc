# Tasks: add-context-aware-agent-assistant

> Backfill. All groups marked done because the implementation shipped in `apps/ledger-insights-ui/src/lib/assist/replies.ts` and `apps/ledger-insights-ui/src/lib/assist/context.tsx`. Reviewers should validate against the shipped code.

## 1. Context API + types

- [x] 1.1 Define `AssistContext` discriminated union over the 13 `kind` values (`dashboard`, `runs-list`, `run-detail`, `run-resolver-gate`, `decisions`, `telemetry`, `reports`, `bundles`, `agents-list`, `agent-edit`, `prompts-list`, `prompt-edit`, `phi-classifier`, `changes-list`) in `src/lib/assist/context.tsx`.
- [x] 1.2 Expose `useAssistantContext({kind, id?, label?, payload?})` hook with backward-compatible signature (existing call sites do not change).
- [x] 1.3 Define `ApplyAction` type for state-changing chip outputs (`approve_gate`, `replay`, `open_pr`, `view_artifact`, `open_question`).
- [x] 1.4 Define `AgentReply` shape: `{ text, reasoning?, actions: ApplyAction[], citations?: { label, ref }[] }`.
- [x] 1.5 Wire `assistant-panel.tsx` to call `pickReply(context, userPrompt)` and render `AgentReply` (no signature change to the panel).

## 2. gatherContext() reader

- [x] 2.1 Define `GatheredContext` type: `{ viewing, run?, decisions[], portfolio?, resource? }`.
- [x] 2.2 Implement `gatherContext(viewing: AssistContext): GatheredContext`. Called fresh on every turn, no caching.
- [x] 2.3 For `run-detail` and `run-resolver-gate`: read `getDemoRun(id)` and slice fields `{id, status, stage, awaiting_gate, completed_stages, has_artifacts, pr_url}` into `GatheredContext.run`.
- [x] 2.4 For `run-detail` and `run-resolver-gate`: read `listDemoLedgerEntries({run_id: id})`, take the most recent 20, project into `GatheredContext.decisions[]` with full `bundle_refs` arrays.
- [x] 2.5 For `dashboard`, `runs-list`, `decisions`, `telemetry`, `reports`: read `listDemoRuns()` and `listDemoLedgerEntries()`; aggregate `{total_runs, by_status, awaiting_gate_count, total_cost_usd, total_decisions, bundle_citation_density}` into `GatheredContext.portfolio`.
- [x] 2.6 For resource-editor kinds (`agents-list`, `agent-edit`, `prompts-list`, `prompt-edit`, `phi-classifier`): copy `payload` from `viewing` into `GatheredContext.resource` and skip the demo store reads.
- [x] 2.7 For `bundles` and `changes-list`: portfolio rollup only.

## 3. Intent detection

- [x] 3.1 Implement `classifyIntent(prompt: string): Intent` with keyword-weighted rules. Output set: `summarize`, `why_blocked`, `next_action`, `cite_decision`, `cost_breakdown`, `apply_change`, `open_question`.
- [x] 3.2 `open_question` fallback ALWAYS fires when no rule scores above threshold.
- [x] 3.3 Unit-level smoke check: every intent has at least one canonical phrasing the rule set classifies correctly.

## 4. Per-context composers

- [x] 4.1 Implement `composeRunReply(gathered, intent, prompt)` for `run-detail` and `run-resolver-gate`. Cites `bundle_refs` from `gathered.decisions[]`.
- [x] 4.2 Implement `composePortfolioReply(gathered, intent, prompt)` for portfolio kinds. References `gathered.portfolio.*` counts directly in the reply text.
- [x] 4.3 Implement `composeResourceReply(gathered, intent, prompt)` for editor kinds. Reads from `gathered.resource` only, never invents portfolio numbers.
- [x] 4.4 All composers route `open_question` intent to a state-grounded summary that surfaces the most-relevant fields plus the suggestion chips.

## 5. Suggestions wired to state

- [x] 5.1 Implement `suggestionsFor(context: AssistContext): string[]` that calls `gatherContext` and returns chips reactive to the current state.
- [x] 5.2 Run kinds: when `gathered.run.awaiting_gate === true`, the chip set MUST include a chip whose text mentions the gate (e.g. "Why is this awaiting gate?").
- [x] 5.3 Portfolio kinds: when `gathered.portfolio.awaiting_gate_count > 0`, the chip set MUST include a chip that surfaces the count (e.g. "3 runs awaiting gate, show me which").
- [x] 5.4 `assistant-panel.tsx` renders `suggestionsFor(context)` below the prompt input.

## 6. Validation

- [x] 6.1 `pnpm tsc --noEmit` clean for `apps/ledger-insights-ui/`.
- [x] 6.2 `pnpm lint` clean for `apps/ledger-insights-ui/`.
- [x] 6.3 Manual click-through: `/runs/[id]` with a run awaiting gate, open ⌘K, confirm chip strip mentions the gate; reply text cites at least one real `bundle_ref` from the run's ledger entries.
- [x] 6.4 Manual click-through: `/` (dashboard) with N>0 awaiting-gate runs, open ⌘K, confirm chip strip surfaces the count.
- [x] 6.5 Confirm zero network requests fire from `replies.ts` in demo mode (browser devtools, Network tab filtered to the assistant slide-over).
- [x] 6.6 `openspec validate add-context-aware-agent-assistant --strict` clean.
