# Proposal: add the Enterprise Integrations plane (external systems + Settings surface)

> **Status:** DRAFT (2026-08-20)
> **Capabilities:** `integrations-plane` (new), `ledger-insights-ui` (new Settings surface)
> **Related:**
>   - `add-configuration-plane` (ARCHIVED — the opt-in config-loader idiom this reuses: `org.yaml`, `autonomy.yaml`, `models.yaml`)
>   - `swap-deliver-ado-to-github` (the delivery-side GitHub client this formalizes as a registered integration)
>   - `adopt-github-native-execution-substrate` (GitHub as execution substrate)
>   - `master-v07-four-plane-architecture`

## Why

The pipeline has a governed middle and a governed exit, but no governed **entrance**, and
no single place an enterprise operator can see or configure how this instance is wired
into the systems it does not own.

Three concrete gaps:

1. **No inbound work-item provenance.** A run today starts from a PRD blob. In a real
   enterprise the PRD is downstream of a planning system of record — epics and stories
   live in a product-planning tool (Aha!, Jira, Azure Boards) and the PRD is a rendering
   of one of those records. Because the pipeline never records *which* work item a run
   came from, the Decision Ledger cannot answer the audit question one level up:
   "which planned epic caused this decision, and did the delivered PR close it?" The
   lineage chain is broken at both ends of the ledger.

2. **Integration configuration is scattered, invisible, and unattributed.** GitHub
   delivery is configured by loose env vars (`DELIVER_GH_TOKEN`, `DELIVER_TARGET_REPO`),
   model providers by `STAGE_*_PROVIDER`/`AOAI_ENDPOINT`, the ledger MCP by a bearer
   secret. There is no inventory of "what external systems does this instance touch,
   under which identity, with which scopes, and is it currently reachable." An operator
   discovers a broken integration by watching a run fail.

3. **No enterprise Settings surface.** The dashboard exposes authorable objects
   piecemeal (`/agents`, `/prompts`, `/bundles`) and hides the rest (org model, autonomy
   matrix, model policy, hard-gate floor) behind endpoints with no page. The three
   questions an enterprise buyer asks after the demo — *how do I connect it to my
   systems, how do I configure it for my org, and what can I not change* — have no
   screen.

This is the management/integration layer the four-plane architecture assumes and never
built.

## What changes

### 1. A new configuration object: `config/integrations.yaml`

A registry of **external systems** this instance is wired to, following the same opt-in
loader posture as `org.yaml`/`autonomy.yaml`/`models.yaml` (env path first, then deploy
locations, never the repo `.example`; absent ⇒ bootstrap/unconfigured, never a brick).

Two integration kinds ship in this change:

- **`code_host`** — GitHub (delivery + execution substrate). Formalizes the existing
  `DELIVER_GH_TOKEN` / `DELIVER_TARGET_REPO` wiring as a declared, inspectable
  integration with an owning identity and declared scopes.
- **`planning_tracker`** — a product-planning system of record that holds ideas, epics,
  and stories. Provider-pluggable (`aha`, `jira`, `azure_boards`, `generic`), because
  the record shape the pipeline needs is the same across all of them: a stable work-item
  id, a type (idea/epic/story/task), a title, a body that can serve as PRD input, and a
  URL.

The object is **declarative only in this change**: it declares the connection, its
identity, its scopes, and a reference-resolution URL template. Secrets are NEVER stored
in the YAML — each integration names an env/secret **reference** (`token_env`), and the
API surface returns a redacted view plus a boolean `credential_present`.

### 2. Work-item provenance end-to-end

A run may be submitted with `source_system` + `source_ref` (e.g. tracker id `E-1042`).
The orchestrator normalizes it into a `WorkItemRef` on the run and stamps it onto every
ledger entry the run writes, so the ledger's existing lineage graph gains one upstream
hop:

```
planning work item  →  run  →  stage decisions  →  delivered PR
```

Provenance is **optional and non-blocking** — a run without it behaves exactly as today.
When present, it is recorded as an unverified *claim* unless the named integration is
configured and reachable; the ledger distinguishes `claimed` from `verified` rather than
implying the pipeline validated an id it never fetched.

### 3. Integration health, without pretending

`GET /api/integrations` returns each declared integration with a redacted config and a
`status` of `unconfigured | configured | verified | failing`. `POST /api/integrations/{id}/test`
performs a bounded, read-only reachability probe (whoami-class call) and records the
result. A probe that cannot run returns `unknown` with a reason — never a green check.

### 4. `GET /api/config/settings` — one aggregated enterprise posture read

A single read that composes the already-existing config surfaces (org model, autonomy
matrix, model policy, standards pins, hard-gate floor, repo autonomy) plus the new
integrations registry, each tagged `bootstrap` or `activated`, and each marked
`editable_here` vs `governed_pr_only`. No new source of truth — it is a composition of
existing loaders.

### 5. `/settings` — the enterprise Settings surface

A new page (Configure section of the nav) with tabs mirroring the aggregated read:

```
apps/ledger-insights-ui/src/
├── app/settings/page.tsx                     NEW — tabbed enterprise settings
├── app/settings/_tabs/*.tsx                  NEW — Organization / Integrations /
│                                                   Autonomy / Models / Governance
├── app/api/settings/route.ts                 NEW — server proxy (fail-safe)
├── app/api/integrations/[...path]/route.ts   NEW — server proxy for list + test
├── lib/api/orchestrator.ts                   MOD — client methods + types
└── components/layout/sidebar.tsx             MOD — nav entry (Configure)
```

The **Governance** tab is deliberately read-only: the hard-gate floor, PHI-locked bundle
rules, and the invariant classes render as locked chips with the honest statement that
changing them is a standards-change PR, not a toggle. A settings page that lets an
operator click away the PHI floor would invert the entire product.

## What does NOT change

- **No tracker write-back.** This change never creates, updates, or closes a work item in
  a planning system. Inbound provenance and outbound status sync are separate concerns;
  write-back is a later proposal with its own governance analysis.
- **No secret storage.** The registry stores references, not credentials. No new secret
  material enters the repo, the image, or the ledger.
- **No change to the hard-gate floor or bundle precedence.** Settings renders governance;
  it does not grant a new way to weaken it.
- **No polling/sync loop.** Integrations are probed on demand, not on a timer.

## Impact

- New: `apps/orchestrator/integrations.py`, `config/integrations.yaml.example`,
  tests, the five endpoints above, the `/settings` surface.
- Modified: run intake (optional provenance fields), `models.py` (`WorkItemRef` on run +
  ledger entry — **both** LedgerEntry models per the known two-model drift), sidebar,
  `config/README.md`, `.gitignore` (activated filenames).
- Risk is contained by the opt-in posture: with no `integrations.yaml` present, every
  new surface renders "unconfigured" and pipeline behaviour is byte-identical to today.
