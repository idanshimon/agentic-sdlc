# Live demo runbook — agentic-sdlc v0.7 (dashboard-centric)

Generated for a same-day demo off the LIVE vnet stack. Verified reachable:
UI 200, orchestrator /api/runs 200 with real completed runs, ledger real
(DEMO_MODE=0). This is the ready-now path — no state changes to the demo system.

## URLs (open as tabs, in order)

- Tab A — UI runs:      https://ca-ledger-ui-vnet.thankfulflower-0a94d0d3.eastus2.azurecontainerapps.io/runs
- Tab B — Decisions:    https://ca-ledger-ui-vnet.thankfulflower-0a94d0d3.eastus2.azurecontainerapps.io/decisions
- Tab C — Telemetry:    https://ca-ledger-ui-vnet.thankfulflower-0a94d0d3.eastus2.azurecontainerapps.io/telemetry
- Tab D — Delivery PR:  https://github.com/idanshimon/agentic-sdlc-delivery/pull/3
- Tab E (backup) — explainer: open docs/explainer.html locally (file://), dark 4-plane diagram

## The story in one line

Governance is the differentiator, not codegen quality. Every AI-agent decision
lands on one auditable ledger; every standards change is a committee-reviewed PR.

## Flow (10 min)

1. FRAME (60s, talk over Tab E explainer, no clicks)
   Engineers work in Slack/Teams/portals, not just VS Code. Today's AI agents are
   invisible to compliance — we see what landed in main, not WHY the agent chose it.
   v0.7 closes that with four planes: Standards / Pipeline / Ledger+Doctor / Agent HQ.

2. RUNS (Tab A)
   Show the list of completed runs with model badges + cost. Click one completed run.
   On the run-detail page point at: stage duration bars, per-stage model routing,
   artifact sizes (catches truncation regressions visually), experiment provenance.

3. ARTIFACTS (same run page)
   Open the 5-tab artifacts panel: Decisions / Architecture / Test plan / Code /
   decisions.md. "Every line of this service was emitted by the pipeline. No manual edits."

4. DECISIONS (Tab B)
   Table view. Filter by model or class. Click a row → rationale, provenance,
   classification, bundle_refs chips (each decision grounded in a specific rule
   like security/v0.1.0/PHI-001). Click 👎 / Flag / Pause autopilot → Sonner toasts
   ("Decision flagged — findPrecedent will skip it next time").

5. ASSISTANT (⌘K on any tab)
   Open the slide-over. Note the chip suggestions are STATE-AWARE (awaiting-gate count
   is real). Type "what do you recommend" — reply quotes the actual run id, lists
   awaiting-gate decisions verbatim with their real bundle_refs, sums real cost.
   Switch to dashboard, "summarize the portfolio" — same component, different context.
   Honesty line: v0.7 ships the deterministic composer; live-LLM is the same contract.

6. TELEMETRY (Tab C)
   Ledger feed (audit substrate) + cost dashboard (per-stage, apportioned = CFO buckets)
   + class drift (where the next bundle rule needs writing).

7. THE PR (Tab D)  ← this is the "PROVE IT" moment given the delivery question
   github.com/idanshimon/agentic-sdlc-delivery/pull/3 — a real PR the pipeline's
   deliver stage produces: FastAPI src/main.py, tests, architecture, decisions.md.
   "The pipeline doesn't just render a dashboard — it opens a real PR into a
   separate deliveries repo, code + decision record in one commit."

8. CLOSE (3 sentences)
   Governance is the differentiator. Every agent decision hits one audit substrate
   regardless of runtime. Rules are versioned PRs with committee review, not tribal
   knowledge. The ledger feed is the single source of truth; everything else is a view.

## HONEST GAP — know this before the room asks

The LIVE orchestrator has DELIVER_PROVIDER=github but NO delivery token wired.
So if you drop a NEW PRD and run all 9 stages live, the deliver stage will honestly
emit "not_delivered — no delivery backend configured" and produce NO link. That is
BY DESIGN (no fabricated URLs). PR #3 was opened out-of-band through the same
production code path (open_delivery_pr) so you have a real artifact to show.

=> Recommendation: demo off COMPLETED runs + show PR #3. Do NOT do a live PRD-to-PR
run on the live stack until the token is wired (see below), or the money shot fails
in the room.

## To enable live PRD-to-PR (do this BEFORE the demo, not during)

Wire a delivery token onto the orchestrator, then a live run opens its own PR:

    az containerapp secret set -n ca-orchestrator-vnet -g rg-agentic-sdlc-v07-eastus2 \
      --secrets deliver-gh-token=<FINE_GRAINED_PAT>

    az containerapp update -n ca-orchestrator-vnet -g rg-agentic-sdlc-v07-eastus2 \
      --set-env-vars \
        DELIVER_GH_TOKEN=secretref:deliver-gh-token \
        DELIVER_TARGET_REPO=idanshimon/agentic-sdlc-delivery \
        DELIVER_AUTO_CREATE=1

Use a fine-grained PAT scoped to ONLY the agentic-sdlc-delivery repo (contents:write,
pull_requests:write) — not your gh OAuth token. Restart is automatic (~2 min).
Verify with a live run before showing anyone.

## Reset the deliveries repo between demos

    python scripts/reset_deliveries.py            # dry run
    python scripts/reset_deliveries.py --apply    # close agentic/* PRs + delete branches

## Sample PRDs on disk (for New Run, if/when live delivery is wired)

- samples/prds/patient-vitals-streaming.txt      (PHI + third-party egress traps)
- samples/prds/cardiology-deterioration-alerts.txt
