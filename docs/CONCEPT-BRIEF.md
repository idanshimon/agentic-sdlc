# Concept Brief — Governed AI Development, as an operating model
_Customer-facing. For a COE / AI-center leader at an HLS enterprise. One read, ~5 min._
_Working name deferred. Substrate referred to here as "the Decision Record."_

---

## The problem you actually have

You are being asked to set a strategic direction for how your organization
develops software WITH AI. Not a tool decision — a governance decision. Because
the moment your teams adopt Copilot, coding agents, and PRD-to-PR pipelines, you
inherit a question your compliance function cannot answer today:

> "An AI agent made a decision that shipped to production. Which policy governed
> that decision, who approved it, what did it cost, and can you prove it?"

Your existing stack tells you WHAT happened. GitHub audit shows the PR. Purview
shows the data lineage. Foundry shows the model usage and spend. None of them
capture WHY the AI chose the path it did, bound to the specific version of YOUR
policy that was in force at that moment. That gap is where shadow-AI risk lives,
and it grows with every team that adopts.

## The idea in one sentence

A governed operating model for AI-assisted development: your standards become
versioned code, every AI decision writes an auditable record of its reasoning
bound to the rule that governed it, the cost of that decision is attributed to
the team that made it, and a drift-watcher proposes updates to your rules as the
system learns — all configured by you, running on your Azure.

## How it is shaped — two planes

**Data plane** — where AI does the work. A PRD-to-PR pipeline, IDE Copilot,
coding agents, chat bridges. This is swappable. Bring your own. If you have a
codegen approach you like, keep it — the value is not here.

**Control plane** — how you govern it. Four capabilities:

1. **Standards as code.** Each department authors its own rules as versioned,
   PR-reviewed policy — not a wiki, not tribal knowledge. Changing a rule is a
   pull request with a required reviewer roster. PHI rules are hard-locked.

2. **The Decision Record.** Every meaningful AI decision — from the pipeline,
   from an IDE session, from a coding agent — writes one immutable entry:
   what was decided, the full rationale, the exact policy rule that governed it,
   the human or agent identity behind it, the PHI classification, the model used,
   and the cost. One query surface across every AI surface. This is the substrate
   compliance reads. It is the point of the whole system.

3. **Cost economics.** Cost is attributed per DECISION, not per token, and rolled
   up to the team and cost-center that owns it — in your accounting vocabulary,
   not ours. The hard-savings line and the cost-avoidance line map to categories
   your CFO already uses.

4. **The Drift Doctor.** Reads the Decision Record continuously and watches for
   five signals — autopilot rejections climbing, cost per decision climbing,
   ambiguity classes with no governing rule, unused rules, PHI-classification
   violations. For each it either applies a fix WITHIN a policy envelope you
   defined, or opens a standards-change PR for your committee. It never relaxes a
   PHI rule on its own. Ever.

## What you configure — this is the product

The system is not a fixed demo. It is a surface where YOU instantiate your
governed operating model, without writing code:

- **Your organization** — departments, teams, cost centers, reviewer rosters,
  and the mapping to your Entra/M365 identities.
- **Your standards** — author and version your own rules per department.
- **Your autonomy policy** — for each class of decision, per team, you set how
  much you trust AI: always gate to a human, autopilot above a confidence
  threshold, or full autopilot. PHI-classification and auth-policy are locked to
  human gate and cannot be opened. This matrix IS your AI-adoption strategy,
  expressed as configuration.
- **Your model policy** — which models are approved, which are banned, which are
  cleared for PHI-adjacent work, how they route per stage, and your cost ceilings.

## The one thing to judge us on

Forget the pipeline. Forget the dashboard. The acceptance test is a single query:

> "Show me every AI decision made on PHI-classified data in the last 30 days —
> the rule that governed each one, whether a human or an agent decided, and what
> it cost."

If that returns complete, real, cross-surface rows, you have a governed AI
operating model. If it can't, you have a demo. Everything else in this system
exists to make that query true.

## How it is delivered

An accelerator you own and adapt, that assembles Azure-native primitives you
already trust — Entra for identity, Foundry for models, GitHub for standards
PRs, APIM as the gateway, and your existing observability as substrate it reads
and writes. It pulls Azure consumption; it does not compete with your platform.
Your platform team sees an integration they own, not a rival control plane. Your
COE sets the direction. Your developers get velocity with guardrails built in,
and their IDE stays exactly where it is.

## What is real today vs. what is roadmap

Real: the pipeline, the Decision Record with rationale + policy binding + cost +
identity, the standards-as-code loop with PR review, the PHI hard-lock validator,
and a working config surface for standards and autonomy. Roadmap, and documented
honestly as such: full cross-surface connectors beyond the pipeline, chargeback
vocabulary mapping, and live-LLM rationale composition (today's is deterministic).
We show you the openspec proposals so you can read exactly what is coming.

---

_Positioning discipline: this is an accelerator, not a product. You adopt and
adapt it. If you don't take it verbatim, the concept — control plane over data
plane, decisions as the system of record — transfers to whatever you build._
