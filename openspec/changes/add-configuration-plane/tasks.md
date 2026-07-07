# Tasks — add-configuration-plane

> Order feeds the acceptance query — identity + policy rows must exist before the
> query returns complete cross-surface results. **All five phases shipped.**
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

## Phase 3 — standards authorable (extends add-standards-bundles)  ✅ SHIPPED
- [x] Add `blast_class` + `phi_locked` to rule schema (`apps/orchestrator/bundle_rules.py`)
- [x] Wire bundle editor → governed PR write-back (reuse config-editing-plane) + PHI-lock
      validation: a rules.yaml edit that deletes/unlocks/de-classifies/downgrades a
      phi_locked rule is refused HTTP 409 before the PR opens (the governance teeth)
- [x] PINS.yaml selection surfaced in config UI (`GET /api/config/pins`, `pins.py`)
- [x] Stamp `blast_class` + `phi_locked` on shipped security bundle (PHI-* + AUTH-001 locked)
- [x] 14 tests (11 bundle_rules incl. weaken-refused/strengthen-allowed + 3 pins endpoint)

## Phase 4 — model policy  ✅ SHIPPED
- [x] Define `config/models.yaml` schema (allowlist/denylist/phi_eligible/routing/ceilings)
      + `phi_stages` — loader `apps/orchestrator/model_policy.py` (opt-in, fail-open permissive)
- [x] Enforce at stage dispatch (`_pipeline_stages._call` chokepoint); a denied /
      non-allowlisted model, or a non-phi_eligible model on a PHI-adjacent stage,
      raises ModelPolicyRefusal → run FAILED + ledger entry citing the rule (autonomy_ref)
- [x] Opt-in activation (MODELS_PATH / deploy-location) + `models.yaml.example`
- [x] 21 tests (13 policy + 5 dispatch enforcement + 3 refusal-ledger-audit)

## Phase 5 — the acceptance query (hero)  ✅ SHIPPED
- [x] Query endpoint: filter phi_class, date range, actor kind, team
      (`GET /api/compliance/decisions`, `apps/orchestrator/compliance_query.py`)
- [x] Returns what + why + rule version + actor + model + cost per row
- [x] Cross-surface-capable read path (one ledger container, no surface-specific branch)
- [x] Compliance UI over the endpoint (`apps/ledger-insights-ui/src/app/compliance/page.tsx`,
      URL-state filters + completeness banner + attributed-decision table; TS build clean)
- [x] ACCEPTANCE TEST: phi_class=high / 30d returns complete non-null rows
      (`test_compliance_query.py::test_acceptance_phi_high_30d_returns_complete_nonnull_rows`)
- [x] 10 tests (8 pure query/builder incl. acceptance + 2 endpoint)

## Cross-cutting
- [x] Neutrality scrub on shipped config templates (no customer names)
- [x] Tests per phase before commit (Phases 1–2)
- [x] Opt-in onboarding guide (`config/README.md`)
- [x] Honest-disclaimer pass: connectors beyond pipeline are Tier 2 — the
      compliance query is cross-surface-CAPABLE (single ledger container, no
      surface branch) and demo-proves completeness on pipeline + autopilot +
      human-gate + model-refusal entries; IDE/coding-agent connector rows
      backfill when those surfaces land (Tier 2, per proposal scope discipline).
