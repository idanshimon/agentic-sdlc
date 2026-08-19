# Demo Runbook — Agentic Pipeline Reference Architecture

**Audience:** enterprise dev team + architecture leads, CISO, VP Eng
**Duration:** 18-22 min (12 min deck, 6 min live, buffer)
**Deck:** `docs/reference-architecture-demo.html` (press `N` for presenter notes, `?s=N` to jump)
**Live app:** http://localhost:3005

> All ledger data in this demo is **seeded sample data** for a fictional product
> called Meridian. Say that once, early. Never imply live telemetry.

---

## Before you present

```bash
cd apps/ledger-insights-ui && pnpm dev      # port 3005
open docs/reference-architecture-demo.html
```

Open three browser tabs in this order so you never fumble mid-demo:

1. `http://localhost:3005/decisions/graph`     — Decision Map
2. `http://localhost:3005/decisions/lineage`   — Precedent Lineage
3. `http://localhost:3005/decisions/runflow`   — Run Flow

Verify before the room fills: each canvas shows nodes, and the legend is
top-left. If a canvas is empty, the demo fallback did not load — restart the
dev server rather than presenting an empty graph.

---

## The scenario, in one paragraph

Meridian is a patient self-service portal built across three pipeline runs.
In run 1 a human lead sets four precedents. In run 2 agents reuse them
correctly on a new module. In run 3 an agent sets billing retention to
**3 years** when clinical policy is **7**. A human catches it, flags it, and
autopilot **pauses for that entire decision class**.

The point is not that the agent was wrong. Agents will be wrong. The point is
that the system noticed, recorded why, and narrowed its own authority.

---

## Live demo — 4 moves, 6 minutes

### Move 1 — "Which rule does the most work?" (Decision Map, ~90s)

Open `/decisions/graph`.

- 29 nodes, 44 edges, five edge kinds. Open the legend and read it aloud —
  **solid = cited or authored, dashed = inferred by the system.** That
  distinction is the whole trust model in one visual.
- Point at a hub: one rule node with many decisions hanging off it. Say:
  *"That is a policy earning its keep. If you retire it, this is your blast
  radius — you can see it before you change it, not after."*

### Move 2 — "Where did this answer come from?" (Precedent Lineage, ~90s)

Open `/decisions/lineage`.

- The hubs are human rulings. The fan below each is every later decision an
  agent resolved the same way.
- Click a node. The modal shows the rule reference in **monospace** and the
  prose in sans. Mention it once: *"machine-generated values are monospace,
  human-authored text is not — you can tell at a glance who produced what."*
- The headline: **one human decision, reused twice by agents.** That is the
  cost curve bending. The corpus makes the next decision cheaper.

### Move 3 — The catch (the hinge of the demo, ~2 min)

This is the moment the room remembers. Slow down.

- Go to `/decisions/runflow`, select **meridian-run-0003**.
- Find: `Billing data retention set to 3 years (SHORTER than clinical policy)`
- Then show the flag on it: `Flagged: billing retention must match 7y clinical
  policy, not 3y` — a human correction, linked to the exact decision.
- Then the consequence: `Paused autopilot for data-retention across Meridian`.

Say it plainly:

> "The agent got this wrong. It reused a pattern that did not apply. A human
> caught it in review — and the system did not just fix that one record. It
> withdrew autonomy for that entire decision class until a human re-authorises
> it. Autonomy is per-decision-class, and it is revocable."

### Move 4 — "Now ask it anything" (~60s)

Return to `/decisions`. Show that every one of these is a queryable record,
not a log line. Land the close:

> "Pick any agent decision from last quarter and ask why it was made. You
> should get the rule version, the human who approved it, and the precedent it
> reused — in one hop. That is the bar. Ask every vendor in this space for it."

---

## Questions you will get, and honest answers

**"Isn't this what GitHub Agentic Workflows already does?"**
Partly, and it is genuinely good. `gh-aw` (technical preview, Feb 2026) runs
agents **read-only** and routes every write through declared `safe-outputs`
executed by a separate permission-controlled job. That is real enforcement.
But safe-outputs controls **whether** a write happens. It does not record
**why** the decision was made, which rule version governed it, or what
precedent it reused. An auditor cannot accept "the agent had read-only
permissions" as evidence of *why* PHI was classified a given way.
Position it as a **fourth writer surface into the same ledger**, not a
competitor. Argue the record, not the permissions.

**"What is the developer overhead?"**
None that they type. The agent loads `AGENTS.md` plus its pinned bundle at
session start and writes its own entries. The developer reviews gating cards —
which is review work they were already doing, now with the reasoning attached.

**"What happens when the agent is wrong?"**
Show move 3 again. That is the answer.

**"Does this slow us down?"**
It gates by decision class, not by volume. Classes where agents have earned
trust run unattended; classes where they have not, stop. The gate narrows over
time in the places it should.

**"Can we see it fail?"**
Yes — and offer it. Slide 13 is the candour slide: a rewind feature shipped
disabled because its state had no consumer; a run-flow axis that meant two
different things; three graph views that shipped rendering completely empty
while the full test suite stayed green. Offering your own defects is the
cheapest credibility you can buy in a CISO room.

---

## What NOT to say

- Do not call the sample data real, or cite its counts as production metrics.
- Do not claim `gh-aw` is GA. It is technical preview.
- Do not say "template" or "sellable" about a pattern on synthetic data with
  no clinical validation. Say **reusable pattern**.
- Do not promise full automation. The honest promise is narrower: automate
  only what can be grounded, and show the source every time.
