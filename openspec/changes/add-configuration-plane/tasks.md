# Tasks — add-configuration-plane

> Design-gate scope. Build sequencing only; not started. Order feeds the
> acceptance query (Requirement 5) — identity + policy rows must exist before the
> query can return complete cross-surface results.

## Phase 1 — identity spine (org model)
- [ ] Define `config/org.yaml` schema + JSON Schema validator
- [ ] Orchestrator reads org model; resolves team → cost_center / m365_group
- [ ] Reject runs referencing unknown teams (no anonymous ledger entries)
- [ ] Backfill neutral demo-zero `org.yaml` (customer-neutral topology)

## Phase 2 — standards authorable (extends add-standards-bundles)
- [ ] Add `blast_class` + `phi_locked` to rule schema
- [ ] Wire bundle editor → governed PR write-back (reuse config-editing-plane)
- [ ] PINS.yaml selection surfaced in config UI

## Phase 3 — autonomy matrix
- [ ] Define `config/autonomy.yaml` schema
- [ ] Replace code-resident autopilot logic with a read from the matrix
- [ ] Validator hard-locks phi-classification + auth-policy to gate
- [ ] Threshold path writes ledger entry citing the autonomy rule + precedent

## Phase 4 — model policy
- [ ] Define `config/models.yaml` schema
- [ ] Enforce allowlist/denylist/phi_eligible + cost ceilings at stage dispatch
- [ ] Refusal path writes ledger entry citing the model-policy rule

## Phase 5 — the acceptance query (hero)
- [ ] Query endpoint: filter phi_class, date range, actor kind, team
- [ ] Returns what + why + rule version + actor + model + cost per row
- [ ] Cross-surface-capable read path (no surface-specific branches)
- [ ] Compliance UI over the endpoint
- [ ] ACCEPTANCE TEST: phi_class=high / 30d returns complete non-null rows

## Cross-cutting
- [ ] Neutrality scrub on all new samples/config (no customer names)
- [ ] Tests per phase before commit (org read, autonomy lock, model refusal, query completeness)
- [ ] Honest-disclaimer pass: connectors beyond pipeline are Tier 2
