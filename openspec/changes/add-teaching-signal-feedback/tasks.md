# Tasks: Track B teaching-signal feedback

## 1. Schema additions (`apps/decision-ledger-mcp/src/schema.ts`)
- [x] 1.1 Add 4 new `RuntimeKindSchema` values: `feedback_thumbs`, `decision_flagged`, `replay_requested`, `class_paused`
- [x] 1.2 Add `FeedbackKindSchema = z.enum(["thumbs_up", "thumbs_down"])`
- [x] 1.3 Add 3 optional fields on `RuntimeEntrySchema`: `references_entry_id`, `feedback_kind`, `paused_class`
- [x] 1.4 Add `.refine()` enforcing per-kind required-field combos (feedback_thumbs needs both refs; decision_flagged + replay_requested need references_entry_id; class_paused needs paused_class non-empty)
- [x] 1.5 Verify pre-Track-B entries (no runtime_kind or stage_decision) still parse — regression test in `schema.test.ts`

## 2. MCP tools (`apps/decision-ledger-mcp/src/tools.ts`)
- [x] 2.1 Add `ledger.add_feedback` — writes runtime_kind=feedback_thumbs
- [x] 2.2 Add `ledger.flag_decision` — writes runtime_kind=decision_flagged
- [x] 2.3 Add `ledger.request_replay` — writes runtime_kind=replay_requested
- [x] 2.4 Add `ledger.pause_class` — writes runtime_kind=class_paused, mirrors paused_class into ambiguity_class
- [x] 2.5 All 4 default `team_id` to the authed team when caller omits it
- [x] 2.6 All 4 reject cross-team requests with the canonical `Token scoped to '<team>'` error
- [x] 2.7 All 4 validate required string inputs at the handler boundary (typeof + non-empty) — NOT just via Zod refine, because `String(undefined) === "undefined"` would otherwise pass
- [x] 2.8 All 4 auto-generate kind-prefixed `agent_session_id` (feedback-/flag-/replay-/pause-) when caller omits it

## 3. `findPrecedent` teaching-signal honor (`apps/decision-ledger-mcp/src/cosmos-client.ts`)
- [x] 3.1 Class-pause short-circuit: query class_paused entries first, return null if any exist for (team_id, ambiguity_class) — skips candidate query entirely
- [x] 3.2 Restrict candidate query to `runtime_kind='stage_decision' OR NOT IS_DEFINED(c.runtime_kind)` so feedback/flag/replay/pause entries can never win TOP-1
- [x] 3.3 Cap candidates at TOP 5 (predictable RU cost)
- [x] 3.4 Pull flagged-id projection in a second partition-scoped query (`SELECT VALUE c.references_entry_id WHERE runtime_kind='decision_flagged'`)
- [x] 3.5 Exclude flagged candidates in JS, return the first non-flagged
- [x] 3.6 Skip the flagged-id query when candidates is empty (cost optimization)

## 4. Test coverage — decision-ledger-mcp
- [x] 4.1 NEW `tests/teaching-signals.test.ts` — 17 cases covering all 4 handlers (cross-team rejection, runtime_kind correctness, missing required fields, agent_session_id auto-prefix, inputSchema regression guards)
- [x] 4.2 NEW `tests/find-precedent.test.ts` — 8 cases covering class-pause short-circuit, flagged-id exclusion, mixed flagged/unflagged candidates, optimization regression guards (no flagged-id query when candidates empty), candidate-query SQL filter regression guards
- [x] 4.3 EXTEND `tests/schema.test.ts` — 15 new cases covering each runtime_kind's refine, plus pre-Track-B regression guard
- [x] 4.4 All 56/56 tests passing (was 31, +25 new)
- [x] 4.5 `tsc --noEmit` clean

## 5. UI types + DecisionCard rendering (`apps/ledger-insights-ui/`)
- [x] 5.1 Extend `LedgerEntry` in `src/lib/types.ts` with the 4 new runtime_kind values + `references_entry_id`, `feedback_kind`, `paused_class`, `ambiguity_class` (the last was already declared by the orchestrator but the type didn't surface it)
- [x] 5.2 `DecisionCard` renders kind-specific badge for any `runtime_kind !== "stage_decision"`
- [x] 5.3 `DecisionCard` renders kind-specific icon (Flag / RotateCcw / PauseCircle / ThumbsUp / ThumbsDown)
- [x] 5.4 `DecisionCard` renders `↳ refers to <shortId>` line when `references_entry_id` is set
- [x] 5.5 `normalize()` in DecisionCard preserves the new fields (regression guard: pre-Track-B card rendering unchanged)

## 6. UI — TeachingSignalBar component
- [x] 6.1 NEW `src/components/domain/teaching-signal-bar.tsx` with 5 buttons (👍 / 👎 / Flag / Replay / Pause autopilot)
- [x] 6.2 All hooks (`useMutation`, `useState`) called UNCONDITIONALLY at the top of the component — early return for self-suppression happens AFTER all hook calls (React rules-of-hooks compliance)
- [x] 6.3 Self-suppression: bar returns null when `entry.runtime_kind` is one of the 4 teaching-signal kinds
- [x] 6.4 "Pause autopilot" button only renders when `entry.ambiguity_class` is set
- [x] 6.5 Reason required for Flag and Pause (submit gated until non-empty); rationale optional for Replay; thumbs need no rationale
- [x] 6.6 No optimistic updates — UI waits for server confirmation
- [x] 6.7 Embedded into `DecisionCard` after the cost/relativeTime row

## 7. UI — feedback hooks + proxy route
- [x] 7.1 NEW `src/lib/hooks/use-feedback.ts` exposing `useThumbsMutation`, `useFlagMutation`, `useReplayMutation`, `usePauseClassMutation` via TanStack
- [x] 7.2 Each hook posts to `/api/feedback/<kind>` with `Content-Type: application/json`
- [x] 7.3 On success, each hook invalidates the relevant TanStack query keys (decisions, economics, feedback)
- [x] 7.4 NEW `src/app/api/feedback/[kind]/route.ts` mapping `thumbs | flag | replay | pause-class` → `ledger.*` tool paths
- [x] 7.5 Proxy uses existing `forwardToLedgerMcp` helper — token stays server-side
- [x] 7.6 Unknown `kind` returns 400 with descriptive error

## 8. Build + smoke
- [ ] 8.1 `pnpm tsc --noEmit` clean in `ledger-insights-ui`
- [ ] 8.2 `pnpm vitest run` 56/56 passing in `decision-ledger-mcp`
- [ ] 8.3 `pnpm build` clean in `ledger-insights-ui`
- [ ] 8.4 Local dev smoke: render `/decisions` with a stage_decision entry adjacent to a `decision_flagged` entry — TeachingSignalBar appears on the former, NOT on the latter, no React errors in the console
- [ ] 8.5 ACR build + Container App revision rollout (deferred to deploy commit)

## 9. Documentation
- [ ] 9.1 Update `customer-engagement/hca-agentic-sdlc-demo` skill — add Track B status block (what shipped, what's deferred, demo flow)
- [ ] 9.2 Strip the dangling `/feedback` aggregator pointer from `teaching-signal-bar.tsx` comment (out-of-scope follow-up, not delivered in this change)
- [ ] 9.3 Add Track B to `references/v07-four-plane-architecture.md` (operator-write-path section)

## 10. Follow-ups (deferred — NOT in this change)
- [ ] 10.1 `/feedback` aggregator page — sidebar entry under Ledger Plane, view of all teaching signals scoped by team / kind / time
- [ ] 10.2 Replay execution worker — Track C, consumes `replay_requested` entries and re-runs against current rules
- [ ] 10.3 "Resume autopilot" button — UI to clear `class_paused` entries
- [ ] 10.4 Embed thumbs sentiment in `/economics` per-agent breakdown
- [ ] 10.5 Pipeline Doctor consumes flag rate per-bundle as a drift signal

## 11. Archive
- [ ] 11.1 Move to `openspec/changes/archive/<YYYY-MM-DD>-add-teaching-signal-feedback/` after deploy soaks for 24h
