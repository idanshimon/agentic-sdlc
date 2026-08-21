# Tasks — add-enterprise-integrations-plane

## Phase 1 — Integrations registry (config object)

- [ ] 1.1 `apps/orchestrator/integrations.py`: `IntegrationsRegistry` + `load_integrations(path=None)` following the opt-in loader idiom (`INTEGRATIONS_PATH` env → `/app/integrations.yaml` → `./integrations.yaml`; never `config/*.example`).
- [ ] 1.2 Validation: refuse inline credential fields; refuse unknown `provider`; malformed file ⇒ not-loaded with a logged reason (never half-applied).
- [ ] 1.3 `redacted()` view — credential presence only, no values.
- [ ] 1.4 Module singleton `INTEGRATIONS = load_integrations()` + `reload_integrations(path=None)`.
- [ ] 1.5 `config/integrations.yaml.example` — customer-neutral template (code_host + planning_tracker).
- [ ] 1.6 `.gitignore`: `config/integrations.yaml`, `/integrations.yaml`.
- [ ] 1.7 Tests: `test_default_singleton_is_opt_in_not_auto_loaded`, inline-credential refusal, unknown-provider refusal, malformed degradation, redaction contains no secret substring.

## Phase 2 — Work-item provenance

- [ ] 2.1 `WorkItemRef` model (`source_system`, `source_ref`, `item_type`, `url`, `verification: claimed|verified|unverifiable`, `reason`).
- [ ] 2.2 Run intake accepts optional `source_system` / `source_ref`; normalize to `WorkItemRef`; absent ⇒ `None`.
- [ ] 2.3 Add `work_item` to **both** `LedgerEntry` models (`apps/orchestrator/models.py` AND `packages/ledger-core/ledger_core/models.py`) with a safe default so pre-existing entries still validate; bridge through `from_legacy_v06_dict()` dropping nulls.
- [ ] 2.4 Stamp the run's `work_item` on every ledger entry the run writes.
- [ ] 2.5 Tests: provenance flows intake → entries; absent provenance is null and non-blocking; unconfigured planning system ⇒ `claimed`; resolution failure ⇒ unverified + reason, run still proceeds.

## Phase 3 — Planning-tracker provider seam (read-only)

- [ ] 3.1 Normalized `WorkItem` shape (id, item_type, title, body, url) + `PlanningProvider` protocol with `resolve()` and `probe()`.
- [ ] 3.2 Generic REST provider driven by registry templates; provider registry keyed by name.
- [ ] 3.3 No mutation path — assert in tests that the provider protocol exposes no write method.
- [ ] 3.4 Tests: normalized shape identical across two providers; unknown provider refused at load.

## Phase 4 — Endpoints

- [ ] 4.1 `GET /api/integrations` — redacted registry + `loaded` flag + per-entry status.
- [ ] 4.2 `POST /api/integrations/{id}/test` — bounded read-only probe; `verified|failing|unknown` with reason; never upgrades to `verified` without a real success.
- [ ] 4.3 `GET /api/config/settings` — composed posture (org, autonomy, models, pins, hard-gate floor, repo autonomy, integrations); per-section `bootstrap|activated` + `editable_here|governed_pr_only`; one failing section reported, not silently omitted.
- [ ] 4.4 AuthZ: reads require operator-class role; probes require operator; nothing here can weaken governance.
- [ ] 4.5 Tests: status honesty (declared ≠ verified), aggregate agrees with individual endpoints, section-failure isolation, no credential substring in any response.

## Phase 5 — UI: `/settings`

- [ ] 5.1 Server proxies: `app/api/settings/route.ts`, `app/api/integrations/[...path]/route.ts` (orchestrator URL + auth stay server-side; explicit error state, no fail-open-to-empty).
- [ ] 5.2 API client methods + types in `src/lib/api/orchestrator.ts`.
- [ ] 5.3 `app/settings/page.tsx` + tab components; tab reflected in URL search params.
- [ ] 5.4 Integrations tab: provider, identity, scopes, credential presence, status; distinct treatment for configured vs verified; test action surfaces real outcome; guiding empty state when unactivated.
- [ ] 5.5 Governance tab: locked chips for hard-gate floor / invariant classes / PHI-locked rules + standards-change-PR statement; no edit affordance.
- [ ] 5.6 Run detail: render work-item provenance with verification state; render nothing when absent.
- [ ] 5.7 Sidebar nav entry under Configure.
- [ ] 5.8 House style: lucide icons, `var(--*)` tokens, house `Card`/`Badge` primitives, no gradients/glow/uppercase-tracking.

## Phase 6 — Verification

- [ ] 6.1 `python -m pytest apps/orchestrator/tests/ -q` green from repo root.
- [ ] 6.2 `(cd packages/ledger-core && python -m pytest -q)` green.
- [ ] 6.3 `python -m pytest apps/pipeline-doctor/tests/ -q` green.
- [ ] 6.4 `cd apps/ledger-insights-ui && npx tsc --noEmit` clean + `npm run build` succeeds.
- [ ] 6.5 `openspec validate add-enterprise-integrations-plane --strict` prints valid.
- [ ] 6.6 Grep every changed file for credential material before staging.
- [ ] 6.7 Bootstrap-parity check: with no `integrations.yaml`, a run behaves identically to pre-change.
