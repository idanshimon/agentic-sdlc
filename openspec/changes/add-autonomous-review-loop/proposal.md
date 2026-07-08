# Proposal: autonomous review→remediate→re-review loop (Dark-Factory review)

> **Status:** DRAFT (2026-07-08)
> **Capability:** autonomous-review-loop (NEW)
> **Author:** Idan Shimon
> **Motivating engagement:** CVS Health Innovation Lab, AI SDLC deep dive
>   (2026-07-08). The customer (a Principal Architect who already owns the
>   four-plane concept) named exactly one frontier his org has not solved and
>   wants by EOY: an autonomous **"dark factory"** where agents review agents'
>   pull requests, the human-in-the-loop review bottleneck is removed, and a
>   rejected PR causes the coding agent to **pick up the rejection comment and
>   come back with an approved method** — all **without relaxing standards**.
>   GitHub's own field engineers confirmed on the call that closing this loop
>   is not on a committed roadmap and is blocked on model reliability. This is
>   the capability that lets the reference design *show it is possible on
>   GitHub as an engine*.

## Why

The reference design already has every ingredient of a governed loop **except
the wire that closes it autonomously**:

- `review-scan.agent.md` produces `status: FAIL` with per-blocker bundle-rule
  citations — but nothing feeds that failure **back** to codegen. It is
  reject-and-stop, not reject→fix→re-review.
- `codegen.agent.md` generates from an architecture proposal — but has no
  entry path that takes a *review verdict* as its input and remediates against
  it.
- `swap-deliver-ado-to-github` opens a **real** GitHub PR (Git Data API, no
  fakes) — so a real PR object exists to be reviewed, but the review that runs
  today is pipeline-internal, not triggered by an external **Coding Agent** PR.
- `add-self-heal-cowork` builds a reject→fix loop but its **core invariant is
  the opposite of what is needed here**: every heal is human-invoked and every
  action requires explicit per-action human approval. It is the *co-pilot*
  loop. Bobu's ask is the *autopilot* loop.
- `add-graduated-autonomy-tier2` governs autonomy **per ambiguity-class** at
  the resolver gate — but there is no **per-repository** autonomy tier that
  decides whether a given repo may run review→merge with no human at all.

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
the customer has decided it is safe*, and every hop is a ledger entry.

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
  bound** (`REVIEW_LOOP_MAX_ATTEMPTS`, default 3) and a **cost ceiling**
  (reuses the model-policy cost-ceiling seam from the config plane).
- Convergence (PASS) or exhaustion (still FAIL after N) are both terminal and
  both audited. Exhaustion **always escalates to a human** — it never silently
  merges and never loops unbounded.

### 3. Per-repo autonomy tier (the "move the dial" control Bobu asked for)

- A new authorable config object `config/repo_autonomy.yaml` →
  `apps/orchestrator/repo_autonomy.py`, mirroring the shipped opt-in-loader +
  governance-teeth pattern (`org_model.py`, `autonomy.py`, `model_policy.py`).
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
  forces escalation. Same `InvariantUnlockError` shape as autonomy invariants.

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
  the boundary the customer chose.

## Impact

- **Affected specs (new):** `autonomous-review-loop`.
- **Composes (does not modify) existing changes:** `add-self-heal-cowork`
  (interactive sibling — this is its unattended counterpart, same "never
  auto-merge a PHI/deny change" floor), `add-graduated-autonomy-tier2`
  (per-class autonomy — this adds the orthogonal per-repo axis),
  `swap-deliver-ado-to-github` (provides the real PR object under review),
  `add-teaching-signal-feedback` (a converged loop becomes precedent).
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
