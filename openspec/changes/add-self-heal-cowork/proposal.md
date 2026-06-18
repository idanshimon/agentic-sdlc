# Proposal: gate-triggered self-healing cowork sessions

> **Status:** DRAFT (2026-06-17)
> **Capability:** self-heal-cowork
> **Related:**
>   - `add-pipeline-doctor` — the SCHEDULED-BATCH sibling. That Doctor is a
>     Container Job that runs hourly, reads the ledger unattended, and opens
>     standards-change PRs for drift. THIS change is its INTERACTIVE,
>     HUMAN-INVOKED counterpart. They share the envelope/bounds concept and
>     the "Doctor never auto-merges" invariant, but differ on trigger model
>     (cron vs. gate), UX (none vs. streaming cowork session), and human
>     relationship (notify-after vs. decide-together). Neither replaces the
>     other; they are two consumers of the same ledger signal.
>   - `add-context-aware-agent-assistant` — the read-only AssistantPanel this
>     change extends into an ACTION-capable cowork surface. The standing
>     boundary "AssistantPanel MUST NOT write to the ledger" is deliberately
>     and explicitly relaxed for heal sessions, gated behind human approval.
>   - `master-v07-four-plane-architecture` — this is the Ledger+Doctor plane
>     (decides) handing off to the Agent HQ runtime plane (executes).
>   - `add-teaching-signal-feedback` — heal decisions become precedent the
>     same way teaching signals do; a heal that worked is a positive precedent
>     that lets the next identical failure auto-heal within bounds.

## Why

Today the Decision Ledger is a **recorder**. It watches the pipeline run and
writes down what happened — decisions, costs, bundle refs, prompt chains.
It is passive. Every plane *reads* it (compliance audits, finance reviews,
the operator browses), but nothing closes the loop back into the pipeline
except the scheduled `add-pipeline-doctor` daemon, which acts unattended and
notifies after the fact.

What is missing is the thing that makes human+agent collaboration actually
work the way it works in a coding-agent session: a **shared working state
both sides read and take turns acting on, in real time, with the human in
the loop.** In a coding-agent CLI the shared state is the working tree. Here,
the natural equivalent is the ledger — it already holds the decisions, the
precedents, the costs, the failures. Make it the substrate of an interactive
heal session and it stops being an audit log and becomes a **control plane**.

The operator watching a pipeline run sees decisions, gates, costs, failures
stream by and currently can only: approve a gate, or walk away. They cannot
say "this codegen output is broken, heal it" and cowork with an agent to fix
it on the spot. That is the gap.

### The reframe in one line

The ledger becomes the shared memory a human and a Doctor agent cowork over
to heal the pipeline — invoked at a gate or at end-of-run, by human choice,
never as a background watcher.

## What changes

### Trigger model — gate-anchored, human-invoked (NOT a daemon)

A heal session is opened by the human, at one of two moments:

1. **At any gate** — the resolver gate and the design-review gate already
   pause the pipeline for a human decision. A new "Heal / cowork" affordance
   on the gate panel lets the operator open a heal session instead of (or
   before) approving. Use case: "the assessor surfaced 7 cards but card 3 is
   wrong because the PRD section it cites is stale — let's fix the prompt
   before I approve."

2. **At end-of-run** — when a run reaches `completed` or `failed`, a
   "Review & heal" affordance opens a session scoped to the whole run. Use
   case: "this run completed but the codegen tests are red — heal it."

There is NO scheduled trigger, NO background watcher, NO polling. The session
exists only when a human opens it. This is the load-bearing distinction from
`add-pipeline-doctor`.

### The heal loop

```
SIGNAL     A failure/drift the human points at: red tests, blocked scan,
           a wrong gating card, a prompt regression, a cost spike.
   │       Surfaced FROM the ledger + run state the human is already looking at.
   ▼
DIAGNOSE   The Cowork agent (Foundry-grade) reads ledger + run state +
           GitHub state, proposes a heal, and CITES PRECEDENT from the ledger
           ("3 similar failures, here's the pattern that fixed them").
           Streams its reasoning into the session panel.
   ▼
DECIDE     The human, in-session: approve / "show me the diff" / "no, the
           real fix is the prompt not the code" / take over entirely. This
           is the cowork turn-taking. Every turn is a ledger write.
   ▼
ACT        The heal lands WHERE THE CODE LIVES — GitHub. The Cowork agent
           does not edit files itself. It hands the approved heal to the
           EXECUTOR (the GitHub Copilot coding agent) as an assigned issue/PR,
           OR re-runs a stage, OR bumps a prompt/bundle version via PR.
   ▼
RECORD     The ledger pins the full chain: who decided (human or agent), why,
           cost, the precedent cited, the PR/branch the heal landed in.
   ▼
LEARN      The heal becomes precedent. Next time that exact signal appears,
           graduated autonomy can auto-propose (or, within envelope bounds,
           auto-apply) the same heal — surfacing it at the gate for one-click
           human confirmation instead of a from-scratch diagnosis.
```

### Two agents, two planes, ledger bridges them

This change deliberately splits the work across two runtimes, resolving the
"GitHub Copilot vs Foundry" question by giving each the job it is best at:

| Role | Runtime | Responsibility | Writes |
|---|---|---|---|
| **Cowork brain** | Foundry-registered agent (governance-grade, one A365 identity, the compliance-grade runtime per AGENTS.md) | Diagnoses, cites precedent, holds the conversation, decides WHAT to heal. Lives in the dashboard heal-session panel. | `runtime` ledger entries (`heal_proposed`, `heal_decided`) |
| **Executor** | GitHub Copilot coding agent (native to the repo where code lives and breathes) | Does the actual code surgery: opens the branch, edits files, the Action runs, reports back. | The PR/commit in GitHub; a `heal_executed` ledger entry on completion |

The ledger is the handoff contract. The Cowork agent records decided intent;
the Executor does the work and reports back; the ledger pins both halves.
This maps exactly onto the four-plane model: Ledger+Doctor plane decides,
Agent HQ runtime plane executes.

### The "cowork session" surface

A new interactive surface, the Heal Session — NOT a form, a session you are
in. Built by extending the existing `AssistantPanel` (the floating Sparkles /
⌘K slide-over) from read-only into action-capable when scoped to a heal:

- The Cowork agent opens with a streaming diagnosis + recommendation.
- The human can interrupt, redirect, ask for the diff, or take over.
- It shows the heal (the proposed PR diff, the prompt change, the re-run plan)
  BEFORE anything lands.
- On approval it dispatches to the Executor and streams progress
  (`assistant.message_delta`-style, reusing the run-stream SSE plumbing).
- Every turn writes to the ledger.
- A one-click "open in GitHub" drops the human into the real PR to take the
  wheel at any point.

### Heal action types (the bounded surgery the Cowork agent can propose)

| Action | What it does | Bound |
|---|---|---|
| `reprompt_stage` | Bump a prompt-library version + re-run the stage | Prompt PR + human approve; never silent |
| `rerun_stage` | Re-run a failed stage with the same inputs | Idempotent; safe; in-envelope auto-allowed |
| `assign_code_heal` | Hand a code fix to the GitHub Copilot coding agent as an issue/PR | Always opens a PR; human/CODEOWNERS merge |
| `bump_bundle_rule` | Propose a standards-bundle change | Routes through `add-pipeline-doctor`'s PROPOSE-CHANGE path; committee merges |
| `adjust_autopilot` | Tune a confidence threshold | Same finops envelope bounds as the scheduled Doctor; PHI never |

PHI-class and explicit-deny rules can NEVER be auto-healed — the same hard
validator boundary as `add-pipeline-doctor`. A heal that touches a PHI rule
is always escalated to a human-authored decision, even if machine-proposed.

## Why this design (the constraints)

- **Human-invoked, gate-anchored, never a daemon.** The whole point is
  coworking *with* the human at a moment they chose. A background self-healer
  that acts unattended is the existing scheduled Doctor; this is its opposite
  and they coexist.

- **The Cowork agent decides; it does NOT do code surgery.** Code heals land
  via the GitHub coding agent (a real PR in the repo) because that is where
  the code lives and where the existing review/CI/merge governance already
  applies. We do not remote-control GitHub over a REST API; we let GitHub's
  own agent do what it is best at.

- **Action capability is gated behind human approval, per-action.** This
  change crosses the "AssistantPanel is read-only" line ON PURPOSE, but every
  write-causing action requires an explicit in-session human approval — the
  same human-in-the-loop discipline the gates already enforce. The SDK-level
  `onPermissionRequest` handler is the enforcement point.

- **Every heal is ledger-pinned and becomes precedent.** A heal is just a new
  decision class in the ledger. It carries actor (human or agent), rationale,
  cost, precedent_refs, and the PR it landed in — identical schema to every
  other ledger entry, so the audit story and the learning loop are unchanged.

## Risks and rollback

| Risk | Mitigation | Rollback |
|---|---|---|
| Cowork agent proposes a wrong heal | Human approves every action; diff shown before land | Don't approve; or revert the PR |
| Action capability abused / runaway | Per-action human approval; no auto-apply outside envelopes; PHI hard-blocked | Feature flag `heal.actions_enabled=false` → falls back to read-only assistant |
| GitHub coding agent makes a bad fix | Lands as a PR, not a direct commit; CODEOWNERS + CI gate it | Close the PR; the run is unaffected |
| Foundry cowork agent + GitHub executor disagree / desync | Ledger is the single source of truth for handoff state; executor reports back before `heal_executed` is written | Session can be abandoned; no partial state in the pipeline |
| Heal session writes pollute the ledger | Heal entries are a typed class, filterable; same retention/audit as all entries | N/A — they ARE the audit trail |

## Out of scope (filed separately or deferred)

- The scheduled/unattended drift remediation — that IS `add-pipeline-doctor`,
  already speced. This change does not touch it.
- Auto-apply of code heals without a human in the loop — never, by design.
- A standalone heal CLI — the surface is the dashboard session; CLI is a
  possible future.
- Multi-run batch healing — one session heals one run (or one gate) at a time
  in v1.

## Test targets

- Unit: heal action validation (PHI block, deny-rule block, per-action
  approval required), ledger entry construction for each heal type, precedent
  citation lookup.
- Integration: a synthetic failed run → open heal session → diagnose →
  approve a `rerun_stage` → verify ledger gets `heal_proposed` +
  `heal_decided` + `heal_executed` chain.
- E2E: a real failed-codegen run on the live deploy → open heal session →
  `assign_code_heal` → verify a real PR opens on the repo and the ledger pins
  the chain.

## The thinnest first slice (what we build to prove the loop)

ONE signal class: **a failing pipeline stage (codegen produces code, tests go
red).** Chosen because it is concrete, happens constantly, and the heal is a
PR — which proves the entire GitHub-native execution path in a single slice.

The slice, end to end:
1. A run completes with red codegen tests (the SIGNAL, visible in the ledger).
2. Operator clicks "Review & heal" at end-of-run.
3. Cowork agent diagnoses, cites any precedent, proposes `assign_code_heal`.
4. Human approves.
5. A real PR opens on the repo via the GitHub coding agent.
6. The ledger pins `heal_proposed` → `heal_decided` → `heal_executed` with the
   PR URL.

If that slice works, the loop is proven and the other action types and the
gate-anchored (mid-run) trigger are incremental.
