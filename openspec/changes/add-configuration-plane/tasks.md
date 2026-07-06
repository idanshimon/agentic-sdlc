# Tasks — add-configuration-plane

> Order feeds the acceptance query — identity + policy rows must exist before the
> query returns complete cross-surface results. Phases 1–2 shipped; 3–5 pending.
> All config objects are OPT-IN (template `<name>.yaml.example`, activated via
> env/deploy-location, never auto-loaded). See `config/README.md`.

## Phase 1 — identity spine (org model)  ✅ SHIPPED (PR #8)
- [x] `org.yaml` loader + schema (`apps/orchestrator/org_model.py`)
- [x] Orchestrator resolves team → cost_center / m365_group; attributes ledger entries
- [x] Reject runs referencing unknown teams (HTTP 422; no anonymous entries)
- [x] Neutral demo-zero `org.yaml.example` (customer-neutral topology)
- [x] Opt-in activation (ORG_MODEL_PATH / deploy-location; template not auto-loaded)
- [x] 6 tests (attribution, unknown-team-reject, bootstrap, malformed-degrade, reload)

## Phase 2 — autonomy matrix  ✅ SHIPPED
- [x] `autonomy.yaml` loader + schema (`apps/orchestrator/autonomy.py`)
- [x] Replace code-resident autopilot logic with a matrix read in `_run_autopilot`
- [x] Hard-lock phi-classification + auth-policy to gate (load-time refuse + runtime force)
- [x] Threshold path gates unless precedent confidence >= threshold; always/gate modes
- [x] Neutral demo-zero `autonomy.yaml.example`
- [x] Opt-in activation (AUTONOMY_PATH / deploy-location; template not auto-loaded)
- [x] 11 tests incl. opt-in guarantee + matrix-overrides-autopilot integration
- [x] Stamp the autonomy rule ref onto the autopilot ledger entry (follow-up)

## Phase 3 — standards authorable (extends add-standards-bundles)  ⬜ PENDING
- [ ] Add `blast_class` + `phi_locked` to rule schema
- [ ] Wire bundle editor → governed PR write-back (reuse config-editing-plane)
- [ ] PINS.yaml selection surfaced in config UI

## Phase 4 — model policy  ⬜ PENDING
- [ ] Define `config/models.yaml` schema (allowlist/denylist/phi_eligible/routing/ceilings)
- [ ] Enforce at stage dispatch; refusal path writes ledger entry citing the rule
- [ ] Opt-in activation (MODELS_PATH / deploy-location) + `models.yaml.example`

## Phase 5 — the acceptance query (hero)  ⬜ PENDING
- [ ] Query endpoint: filter phi_class, date range, actor kind, team
- [ ] Returns what + why + rule version + actor + model + cost per row
- [ ] Cross-surface-capable read path (no surface-specific branches)
- [ ] Compliance UI over the endpoint
- [ ] ACCEPTANCE TEST: phi_class=high / 30d returns complete non-null rows

## Cross-cutting
- [x] Neutrality scrub on shipped config templates (no customer names)
- [x] Tests per phase before commit (Phases 1–2)
- [x] Opt-in onboarding guide (`config/README.md`)
- [ ] Honest-disclaimer pass: connectors beyond pipeline are Tier 2
