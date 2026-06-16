# Spec delta: add-slot-value-hash-to-runtime-schema / ledger

## ADDED Requirements

### Requirement: RuntimeEntrySchema MUST support `slot_value_hash`

The `RuntimeEntrySchema` in `apps/decision-ledger-mcp/src/schema.ts` MUST include `slot_value_hash` as an optional string field. The field MUST be writeable via `ledger.write_runtime`. Entries with `runtime_kind === "stage_decision"` SHOULD carry a `slot_value_hash` so they can be returned by `find_precedent`; entries with other runtime_kinds MAY omit it.

#### Scenario: stage_decision with hash round-trips through write_runtime → find_precedent

- **GIVEN** a `ledger.write_runtime` call with `runtime_kind="stage_decision"`, `ambiguity_class="identifier-format"`, `slot_value_hash="sha256:abc123..."`
- **WHEN** the write succeeds
- **AND** a subsequent `ledger.find_precedent` is called with the same `team_id`, `ambiguity_class`, and `slot_value_hash`
- **THEN** the response MUST contain `entry` with the previously-written stage_decision payload

#### Scenario: legacy entry without hash is silently invisible to find_precedent

- **GIVEN** a legacy `ledger.write_runtime` call without `slot_value_hash` (matches the 25 SBM seeded entries)
- **WHEN** find_precedent is called with any hash
- **THEN** the response MUST be `{entry: null}` — the legacy entry is NOT returned as a match
- **AND** the call MUST NOT throw

### Requirement: Resolver MUST compute deterministic slot_value_hash for every stage_decision

The orchestrator's resolver stage MUST compute `slot_value_hash` from the ambiguity_card + decision payload using SHA-256 over a JSON-canonical encoding of `{class, kind, option_id}` and MUST include it on every `ledger.write_runtime` call that produces a `stage_decision`.

The hash MUST be deterministic — the same logical card+decision produces the same hash across runs, teams, and time.

#### Scenario: same card+decision twice produces same hash

- **GIVEN** an `AmbiguityCard` with `ambiguity_class="identifier-format"` and a `GateDecision` with `kind="accept"`, `option_id="hmac-uuid"`
- **WHEN** the resolver computes `_slot_value_hash(card, decision)` twice
- **THEN** both invocations MUST return the same `sha256:...` string

#### Scenario: different cards produce different hashes

- **GIVEN** two `AmbiguityCard` instances with different `ambiguity_class` values
- **WHEN** the resolver computes `_slot_value_hash` for each
- **THEN** the two returned hashes MUST differ
