# Design: autonomous-review-loop

## Context

The reference design is a four-plane governed SDLC (Standards / Pipeline /
Ledger+Doctor / Agent HQ runtime). Today the pipeline can produce a real
GitHub PR and run a fail-hard `review-scan`, but the review verdict is a
dead end: a FAIL blocks merge and stops. This change closes the loop so a
**Coding Agent's** PR is autonomously reviewed, remediated, and re-reviewed to
convergence — bounded, audited, and permitted only where a per-repo autonomy
tier says it is safe.

The design deliberately reuses proven in-repo patterns where they genuinely
exist, and is explicit about what is net-new:

1. **Opt-in config floor + fail-closed validator** — the *real* shipped idiom is
   `config.py::_hard_gate_classes()` (an env-extends-never-shrinks set floor over
   `INVARIANT_CLASSES`) plus the fail-closed kernel `heal.py::validate_heal_action`.
   `repo_autonomy.py` is written **fresh** against these idioms. (There is no
   `org_model.py`/`autonomy.py`/`model_policy.py` loader triad in the repo — an
   earlier draft claimed one; corrected.)
2. **Structured, grep-able citations** (`autonomy_ref` on ledger entries) so
   every loop hop is queryable by the compliance surface, not free text.
3. **Pure-builder-first ledger reads** so the controller's decisions are
   unit-testable with zero Cosmos.

**Net-new (not a reuse — built by this change):** (a) a real machine-consumable
review verdict — today `stage_review_scan` is a stub (`findings = 0`); (b) a
rule-ref→`phi:true`/deny resolver bridging blocker rule-ids to the floor; (c)
per-run cost-ceiling *enforcement* (`total_cost_usd` accumulates today but never
gates); (d) a GitHub merge primitive (`deliver_pr.py` only opens PRs).

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
- Not the deterministic CI floor. `add-bundle-ci-enforcement` specifies a
  standalone, orchestrator-independent required status check that enforces the
  pattern-matchable bundle rules on any PR's diff. This loop runs *above* that
  floor: the CI gate is the dumb, un-bypassable check; this loop is the smart
  remediation layer. They compose and are specified separately.

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
| `.github/agents/review-scan.agent.md` + `apps/orchestrator/_pipeline_stages.py` | **Make the review actually emit a structured verdict.** Today `stage_review_scan` is a stub (`findings = 0`, never FAIL). Build the real `status`+`blockers[]` (check, rule-id, detail, file:line) + `attempt` + `prior_verdict_ref`. | The loop's load-bearing input — net-new, the true critical path. |
| `.github/agents/review-loop-controller.agent.md` (NEW) | Foundry-registered persona: allowed actions (dispatch remediation, request re-review, auto-merge in-tier, escalate), ledger kinds it writes, bundle subscriptions (security, privacy read-only). | Agent-HQ-side identity for the loop, per the four-plane model. |
| `.github/hooks/` (NEW `pull_request.opened`) | Trigger the loop when a Coding Agent opens a PR on an opted-in repo. | The external-PR trigger surface for un-orchestrated agent PRs. |
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
4. **Cost ceiling.** A per-run cost ceiling (built here — net-new; today
   `total_cost_usd` accumulates but never gates) escalates a loop that would
   exceed it with reason `cost_ceiling`.
5. **Never a silent merge.** Auto-merge writes `loop_converged{merged:true}`
   with the full attempt chain referenced. There is no code path to merge
   without a terminal ledger entry. **The merge itself is net-new** — a real
   `PUT /pulls/{n}/merge` primitive (branch-protection-aware), NOT the
   `deliver_pr.py` open-PR path, which never merges. A merge blocked by branch
   protection MUST surface as an explicit failure/escalation, never a silent
   no-op (which would itself violate this invariant).
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
   "move the dial per repo" control, made legible.
3. **Escalation inbox.** Escalations render as a first-class list: the PR, the
   unresolved blockers with their bundle citations, the attempt history, and a
   single "take it from here" affordance that hands the human the PR. The human
   enters **only** at the boundary the operator's tier configuration chose.
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
  exactly the reckless dark factory this design exists to avoid. Per-repo
  graduation is the safe posture and matches how organizations set
  per-BU risk appetite.
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
- ~~Should Tier A require a *clean* review history window as a precondition to
  graduation?~~ **RESOLVED — yes, required.** This is not optional polish: the
  autonomous loop runs *downstream* of the resolver gate, so a Coding-Agent PR
  that never hit the assessor could otherwise auto-merge PHI code with zero
  human decision — bypassing the per-class tier-2 hard-gate (409-on-bulk) that
  exists precisely to force PHI/auth to be individual human calls. The rule-ref
  →PHI/deny resolver (net-new) plus a required clean-history precondition
  (e.g. 30d, no `phi:true`/deny blocker) enforced in the `repo_autonomy.py`
  loader is what closes that bypass. `RepoTierUnlockError` is a **new** error
  class (there is no `InvariantUnlockError` in the repo to mirror; it follows
  the fail-closed `heal.py` validator shape).
- Re-review after remediation: full scan vs. delta-only on changed hunks.
  Full scan is safer for v1 (no missed cross-file regressions); delta is a
  later cost optimization.
