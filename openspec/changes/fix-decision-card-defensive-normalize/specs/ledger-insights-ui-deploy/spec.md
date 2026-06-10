## ADDED Requirements

### Requirement: DecisionCard MUST normalize all inputs before rendering

The `DecisionCard` component in `apps/ledger-insights-ui/src/components/domain/decision-card.tsx` MUST pass every input through a `normalize(raw)` function before reading any field. The component MUST NOT directly access fields like `entry.actor.kind`, `entry.bundle_refs.map(...)`, or any other field that could be `undefined` on a non-canonical input.

`normalize()` MUST return a valid `LedgerEntry` for ANY input shape — including empty objects, objects with `actor: null`, objects with `actor: {}` (no `kind`), and objects with `created_by` instead of `actor` (legacy fixture shape). The returned entry's `actor` field MUST always have a string `kind` and string `id`.

#### Scenario: canonical LedgerEntry passes through unchanged

- **GIVEN** an input matching the canonical `LedgerEntry` schema (`actor: {kind: "agent", id: "orchestrator"}`, `decision: "Approve PHI redaction"`, etc.)
- **WHEN** `DecisionCard` is rendered with this entry
- **THEN** the card MUST display the original `actor.id`, `decision`, and `phi_class` values
- **AND** the render MUST NOT throw

#### Scenario: legacy fixture shape coerces to a renderable entry

- **GIVEN** an input matching the demo-fixture shape (`created_by: "experiment@local"`, `resolution_text: "Mutual TLS + OAuth"`, `ambiguity_class: "auth-policy"`, NO `actor` field)
- **WHEN** `DecisionCard` is rendered with this entry
- **THEN** the card MUST display `actor.kind = "agent"`, `actor.id = "experiment@local"` (from `created_by`)
- **AND** the card MUST display the `resolution_text` as the decision title
- **AND** the render MUST NOT throw

#### Scenario: empty input renders as "unknown" placeholder

- **GIVEN** an empty input `{}`
- **WHEN** `DecisionCard` is rendered with this entry
- **THEN** the card MUST display `actor.id = "unknown"`
- **AND** the card MUST display `"(no decision text)"` as the title
- **AND** the render MUST NOT throw
- **AND** the card MUST be visible (not hidden / not error-bannered)

#### Scenario: any degenerate `actor` shape returns a valid actor

- **GIVEN** any of `{actor: undefined}`, `{actor: null}`, `{actor: {}}`, `{actor: "string"}`
- **WHEN** `normalize()` is called
- **THEN** the returned `entry.actor.kind` MUST be either `"human"` or `"agent"` (never undefined)
- **AND** the returned `entry.actor.id` MUST be a non-empty string

#### Scenario: non-array `bundle_refs` coerces to `[]`

- **GIVEN** an input where `bundle_refs` is `undefined`, `null`, or a non-array value
- **WHEN** `DecisionCard` renders the card and iterates `entry.bundle_refs.map(...)`
- **THEN** the render MUST NOT throw
- **AND** no bundle ref badges MUST be rendered

### Requirement: DecisionCard test suite MUST cover the normalize contract

The test suite at `apps/ledger-insights-ui/src/components/domain/decision-card.test.ts` MUST exist and MUST include at least 5 cases covering: (a) canonical shape pass-through, (b) legacy fixture coercion, (c) empty input fallback, (d) every degenerate `actor` shape, and (e) non-array `bundle_refs`. The tests MUST execute as part of the standard `pnpm vitest run` and MUST be a pre-commit gate.

#### Scenario: vitest covers all five contract guarantees

- **WHEN** `pnpm vitest run` is invoked from `apps/ledger-insights-ui/`
- **THEN** `src/components/domain/decision-card.test.ts` MUST be discovered and all 5+ cases MUST pass
- **AND** the test count delta from the prior baseline MUST be at least +5

### Requirement: Normalize MUST tolerate two known input sources

`normalize()` MUST recognize and tolerate inputs from at least two sources:

1. **Canonical `LedgerEntry`** from the `decision-ledger-mcp` Cosmos backend (`actor: {kind, id}`, `decision`, `rationale`, `phi_class`, `bundle_refs`, `precedent_refs`, etc.)
2. **Legacy demo-fixture shape** from `apps/ledger-insights-ui/src/lib/demo/fixtures.ts` (`created_by`, `resolution_text`, `ambiguity_class`, NO `actor`)

When a third source is added in the future, `normalize()` MUST be extended to recognize its field names too. New sources MUST NOT break existing rendering paths.

#### Scenario: third source (hypothetical) flows through normalize without crashing existing renders

- **WHEN** a new field name is introduced (e.g. a future migration ships entries with `decision_text` instead of `decision`)
- **AND** `normalize()` is NOT yet updated to recognize `decision_text`
- **THEN** the card MUST still render (falling back to `"(no decision text)"`)
- **AND** the page MUST NOT crash
