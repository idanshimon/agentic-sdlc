# v0.7 demo script — pipeline-centric walkthrough

> **Assistant:** customer-visible reading layer over the ledger, available on every tab via the floating Sparkles button or ⌘K.
> **Audience:** architects + engineering leaders evaluating governed agentic SDLC.
> **Time:** 10 minutes click-by-click + 5 minutes Q&A.
> **Pre-req:** all four planes deployed; URLs filled in at the bottom of this doc.

This script is **pipeline-centric, not speaker-centric**. It works with any room composition.

---

## Step 0 — Tabs to open before you start

Three tabs, in this order:

1. **Tab A — Ledger Insights UI** (the demo run): `<LEDGER_UI_URL>/`
2. **Tab B — Telemetry view** (cost-per-decision + class drift): `<LEDGER_UI_URL>/telemetry`
3. **Tab C — explainer** (offline backup, dark theme, 4-plane diagram): open `docs/explainer.html` locally as a file:// URL

Optional Tab D for Q&A: standards-bundles directory in GitHub (`https://github.com/idanshimon/agentic-sdlc/tree/main/standards-bundles`).

The AgentAssistant slide-over (floating Sparkles button, or ⌘K) is wired on every tab in Tab A and Tab B. It reads whatever page you are on and answers from real run state. See Step 9.

---

## Step 1 — Frame the problem in 60 seconds

**Action:** Don't click anything. Talk over Tab C's hero diagram.

**Verbal:**

> Most engineers don't live in VS Code. They work in Slack, Teams, Linear,
> Boards, or a portal. A few do work in VS Code and want IDE Copilot. Both
> populations need to ship governed code. The hard problem is that today's
> AI agents are invisible to compliance. We see what landed in main; we
> don't see *why* the agent picked a path.
>
> v0.7 of the agentic SDLC reference design closes that gap with four
> planes. Standards bundles author the rules. The pipeline runs heavy
> work — PRD-to-PR. Agent HQ runtime lanes — coding agent, IDE Copilot,
> chat bridges — handle the medium and light lanes. Everything writes to
> a single Decision Ledger. The Pipeline Doctor reads it back to detect
> drift and propose changes.

---

## Step 2 — Drop a PRD into the orchestrator

**Action:** Tab A. Click "New Run". Drop `samples/prds/patient-vitals-streaming.txt` (in repo). Choose mode = **autopilot**.

**Verbal:**

> This is a vitals-streaming PRD asking for a Patient Vitals Streaming API.
> It mentions PHI without classification, and mentions third-party SaaS
> bedside-monitoring vendors with TBD egress policy. Two specific traps.

---

## Step 3 — Watch the 9 stages fire

**Action:** Stay on Tab A. The pipeline graph animates.

**Verbal (point as each stage completes):**

- **Ingest** — parse the PRD. Cost ~$0.001.
- **Assessor** — surface ambiguities as typed cards. Cost ~$0.027. ~6-7 cards.
- **Resolver** — gate. In autopilot mode, the gate uses Decision Ledger
  precedent + a confidence threshold per ambiguity class. PHI cards never
  autopilot — they always gate to a human.
- **Architect** — propose service topology + data flows + auth model.
- **Design Review** — gate 2 (auto + escalate).
- **Test Plan** — TDD scaffolding.
- **CodeGen** — write code. Cost ~$0.50 per stage on average. By far the
  most expensive stage.
- **Review-Scan** — gate 3, fail-hard. SBOM, SAST, secret scan, PHI scan.
- **Deliver** — open a GH PR with `decisions.md` in the body.

---

## Step 4 — The decision card pattern

**Action:** Click on the auth-policy card.

**Verbal:**

> This card surfaces the third-party SaaS / Grammarly-style egress problem
> in clinical clothing. The Assessor gives two options each citing
> `security/v0.1.0/AUTH-001`. The recommended option is OAuth2 with a
> Vendor Registry. Hit Accept-Recommended, the decision lands in the ledger
> immediately, attributed to the user's M365 identity, with bundle_refs
> populated.

---

## Step 5 — Show the Ledger Insights view (Tab B)

**Action:** Switch to Tab B (`/telemetry`). Three sub-views.

**Verbal:**

- **Decision Ledger feed (left)** — every entry from this run. Note the
  `bundle_refs` chips: each decision is grounded in a specific rule. This
  is the audit substrate compliance reads.
- **Cost dashboard (middle)** — per-stage cost, apportioned to teams.
  Token spend = hard savings line. Cost-per-decision blast radius =
  cost-avoidance line. Map directly to your CFO's IT spend categorization.
- **Class drift (right)** — distribution of ambiguity classes over time.
  Watch for spikes in unexplored classes — that's where the next bundle
  rule needs to be written.

---

## Step 6 — The fourth plane — Pipeline Doctor

**Action:** Show Tab C's "Pipeline Doctor" pane. No live click — explain.

**Verbal:**

> Pipeline Doctor runs hourly in a Container Job. It reads the ledger and
> detects five kinds of drift: autopilot rejection rate climbing, cost
> per decision climbing, class drift unprecedented, bundle rules unused,
> PHI class violations.
>
> For each signal it does ONE of two things:
> A) Apply an auto-fix WITHIN the bundle's declared envelope. Writes a
>    runtime ledger entry of kind `auto_fix`. Notifies a Teams channel.
> B) Open a PR on `standards-bundles/<dept>` with an Architecture
>    Decision Record. The committee decides; the Doctor never decides
>    rule changes alone.
>
> PHI rules are NEVER auto-fixed. Hard-coded in the validator.
> Defense in depth: even if a bundle's envelope.yaml is mis-edited to
> permit it, the validator refuses.

---

## Step 7 — The Agent HQ runtime lane

**Action:** Show Tab C's hooks pane.

**Verbal:**

> Engineers who don't use the orchestrator pipeline still write to the
> ledger. Five lifecycle hooks fire in every Copilot session — cloud
> agent, CLI, VS Code. The pre-tool-use hook runs the same PHI classifier
> the orchestrator's review-scan stage uses. Local fast-path catches
> raw MRN even when the MCP server is down.
>
> Same ledger, three writers, one query surface for compliance.

---

## Step 8 — Standards-change loop

**Action:** Open Tab D (GitHub). Show `standards-bundles/security/v0.1.0/`.

**Verbal:**

> Every department owns its bundle. Privacy DPO + Security Lead + Legal
> are required reviewers for any HIGH-blast change. Architect can't
> unilaterally relax a PHI rule. The standards-change-agent triages
> the PR, drafts an ADR, assigns reviewers, blocks merge until quorum.
> Five percent canary rollout for seven days; auto-revert if metrics
> regress. Every merge writes a `meta` ledger entry.

---

## Step 9 — Context-aware AgentAssistant

**Action:** Stay on Tab A's run-detail page. There should be 5 awaiting-gate decision cards on screen. Click the floating Sparkles button at the bottom-right, or hit ⌘K. A slide-over opens.

**Verbal:**

> Notice the chip suggestions at the top of the panel. They are not static. Because this run is awaiting gate, the first chip reads `What do you recommend for these cards?`. If I had opened the assistant from the dashboard, the chip would instead read `N runs awaiting gate, what should I clear first?` with N counted from the actual portfolio.

**Action:** Click the recommendation chip, or type `what do you recommend`. The reply appears.

**Verbal (point to the reply text):**

> The reply quotes this run's actual run id. Each of the 5 awaiting-gate decisions is listed verbatim with its `bundle_refs` chips, the same chips you saw in the cards. The cost so far is summed from the real ledger entries for this run. PHI-high count is from the same source. Nothing here is a template; the assistant read the run state and the run-scoped ledger entries and composed the reply from those.

**Action:** Switch to Tab A's dashboard. Open the assistant again. Type `summarize the portfolio`.

**Verbal:**

> Now the same assistant is reading a different shape: total runs, by_status breakdown, total cost across the portfolio, and citation density across the ledger. Same component, different context, different data source.

**Talking point:**

> This is grounded in real data, not pre-canned. The function that gathers context for the demo is `gatherContext()`. In production, that same snapshot is the system prompt sent to the orchestrator's chat agent; the LLM composes the reply. In v0.7 the demo is deterministic, so the composer is local. The contract is identical.

> v0.7 ships the deterministic stand-in. Live LLM integration is not promised in this release.

---

## Close — three sentences

> One: governance is the differentiator, not codegen quality. Two: every
> agent decision lands on the same audit substrate, regardless of
> runtime. Three: rules are versioned PRs with committee review, not
> tribal knowledge.

Ledger feed is the single source of truth. Everything else is a view of it.

---

## Q&A defenses

**"What if the engineer bypasses the hooks?"**
> Hooks are a client-side fast-path. Server-side review-scan stage in the
> orchestrator is the authoritative gate. If the engineer's hook config is
> tampered, code still passes through review-scan before merge.

**"Can Pipeline Doctor relax a PHI rule?"**
> No. Hard-coded in the validator. Even if you mis-edit an envelope.yaml
> to permit it, the validator refuses. The only path to relax a PHI rule
> is a committee-reviewed PR.

**"What about cross-runtime audit?"**
> GitHub's enterprise audit log captures `actor:Copilot` events with
> `agent_session_id`. We capture the same `agent_session_id` on every
> ledger entry from Agent HQ runtimes. Cross-reference is a SQL join.

**"What's the cost story?"**
> Token spend (hard savings) + blast-radius cost-avoidance per ambiguity.
> Categorize it into your CFO's existing IT spend buckets — don't import
> our value-deck vocabulary onto their P&L.

**"How much of this is real vs aspirational?"**
> All four planes have working code (62 unit tests passing, 0 failing).
> Decision Ledger writes are real. Pipeline Doctor envelope validator
> is real. PHI hook block is real. The pieces deliberately not-built-yet
> are documented in the openspec proposals so you can read what's coming.

---

## Demo URLs cheat strip

```
ORCH:    https://<orchestrator-fqdn>
UI:      https://<ledger-ui-fqdn>
MCP:     https://<ledger-mcp-fqdn>
COSMOS:  cosmos-agentic-<suffix>.documents.azure.com
ACR:     acragenticsdlc<suffix>.azurecr.io
RG:      rg-agentic-sdlc-v07-eastus2
SUB:     b3a032cf-f672-4071-b7c8-2bcbe087bbd0
GITHUB:  https://github.com/idanshimon/agentic-sdlc
```

URLs auto-fill on successful deploy via `deploy/scripts/01-*.sh` outputs.
Cross-check `/tmp/agentic-v07-deploy.json` for live values.
