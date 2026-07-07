# MVP Spec — Control Plane Orchestrator (working title)
_Configuration surface + concept scope for HLS enterprise adoption. Draft 1._

> Status: DRAFT for Idan review. Reshaped by a second-frontier pressure test
> (GPT-4.1, see `/tmp/pressure_test_concept.py` output + synthesis in chat).
> The pressure test pushed HARD against "new control plane" framing; this spec
> narrows the hero accordingly.

## 0. What this is (one paragraph)

A reference operating model + accelerator that lets an HLS enterprise stand up a
GOVERNED way to develop with AI. Two planes: a swappable DATA plane (where AI does
work — pipeline, IDE Copilot, coding agents) and a durable CONTROL plane (how you
govern it — standards-as-code, a decision record, cost economics, drift doctor).
The customer adapts it; if they don't take it verbatim, the concept still transfers.

## 1. The hero, narrowed (post-pressure-test)

The defensible wedge is NOT "we built a control plane." Microsoft is building
control-plane pieces (Purview, Foundry observability, Agent 365, GitHub governance).
The ONE thing nothing else does today:

  **Enforceable, structured decision rationale — bound to a versioned policy rule,
  at a known cost, queryable across every AI surface, at the moment of decision.**

Everything else in the MVP exists to make that hero real and adoptable. If a
capability doesn't feed the hero, it's Tier 3 or cut.

## 2. Concept framing for the customer

CONTROL PLANE (durable IP)
  Standards-as-code  →  Decision Record  →  Cost Economics  →  Drift Doctor
       (rules)            (the WHY)          (the $)            (improve rules)
                              ▲
DATA PLANE (swappable, bring-your-own)
  PRD→PR pipeline · IDE Copilot · coding agents · chat bridges
       │
       └── all write to the Decision Record via hooks/MCP

Buyer  = COE / AI-center leader (strategic direction for AI adoption)
User   = dev teams (velocity + guardrails; IDE stays home)
Gate   = platform + security team (they hold veto — see pressure-test §3)

## 3. MVP configuration surface

The product IS the config surface. A fixed demo shows one instance; the product
is what lets a COE instantiate THEIR governed AI operating model without code.

### Config objects (Tier 1 — adoptable floor)

Each is a versioned, PR-reviewed YAML object living in the customer's own repo,
rendered/edited through the dashboard's VersionedEditor (already built).

1. ORGANIZATION MODEL  `config/org.yaml`
   - departments[] (name, owner, reviewer roster by role)
   - teams[] (name, department, m365_group, cost_center)
   - identity: entra_tenant_id, approver RBAC mapping (who gates / who reviews)
   - WHY it feeds the hero: every Decision Record entry is attributed to a real
     identity + team from this model. No org model = anonymous decisions = no audit.

2. STANDARDS BUNDLES  `standards-bundles/<dept>/v<x.y.z>/rules.yaml`  (EXISTS, extend)
   - author your own departments' rules (today: 4 hardcoded → make authorable)
   - each rule: id, statement, blast_class (low/med/high), phi_locked (bool)
   - PINS.yaml controls which version is live per department
   - WHY it feeds the hero: the "under which policy" half of the wedge. A decision
     with no bundle_ref is unenforceable rationale = noise.

3. AUTONOMY MATRIX  `config/autonomy.yaml`   ← the COE leader's steering wheel
   - per (decision_class × team): gate | autopilot_above_threshold(t) | autopilot_always
   - phi-classification and auth-policy classes are HARD-LOCKED to gate (validator-
     enforced, cannot be config'd open — defense in depth)
   - WHY it feeds the hero: this is the single most COE-differentiating config.
     It's literally "set strategic direction for how much we trust AI, per class,
     per team." Nothing in Purview/GitHub expresses this.

4. MODEL POLICY  `config/models.yaml`
   - allowlist[] (approved model ids), denylist[]
   - per-stage routing (which model runs ingest/assessor/architect/codegen/...)
   - cost_ceiling_usd per run / per team / per month
   - phi_eligible[] (models cleared for PHI-adjacent stages — Kapil's hard req)
   - WHY it feeds the hero: the "at a known cost / by which model" columns of the
     record, and the compliance answer to "prove you didn't use an OSS model on PHI."

### Explicitly Tier 2 (fast-follow, NOT MVP)
   - economics chargeback vocabulary mapping (their accounting buckets)
   - connector registry (which AI surfaces write to the record — pipeline is default-on)
   - notification routing (Teams/Slack channels for Doctor signals)

### Explicitly Tier 3 (later)
   - record residency / retention, export to customer SIEM / Purview
   - canary rollout % + auto-revert windows for standards changes

## 4. Non-negotiable capability (the "cut this = dead" line)

Per the pressure test: without a **single, unified, actionable query surface that
returns WHAT + WHY + policy-version + cost + identity for any AI decision, across
all surfaces, drivable for compliance reporting or incident response**, this is
"config noise." That query surface — not the config, not the pipeline — is the MVP
acceptance test. Everything else can be thin.

MVP DONE = a COE leader configures org + standards + autonomy + models (no code),
runs a governed pipeline, and pulls one compliance-grade query:
"show me every AI decision on PHI-classified data last 30 days, the rule that
governed it, who/what decided, and what it cost" — and it returns real, complete,
cross-surface rows.

## 5. What the pressure test changed vs. draft-zero

- Narrowed hero from "control plane" → "enforceable rationale bound to policy."
- Demoted the 4 config objects from "the product" to "plumbing that feeds the query."
- Elevated the unified compliance query from implicit → THE acceptance test.
- Added the platform-team veto as a first-class stakeholder (was ignored).
- Flagged: overlap with Purview/Foundry is real; MVP must prove the 20% gap
  (structured rationale + policy-version binding) in the FIRST demo or it reads
  as redundant.

## 6. Open questions for Idan

- Delivery vehicle: accelerator/reference (Epic-safe, per territory knowledge) vs
  the pressure test's "make it an Azure-native extension" push. These conflict —
  see chat synthesis. Need a call before build.
- Name for the Decision Record substrate (candidates in chat).
- Which HLS customer is demo-zero — shapes whether org.yaml ships with a real
  department topology or a neutral one.
