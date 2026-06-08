# Fix renderer-OOM crash from unbounded demo store growth

## Why

Operators clicking through several demo runs in one browser tab triggered
a Chrome "Aw Snap" renderer crash on `/runs/[runId]` and `/decisions`.
The crash had no JS exception in the console and no server-side fault.

Root cause: every page calls `useAssistantContext` which calls
`getSuggestions(context)` → `gatherContext()` → `listDemoRuns()` +
`listDemoLedgerEntries()`. Each of those does a full `JSON.parse` of the
entire `agentic-sdlc.demo.runs` localStorage key. With ~3 demo runs that
each carry 8+ events, ~9 ledger entries, plus payloads (architecture,
test plan, code, decisions.md), the store quickly grows to multi-MB.
Multiplying that parse cost by N pages × M renders/sec from the React
Query refetch loop (3s interval on `/decisions`), the AssistantPanel
context-publish chain, and the demo replay engine's setTimeout cascade
(~16 setTimeout calls between approve and PR), the main thread chokes
on JSON parsing and the renderer gets SIGKILL'd by Chrome.

Aggravating: there was no eviction (runs accumulated forever across
sessions), no in-tab reset affordance (users had to open DevTools to
clear localStorage), and `clearDemoRuns` dispatched a `demo-runs-changed`
event that had zero listeners in the codebase.

## What Changes

- **`src/lib/demo/index.ts`**: Memoize `loadStore()` by raw-string identity.
  Subsequent calls with the same localStorage value return the cached
  parsed object — one parse per write, not one per call. Cache is
  invalidated on every `saveStore()` and `clearDemoRuns()`.
- **`src/lib/demo/index.ts`**: Add `MAX_DEMO_RUNS = 10` LRU cap. On every
  `saveStore()`, runs beyond the cap are evicted by oldest `updated_at`.
  Quota-exceeded fallback drops oldest half before retrying.
- **`src/lib/demo/index.ts`**: Drop the unused `demo-runs-changed`
  CustomEvent dispatches from `saveStore()` and `clearDemoRuns()`. No
  listeners, dead code.
- **`src/components/layout/topbar.tsx`**: Add a Reset button next to the
  DEMO MODE pill. Confirms, calls `clearDemoRuns()`, toasts, reloads.
- **`src/lib/demo/store.test.ts`**: New Vitest suite with 4 tests covering
  memoization-by-identity, corruption-survival, LRU cap on bulk inserts,
  and post-clear cache invalidation.

## Impact

- Affected specs: `demo-store` (NEW capability)
- Affected code:
  - `apps/ledger-insights-ui/src/lib/demo/index.ts`
  - `apps/ledger-insights-ui/src/components/layout/topbar.tsx`
  - `apps/ledger-insights-ui/src/lib/demo/store.test.ts` (new)
- User-visible: ⌘K assistant + page navigation no longer crash the tab
  after several demo runs; new "reset demo" affordance in the topbar.
- Deployment: rebuild + push `ledger-insights-ui` image, roll
  `ca-ledger-ui` revision.
