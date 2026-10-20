# Demo Run-of-Show — Governed Agentic SDLC

**Audience:** payer / PBM engineering + compliance leadership
**Duration:** 20 min demo + Q&A
**Primary artifact:** `docs/briefing-deck.html` (20 slides)
**Live stack:** verified up — all four routes HTTP 200, ledger proxy returning real entries

---

## Honesty ledger (read this before you narrate anything)

Per repo discipline, every artifact below is classified. Do not blur these.

| Artifact | Classification |
|---|---|
| Decisions / runs / telemetry / compliance views | **Live app, seeded historical data** (newest entry 2026-08-19) |
| 340 ledger entries, 58 runs, 64 PHI cards | **Verified live read** from Cosmos via MCP |
| Branch protection, required checks bound to app_id 15368 | **Verified live** (GitHub API) |
| `autonomous-review-loop.yml` agent-PR trigger | **Verified live** — green on 3 PRs |
| Live LLM (own AOAI, keyless MI, real cost) | **Verified live** |
| Merge authorization CAS + patch attestation | **Implemented + tested, NOT wired to GitHub** |
| Stages running as agentic workflows (6c) | **Not started** — 0/8 |
| `accuracy_score` | **Never measured** — not zero. Say it that way. |

If asked something not on this list: "I don't know, I'll verify and come back."
That answer is worth more here than a confident paint-over.

---

## Run order

### 1. Open cold — the question (2 min)
Deck slide 1: *"A question your compliance function cannot answer today."*

> "Six months from now, an auditor asks: which AI agent made this change, under
> which rule, approved by whom. Most orgs cannot answer that. Not because they
> were careless — because nothing recorded it at the time."

Do **not** open the app yet. Let the question sit.

### 2. Four planes (2 min)
Deck slides 2–4. Standards / Pipeline / Ledger+Doctor / Agent HQ.
One line each. Do not go deep — the app does the work.

### 3. The ledger, live (5 min) — **the hero beat**
Tab B → `/decisions`

- **340 decisions across 58 runs.** Every row carries an actor.
- Actors are mixed and real: `development-principal`, `autopilot:team-cardiology`,
  `operator@dashboard`, `idan@demo`. Human vs. agent is recorded **at write time**,
  never inferred afterward.
- Class distribution is real: scope-resolution 96, sla-binding 70,
  **phi-classification 64**, identifier-format 35, auth-policy 34, data-retention 33.
- Open a PHI card. **This is the beat that lands.**
  > "The agent stopped here. PHI is an invariant class. Autopilot does not get to
  > decide it — it opens a gate and waits for a human. That is not the system
  > failing. That is the gate holding."
- Show the bundle citation on the entry: rule ID + version.

**Say out loud:** "This is seeded history, not live telemetry."

### 4. Where GitHub stops (4 min) — **the new beat**
No app needed. This is the differentiation, and it is sourced.

GitHub Agentic Workflows already ship the safe **execution** substrate — verified
in real source (`pr-doc-tests-check.md`, octodemo bootstrap, 30+ repos):

- agent job runs `permissions: read` — cannot write anything directly
- declares a **typed, capped output**: `safe-outputs: submit-pull-request-review: max: 1`,
  materialized by a separate privileged step
- deny-by-default egress: `network: allowed: [defaults, node]`
- tracked `.md` compiled to `.lock.yml` — reviewable, diffable, CODEOWNED

> "That is real, and it is more than most vendors have."

**Then the turn:**

> "What it does not give you is a governed *policy*. The reviewer's rules are
> English prose inside the prompt — 'high priority', 'tests are nice-to-have but
> not critical.' Un-versioned. No rule ID. No bundle citation. No ledger entry.
> No committee. And a pull request can edit that prose — and the diff looks like
> a documentation tweak."

> "For a regulated payer, a reviewer whose rules are not versioned is not an
> audit artifact. That is the layer we add."

### 5. The honesty arc (4 min) — **do not skip this**
Deck slides 12–18. This is what earns the room.

- **"What we got wrong"** — keep as-is.
- **"Identity not enforced end-to-end"** — *update*: attestation now derives
  authorship from provenance, never from PR opener. Transplant attack (agent patch
  cherry-picked into a human-opened PR) **defeated by execution**, not by unit test.
  Still not wired to a live GitHub ref — that is per-customer, on their delivery repo.
- **"Delivery not wired for every path"** — *update*: live LLM is wired now
  (own AOAI, keyless managed identity, real runs, real cost).
- **"Precedent is thin"** — **leave it standing.** Still true.
- **`accuracy_score`** — zero on all 340 entries because nothing writes it yet.
  We report **"never measured,"** not 0.0. An operator control that lies about
  its own strength is the exact failure mode this project keeps finding in itself.

### 6. Close — the follow-up question (2 min)
Deck slides 19–20: *"Ask every vendor this follow-up"* / *"Judge us on one query."*

Add the new one:

> **"Can a pull request edit the rule that judges it?"**

That question now has a demonstrated, sourced example behind it.

---

## Tabs to open, in order

- Tab A — `https://ca-ledger-ui-vnet.thankfulflower-0a94d0d3.eastus2.azurecontainerapps.io/runs`
- Tab B — `.../decisions`  ← **hero tab**
- Tab C — `.../telemetry`
- Tab D — `.../compliance`
- Tab E — `docs/briefing-deck.html` (local file)
- Tab F — GitHub branch protection API output (for the enforcement claim)

---

## Landmines

- **Do not** claim stages run on agentic workflows. 6c is 0/8.
- **Do not** call seeded ledger data live telemetry.
- **Do not** say `accuracy_score` is 0 — say never measured.
- **Do not** demo Thomas's repo. Access unverified; exact repo name unrecoverable
  from the transcript. The architectural insight is already in section 4 and needs
  no live repo.
- **Do not** promise a delivery-target branch-protection config as shipped. It is
  documented + verifiable (`scan_ref_protection`), applied per customer.
