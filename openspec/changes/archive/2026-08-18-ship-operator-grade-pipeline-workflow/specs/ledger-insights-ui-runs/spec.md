# Spec delta: ship-operator-grade-pipeline-workflow / ledger-insights-ui-runs

## ADDED Requirements

### Requirement: Run-detail page MUST surface live pipeline progress without manual refresh

The `/runs/{run_id}` page MUST subscribe to the orchestrator's `/api/runs/{run_id}/stream` SSE endpoint and MUST invalidate the React Query cache for the run on every incoming event. Stage pills, status badges, decision counts, and cost totals MUST update within one stage transition without operator-side refresh action.

Events from server-side polling (the existing `useRun` query) and from SSE MUST be deduped by composite key `(stage, status, ts)` so each transition renders exactly once.

#### Scenario: stage transitions update UI in real time

- **GIVEN** an operator viewing `/runs/{run_id}` while the pipeline is at the assessor stage
- **WHEN** the orchestrator emits `assessor_completed` followed by `gate_open` via SSE
- **THEN** the assessor StagePill MUST flip from "running" to "completed" within 500ms of the event arrival
- **AND** the resolver gate panel MUST render without manual refresh
- **AND** the event stream MUST contain each event exactly once (no duplicates from polling)

### Requirement: Run-detail page MUST surface a sticky "needs attention" banner when paused at a gate

When the run status is `awaiting_gate`, the page MUST render a sticky banner pinned to the top of the viewport with: (a) a pulsing visual indicator, (b) a human-readable description naming the specific gate ("Resolver gate", "Design Review gate"), (c) a "Jump to gate ↓" button that smooth-scrolls to the gate card.

The banner MUST stay pinned while the operator scrolls through events and payload data below.

#### Scenario: operator sees sticky banner when pipeline pauses

- **GIVEN** an operator viewing `/runs/{run_id}` while the pipeline is running
- **WHEN** the run status flips to `awaiting_gate` at the resolver stage
- **THEN** a sticky banner MUST appear at the top of the viewport within one render tick
- **AND** the banner MUST contain the text "Pipeline paused at Resolver gate"
- **AND** clicking the "Jump to gate ↓" button MUST smooth-scroll the page to the gate card

### Requirement: Resolver gate MUST present per-card decisions and a finalize action

When the run status is `awaiting_gate` and `current_stage === "resolver"`, the page MUST render the `<ResolverGate>` component. The component MUST parse the gating cards from the most recent `gate_open` SSE event (matching `(resolver, gate_open)` OR legacy `(assessor, awaiting_gate)`).

The component MUST send per-card `GateDecision` payloads (not a bulk shape) when the operator approves cards, and MUST call `POST /api/runs/{id}/finalize` after the last per-card decision to release the gate. Each card MUST surface its options with per-option "Use this" buttons so the operator can override recommendations per-card.

#### Scenario: operator approves all recommended cards and gate closes

- **GIVEN** an operator viewing the resolver gate with 5 gating cards
- **WHEN** the operator clicks "Approve all recommended"
- **THEN** the UI MUST send 5 sequential `POST /approve` calls, each carrying `{card_id, decision_kind: accept, option_index: <recommended_idx>}`
- **AND** the UI MUST then call `POST /finalize` with empty body
- **AND** the toast MUST display "Approved 5 cards · Pipeline advancing to Architect"
- **AND** the run status MUST flip from `awaiting_gate` to `running` within the next SSE event

### Requirement: Design Review gate MUST present whole-stage Approve / Reject buttons

When the run status is `awaiting_gate` and `current_stage === "design_review"`, the page MUST render the `<DesignReviewGate>` component (NOT the resolver gate). The component MUST send a gate-level approve (`gate: "design_review"`, no real card_id required) and MUST NOT call finalize (the orchestrator auto-releases non-resolver gates on approve).

The component MUST surface the architecture artifact inline via a collapsible "▶ Show architecture preview" affordance so the operator can scan the artifact before approving.

#### Scenario: operator approves design review and pipeline advances

- **GIVEN** an operator viewing `/runs/{run_id}` with the design_review gate open
- **WHEN** the operator clicks "Approve architecture"
- **THEN** the UI MUST send `POST /approve` with `{card_id: "design-review-<rid>", decision_kind: accept, gate: "design_review", resolution_text: "..."}`
- **AND** the response MUST be HTTP 200
- **AND** the toast MUST display "Design review approved · Pipeline advancing to Test Plan stage"
- **AND** the run status MUST flip and current_stage MUST advance past design_review

### Requirement: Run artifacts panel MUST render code and markdown with operator affordances

The `<RunArtifactsPanel>` MUST render each artifact (Architecture / Test plan / Code) with: (a) line numbers in a left margin, (b) Copy + Download buttons in the header, (c) light syntax color (Python keywords, string literals, decorators, comments; markdown headings, blockquotes, bullets), (d) collapse-to-200-lines for artifacts longer than 200 lines with a "Show all N lines" toggle.

The viewer MUST NOT require an external syntax-highlighting library (shiki / prism / hljs) — a regex tokenizer is sufficient for glance-check on a 30-line FastAPI handler.

#### Scenario: code artifact renders with line numbers and color

- **GIVEN** a completed run with a CodeGen artifact containing Python source code
- **WHEN** the operator clicks the "Code" tab in the artifacts panel
- **THEN** every line MUST display a tabular line number in the left margin
- **AND** Python keywords (def, class, async, return, etc.) MUST render in purple
- **AND** the header MUST display "Copy" and "Download" buttons
- **AND** clicking "Download" MUST save the artifact as `artifact.py`
