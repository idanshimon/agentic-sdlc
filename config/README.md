# Configuration plane — operator onboarding

This directory holds the **configuration objects** a Center-of-Excellence (COE)
leader authors to instantiate their governed AI operating model. Each is a
versioned YAML the pipeline reads. This is the surface that turns a fixed demo
into *your* governed instance.

> **Activation is opt-in.** The files here end in `.example` and are **templates**.
> A fresh deploy stays in **bootstrap mode** (permissive / mode-driven, i.e. the
> pre-configuration behaviour) until you explicitly activate a config object.
> Nothing here changes pipeline behaviour just by existing in the repo or image.

## The objects

| File | Object | What it controls | Phase |
|---|---|---|---|
| `org.yaml.example` | Organization model | Departments, teams (cost_center, m365_group), Entra identity, approver RBAC. The identity spine — every ledger entry attributes to a real team. | 1 |
| `autonomy.yaml.example` | Autonomy matrix | Per (decision_class × team): `gate` / `autopilot_always` / `autopilot_above_threshold(t)`. The COE's steering wheel. PHI + auth-policy are hard-locked to gate. | 2 |
| `models.yaml.example` | Model policy | `allowlist` / `denylist` / `phi_eligible` / per-stage `routing` / `cost_ceiling_usd` / `phi_stages`. Enforced at stage dispatch — a denied model or a non-cleared model on a PHI-adjacent stage fails the run with a ledger entry citing the rule. | 4 |

Standards bundles (`blast_class` + `phi_locked` per rule) are authored in
`standards-bundles/<dept>/<version>/` and edited through the governed PR flow
(`POST /api/config/bundles/save`) — a PHI-lock-weakening edit is refused before
the PR opens. The unified compliance query (Phase 5) reads across all of these.

## Activate in 3 steps

1. **Copy a template and edit it for your org:**
   ```bash
   cp config/org.yaml.example config/org.yaml           # then edit
   cp config/autonomy.yaml.example config/autonomy.yaml # then edit
   ```
   (These real filenames are git-ignored so your org's topology never lands in
   the reference repo — see `.gitignore`.)

2. **Point the orchestrator at them.** Two equivalent ways:
   - **Env var (recommended for Container Apps):**
     ```bash
     az containerapp update -n ca-orchestrator-vnet -g rg-agentic-sdlc-v07-eastus2 \
       --set-env-vars ORG_MODEL_PATH=/app/config/org.yaml \
                      AUTONOMY_PATH=/app/config/autonomy.yaml
     ```
   - **Deploy-location file:** drop the file at `/app/org.yaml` or `/app/autonomy.yaml`
     (or `./org.yaml` / `./autonomy.yaml` relative to the process CWD). These
     locations ARE auto-discovered; the repo `config/` template dir is NOT.

3. **Verify activation:**
   ```bash
   # org model loaded?  unknown team is now refused (HTTP 422 on /api/run)
   curl -sf $ORCH/api/run -F prd=@x.txt -F team_id=ghost-team ; echo
   # autonomy matrix loaded?  a class you set to `gate` now gates in autopilot
   ```

## Behaviour: bootstrap vs activated

| | Bootstrap (no file) | Activated (file loaded) |
|---|---|---|
| **org model** | Any `team_id` accepted, synthesized as `(unassigned)`. | Unknown `team_id` → **HTTP 422**. Known teams attribute cost_center + m365_group onto every ledger entry. |
| **autonomy** | `run.mode` drives autopilot (legacy). Invariants always gate. | Per (team, class) rule drives it. Matrix may tighten to `gate`; **can never open** phi-classification / auth-policy. |

## Safety guarantees (enforced by tests)

- **Opt-in, never silent.** The repo template is not auto-discovered
  (`test_default_singleton_is_opt_in_not_auto_loaded`). Deploying the image
  changes nothing until you activate.
- **PHI/auth hard-lock, defense in depth.** An `autonomy.yaml` that tries to set
  `phi-classification` or `auth-policy` to any autopilot mode is **refused at load
  time** (`InvariantUnlockError`), and the resolver forces `gate` at decision time
  regardless of config (`test_invariant_class_cannot_be_configured_open`,
  `test_invariant_always_gates_even_if_matrix_silent`).
- **Malformed config fails safe.** Bad org YAML → bootstrap (permissive, pipeline
  still runs). Bad autonomy YAML → bootstrap (mode-driven) with a loud error log —
  never a half-applied gate policy.

## Reference

- Capability spec: `openspec/changes/add-configuration-plane/`
- Concept + MVP framing: `docs/CONCEPT-BRIEF.md`, `docs/MVP-control-plane-spec.md`
- Loaders: `apps/orchestrator/org_model.py`, `apps/orchestrator/autonomy.py`
