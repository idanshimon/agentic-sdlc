# Design: autonomous-review-loop

## Context

The reference design is a four-plane governed SDLC (Standards / Pipeline /
Ledger+Doctor / Agent HQ runtime). Today the pipeline can produce a real
GitHub PR and run a fail-hard `review-scan`, but the review verdict is a
dead end: a FAIL blocks merge and stops. This change closes the loop so a
**Coding Agent's** PR is autonomously reviewed, remediated, and re-reviewed to
convergence — bounded, audited, and permitted only where a per-repo autonomy
tier says it is safe.

The design deliberately reuses three proven in-repo patterns rather than
inventing new ones:

1. **Opt-in config loader + governance teeth** (from the shipped configuration
   plane: `org_model.py`, `autonomy.py`, `model_policy.py`). A config edit can
   only *tighten*; the unsafe state is refused at load AND forced-safe at
   runtime.
2. **Structured, grep-able citations** (`autonomy_ref`, `rule_ref`) so every
   loop hop is queryable by the Phase-5 compliance engine, not free text.
3. **Pure-builder-first ledger reads** so the controller's decisions are
   unit-testable with zero Cosmos.

## Goals / Non-goals

**Goals**
- Close review→remediate→re-review autonomously, with a hard governor.
- Make "remove the human" a **per-repo, graduated** decision, not global.
- Guarantee PHI/auth/deny changes can never be inside the autonomous envelope.
- Make the autonomous loop fully **observable** (a human can watch and audit
  without being in the merge path).

**Non-goals**
- Not solving model variance. The loop *contains* an unreliable model via the
  attempt bound + escalation; it does not make the model reliable.
- Not replacing `add-self-heal-cowork` (interactive, human-approved) — this is
  its unattended sibling. Both share the never-auto-merge-PHI floor.
- Not a new gate model. The resolver gate and its tier-2 hard-gate are
  unchanged; this operates on the *delivered PR*, downstream of the gate.

## Architecture

### The loop (state machine)

```
                    ┌───────────────────────────────────────────────┐
 Coding Agent PR ──▶│ review-scan verdict  (PASS | FAIL, cited)      │
 (or pipeline       └───────────────┬───────────────────────────────┘
  deliver PR)                       │
                          FAIL      │      PASS
                 ┌──────────────────┘        └───────────────┐
                 ▼                                            ▼
      ┌────────────────────────┐                  ┌────────────────────────┐
      │ repo tier gate         │                  │ repo tier gate         │
      │  A/B → remediate       │                  │  A → auto-merge        │
      │  C   → comment & stop  │                  │  B → await human merge │
      └───────────┬────────────┘                  │  C → comment & stop    │
                  │ (A/B)                          └────────────────────────┘
                  ▼
      ┌────────────────────────┐   attempt < MAX &&  cost < ceiling
      │ codegen remediation    │───────────────────────────────┐
      │  (blockers-in → commit)│                                │
      └───────────┬────────────┘                                │
                  │ new commit on PR branch                     │
                  ▼                                             │
          (back to review-scan) ─────────────────────────────┘
                  │
                  │ attempt == MAX  (still FAIL)
                  ▼
      ┌────────────────────────┐
      │ ESCALATE to human      │  ← never a silent merge, never an unbounded loop
      │  (inbox + PR + blockers)│
      └────────────────────────┘
```

### Components affected

| Component | Change | Why |
|---|---|---|
| `apps/orchestrator/review_loop.py` (NEW) | The controller: verdict→remediate→re-review, attempt/cost governor, terminal-state resolution. Pure core `plan_next_loop_action(verdict, attempt, tier, cost)` + thin async glue. | The missing wire, testable with zero Cosmos. |
| `apps/orchestrator/repo_autonomy.py` (NEW) | Opt-in loader for `config/repo_autonomy.yaml`; `tier_for(repo)`; `RepoTierUnlockError` teeth. | Per-repo "move the dial" with a tightening-only guarantee. |
| `.github/agents/codegen.agent.md` | Add **remediation entry mode**: input = review verdict, output = commit resolving only cited blockers, same-rule citation, no unrelated edits. | Codegen becomes the remediator without a second agent. |
| `.github/agents/review-scan.agent.md` | Verdict gains machine-consumable `blockers[]` already present; add `attempt` + `prior_verdict_ref` so re-reviews are chainable. | Chainable verdicts = auditable loop. |
| `.github/agents/review-loop-controller.agent.md` (NEW) | Foundry-registered persona: allowed actions (dispatch remediation, request re-review, auto-merge in-tier, escalate), ledger kinds it writes, bundle subscriptions (security, privacy read-only). | Agent-HQ-side identity for the loop, per the four-plane model. |
| `.github/hooks/` (NEW `pull_request.opened`) | Trigger the loop when a Coding Agent opens a PR on an opted-in repo. | The external-PR trigger surface Bobu specified. |
| `apps/decision-ledger-mcp/src/schema.ts` | New runtime kinds: `review_remediation`, `loop_converged`, `loop_escalated`. | First-class audit of every loop hop. |
| `apps/orchestrator/main.py` | `GET /api/review-loops`, `GET /api/review-loops/{id}` (stream), `POST /api/review-loops/{id}/merge` (Tier B human merge), `GET /api/config/repo-autonomy`. | Read + the single human touch-point (Tier B). |
| `apps/ledger-insights-ui/` | New `/review-loop` page; `/autonomy` per-repo panel; escalation inbox. | Make the dark factory observable + governable. |
| `packages/ledger-core/ledger_core/models.py` **and** `apps/orchestrator/models.py` | Add the three new kinds to BOTH LedgerEntry models (the known two-model drift). | Avoid the silent precedent-swallow bug. |

### Data / schema

Three new `runtime_kind` values (additive; pre-existing entries parse
unchanged):

- `review_remediation` — one per remediation attempt. Fields: `pr_ref`,
  `attempt`, `blockers_in[]`, `blockers_resolved[]`, `bundle_refs[]`,
  `cost_usd`, `model_used`, `actor{kind:agent,id:review-loop-controller}`.
- `loop_converged` — terminal PASS. Fields: `pr_ref`, `attempts`, `merged`
  (bool), `repo_tier`, `total_cost_usd`.
- `loop_escalated` — terminal exhaustion or tier-forced escalation. Fields:
  `pr_ref`, `attempts`, `unresolved_blockers[]`, `escalation_reason`
  (`max_attempts` | `cost_ceiling` | `tier_floor_phi` | `tier_floor_deny`).

Structured citation for the controller's autonomy decision (grep-able, feeds
compliance query):
`reviewloop/<tier>/<repo>/<merge|remediate|escalate>[@attempt=N]:<reason>`.

## Safety invariants (the teeth)

These are enforced **twice** — refused at config load/save AND forced-safe at
runtime — exactly like the shipped autonomy/model-policy invariants.

1. **PHI/deny floor.** If any blocker on a PR cites a `phi: true` rule or an
   explicit-deny pattern, the loop **must** escalate to a human — the repo's
   tier is irrelevant. A remediation attempt on a PHI-classed blocker is never
   auto-dispatched; it is `loop_escalated` with reason `tier_floor_phi`.
2. **Tightening-only tiers.** `repo_autonomy.yaml` can raise a repo's scrutiny
   (C→B→A is the *permission* direction; A is most autonomous). Setting Tier A
   on a repo whose recent history includes a PHI/deny blocker is refused at
   load (`RepoTierUnlockError`) and, if somehow present, forced to escalate at
   runtime.
3. **Bounded attempts.** `REVIEW_LOOP_MAX_ATTEMPTS` (default 3) is a hard
   ceiling; the env may lower it but a value that would allow unbounded loops
   is rejected. Exhaustion escalates; it never merges.
4. **Cost ceiling.** The loop reuses the model-policy cost-ceiling seam; a loop
   that would exceed the per-run ceiling escalates with reason `cost_ceiling`.
5. **Never a silent merge.** Auto-merge writes `loop_converged{merged:true}`
   with the full attempt chain referenced. There is no code path to merge
   without a terminal ledger entry.
6. **Absence = safe.** A repo not listed in `repo_autonomy.yaml` is Tier C
   (advisory) — the loop comments but changes nothing. Deploying the image
   changes no repo's behavior until a human graduates it.

## UX / UI experience

Design rules honored (Idan's standing conventions): LEFT-sidebar nav,
URL-as-view-state (filters are search-params), tonal buttons, lucide/SVG
icons, `var(--*)` theme tokens, plane-coded color (this surface is
Agent-HQ **pink** + Ledger **green** where it shows audit).

1. **`/review-loop` (new page).** A live table of in-flight and recent loops.
   Each row: real PR link, repo + its tier badge, an **attempt timeline**
   (review 1 → remediate 1 → review 2 …) rendered as a horizontal stepper,
   terminal state chip (MERGED green / ESCALATED amber / ADVISORY grey), total
   cost, total time. Clicking a hop opens its ledger entry. Every PR/commit
   number deep-links to real GitHub. This is where a human *watches the dark
   factory run* without being in it.
2. **`/autonomy` per-repo panel (extends existing page).** Beside the existing
   per-class autonomy matrix, a per-repo tier list: repo, current tier, **why
   it is capped** (e.g. "held at C — PHI blocker seen in last 30d"), who
   graduated it and when, and the last 10 loop outcomes as sparkline dots. The
   "move the dial per repo" control Bobu asked for, made legible.
3. **Escalation inbox.** Escalations render as a first-class list: the PR, the
   unresolved blockers with their bundle citations, the attempt history, and a
   single "take it from here" affordance that hands the human the PR. The human
   enters **only** at the boundary the customer's tier configuration chose.
4. **Demo-mode parity.** The page renders from deterministic fixtures in DEMO
   MODE (no live Cosmos) so the loop is presentable offline — same discipline
   as the existing demo store.

## Alternatives considered

- **Extend `add-self-heal-cowork` to allow unattended runs.** Rejected: its
  spec's core requirement is human-invoked + per-action human approval.
  Bolting "no human" onto it would violate its own invariants and muddy two
  distinct products (co-pilot vs autopilot). Cleaner as a sibling that shares
  the PHI/deny floor.
- **Global "autonomous mode" flag.** Rejected: a single global switch is
  exactly the reckless dark factory GitHub warned against on the call. Per-repo
  graduation is the safe, sellable version and matches the customer's own
  per-BU risk-appetite framing.
- **Unbounded retry until PASS.** Rejected: an unreliable model can thrash or
  burn cost indefinitely. The attempt/cost governor + escalation is what makes
  an unreliable model *safe to run unattended* — this is the whole point.
- **New reviewer agent distinct from codegen.** Rejected for v1: codegen
  gaining a remediation entry mode is less surface area and keeps the
  architecture-authorship boundary intact. A dedicated remediator can come
  later if evidence justifies it.

## Open questions

- Attempt-bound default: 3 vs 5. Start at 3 (cheap, escalates fast); revisit
  with real convergence-rate data.
- Should Tier A require a *clean* review history window (e.g. 30d no PHI/deny
  blocker) as a *precondition* to graduation, enforced in the loader? Leaning
  yes — makes graduation earned, not asserted.
- Re-review after remediation: full scan vs. delta-only on changed hunks.
  Full scan is safer for v1 (no missed cross-file regressions); delta is a
  later cost optimization.
