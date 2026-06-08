# agent-assistant Specification

## Purpose
TBD - created by archiving change add-context-aware-agent-assistant. Update Purpose after archive.
## Requirements
### Requirement: Every page declares assistant context via useAssistantContext

Every page in `apps/ledger-insights-ui/` that mounts the assistant slide-over MUST declare its context by calling `useAssistantContext({kind, id?, label?, payload?})` from `src/lib/assist/context.tsx` exactly once in the page render path. The `kind` field SHALL be one of the 13 enumerated values: `dashboard`, `runs-list`, `run-detail`, `run-resolver-gate`, `decisions`, `telemetry`, `reports`, `bundles`, `agents-list`, `agent-edit`, `prompts-list`, `prompt-edit`, `phi-classifier`, `changes-list`. Pages that do not declare a context MUST NOT render the floating ⌘K Sparkles button.

#### Scenario: page mounts with a declared context
- **WHEN** a user navigates to `/runs/[id]`
- **THEN** the page MUST call `useAssistantContext({kind: "run-detail", id: <run_id>})` and the floating ⌘K Sparkles button MUST render

#### Scenario: page without a context declaration
- **WHEN** a developer adds a new page that omits `useAssistantContext({...})`
- **THEN** the floating ⌘K Sparkles button MUST NOT render on that page and the assistant slide-over MUST NOT mount

### Requirement: Reply engine gathers context fresh on every turn

The reply engine MUST call `gatherContext(viewing)` at the start of every user turn and SHALL NOT cache replies, SHALL NOT short-circuit by `kind` alone, and SHALL NOT reuse a `GatheredContext` snapshot across turns. Pre-canned text keyed only on `kind` is forbidden.

#### Scenario: same kind, two turns, different state
- **WHEN** a user opens ⌘K on `/runs/[id]` with `awaiting_gate=true`, asks a question, then approves the gate (now `awaiting_gate=false`) and asks the same question again
- **THEN** the reply engine MUST call `gatherContext` twice and the second reply MUST reflect the post-gate state (no awaiting-gate language)

#### Scenario: cached reply forbidden
- **WHEN** the reply engine receives two identical `(context, userPrompt)` tuples in one session
- **THEN** the engine MUST re-run `gatherContext` for the second call and MUST NOT return a memoized `AgentReply` from the first call

### Requirement: Run-focused gathered context fields

For `run-detail` and `run-resolver-gate` kinds, `gatherContext(viewing)` MUST return a `GatheredContext.run` object containing exactly these fields read from the demo run state via `getDemoRun(viewing.id)`: `id`, `status`, `stage`, `awaiting_gate`, `completed_stages`, `has_artifacts`, and `pr_url` (optional, present only when the run has a PR). Missing the run from the demo store SHALL produce `GatheredContext.run = undefined` and the composer SHALL fall back to an open-question reply.

#### Scenario: run exists in demo store
- **WHEN** `gatherContext({kind: "run-detail", id: "run-123"})` is called and `getDemoRun("run-123")` returns a run with `status="in_progress"`, `stage="codegen"`, `awaiting_gate=false`, `completed_stages=["assessor","resolver","architect"]`, `has_artifacts=true`, no PR yet
- **THEN** `GatheredContext.run` MUST equal `{id:"run-123", status:"in_progress", stage:"codegen", awaiting_gate:false, completed_stages:["assessor","resolver","architect"], has_artifacts:true}` with no `pr_url` field

#### Scenario: run-resolver-gate carries the same shape
- **WHEN** `gatherContext({kind: "run-resolver-gate", id: "run-456"})` is called
- **THEN** `GatheredContext.run` MUST be populated using the identical field set as the `run-detail` kind

#### Scenario: missing run id
- **WHEN** `gatherContext({kind: "run-detail", id: "run-does-not-exist"})` is called and `getDemoRun` returns null
- **THEN** `GatheredContext.run` MUST be `undefined` and the composer MUST route the reply through the open-question fallback

### Requirement: Portfolio gathered context fields

For the portfolio kinds (`dashboard`, `runs-list`, `decisions`, `telemetry`, `reports`), `gatherContext(viewing)` MUST return a `GatheredContext.portfolio` object containing exactly these aggregated fields computed from `listDemoRuns()` and `listDemoLedgerEntries()`: `total_runs`, `by_status`, `awaiting_gate_count`, `total_cost_usd`, `total_decisions`, and `bundle_citation_density`. The aggregation MUST run on every turn, no caching.

#### Scenario: dashboard with mixed-status runs
- **WHEN** `gatherContext({kind: "dashboard"})` is called against a demo store with 12 runs (3 awaiting gate, 5 in progress, 4 completed) and 87 ledger entries
- **THEN** `GatheredContext.portfolio.total_runs` MUST equal 12, `by_status` MUST equal `{awaiting_gate: 3, in_progress: 5, completed: 4}`, `awaiting_gate_count` MUST equal 3, and `total_decisions` MUST equal 87

#### Scenario: bundle citation density is computed, not stored
- **WHEN** `gatherContext({kind: "telemetry"})` is called and ledger entries carry a total of 134 `bundle_refs` across 87 entries
- **THEN** `GatheredContext.portfolio.bundle_citation_density` MUST equal 134/87 rounded to two decimal places

#### Scenario: empty portfolio
- **WHEN** `gatherContext({kind: "runs-list"})` is called against an empty demo store
- **THEN** `GatheredContext.portfolio` MUST equal `{total_runs: 0, by_status: {}, awaiting_gate_count: 0, total_cost_usd: 0, total_decisions: 0, bundle_citation_density: 0}`

### Requirement: Citations cite real bundle_refs from real ledger entries

Every entry in `AgentReply.citations` MUST be a `bundle_ref` string that appears in at least one `LedgerEntry.bundle_refs` array returned by `listDemoLedgerEntries({run_id?})` for the current `viewing` context. The composer SHALL NOT invent, paraphrase, or synthesize bundle refs; it SHALL only emit refs that literally exist in the gathered ledger entries.

#### Scenario: cited ref exists in ledger
- **WHEN** the composer emits a reply with `citations: [{label: "PHI rule", ref: "security/v0.1.0/PHI-001"}]` for a run-detail context
- **THEN** at least one `LedgerEntry` returned by `listDemoLedgerEntries({run_id: viewing.id})` MUST contain `"security/v0.1.0/PHI-001"` in its `bundle_refs` array

#### Scenario: invented citation forbidden
- **WHEN** the composer would emit a citation `ref` that is not present in any gathered ledger entry's `bundle_refs`
- **THEN** the composer MUST drop that citation rather than emit it

#### Scenario: no real citations available
- **WHEN** the gathered context has zero ledger entries with `bundle_refs`
- **THEN** the `AgentReply.citations` field MUST be omitted or set to an empty array

### Requirement: Suggestion chips react to gathered state

`suggestionsFor(context)` MUST call `gatherContext(context)` and return a chip set that reflects the current state. For run kinds, when `gathered.run.awaiting_gate === true`, the chip set MUST include a chip whose text mentions the gate (the literal substring "gate" or "awaiting"). For portfolio kinds, when `gathered.portfolio.awaiting_gate_count > 0`, the chip set MUST include a chip whose text contains the literal numeric count of awaiting-gate runs.

#### Scenario: run awaiting gate
- **WHEN** `suggestionsFor({kind: "run-detail", id: "run-789"})` is called and the gathered run has `awaiting_gate=true`
- **THEN** the returned chip array MUST contain at least one string matching the regex `/(gate|awaiting)/i`

#### Scenario: dashboard with N awaiting-gate runs
- **WHEN** `suggestionsFor({kind: "dashboard"})` is called and `gathered.portfolio.awaiting_gate_count` equals 4
- **THEN** the returned chip array MUST contain at least one string that includes the literal substring "4"

#### Scenario: nothing awaiting, no gate chip
- **WHEN** `suggestionsFor({kind: "run-detail", id: "run-clean"})` is called and the gathered run has `awaiting_gate=false`
- **THEN** the returned chip array MUST NOT include a chip whose only purpose is the gate prompt

### Requirement: Production parity with the live mode LLM call

The `GatheredContext` shape produced by `gatherContext(viewing)` MUST be the exact shape that live mode serializes as the system-prompt context block sent to the orchestrator chat agent. Demo mode and live mode SHALL share the same TypeScript type for `GatheredContext` and SHALL NOT diverge on field names, field types, or per-kind selectivity rules. The demo composer is the deterministic stand-in for the LLM call; the contract under test is the gathered shape, not the prose of the reply.

#### Scenario: shape parity across modes
- **WHEN** the live-mode endpoint is implemented (future change `add-orchestrator-chat-endpoint`) and serializes its system-prompt context block from a server-side `gatherContext`
- **THEN** the resulting JSON MUST validate against the same TypeScript `GatheredContext` type used by the demo composer

#### Scenario: divergence is rejected
- **WHEN** a developer adds a field to `GatheredContext.run` in the demo composer without updating the live-mode serializer (or vice versa)
- **THEN** the shared type definition MUST cause a TypeScript compile error in whichever build sees only the unilateral change

