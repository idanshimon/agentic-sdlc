# Proposal: autonomous review→remediate→re-review loop (Dark-Factory review)

> **Status:** DRAFT (2026-07-08)
> **Capability:** autonomous-review-loop (NEW)
> **Author:** Idan Shimon
> **Motivation:** The one frontier this class of governed pipeline has not yet
>   closed is an autonomous **"dark factory"** review: agents review agents' pull
>   requests, the human-in-the-loop review bottleneck is removed, and a rejected
>   PR causes the coding agent to **pick up the rejection comment and come back
>   with an approved method** — all **without relaxing standards**. Closing this
>   loop on GitHub is not on a committed platform roadmap and is blocked on model
>   reliability. This capability lets the reference design *show it is possible on
>   GitHub as an engine* — by containing an unreliable model with bounded
>   attempts + a hard escalation floor rather than waiting for a reliable one.

## Why

The reference design already has every ingredient of a governed loop **except
the wire that closes it autonomously**:

- `review-scan.agent.md` describes a `status: FAIL` verdict with per-blocker
  bundle-rule citations — but **the executable `stage_review_scan`
  (`_pipeline_stages.py`) is a stub** (`findings = 0  # demo: stubbed clean`,
  always `completed`). The structured verdict lives only in persona markdown.
  **Emitting a real machine-consumable verdict is net-new Phase-0 work, and is
  the true critical path** — the loop cannot exist without it.
- `codegen.agent.md` generates from an architecture proposal — but has no
  entry path that takes a *review verdict* as its input and remediates against
  it.
- `swap-deliver-ado-to-github` opens a **real** GitHub PR (Git Data API, no
  fakes, `deliver_pr.py`) — so a real PR object exists to be reviewed. But that
  change states outright the orchestrator **never merges**; a Tier-A auto-merge
  primitive (`PUT /pulls/{n}/merge`, branch-protection-aware) is **net-new**,
  not a reuse of the deliver path.
- `add-self-heal-cowork` builds a reject→fix loop but its **core invariant is
  the opposite of what is needed here**: every heal is human-invoked and every
  action requires explicit per-action human approval. It is the *co-pilot*
  loop. The autonomous loop is the *autopilot* counterpart.
- `add-graduated-autonomy-tier2` governs autonomy **per ambiguity-class** at
  the resolver gate (the shipped `INVARIANT_CLASSES` floor +
  `config.py::_hard_gate_classes()` env-extends-never-shrinks idiom) — but there
  is no **per-repository** autonomy tier, and that per-class floor keys on the
  assessor's ambiguity **class**, not on the bundle **rule ids** a review
  blocker cites (a gap this change must bridge with new code, see below).

So the missing capability is a **new composition**, not a duplicate: a
closed, bounded, autonomous loop —

```
Coding Agent opens PR → review-scan verdict (PASS|FAIL, cited)
        │ FAIL
        ▼
  remediation dispatched to codegen  (bounded: N attempts, envelope-scoped)
        │ new commit on the same PR branch
        ▼
  review-scan re-runs → … → PASS → auto-merge  (only if repo tier allows)
        │ still FAIL after N attempts
        ▼
  ESCALATE to human  (never silently merge, never silently loop forever)
```

— governed by a **per-repo autonomy tier** so the human is removed *only where
an operator has decided it is safe*, and every hop is a ledger entry.

This is the honest, demonstrable answer to "is a dark factory possible on
GitHub without relaxing standards?": **yes, on repos you have graduated to
Tier A, with a hard escalation floor that PHI/auth/deny rules can never leave.**

## What changes

Four coordinated additions. All are **additive** — no existing pipeline run,
gate, or heal session changes behavior unless the new per-repo tier opts a repo
in.

### 1. Review verdict → codegen remediation bridge (the missing wire)

- A new orchestrator module `apps/orchestrator/review_loop.py` that consumes a
  `review-scan` FAIL verdict and dispatches a **remediation task** to codegen,
  passing the structured blockers (`check`, `rule`, `detail`, `file:line`) as
  the remediation contract.
- `codegen.agent.md` gains a documented **remediation entry mode**: given a
  review verdict, produce a commit that resolves *only* the cited blockers,
  cite the same bundle rule it satisfied, and never touch unrelated code.
- Each remediation attempt writes a `review_remediation` runtime ledger entry
  (attempt N, blockers-in, blockers-resolved, cost, model).

### 2. Bounded re-review controller (the loop with a governor)

- `review_loop.py` runs review→remediate→re-review with a **hard attempt
  bound** (`REVIEW_LOOP_MAX_ATTEMPTS`, default 3) and a **cost ceiling**. Note:
  there is no shipped cost-enforcement seam to reuse — `total_cost_usd`
  accumulates on the run but never gates. The per-run ceiling is **net-new**
  enforcement built here (the existing `_STAGE_WEIGHTS` apportionment is
  display-only).
- Convergence (PASS) or exhaustion (still FAIL after N) are both terminal and
  both audited. Exhaustion **always escalates to a human** — it never silently
  merges and never loops unbounded.

### 3. Per-repo autonomy tier (the "move the dial" control)

- A new authorable config object `config/repo_autonomy.yaml` →
  `apps/orchestrator/repo_autonomy.py`, following the **actual shipped floor
  idiom** — `config.py::_hard_gate_classes()` (env-extends-never-shrinks set)
  and the fail-closed validator shape in `heal.py::validate_heal_action`. (Note:
  there is no `org_model.py`/`model_policy.py` triad to mirror — the loader is
  written fresh against the `config.py`/`heal.py` idioms.)
- Three tiers per repo:
  - **Tier A — Autonomous merge:** PASS auto-merges with no human. Permitted
    only for repos explicitly graduated in config.
  - **Tier B — Autonomous review, human merge:** the loop runs to PASS, then a
    human clicks merge (default for opted-in repos).
  - **Tier C — Advisory:** the loop runs, posts its verdict as a PR comment,
    changes nothing (default for **every** repo not listed — safe by absence).
- **Governance teeth (tightening-only, enforced at load AND runtime):** a repo
  that touches a `phi: true` or explicit-deny rule can **never** be Tier A,
  regardless of config; the loader refuses the unsafe tier and the runtime
  forces escalation (fail-closed, same shape as `heal.py::validate_heal_action`).
- **New rule-ref → PHI/deny resolver.** The shipped per-class floor
  (`INVARIANT_CLASSES`) keys on the assessor's ambiguity **class**; review
  blockers cite bundle **rule ids** (`security/v0.1.0/PHI-001`). PHI-ness lives
  at rule level (`rules.yaml: phi: true`, `envelope.yaml: forbidden`). Mapping a
  blocker to the floor therefore needs a **new** rule-ref→`phi:true`/deny lookup
  sourced from the bundle files — this is net-new governance code, not a reuse
  of `INVARIANT_CLASSES`, and is the airtight link that makes the per-repo tier
  safe at the exact PHI boundary the resolver-gate tier-2 protects.

### 4. UX — the Autonomous Review surface (so a human can *watch* the dark factory)

A "dark factory" that no one can see is unauditable. The UI makes the
autonomous loop **observable and governable** without putting a human in the
merge path:

- New page `apps/ledger-insights-ui/src/app/review-loop/page.tsx` — a live view
  of in-flight loops: PR → attempt timeline (review N → remediate N → review
  N+1) → terminal state (MERGED / ESCALATED), each hop linking to its ledger
  entry and the real GitHub PR/commit.
- The `/autonomy` page gains a **per-repo tier** panel (tier, why it's capped,
  who graduated it, last 10 loop outcomes) next to the existing per-class view.
- Escalations surface as a first-class inbox: "this loop exhausted N attempts,
  here are the unresolved blockers, here is the PR" — the human enters only at
  the boundary the operator configured.

## Impact

- **Affected specs (new):** `autonomous-review-loop`.
- **Composes (does not modify) existing changes:** `add-self-heal-cowork`
  (interactive sibling — this is its unattended counterpart, same "never
  auto-merge a PHI/deny change" floor), `add-graduated-autonomy-tier2`
  (per-class autonomy — this adds the orthogonal per-repo axis),
  `swap-deliver-ado-to-github` (provides the real PR object under review),
  `add-teaching-signal-feedback` (a converged loop becomes precedent),
  `add-bundle-ci-enforcement` (the deterministic, orchestrator-independent
  required-check floor this loop runs above — a PR passes the CI bundle gate
  before the loop's richer LLM verdict and remediation apply).
- **Affected code:** `apps/orchestrator/` (new `review_loop.py`,
  `repo_autonomy.py`; edits to `_pipeline_stages.py` deliver dispatch and
  `main.py` endpoints), `.github/agents/` (codegen remediation mode,
  review-scan verdict shape, new `review-loop-controller` persona),
  `.github/hooks/` (PR-opened trigger), `apps/ledger-insights-ui/` (new page +
  autonomy panel), `apps/decision-ledger-mcp/` (new `review_remediation` /
  `loop_converged` / `loop_escalated` runtime kinds).
- **Config:** new `config/repo_autonomy.yaml.example` (customer-neutral),
  `.gitignore` the activated filename, `config/README.md` bootstrap table.
- **Honest limits carried into every artifact:** autonomous merge is bounded
  and repo-scoped; PHI/auth/deny rules are never inside the autonomous envelope;
  model variance (the reason GitHub can't promise this) is *contained* by the
  attempt bound + escalation, not *solved* — the loop degrades to a human, it
  never degrades to an unreviewed merge.
