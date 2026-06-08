# Design: Context-aware AgentAssistant

> Companion to `proposal.md`. This doc covers context, goals, non-goals, decisions, and risks for the reply-engine rewrite shipped in `apps/ledger-insights-ui/src/lib/assist/replies.ts`.

## Context

The ledger-insights-ui dashboard ships a universal in-UI assistant: a floating ⌘K Sparkles button on every page that opens a slide-over panel (`src/components/domain/assistant-panel.tsx`). Every page declares its context via `useAssistantContext({kind, id?, label?, payload?})` from `src/lib/assist/context.tsx`. There are 13 context kinds today:

- Portfolio kinds: `dashboard`, `runs-list`, `decisions`, `telemetry`, `reports`, `bundles`, `changes-list`
- Run kinds: `run-detail`, `run-resolver-gate`
- Resource-editor kinds: `agents-list`, `agent-edit`, `prompts-list`, `prompt-edit`, `phi-classifier`

Before this change the panel called `pickReply(context, userPrompt)` and the implementation matched `userPrompt` against a per-kind keyword table that returned static text. The `id` and `payload` fields on the context were carried through but never read.

After this change `pickReply` calls `gatherContext(viewing: AssistContext)` first, then routes to a per-kind composer that reads the gathered state and synthesizes a reply with real citations and state-reactive suggestion chips.

`gatherContext` reads from three sources, all in-process in demo mode:

- The demo run store: `getDemoRun(id)`, `listDemoRuns()` from `src/lib/demo/index.ts`.
- The demo ledger store: `listDemoLedgerEntries({run_id?})` from the same module.
- The demo artifact store: `getDemoArtifacts(run_id)` from the same module.

There is no versioning store read in demo mode today; resource-editor kinds gather only the editor target's `payload` (the version snapshot the page already has in memory) and do not read the demo store. This is intentional and recorded as decision 4 below.

The portfolio rollup is computed in-line inside `gatherContext` on every turn from `listDemoRuns()` and `listDemoLedgerEntries()`. With the demo dataset capped at roughly 20 runs and 200 ledger entries this rollup costs under 1 ms in the browser.

## Goals

1. Replies grounded in real data. A run-detail reply about "what is blocking this run" cites the actual `awaiting_gate` flag, the actual stage name, and the actual ledger entry that wrote the gate decision.
2. Suggestions react to state. The chip strip below the input surfaces prompts that are relevant to the current state (e.g. "Why is this awaiting gate?" only appears when `run.awaiting_gate === true`).
3. Real citations. Every `citations[]` entry on an `AgentReply` is a real `bundle_ref` pulled from a real `LedgerEntry`. No invented refs.
4. Production parity. The `GatheredContext` shape sent to the live-mode LLM in `add-orchestrator-chat-endpoint` (future) is byte-for-byte the shape composed in demo mode. Demo composer is the deterministic stand-in.
5. No client-side LLM calls in demo mode. Demo mode is zero-network for the assistant by hard rule (lets the public Container App stay PHI-safe-by-construction per the deploy spec).

## Non-goals

1. Multi-turn conversation state. Each turn re-runs `gatherContext` from scratch. There is no chat history accumulator. If the user asks a follow-up the assistant treats it as a fresh turn against fresh context. Rationale: state freshness beats coherence for a state-aware demo, and multi-turn memory introduces a stale-state class of bug we explicitly do not want to ship before live mode.
2. ML-based intent classification. Intent classification is keyword-weighted (see decision 2).
3. A backend chat endpoint. Live mode is a follow-up change.
4. Editing the 13 context kinds. Adding a new kind is a forward change.
5. PHI classifier inside `replies.ts`. That gate lives at the LLM boundary in live mode.

## Decisions

### Decision 1: Gather at every turn, do not cache

**Choice:** call `gatherContext(viewing)` on every user turn. No memoization, no React state-pinned snapshot.

**Why:** the demo store mutates between turns (user advances a run, approves a gate, edits a prompt). A cached snapshot would surface stale state and the customer feedback that prompted this change ("not really smart and aware of the pipeline state") would survive the rewrite. The cost of re-gathering is sub-millisecond against the demo dataset and bounded in live mode by the future endpoint's read budget.

**Trade-off accepted:** in live mode each turn re-reads from the orchestrator's read API. The endpoint contract is "context read is cheap" and is owned by `add-orchestrator-chat-endpoint`.

### Decision 2: Keyword-weighted intent classification, not ML

**Choice:** intent classification is a small set of regex-weighted keyword rules in `classifyIntent(prompt)`. Output is one of: `summarize`, `why_blocked`, `next_action`, `cite_decision`, `cost_breakdown`, `apply_change`, `open_question`.

**Why:** the universe of useful intents on this dashboard is small (under 10), the prompts are short, and keyword rules are debuggable in CI. An ML classifier is unnecessary at v0.7 scale and would introduce a model-version dependency we do not want before live mode.

**Trade-off accepted:** miss rate on novel phrasings. Mitigation: an `open_question` fallback ALWAYS fires; the composer for `open_question` returns a state-grounded summary plus the suggestion chips, so a missed intent still yields a useful reply.

### Decision 3: Read state from `src/lib/demo/index.ts` via the public functions, not the underlying store object

**Choice:** `gatherContext` calls `getDemoRun`, `listDemoRuns`, `listDemoLedgerEntries`, `getDemoArtifacts`. It does not import the underlying `demoStore` singleton.

**Why:** these four functions are the same shape the future live-mode endpoint will return (modulo the network boundary). Coupling to the public functions preserves production parity (goal 4) and means the `replies.ts` rewrite does not need to be touched again when live mode lands; only the import target swaps from `@/lib/demo` to `@/lib/orchestrator-client`.

**Trade-off accepted:** if the demo functions ever diverge from the live API shape, this file silently miscomposes. Mitigation: a single shared TypeScript type (`DemoRun`, `LedgerEntry`, `DemoArtifact`) that both demo and live mode produce.

### Decision 4: Resource-editor kinds gather only the editor payload, not the demo store

**Choice:** for `agent-edit`, `prompt-edit`, `phi-classifier`, `agents-list`, `prompts-list`, the composer reads `payload` (passed in via `useAssistantContext({payload: {...}})` from the editor page) and does NOT call `listDemoRuns` or `listDemoLedgerEntries`.

**Why:** the editor pages already hold the version snapshot in memory and the assistant on those pages is about the resource being edited, not the portfolio. Gathering portfolio state on those turns is wasted work and gives the composer ambient noise.

**Trade-off accepted:** an editor turn cannot answer cross-resource questions (e.g. "where else is this prompt referenced"). That is a forward feature, not a v0.7 contract.

## Risks

### Risk 1: GatheredContext can grow large for run kinds with many ledger entries

A run with 50 ledger entries has roughly 4 KB of `decisions[]` payload at the JSON level. In live mode this is the system-prompt context; at 50 runs of 50 entries each (the v1.0 ceiling) it stays under 200 KB total, but a single huge run can push the per-turn budget.

**Mitigation:** per-kind selectivity. The composer for run kinds slices `decisions` to the most recent 20 entries before serializing. Portfolio kinds aggregate counts only and never serialize per-entry detail.

### Risk 2: Intent miss rate on novel phrasings

Keyword classification will miss intent on phrasings the rule set does not anticipate.

**Mitigation:** `open_question` fallback ALWAYS exists and ALWAYS returns a state-grounded summary plus suggestion chips. A missed classification degrades to a useful reply, never to a pre-canned non-answer. Eval harness adds a misfire-rate dimension when it lands (tracked in `add-pipeline-eval-harness`).

### Risk 3: PHI leakage via the rationale field in live mode

`LedgerEntry.rationale` is free text written by upstream agents. In live mode, unfiltered `rationale` would be injected into a system prompt. If an upstream agent writes patient-identifying text into rationale, the assistant's prompt carries PHI to the LLM provider.

**Mitigation:** classifier gate at the LLM boundary, owned by the future `add-orchestrator-chat-endpoint` change. That change MUST run rationale through the PHI classifier before serializing the system-prompt block. Demo mode does not need this gate because demo mode never sends a network request.

### Risk 4: Production parity drift between demo composer and live LLM

If demo and live diverge on what they consider an answer to "why is this run blocked", the demo lulls the customer into expectations live mode will not meet.

**Mitigation:** the `GatheredContext` shape is the contract, not the prose of the reply. Live mode receives the same shape, the LLM composes the prose. The eval harness scores live-mode replies against the shape of the gathered state, not against demo prose.
