## ADDED Requirements

### Requirement: Operator teaching-signal entries on the runtime ledger

The Decision Ledger MUST support four operator-authored `runtime_kind` values that record operator interventions on past stage decisions. All four are runtime entries (NOT meta) — they record what an operator decided about an agent decision, not what got changed about the rules. The four kinds are `feedback_thumbs`, `decision_flagged`, `replay_requested`, and `class_paused`.

A teaching-signal entry MUST be additive — writing one MUST NOT modify the original decision entry it references. The original decision MUST remain queryable, and the audit trail MUST attribute the teaching signal to the operator via the entry's `actor` field.

#### Scenario: operator submits thumbs_up

- **GIVEN** a runtime stage_decision entry exists with id `decision-42` on team `team-cardiology`
- **WHEN** the operator clicks 👍 on the DecisionCard for that entry
- **THEN** a new ledger entry MUST be written with `entry_type = "runtime"`, `runtime_kind = "feedback_thumbs"`, `feedback_kind = "thumbs_up"`, `references_entry_id = "decision-42"`, and `actor.kind = "human"`
- **AND** entry `decision-42` MUST remain unchanged
- **AND** both entries MUST be returned by `ledger.query` for `team-cardiology`

#### Scenario: operator flags a decision

- **GIVEN** a runtime stage_decision entry exists with id `decision-bad` on team `team-cardiology`
- **WHEN** the operator submits a flag with rationale `"Cited the wrong PHI rule version"`
- **THEN** a new ledger entry MUST be written with `runtime_kind = "decision_flagged"`, `references_entry_id = "decision-bad"`, `rationale = "Cited the wrong PHI rule version"`
- **AND** entry `decision-bad` MUST remain unchanged
- **AND** the rationale MUST NOT be empty (handler MUST reject empty rationale with HTTP 400)

#### Scenario: operator pauses an ambiguity class

- **GIVEN** team `team-cardiology` has decided several stage_decisions in ambiguity class `auth-policy`
- **WHEN** the operator submits a pause for class `auth-policy` with rationale `"Need to re-teach the auth ladder"`
- **THEN** a new ledger entry MUST be written with `runtime_kind = "class_paused"`, `paused_class = "auth-policy"`, `ambiguity_class = "auth-policy"` (mirrored), `rationale = "Need to re-teach the auth ladder"`
- **AND** the existing stage_decision entries for class `auth-policy` MUST remain unchanged

### Requirement: Schema-level validation of teaching-signal field combinations

`RuntimeEntrySchema.refine()` MUST enforce these per-kind required-field combinations:

| `runtime_kind` | Required additional fields |
|---|---|
| `feedback_thumbs` | `references_entry_id` non-null AND `feedback_kind` ∈ `{thumbs_up, thumbs_down}` |
| `decision_flagged` | `references_entry_id` non-null |
| `replay_requested` | `references_entry_id` non-null |
| `class_paused` | `paused_class` non-empty string |

Pre-Track-B runtime entries (those with `runtime_kind = "stage_decision"`, or with no `runtime_kind` field at all) MUST parse identically to before — the change MUST be additive.

#### Scenario: feedback_thumbs missing feedback_kind

- **GIVEN** a write of `{runtime_kind: "feedback_thumbs", references_entry_id: "x"}` (no `feedback_kind`)
- **WHEN** the entry is parsed via `RuntimeEntrySchema.parse(...)`
- **THEN** parsing MUST throw

#### Scenario: pre-Track-B stage_decision entry parses unchanged

- **GIVEN** a runtime entry of the canonical pre-Track-B shape: `{runtime_kind: "stage_decision", run_id: "run-1", actor: {...}, decision: "...", team_id: "team-x"}`
- **WHEN** the entry is parsed via `RuntimeEntrySchema.parse(...)`
- **THEN** parsing MUST succeed
- **AND** `references_entry_id`, `feedback_kind`, and `paused_class` MUST all be undefined on the parsed result

### Requirement: Handler-boundary validation for required string inputs

The four teaching-signal MCP tool handlers (`ledger.add_feedback`, `ledger.flag_decision`, `ledger.request_replay`, `ledger.pause_class`) MUST validate required string inputs at the handler boundary using `typeof === "string"` AND non-empty checks. They MUST NOT rely solely on the Zod refine for this validation.

This is because `String(undefined)` returns the literal string `"undefined"` (5 characters, non-null), which the schema refine would accept and write as a valid `references_entry_id`. Handler-side validation closes that hole.

#### Scenario: caller omits references_entry_id on flag_decision

- **GIVEN** a `ledger.flag_decision` call with `{actor: {...}, rationale: "wrong"}` and no `references_entry_id`
- **WHEN** the handler runs
- **THEN** the handler MUST throw before calling `writeRuntimeEntry`
- **AND** the thrown error message MUST mention `references_entry_id`
- **AND** no entry with `references_entry_id: "undefined"` MUST land in Cosmos

### Requirement: findPrecedent honors operator teaching signals

The `findPrecedent` function in `apps/decision-ledger-mcp/src/cosmos-client.ts` MUST honor operator teaching signals when looking up precedents. Specifically:

1. **Class-pause short-circuit.** Before querying for candidate precedents, `findPrecedent` MUST query for any `class_paused` entry on the same `(team_id, ambiguity_class)`. If any exists, the function MUST return `null` and MUST NOT execute the candidate-precedent query. This ensures the orchestrator's "no precedent → ask a human" path triggers immediately for paused classes.

2. **Flagged-id exclusion.** When candidates exist, `findPrecedent` MUST query for the set of `references_entry_id` values from all `decision_flagged` entries on the same team, and MUST exclude any candidate whose `id` appears in that set. The function MUST return the most-recent unflagged candidate, or `null` if all candidates are flagged.

3. **Candidate filter.** The candidate-precedent query MUST restrict to entries where `runtime_kind = "stage_decision"` OR `runtime_kind` is undefined. Teaching-signal entries MUST NOT be returnable as precedents.

4. **Bounded candidate set.** The candidate query MUST cap at TOP 5. RU cost MUST remain predictable in the pathological case where every recent decision in a class has been flagged.

5. **Optimization.** When the candidate query returns zero rows, `findPrecedent` MUST NOT execute the flagged-id query — there's nothing to filter.

#### Scenario: paused class returns null without querying candidates

- **GIVEN** team `team-cardiology` has a `class_paused` entry for ambiguity class `auth-policy`
- **AND** team `team-cardiology` has 3 stage_decision entries in class `auth-policy` with matching slot_value_hash
- **WHEN** `findPrecedent({team_id: "team-cardiology", ambiguity_class: "auth-policy", slot_value_hash: "..."})` is called
- **THEN** the result MUST be `null`
- **AND** the candidate-precedent query MUST NOT execute (only the paused-probe query runs)

#### Scenario: only candidate is flagged

- **GIVEN** team `team-cardiology` has one stage_decision entry `decision-bad` matching the lookup key
- **AND** team `team-cardiology` has a `decision_flagged` entry with `references_entry_id = "decision-bad"`
- **AND** no `class_paused` entry exists for the class
- **WHEN** `findPrecedent` is called
- **THEN** the result MUST be `null`

#### Scenario: skip flagged, return next-most-recent unflagged

- **GIVEN** team `team-cardiology` has two stage_decision entries: `decision-bad` (most recent) and `decision-good` (older), both matching the lookup key
- **AND** `decision-bad` has been flagged
- **AND** `decision-good` has NOT been flagged
- **WHEN** `findPrecedent` is called
- **THEN** the result MUST be `decision-good`

#### Scenario: teaching-signal entries cannot be returned as precedents

- **GIVEN** team `team-cardiology` has a `feedback_thumbs` entry that happens to share an `ambiguity_class` and `slot_value_hash` with a real decision
- **WHEN** `findPrecedent` is called for that lookup key
- **THEN** the candidate query MUST exclude the `feedback_thumbs` entry (filter `runtime_kind='stage_decision' OR NOT IS_DEFINED(c.runtime_kind)`)
- **AND** the result MUST be the stage_decision entry, not the feedback entry

### Requirement: TeachingSignalBar UI component

The `/decisions` dashboard MUST embed a `TeachingSignalBar` component on every `DecisionCard` whose entry is NOT itself a teaching signal. The bar MUST surface five operator actions: 👍 thumbs up, 👎 thumbs down, Flag, Replay, and Pause autopilot.

The bar MUST NOT use optimistic UI updates. Each action MUST wait for the server's confirmation before claiming success, because teaching signals affect compliance — a mid-flight failure that silently looks succeeded is a compliance disaster.

The bar MUST self-suppress on entries whose `runtime_kind` is one of the four teaching-signal kinds. The self-suppression check MUST happen AFTER all React hooks have been called (rules-of-hooks: hook order MUST NOT depend on entry shape).

#### Scenario: bar appears on stage_decision card

- **GIVEN** a DecisionCard rendered for a stage_decision entry
- **WHEN** the user views the card
- **THEN** the TeachingSignalBar MUST be visible at the bottom of the card
- **AND** the 👍, 👎, Flag, and Replay buttons MUST always be visible
- **AND** the Pause autopilot button MUST be visible only when the entry has an `ambiguity_class`

#### Scenario: bar self-suppresses on teaching-signal entry

- **GIVEN** a DecisionCard rendered for a `decision_flagged` entry
- **WHEN** the user views the card
- **THEN** the TeachingSignalBar MUST NOT be visible
- **AND** the card MUST still render normally (kind badge, refers-to line, rationale)

#### Scenario: rules-of-hooks compliance with mixed entries

- **GIVEN** the `/decisions` list contains a stage_decision entry adjacent to a `decision_flagged` entry
- **WHEN** the page renders
- **THEN** React MUST NOT throw "Rendered fewer hooks than expected"
- **AND** the page MUST render to completion

#### Scenario: Flag requires non-empty rationale

- **GIVEN** the operator clicks Flag on a DecisionCard
- **WHEN** the rationale textarea is empty
- **THEN** the "Flag decision" submit button MUST be disabled
- **AND** clicking the button MUST NOT fire the mutation

### Requirement: feedback proxy route forwards to MCP server-side

The Next.js API route `/api/feedback/[kind]` MUST forward operator-feedback requests to the matching `ledger.*` MCP tool path, attaching the bearer token server-side via `forwardToLedgerMcp`. The bearer token MUST NOT be exposed to the browser.

The route MUST map exactly four kinds: `thumbs → ledger.add_feedback`, `flag → ledger.flag_decision`, `replay → ledger.request_replay`, `pause-class → ledger.pause_class`. Any other `kind` MUST return HTTP 400.

#### Scenario: thumbs forwards to ledger.add_feedback

- **WHEN** a POST hits `/api/feedback/thumbs` with body `{actor: {...}, references_entry_id: "x", feedback_kind: "thumbs_up"}`
- **THEN** the route MUST POST to `<LEDGER_MCP_URL>/tools/ledger.add_feedback` with the same body
- **AND** the request MUST include `Authorization: Bearer <token>` from server env
- **AND** the response status + body MUST mirror the upstream MCP response

#### Scenario: unknown kind returns 400

- **WHEN** a POST hits `/api/feedback/banana`
- **THEN** the route MUST return HTTP 400 with body `{error: "unknown feedback kind: banana"}`
