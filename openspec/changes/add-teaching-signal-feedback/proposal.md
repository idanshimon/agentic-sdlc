# Proposal: Track B teaching-signal feedback on the Decision Ledger

> **Status:** DRAFT (in progress, 2026-06-16)
> **Capability:** ledger (extends `extend-ledger-runtime-meta-entries`)
> **Related:**
>   - `extend-ledger-runtime-meta-entries` (the runtime/meta discriminator that this builds on)
>   - `add-context-aware-agent-assistant` (archived; defines the AgentAssistant as a reading layer that MUST NOT write — Track B is the operator's intentional write path)
>   - `add-pipeline-doctor` (consumes flag/pause signals; spec'd separately)
>   - `customer-engagement/hca-agentic-sdlc-demo` skill (standing rules)

## Why

The v0.7 ledger captures every stage decision the pipeline makes, but operators who watch the `/decisions` page have no governed way to **push back** on those decisions. Today the only correction loop is "open a PR against the bundle and wait for the standards-change committee" — minutes-to-hours-to-days. That's correct for rule changes; it's the wrong tool for an operator saying *"this one decision was wrong, don't reuse it"* or *"stop auto-deciding this whole class until I re-teach"*.

Without a typed feedback channel:

1. **Operators have no agency in the dashboard.** The `/decisions` cards are read-only. The customer demo on 2026-06-10 surfaced this: *"What do I do when I see a card I disagree with? Email my manager?"*
2. **`findPrecedent` keeps quoting bad decisions back at itself.** Once a stage_decision lands, it becomes precedent forever. There's no audit-preserving way to retire it.
3. **No structured way to pause autopilot.** The all-or-nothing alternative is to flip an entire agent off, which kills the demo for every other class.

We need an **operator teaching signal** — a write path that is (a) low-friction (one click for thumbs, one sentence for flag/pause), (b) audit-preserving (the original decision is never modified, the operator's input is itself a ledger entry under their identity), and (c) actionable (`findPrecedent` reads the signals back so the next decision in the same class behaves differently).

This is the *only* operator write path on the ledger — every other write is system-driven (orchestrator, Pipeline Doctor, standards-change merge). The audit substrate has to capture it as a first-class kind, not glue it on as a comment field.

## What changes

Four new operator-authored `runtime_kind` values on the existing `LedgerEntry` schema, four matching MCP write tools, and two read-side behaviors on `findPrecedent`. Strictly additive — pre-Track-B entries parse and render unchanged.

### Schema additions

`apps/decision-ledger-mcp/src/schema.ts` adds four `runtime_kind` values:

```ts
export const RuntimeKindSchema = z.enum([
  // existing pipeline-internal kinds
  "stage_decision", "ide_session_summary", "ide_tool_call",
  "auto_fix", "delivered", "plan_proposed", "phi_block",
  // Track B — operator teaching signals
  "feedback_thumbs",      // T0 thumbs up/down sentiment
  "decision_flagged",     // T1 "this decision was wrong, don't reuse it"
  "replay_requested",     // T2 "re-run the same inputs against current rules"
  "class_paused",         // T3 "stop auto-deciding this whole ambiguity class"
]);
```

Plus three optional fields on `RuntimeEntrySchema`:

- `references_entry_id` — pointer back to the decision being acted upon (required on `feedback_thumbs`, `decision_flagged`, `replay_requested`)
- `feedback_kind: "thumbs_up" | "thumbs_down"` — required on `feedback_thumbs` only
- `paused_class` — required on `class_paused` only

`.refine()` enforces the per-kind required-field combos. Pre-Track-B entries (no `runtime_kind` or `runtime_kind: "stage_decision"`) parse identically — additive change.

### Four new MCP tools

| Tool | Writes | Required input |
|---|---|---|
| `ledger.add_feedback` | `runtime_kind: "feedback_thumbs"` | `actor`, `references_entry_id`, `feedback_kind` |
| `ledger.flag_decision` | `runtime_kind: "decision_flagged"` | `actor`, `references_entry_id`, `rationale` (non-empty) |
| `ledger.request_replay` | `runtime_kind: "replay_requested"` | `actor`, `references_entry_id` |
| `ledger.pause_class` | `runtime_kind: "class_paused"` | `actor`, `paused_class`, `rationale` (non-empty) |

All four:

- Default `team_id` to the authed team when the caller omits it (mirrors `ledger.query`)
- Reject cross-team requests with the standard `Token scoped to '<team>'` error
- Validate required string inputs at the **handler boundary** (typeof + non-empty), NOT just via the Zod refine. The schema refine accepts the string `"undefined"` because `String(undefined) === "undefined" !== null` — handler-side validation closes that hole.
- Auto-generate `agent_session_id` with kind-prefixed default (`feedback-`, `flag-`, `replay-`, `pause-`) when omitted, so the audit trail always groups operator events by source.

### `findPrecedent` honors teaching signals

`apps/decision-ledger-mcp/src/cosmos-client.ts::findPrecedent` gains two behaviors:

1. **Class-pause short-circuit.** If any `class_paused` entry exists for the (`team_id`, `ambiguity_class`) pair, return `null` immediately and skip the candidate query. The orchestrator interprets `null` as "no precedent → ask a human" — the existing escalation path. **One Cosmos query saved when paused.**

2. **Flagged-id exclusion.** Pull top-5 candidates (capped to bound RU cost; if all 5 are flagged the operator should pause the class anyway) and exclude any whose `id` appears in a `decision_flagged` entry's `references_entry_id`. Done in two partition-scoped queries instead of one nested EXISTS — RU cost is more predictable.

3. **Candidate filter:** the candidate query restricts to `runtime_kind='stage_decision' OR NOT IS_DEFINED(c.runtime_kind)`. Without this filter a `feedback_thumbs` or `replay_requested` row could win the TOP 1 selection and be returned as a "precedent." Major ledger-integrity bug — locked in by regression test.

### UI — TeachingSignalBar on every DecisionCard

`apps/ledger-insights-ui/src/components/domain/teaching-signal-bar.tsx` renders below every `DecisionCard` whose entry is NOT itself a teaching signal (you can't flag a flag). Five buttons: 👍, 👎, Flag, Replay, Pause autopilot (the last only renders when the entry has an `ambiguity_class`).

- **No optimistic updates.** Teaching signals matter for compliance — the customer needs to see the server's confirmation before the UI claims the action landed. Hooks invalidate the relevant TanStack queries on success.
- **Reason required for Flag and Pause.** Both write `rationale` to the audit trail; the UI gates the submit button until non-empty. Replay's rationale is optional (the operator may just want a re-run).
- **Card-level rendering of teaching signals.** When a `decision_flagged` / `class_paused` / `replay_requested` entry appears in the `/decisions` list, the card shows a kind-specific badge + icon and a `↳ refers to <shortId>` line so operators can scan the ledger and see the corrections alongside the decisions.

### Server-side proxy route

`apps/ledger-insights-ui/src/app/api/feedback/[kind]/route.ts` maps `thumbs|flag|replay|pause-class` → `ledger.*` MCP tool paths via the existing `forwardToLedgerMcp` helper. Token stays server-side (same pattern as `/api/ledger/query`).

## Why this design

**Teaching signals ARE ledger entries.** The first instinct is to make this a side-channel feedback table. That's wrong: it splits the audit substrate, and the AGENTS.md "Hard rule — Always write a runtime ledger entry per stage decision" applies just as strongly to operator interventions. Storing feedback as runtime entries with a discriminator means: (a) the same RBAC story, (b) the same partition-key story, (c) `/decisions` renders them for free, (d) Pipeline Doctor can attribute drift to operator-flagged decisions without a join.

**Audit-preserving, never destructive.** Flagging a decision DOES NOT modify the original entry. Pausing a class DOES NOT delete or backdate any precedent. The teaching signal IS a new entry under the operator's identity, with their `actor.id` as the audit key. The compliance story for "who told the system to stop trusting decision X" is a single Cosmos query.

**Top-5 candidate cap is intentional.** If the operator has flagged 5+ decisions in the same `(ambiguity_class, slot_value_hash)` bucket, the system should NOT keep walking back through the history looking for an unflagged precedent. That's a signal to pause the class — and the Pause autopilot button is right there in the UI. Bounding the candidate set keeps Cosmos RU cost predictable in that pathological case.

**Handler-boundary validation, not Zod-only.** Discovered while writing tests: `String(undefined)` in the handler produces the literal string `"undefined"` which the Zod refine cheerfully accepts. Operators submitting an empty form would have written `references_entry_id: "undefined"` to Cosmos — a silent integrity bug. Handler-side `typeof` + non-empty checks close the hole; the test suite pins both layers.

**Teaching-signal entries don't get teaching signals.** `TeachingSignalBar` self-suppresses on `feedback_thumbs / decision_flagged / replay_requested / class_paused` entries. Every hook still runs (rules-of-hooks compliance — the early return MUST happen below all hook calls or React throws "Rendered fewer hooks than expected" on mixed lists). The actual self-suppression is a render-time check.

## Why we did NOT do the alternative fix

- **Comment thread on each decision card.** Fits Slack better than an audit substrate. Free-text doesn't drive `findPrecedent` behavior; you'd still need typed signals underneath.
- **A separate `feedback` table.** Splits the audit story, breaks the partition-key model (feedback would be partitioned by `references_entry_id`, not `team_id`), forces a join on every `/decisions` render. Strictly worse.
- **Modifying the original decision in-place (mark as `flagged: true`).** Destroys auditability. The whole point of the ledger is "every meaningful agent action writes a ledger entry" — overwriting an existing entry violates the AGENTS.md hard rule.
- **Optimistic UI updates.** Teaching signals affect what the orchestrator does next. The customer needs to know the server accepted the signal before the UI implies it landed; an optimistic update that silently fails would be a compliance disaster.

## Out of scope

- **`/feedback` aggregator page.** The TeachingSignalBar comment promises *"Aggregate teaching signals view lives in the sidebar at /feedback"* but the page itself is deferred. The data model supports it (every signal is a runtime entry queryable by `runtime_kind`), but the v0.7 dashboard surfaces signals on each card rather than in a separate view. Tracked as a follow-up. **Action item:** strip the dangling comment in `teaching-signal-bar.tsx` to match shipped reality.
- **Replay execution worker.** `ledger.request_replay` writes a durable request entry; the orchestrator-side worker that actually re-runs the inputs is Track C (out of scope here).
- **Class-pause clearing UI.** Once paused, an operator can't yet un-pause from the dashboard. Workaround: the Cosmos-side admin can delete the `class_paused` entry. A "Resume autopilot" button is a follow-up.
- **Feedback aggregation in `/economics`.** The economics card today doesn't reflect thumbs counts. Once the aggregator page exists, `/economics` should embed thumbs sentiment per agent.
- **Standards-bundles `meta` entry write paths.** Track B is runtime-only. Standards-change PRs continue to write `meta` entries via the existing `extend-ledger-runtime-meta-entries` change.

## Receipts (will be filled in at archive time)

- Commit: TBD
- Image: TBD
- Revision: TBD
- Tests: 56/56 passing in decision-ledger-mcp (was 31, +25 new across `schema.test.ts`, `teaching-signals.test.ts`, `find-precedent.test.ts`)
- `tsc --noEmit` clean for both `decision-ledger-mcp` and `ledger-insights-ui`
- Build time: TBD
