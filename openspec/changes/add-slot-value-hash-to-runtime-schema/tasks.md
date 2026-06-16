# Tasks: add-slot-value-hash-to-runtime-schema

## 1 — Schema extension

- [ ] 1.1 `apps/decision-ledger-mcp/src/schema.ts::RuntimeEntrySchema` — add `slot_value_hash: z.string().optional()`
- [ ] 1.2 Soft validation note (no ctx.addIssue): stage_decision entries SHOULD carry the field; absence means they won't be returned by findPrecedent
- [ ] 1.3 Vitest: `schema.test.ts` — assert stage_decision with hash parses; without hash parses but is filterable

## 2 — Resolver wires hash on write

- [ ] 2.1 `apps/orchestrator/_pipeline_stages.py` — add `_slot_value_hash(card, decision)` helper using `hashlib.sha256` over `{class, kind, option_id}` JSON-canonical
- [ ] 2.2 Resolver's `_record_decision_to_ledger` (or equivalent) calls `_slot_value_hash` and includes `slot_value_hash` in the `ledger.write_runtime` payload
- [ ] 2.3 Pytest: `test_resolver_writes_slot_value_hash.py` — assert resolver invocation produces a write with deterministic hash; same card+decision twice = same hash

## 3 — Verify findPrecedent works end-to-end

- [ ] 3.1 Vitest: `find-precedent.test.ts` — extend existing tests: seed a stage_decision with hash, call findPrecedent with matching hash, assert non-null
- [ ] 3.2 Vitest: assert pause_class on the same class causes findPrecedent to return null even when the hash matches
- [ ] 3.3 Vitest: assert flag_decision on the seeded entry causes findPrecedent to exclude it and return the next candidate (or null if no other)

## 4 — Live verification on SBM cardiology pipeline

- [ ] 4.1 Re-run `experiments/sbm-cardiology/run.py --model databricks-claude-haiku-4-5 --run-idx 4 --team-suffix slot-hash-demo`
- [ ] 4.2 Confirm new run's ledger entries carry slot_value_hash
- [ ] 4.3 Call findPrecedent against the new run's identifier-format hash, confirm returns the entry
- [ ] 4.4 Flag that entry via deployed MCP, re-run, confirm findPrecedent now returns null and orchestrator falls back to fresh LLM call
- [ ] 4.5 Capture before/after as a recorded demo for the customer

## 5 — Build, deploy, document

- [ ] 5.1 Rebuild orchestrator + decision-ledger-mcp images with the changes
- [ ] 5.2 Roll out to ca-orchestrator + ca-ledger-mcp
- [ ] 5.3 Verify GET /tools/ledger.find_precedent against a new run returns non-null when seeded matches exist
- [ ] 5.4 Update MORNING-BRIEFING note that the slot_value_hash gap is closed
