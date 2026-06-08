# Proposal: Context-aware AgentAssistant in ledger-insights-ui

> **Status:** SHIPPED, backfill
> **Authors:** Idan Shimon
> **Date:** 2026-06-08
> **Capabilities touched:** agent-assistant (new), telemetry
> **Depends on:** add-ledger-insights-ui-deploy (the dashboard runtime), master-v07-four-plane-architecture

## Note on retroactive filing

This is a backfill. The implementation already shipped in `apps/ledger-insights-ui/src/lib/assist/replies.ts` (~600 lines) and the `useAssistantContext` hook in `apps/ledger-insights-ui/src/lib/assist/context.tsx`. The OpenSpec change is filed after the fact to record the contract the code now meets, fix the silent gap that v0.7 left in the spec tree (no capability called `agent-assistant` existed), and gate future work (live-mode LLM endpoint, multi-turn memory) against a written baseline. Tasks are checked off because the code is in `main`. Reviewers should validate the spec against the shipped behaviour, not against an unbuilt design.

## Why

The floating Ask-the-agent button (⌘K Sparkles, slide-over panel at `src/components/domain/assistant-panel.tsx`) sits on every page of the v0.7 ledger-insights-ui dashboard. Until this change it carried a `kind` label per page (13 kinds: dashboard, runs-list, run-detail, run-resolver-gate, decisions, telemetry, reports, bundles, agents-list, agent-edit, prompts-list, prompt-edit, phi-classifier, changes-list) but the reply engine matched user input against a static keyword table and returned pre-canned text. It never read the actual run state, decisions list, pipeline stage, or portfolio rollup. Customer feedback after the first demo: "not really smart and aware of the pipeline state". This change replaces the keyword-matched composer with a context-aware reply engine that calls `gatherContext(viewing)` at every turn, reads the demo store live, and composes replies grounded in what is literally on the screen.

## What Changes

- `src/lib/assist/replies.ts` rewritten end-to-end. Adds `gatherContext(viewing: AssistContext): GatheredContext`, an intent classifier (`classifyIntent(prompt)`), per-context-kind composers (run-focused, portfolio-focused, resource-editor), and a state-reactive `suggestionsFor(context)` helper.
- `gatherContext()` reads from `src/lib/demo/index.ts` via `getDemoRun`, `listDemoRuns`, `listDemoLedgerEntries`, `getDemoArtifacts`. No new client store. Demo mode stays deterministic, no LLM calls.
- `useAssistantContext({kind, id?, label?, payload?})` hook signature is unchanged. Every page already declares its context via this hook; this change does not touch the call sites, only what `replies.ts` does with the context.
- Suggestions become state-reactive. On a run that is awaiting gate, the chip surfaces "Why is this awaiting gate?" instead of a generic "Tell me about this run". On the dashboard with N awaiting-gate runs, a chip surfaces the count.
- Citations become real. Every cited `bundle_ref` is pulled from an actual ledger entry returned by `listDemoLedgerEntries(run_id)`. No more invented citations.
- Production parity. The shape of `GatheredContext` is the shape that live mode (future `add-orchestrator-chat-endpoint` change) will serialize as a system-prompt block to the orchestrator chat agent. The demo composer is the deterministic stand-in for the LLM call.

## Capabilities

### New Capabilities

- `agent-assistant`: in-UI conversational interface that reads the live ledger, run, and portfolio state at every turn and replies with grounded answers anchored to real bundle_refs.

### Modified Capabilities

(none in this change)

## Impact

- `apps/ledger-insights-ui/src/lib/assist/replies.ts`, rewritten, ~600 lines.
- `apps/ledger-insights-ui/src/lib/assist/context.tsx`, unchanged signature, no edits.
- `apps/ledger-insights-ui/src/components/domain/assistant-panel.tsx`, unchanged. Still calls `pickReply(context, userPrompt)`.
- All page-level `useAssistantContext({...})` declarations across the 13 surfaces, unchanged.
- No backend change. No Bicep change. No new env var. No new dependency.
- Token / latency cost: zero in demo mode (no network). In future live mode the `GatheredContext` JSON for a run-focused turn is bounded at roughly 4 KB worst case (see design.md size analysis).

## Safety Impact

- Demo mode means no LLM calls and no network; the composer is deterministic and runs entirely in the browser. PHI exposure surface is unchanged from the dashboard's existing read paths.
- Live mode (future change) will send `GatheredContext` as a system-prompt block to the orchestrator chat agent. The fields that ship today are `bundle_refs`, costs, model names, status codes, run ids, stage names, and portfolio counts. These are PHI-safe by construction.
- Decision text in run-focused contexts may include the `rationale` field, which can carry free text written by an upstream agent. Production live-mode integration MUST run `rationale` through the PHI classifier before injecting it into a prompt. This is captured as a non-goal here and a hard gate on the future `add-orchestrator-chat-endpoint` change.
- Telemetry: the existing App Insights wiring (per `add-ledger-insights-ui-deploy` REQ) does not capture request bodies or query strings. User prompt text never leaves the browser in demo mode. No new telemetry surface is added.

## Non-goals

- Not adding a real LLM endpoint. Live-mode integration is a separate change, `add-orchestrator-chat-endpoint`, which should exist or be filed before live mode ships.
- Not redesigning the slide-over UI shell. `assistant-panel.tsx` is unchanged.
- Not adding multi-turn memory. Each turn re-gathers fresh context, by design (see design.md decision 1).
- Not changing the set of 13 context kinds. Adding kinds is a forward change.
- Not adding a PHI classifier gate inside `replies.ts`. That gate belongs at the LLM boundary in live mode and is the hard gate on `add-orchestrator-chat-endpoint`.
