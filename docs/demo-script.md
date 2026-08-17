# Demo script — governed agentic SDLC

**Mode:** live submit against the deployed v0.7 stack.
**Verified:** 2026-08-17 by driving the full cycle end to end via the live API.
**Reference run:** `f4e744c0-16a3-41bd-aabd-4687f5b129fd` (team `team-cardiology`).

Every number below was observed on the deployed system, not estimated. If you
re-run live, the numbers will differ — narrate what is on screen, not what is
written here.

---

## What this demo proves

A PRD enters. Every consequential decision is classified, gated, attributed to a
named actor, recorded with the alternatives that were rejected, and cited back to
a standards bundle. Code that violates a bundle rule does not ship.

The demo's strongest moment is a **failure**: the pipeline generates working code
and then blocks its own delivery on a PHI rule. That is the product.

---

## Pre-flight (do this before the room)

```bash
B=https://ca-orchestrator-vnet.thankfulflower-0a94d0d3.eastus2.azurecontainerapps.io
U=https://ca-ledger-ui-vnet.thankfulflower-0a94d0d3.eastus2.azurecontainerapps.io

curl -s -o /dev/null -w "orchestrator %{http_code}\n" "$B/api/runs"
curl -s -o /dev/null -w "ui           %{http_code}\n" "$U/decisions"
```

Both must return `200`. The orchestrator has no `/health` route — `/api/runs` is
the liveness check that actually exercises Cosmos.

**Known state as of 2026-08-17:** 50 prior runs, 311 decision rows.

---

## Act 1 — Submit a PRD (~1 min)

`prd` is a **file upload**, not a string. A string returns HTTP 422.

```bash
cat > /tmp/demo_prd.md <<'EOF'
# Patient Appointment Reminder Service

## Goal
Reduce no-show rates by reminding patients ahead of scheduled appointments.

## Requirements
- Send an SMS reminder 24 hours before each appointment.
- Log delivery status (sent, failed, opted-out) for operational reporting.
- Expose a REST endpoint to schedule and cancel reminders.
- Reminder content must not include diagnosis or treatment details.
- Retain delivery logs for operational auditing.
EOF

curl -s -X POST "$B/api/run" \
  -F "prd=@/tmp/demo_prd.md;type=text/markdown" \
  -F "team_id=team-cardiology" \
  -F "mode=manual"
```

**Observed:** run_id returned in **0.8 s**.

> Say: "That PRD is deliberately ordinary. Nobody wrote HIPAA in it. Watch what
> the system notices anyway."

---

## Act 2 — The assessor finds what the PRD left ambiguous (~30 s)

Poll `GET $B/api/runs/$R` until `status` is `awaiting_gate`.

**Observed:** `running → assessor → awaiting_gate` at the resolver in ~20 s,
**2,071 tokens, $0.0258**, and `contains_synthetic_output: false` — real model
output, not a stub.

Six cards, five gating:

| Class | Title |
|---|---|
| `phi-classification` | PHI Classification of Delivery Logs |
| `data-retention` | Delivery Log Retention Period |
| `auth-policy` | Opt-Out Handling Policy |
| `sla-binding` | SLA for SMS Delivery Attempt |
| `identifier-format` | Identifier Format for Patients |
| `naming-convention` | REST Endpoint Naming Convention (auto-deferred) |

Open the PHI card. It carries:

- `detail` — "It is unclear whether delivery logs contain PHI and must be handled per HIPAA §164.502."
- `prd_quote` — "Retain delivery logs for operational auditing."
- two options, each with `resolution`, `rationale`, `downstream_impact`, `recommended`
- `blast_radius_cost_usd: 350.00` vs `re_run_cost_usd: 0.0258`
- **`is_hard_gated: true`**

> Say: "Three hundred and fifty dollars to get this wrong downstream. Two and a
> half cents to re-run it now. That ratio is the whole argument."

> Say: "This card is hard-gated. Not because a human flagged it — because
> `phi-classification` is an invariant class. Autopilot cannot self-approve it."

---

## Act 3 — A human decides, and the record remembers why (~2 min)

```bash
curl -s -X POST "$B/api/runs/$R/approve" -H 'Content-Type: application/json' -d '{
  "card_id":"<phi card id>",
  "decision_kind":"accept",
  "option_index":0,
  "actor":"<your.name@example.org>",
  "confidence_source":"human",
  "approval_path":"individual"
}'
```

`decision_kind` must be one of `accept` | `swap` | `reject` | `auto-deferred`.

Resolve all six, then close the gate:

```bash
curl -s -X POST "$B/api/runs/$R/finalize" -H 'Content-Type: application/json' \
  -d '{"actor":"<your.name@example.org>","expected_gate_version":1}'
```

**Observed:** `gate_closed: true`, `decisions_count: 6`, `next_stage: architect`.

Now show the audit record:

```bash
curl -s "$B/api/compliance/decisions?team_id=team-cardiology&run_id=$R"
```

Each row carries the decision, the **`rejected_options` with their rationale**,
the actor and `actor_kind`, and a `gate_reason` that discriminates correctly:

- `phi-classification` → `invariant_class`
- `auth-policy` → `invariant_class`
- `data-retention`, `sla-binding`, `identifier-format` → `autonomy_tier`

> Say: "Six months from now, 'why did we pick MRN over phone number?' is
> answerable from the record — including the option we rejected and why."

---

## Act 4 — The pipeline builds, then blocks itself (~3 min)

After the gate closes the run proceeds unattended. It pauses once more at
**Gate 2 (Design Review)** — close it the same way with the current
`expected_gate_version` (read it from `pending_gate.version`; it was `3`).

**Observed stage progression, with real spend at each step:**

| Stage | Event | Cumulative |
|---|---|---|
| ingest | Spec-package built (449 chars) | — |
| assessor | 6 cards (5 gating, 1 auto-deferred) | 2,071 tok / $0.0258 |
| resolver | Gate open — awaiting human decisions | — |
| architect | Architecture drafted | 2,920 tok / $0.0364 |
| design_review | Gate 2 — human review | — |
| test_plan | Test plan ready | 5,092 tok / $0.0384 |
| codegen | **Code generated: app=12,950 chars, tests=13,076 chars** | 17,994 tok / $0.1663 |
| review_scan | **Policy gate FAILED — 3 blockers: `security/v0.1.0/PHI-001`** | — |

Final status: **`failed` at codegen**, `contains_synthetic_output: false`.

> Say: "It wrote thirteen thousand characters of working application code and
> thirteen thousand of tests. Then its own review scan refused to let it
> through, and told you exactly which rule: `security/v0.1.0/PHI-001`."

> Say: "This is the demo. Not that the AI wrote code — everyone's seen that.
> That the AI could not ship code that violated a standard, and the block is
> attributable to a versioned, committee-owned rule."

**Do not describe this as a bug or apologise for the red status.** It is the
enforcement surface doing its job.

---

## Act 5 — Artifact integrity (~1 min)

```bash
curl -s "$B/api/runs/$R" | python3 -c "import json,sys; d=json.load(sys.stdin); \
print(d['input_sha256']); print(json.dumps(d['reviewed_artifact_manifest'],indent=1))"
```

**Observed:** input `sha256 b0502f40…`, plus a per-artifact manifest —
`decisions.md`, `docs/architecture.md`, `docs/test-plan.md`, `src/main.py`, each
with its own SHA256.

> Say: "The reviewer signed off on exactly these bytes. If any artifact changes
> after review, the hash no longer matches and the approval no longer applies."

---

## Act 6 — The supply-chain gate (optional, ~2 min)

Open the latest `supply-chain-scan` run on PR #11. It is **red**, on purpose.

```
[security/v0.2.0/SUPPLY-001] scanned SBOM — 102 finding(s): 33 high, 46 medium, 23 low
[security/v0.2.0/SUPPLY-001] BLOCKED — 33 finding(s) at or above 'high'
```

The honest story, which is stronger than a green check:

1. This gate was **silently dead for 22 weeks.** `anchore/scan-action@v3` pins
   grype v0.74.4, whose embedded DB listing had expired. grype aborted with
   `db could not be loaded: the vulnerability database was built 22 weeks ago`,
   wrote no SARIF, and the action still emitted "Failed minimum severity level" —
   an infrastructure failure indistinguishable from a real CVE block.
2. SUPPLY-001 was therefore **not being enforced**. The gate was producing the
   paperwork of assurance without the substance.
3. Our own audit found it, and the fix is in the record with the evidence
   retained as a build artifact.

> Say: "We are showing you a control that failed, how we detected it, and what
> we changed. A governance system nobody has ever caught failing is a system
> nobody has really tested."

The 33 findings are dispositioned via a standards-change proposal — the
enforcer's own message says so explicitly: *"If a finding is a false positive,
it must be dispositioned in the bundle via a standards-change proposal — not
silenced in this workflow."*

---

## Questions you should expect

**"Is the AI making these decisions or is a human?"**
Both, and the record distinguishes them. `actor_kind` is `human` or `agent`, and
`gate_reason` says why a human was required — `invariant_class` means the class
is never self-approvable; `autonomy_tier` means the agent had not yet earned
autonomy for that class on that team.

**"What stops someone approving everything blindly?"**
Nothing stops it, and that is deliberate — the system records who did it, when,
and what they rejected. Governance is accountability, not obstruction.

**"Does this work outside healthcare?"**
Yes. `phi-classification` is one ambiguity class in one bundle. The invariant
mechanism is domain-neutral; the bundle contents are not.

**"Is any of this mocked?"**
No. `contains_synthetic_output` is `false` on this run, and the delivery stage
refuses to open a PR on any run where it is `true`. That flag exists precisely so
this question has a checkable answer.

---

## Known rough edges (say these before someone finds them)

- **Cards report `resolved: false` after a successful approval.** All six
  approvals returned HTTP 200 and wrote six ledger decisions, but the card flag
  does not flip. Decision state and card state are tracked separately. Cosmetic
  in the API; verify the UI before relying on it on screen.
- **The `GateDecision.actor` field defaults to a customer-named value.** Always
  pass `actor` explicitly. Do not let the default appear on screen.
- **`accuracy_score` is not surfaced** by the compliance API. Do not promise a
  retrospective accuracy metric.
- **Delivery cannot complete** on this deploy: `DELIVER_GH_TOKEN` and
  `DELIVER_TARGET_REPO` are unset, so no real PR is opened. The run ends at
  review_scan. Do not promise a merged PR.

---

## If the live run misbehaves

Fall back to an existing completed run rather than debugging on stage. Fifty runs
are already in the system. Narrate the same story from the record — but say
plainly that you are showing a previous run, never call it live telemetry.
