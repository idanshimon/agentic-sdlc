# Proposal: configuration plane — a COE-authored governed AI operating model

> **Status:** DRAFT (2026-07-06)
> **Capability:** configuration-plane
> **Related:** add-config-editing-plane, add-standards-bundles,
> add-graduated-autonomy-tier2, master-v07-four-plane-architecture
> **Design inputs:** docs/MVP-control-plane-spec.md, docs/CONCEPT-BRIEF.md,
> two-model pressure test (GPT-4.1 critique + fork adjudication, 2026-07-06)

## Why

The four planes exist and the pipeline runs, but the system today is a FIXED
INSTANCE: four hardcoded standards bundles, a hardcoded 9-stage model routing,
no organization model, and an autonomy behaviour that is code-resident rather
than configured. A customer cannot instantiate THEIR governed operating model
without editing our repo.

A second-frontier pressure test (GPT-4.1, independent family) reframed the MVP:
the config objects are not the product — the unified compliance query they feed
is. This proposal therefore scopes the config surface as PLUMBING that makes ONE
acceptance query true, not as the hero.

Acceptance query (the definition of done for this capability):
> "Every AI decision on PHI-classified data in the last 30 days, the governing
> rule version, the deciding actor (human UPN or agent principal), and the cost"
> returns complete, real, cross-surface rows.

Delivery posture (fork resolved 2026-07-06): ACCELERATOR that rides Azure
primitives is the default. Azure-native EXTENSION is a scoped upgrade path only
when an account's platform team already runs strong Azure-native governance.
Config objects live in the CUSTOMER's repo and are edited via governed PRs
(reuses the shipped config-editing-plane write-back), never live-mutated.

Activation posture (decided 2026-07-06): config objects are **opt-in, never
auto-loaded**. The repo ships each object as a `<name>.yaml.example` TEMPLATE
that is NOT auto-discovered. A fresh deploy stays in bootstrap mode (permissive
org / mode-driven autonomy — i.e. exact pre-configuration behaviour) until an
operator activates a config object via `ORG_MODEL_PATH` / `AUTONOMY_PATH` env or
a deploy-location file (`/app/<name>.yaml`). Real (activated) config filenames
are git-ignored so a customer's topology never lands in the reference repo. This
prevents the shipped neutral template from silently changing behaviour on deploy.
Onboarding guide: `config/README.md`.

## What changes

### #1 — Organization model (`config/org.yaml`)
- New authorable object: departments[], teams[] (name, department, m365_group,
  cost_center), identity (entra_tenant_id, approver RBAC mapping).
- Orchestrator reads it to attribute every ledger entry to a real team + identity.
- WHY: no org model = anonymous decisions = the acceptance query returns null
  actors. This is the identity spine of the Decision Record.

### #2 — Standards bundles become authorable (extends add-standards-bundles)
- Today 4 hardcoded bundles; make departments + rules customer-authorable.
- Each rule gains `blast_class` (low|med|high) and `phi_locked` (bool).
- PINS.yaml selects the live version per department (exists — wire to config UI).

### #3 — Autonomy matrix (`config/autonomy.yaml`)  ← the COE's steering wheel
- Per (decision_class × team): gate | autopilot_above_threshold(t) | autopilot_always.
- phi-classification and auth-policy classes are validator-hard-locked to gate;
  config cannot open them (defense in depth — even a mis-edited file is refused).
- Replaces the code-resident autopilot behaviour with a read from this object.

### #4 — Model policy (`config/models.yaml`)
- allowlist[], denylist[], phi_eligible[] (models cleared for PHI-adjacent stages),
  per-stage routing, cost_ceiling_usd (per run | per team | per month).
- Orchestrator enforces at stage dispatch; a denied/over-ceiling run gates or fails
  with a ledger entry citing the model-policy rule.

### #5 — The acceptance query surface (THE hero, not the config)
- A single compliance query endpoint + UI: filter by phi_class, date range, actor
  kind, team; returns what + why + bundle_ref version + actor + cost per row.
- This is the capability's acceptance test; #1–#4 exist to make its rows complete.

## Scope discipline

- Tier 2 (NOT this change): economics chargeback vocabulary mapping, connector
  registry beyond the pipeline, notification routing.
- Tier 3 (NOT this change): record residency/retention, SIEM/Purview export,
  canary rollout % + auto-revert.
- Explicit non-goal: becoming a Purview/Foundry extension. That is a separate
  posture-B change, gated on account platform-team maturity, not built here.

## Open questions (resolve before tasks.md)

- Substrate name (deferred by product owner).
- Demo-zero org.yaml: ship NEUTRAL topology (resolved — customer-neutral posture),
  swap real department topology per account at engagement time.
- Does the acceptance query read cross-surface entries that do not yet exist
  (IDE/coding-agent connectors are Tier 2)? MVP answer: query is cross-surface-
  CAPABLE but demo-proves it on pipeline entries; connectors backfill the rows.
