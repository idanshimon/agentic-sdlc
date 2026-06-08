# Demo Mode

A click-to-replay demo for `ledger-insights-ui` that surfaces audit-grade
pipeline output (architecture, test plan, code, decisions.md) sourced from
**real Phase-A-fixed pipeline runs** — no LLM calls, no network dependency.

## Enable

```bash
cd apps/ledger-insights-ui
echo 'NEXT_PUBLIC_DEMO_MODE=1' > .env.local
pnpm install
pnpm dev   # runs on http://localhost:3005 with port preflight
```

Open http://localhost:3005/runs/new → click any sample tagged **DEMO** →
the run replays end-to-end (~30s with a human gate in the middle).

## Behaviour when enabled

- Topbar shows an amber **DEMO MODE** pill linking to `/runs/new`
- `/runs/new` flips to "Start a new demo run", DEMO-tagged sample cards become
  the only path forward; paste/upload submission is disabled
- Each click creates a fresh `demo-<scenario>-<timestamp>` run that persists
  in `localStorage` and shows up in `/runs` alongside live runs
- Resolver gate awaits a human approval click; approval triggers the
  architect → test_plan → codegen → review_scan → deliver chain
- Orchestrator API methods (`approve`, `reject`, `pause`, `resume`) detect
  `demo-` prefixed run IDs and short-circuit to the local replay engine

## Architecture

Single rip-out unit at `src/lib/demo/`:

| File | Purpose |
|---|---|
| `index.ts` | Feature flag (`isDemoMode`), `isDemoRun`, store, `subscribeDemoRun`, `startDemoRun`, `approveDemoRun` |
| `fixtures.ts` | Auto-generated 46KB of pre-canned audit-grade content from `experiments/results/phase-a-fixed/run-1/` (vitals scenario) |

Four touchpoints in the rest of the app — all guarded with `if (isDemoMode())`
or `if (isDemoRun(...))`:

1. `src/lib/api/orchestrator.ts` — `listRuns`, `getRun`, `approve`, `reject`, `pause`, `resume`
2. `src/lib/hooks/use-run-stream.ts` — subscribes to local replay engine instead of SSE
3. `src/components/layout/topbar.tsx` — DEMO MODE pill
4. `src/app/runs/new/page.tsx` — DEMO badges + short-circuit `onSample`

## AgentAssistant subsystem

A floating Sparkles button (or `⌘K`) opens a slide-over assistant on every page. Replies are composed from the live demo store, not from canned templates. The whole thing is wired through one rip-out unit at `src/lib/assist/`.

### Module layout

| File | Purpose |
|---|---|
| `src/lib/assist/context.tsx` | provider + `useAssistantContext` hook (the page declares its kind + ids) |
| `src/lib/assist/replies.ts` | `gatherContext()`, `pickReply()`, `getSuggestions()`, intent detection (8 classes: `recommend`, `explain`, `summarize`, `what_if`, `drill_in`, `compare`, `next_step`, `open_question`) |
| `src/components/domain/assistant-panel.tsx` | slide-over UI (Sheet from radix), chat history, `applyHandler` |
| `src/components/layout/assist-keyboard-shortcut.tsx` | ⌘K binding |

`gatherContext()` reads from `src/lib/demo/index.ts`:

- `getDemoRun(runId)`
- `listDemoRuns()`
- `listDemoLedgerEntries({ run_id, entry_type, limit })`
- `getDemoArtifacts(runId)`

### Behaviour by context kind

| Context | What gatherContext reads | Reply shape |
|---|---|---|
| `run-detail` / `run-resolver-gate` | run state + run-scoped ledger entries + artifacts | run line + per-decision bullets with `bundle_refs` |
| `dashboard` / `runs-list` | portfolio rollup + recent decisions | aggregate counts + `by_status` |
| `decisions` / `telemetry` / `reports` | full ledger query + portfolio | citation density, model breakdown, cost rollup |
| `agent-edit` / `prompt-edit` | resource id from `context.id` | resource-specific prompts, no aggregation |
| `bundles` | none, bundles are spec-only | refers user to OpenSpec change flow |

13 context kinds are wired across pages: `dashboard`, `runs-list`, `run-detail`, `run-resolver-gate`, `decisions`, `telemetry`, `reports`, `bundles`, `agents-list`, `agent-edit`, `prompts-list`, `prompt-edit`, `phi-classifier`, `changes-list`.

### Production parity

The shape returned by `gatherContext()` is the same shape that would be sent as the system prompt to the orchestrator's chat agent in live mode. Demo mode is a deterministic composer; live mode is the LLM. The contract does not change.

Live LLM integration is not part of v0.7.

### How to test

```bash
pnpm dev   # :3005
# open any page, click the floating Sparkles button or ⌘K
# type a question; chips reflect current state
```

Suggestion chips are dynamic. On a run that is awaiting gate, the recommend chip says `What do you recommend for these cards?`. On the dashboard with N awaiting-gate runs, the chip says `N runs awaiting gate, what should I clear first?`.

### Rip-out semantics

`src/lib/assist/` is the rip-out unit. Removing it removes the assistant entirely. Touchpoints outside the folder are: the `<AssistantPanel/>` mount + `<AssistKeyboardShortcut/>` mount in the root layout, and a `useAssistantContext({ kind, id })` call in each page that opts in. Drop the imports and the assistant is gone.

## Regenerate fixtures

```bash
# Run the real pipeline against a sample PRD to capture fresh audit-grade output
python experiments/run_phase_a_blind_read.py   # untruncated architecture
python experiments/run_phase_a_fixed.py        # post-bugfix run

# Then regenerate the TS fixture file
python experiments/extract_demo_fixture.py
# → writes apps/ledger-insights-ui/src/lib/demo/fixtures.ts
```

The current fixture content (vitals scenario) covers:

- 1040-char PRD on FHIR HL7 patient vitals streaming for cardiology
- 8 ambiguity cards (5 gating, 3 auto-deferred)
- 5 typed decisions: PHI redaction, vendor auth (mTLS+OAuth client_credentials),
  WebSocket auth (RS256 JWT 15min TTL), ingest SLA (99.95% / <100ms p95),
  observability stack
- 4360-char architecture document (untruncated, post Bug #3 fix)
- 6000-char test plan with verbatim decision citations
- 4000-char generated FastAPI/WebSocket code
- decisions.md and run summary (cost, tokens, stages)

## Add another scenario

1. Generate a real pipeline run for the new scenario (`experiments/run_phase_a_fixed.py`
   pointed at a different PRD file)
2. Run `extract_demo_fixture.py --scenario <name>` to re-emit `fixtures.ts`
3. Append a `DemoScenario` entry in `src/lib/demo/index.ts` (`DEMO_SCENARIOS` array)
4. Make sure the `id` field matches the `id` of an existing sample card in
   `runs/new/page.tsx` — `getScenario(s.id)` is the lookup key

## Rip out for production

```bash
# 1. Disable the feature flag
sed -i '' 's/^NEXT_PUBLIC_DEMO_MODE=.*//' .env.local

# 2. Delete the subsystem
rm -rf src/lib/demo

# 3. Remove the four touchpoint guards (each is a single `if (isDemoMode())`
#    or `if (isDemoRun(...))` block — search & destroy):
grep -rn "from \"@/lib/demo\"" src/

# 4. Verify clean
grep -rn "demo" src/app src/components src/lib | grep -v node_modules
# → should return nothing demo-related
```

The four touchpoints are all isolated guards, so the production rip-out is a
mechanical 5-minute task. No demo logic lives outside `src/lib/demo/`.

## Why this design

- **Single feature flag** — one switch enables/disables everything
- **Single folder** — one `rm -rf` removes 100% of the data
- **No conditional bundling** — when `NEXT_PUBLIC_DEMO_MODE` is unset, the
  demo branches are dead code that tree-shakes out of the production bundle
- **Real fixtures** — sourced from actual pipeline runs, not synthetic — so
  the demo's content is customer-readable and audit-grade by construction
- **localStorage persistence** — demo runs survive page refresh and accumulate
  in the run list, mirroring real pipeline behaviour
- **API parity** — `approve(runId, body)` accepts the same arguments as the
  real endpoint; the demo branch ignores `body` but the call signature matches,
  so existing approve UI works unchanged on demo runs

## Port & preflight

Project default port is **3005** (was 3000). `pnpm dev` and `pnpm start` both
run a preflight check (`scripts/check-port.cjs`) that refuses to start if 3005
is already in use, with a copy-paste kill command. Override via
`PORT=3006 pnpm dev` if 3005 is also taken.
