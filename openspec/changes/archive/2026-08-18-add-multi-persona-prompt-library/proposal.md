# Add multi-persona prompt library

> **Status:** DRAFT (filed 2026-06-16 as part of Agentic-SDLC v1.0 production-credibility plan)
> **Capability:** prompt-library (new)
> **Severity:** Foundational — every other Phase 1+ deliverable in the v1.0 plan depends on this contract

## Why

The Agentic-SDLC pipeline runs on six system prompts hardcoded in
`apps/orchestrator/prompt_library.py` as Python dataclass strings. One person
edits them, one PR ships the orchestrator image, and there is no governance
about who is allowed to change what. In production, a Cardiology team's
Architect persona needs to control the Architect-stage prompt for that team's
runs without needing platform-team approval for every wording tweak. Today
that is impossible — there is one prompt per stage globally.

Three real-world failure modes the current design can't handle:

1. **Persona ownership.** The Assessor prompt for a Compliance team should
   say "treat every PHI handling decision as gating" — for a Platform team
   it should say "treat PHI as advisory until production." Today both teams
   get the same prompt because the dataclass has no notion of who owns it.

2. **Versioning.** A run from 2026-05 used prompt v1. We change v1 to v2
   in 2026-06. The 2026-05 run is now non-reproducible — its ledger says
   "used the Assessor prompt" but doesn't pin which version. Audit
   compliance fails.

3. **No PR loop.** Operators today edit prompts by submitting a code PR
   that they may not have write access to. There's no in-UI authoring,
   no draft state, no persona-owner approval, no merge → live cycle. The
   Prompt Library UI page exists but is read-only.

The Workshop framing (Kapil, 2026-05-27) was a prompt library "where I can
sync up the gateway to basically say: if I get this [429], looking at the
prompt library reference, it's going to go pick up: this is the prompt I
want to use for system." That's the lookup contract. This change formalizes
the **authoring + governance** contract that sits behind it.

## What changes

### Storage: YAML files in git, one prompt per file

```
prompts/
  global/                    # platform-team-owned, applies to all teams
    ingest/v1.yaml           # owned_by: pm
    assessor/v1.yaml         # owned_by: pm
    architect/v1.yaml        # owned_by: architect
    test_plan/v1.yaml        # owned_by: qa
    codegen/v1.yaml          # owned_by: sre
    review_scan/v1.yaml      # owned_by: seceng
  persona/                   # persona-team-overridable
    seceng/review_scan/v1.yaml
  team/                      # team-overridable (where Cardiology lives)
    cardiology/architect/v1.yaml
    cardiology/assessor/v1.yaml
```

### Schema: every prompt file has frontmatter

```yaml
prompt_id: assessor-global       # stable across versions
version: v1                       # immutable once status=published
status: draft | published | superseded
scope: global | persona | team    # determines inheritance precedence
owner_persona: pm | architect | qa | seceng | sre | compliance
stage: ingest | assessor | architect | test_plan | codegen | review_scan
model_compat_notes: "Anthropic messages shape; ..."
effective_from: 2026-06-16T00:00:00Z
superseded_by: assessor-global/v2   # nullable; set when retired
git_sha: a1b2c3d4                 # set by CI on publish PR merge
authored_by: idanshimon@microsoft.com
reason: "Initial migration from prompt_library.py dataclass"
template: |
  You are the Assessor agent in a healthcare SDLC pipeline. ...
```

### Resolution: inheritance walk at run time

`resolve(stage, model, team, run_id) → (template, chain)`

Walks team → persona → global in that order; returns the most specific
match plus the full chain it considered. Both are written to the ledger
on every stage_decision so operators can answer "which prompt did this?"
in one click.

### Authoring: in-UI edit → GitHub PR → CI rebuild → live

1. Operator edits prompt in `/prompts` UI
2. UI POSTs the new YAML to `/api/prompts/[id]/draft`
3. Server uses GitHub API to commit the new file + open a PR titled
   `feat(prompts): {persona}/{stage}/{prompt_id} v{new_version} — {reason}`
4. Persona owner (codeowner) reviews + merges
5. Merge → GitHub Action → ACR build of orchestrator → deploy → next run
   uses new prompt; ledger pins git_sha

## Impact

### Affected specs

- `prompt-library/spec.md` — NEW capability, 8 ADDED Requirements
- `pipeline/spec.md` — MODIFIED to require resolver chain in ledger
- `ledger/spec.md` — MODIFIED to require `prompt_resolution_path` field
  on RuntimeEntrySchema

### Affected code

- `prompts/**.yaml` — NEW; 6 initial files migrated from current dataclass
- `apps/orchestrator/prompt_library.py` → backward-compat shim
- `apps/orchestrator/prompt_library_v2.py` → NEW resolver
- `apps/orchestrator/prompts_loader.py` → NEW YAML loader
- `apps/orchestrator/_pipeline_stages.py` → call resolver, log chain
- `apps/orchestrator/models.py::LedgerEntry` → add field
- `apps/decision-ledger-mcp/src/schema.ts::RuntimeEntrySchema` → add field
- `apps/orchestrator/Dockerfile.repo-root` → COPY prompts/
- `.dockerignore` → whitelist prompts/

### Affected images

- orchestrator: rebuild required after every published prompt change
- ledger-mcp: rebuild required once for schema extension; stable after

### Out of scope (separate changes)

- UI editor + viewer (filed as `add-prompt-editor-github-pr-flow`)
- Live observability panels (filed as `add-live-pipeline-observability`)
- Decisions redesign (filed as `redesign-decisions-master-detail`)
- Hot-reload without rebuild (Phase 2 follow-on)
- Auth + RBAC on who can edit which prompts (Phase 8)

## Migration

1. Existing 6 prompts in `prompt_library.py` ship as `prompts/global/<stage>/v1.yaml`
2. `prompt_library.py` becomes a re-export shim so any caller still works
3. `_pipeline_stages.py` switches to `resolve()` — same return type for
   the template, plus a new `chain` field captured into the ledger
4. Existing runs in Cosmos won't have `prompt_resolution_path` — UI must
   render `chain unavailable (pre-v2)` gracefully

## Open questions

- **Q1:** PR target — directly to `main` or via a `prompts/staging` branch?
  **Resolution:** `main` directly (simpler audit, faster cycle, codeowner
  acts as the safety gate). Revisit if a bad prompt ever lands.

- **Q2:** Hot reload vs rebuild?
  **Resolution:** Rebuild first (ACR build ≈ 2 min, every prompt change
  is a versioned image tag). Add hot reload in Phase 2 follow-on once
  the rebuild path is proven.

- **Q3:** How far back must reproducibility go?
  **Resolution:** Forever — prompts live in git, git history is the
  archive. The expensive part is reproducing the *model + dependencies*
  at that point, which is out of scope here.

- **Q4:** Persona list — what's right for HLS?
  **Default:** PM / Architect / SecEng / SRE / QA / Compliance.
  Confirmable in customer-engagement workshops; the schema accepts any
  string so the persona list is data, not code.
