#!/usr/bin/env python3
"""seed_graph_demo.py — seed a rich, graph-shaped decision ledger for the
Decision Map / lineage / run-flow views.

WHY: the existing team-demo ledger has decisions but ZERO bundle_refs and ZERO
precedent/reuse edges, so the governance graph can't show its two headline
stories — "which rule does the most work" (bundle hubs) and the human→agent
learning loop (reuse edges). This writes a coherent, HONESTLY-SYNTHETIC
scenario that exercises every graph edge type.

The scenario is a customer-neutral sample product: "Meridian", a patient
self-service portal, built across several pipeline runs by agent roles
(assessor / architect / codegen) with a human lead (idan) making the calls the
agents defer. It is sample data, narrated as seeded — never live telemetry.

Edge types exercised:
  grounded_in  — decisions cite security/privacy/architect bundle rules (hubs)
  of_class     — decisions carry ambiguity_class (clusters)
  in_run       — decisions carry run_id (run grouping)
  reuses       — later autopilot decisions set precedent_refs=[human decision id]
  teaches      — teaching signals set references_entry_id=[decision id]

Usage:
  LEDGER_MCP_TOKEN=<team-demo token> python3 scripts/seed_graph_demo.py
  LEDGER_MCP_TOKEN=... python3 scripts/seed_graph_demo.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error

MCP_URL = os.environ.get(
    "LEDGER_MCP_URL",
    "https://ca-ledger-mcp-vnet.thankfulflower-0a94d0d3.eastus2.azurecontainerapps.io",
)
TOKEN = os.environ.get("LEDGER_MCP_TOKEN", "")
TEAM = os.environ.get("LEDGER_TEAM", "team-demo")

# Bundle rules the decisions cite — these become the graph's hub nodes.
R_PHI = "security/v0.1.0/PHI-001"
R_AUTH = "security/v0.1.0/AUTH-002"
R_RETAIN = "privacy/v0.1.0/RETAIN-004"
R_NAMING = "architect/v0.1.0/NAMING-001"
R_SLA = "architect/v0.1.0/SLA-007"


def post(path: str, body: dict) -> tuple[int, dict]:
    req = urllib.request.Request(
        f"{MCP_URL}{path}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {TOKEN}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or "{}")
        except Exception:
            return e.code, {"error": str(e)}
    except Exception as e:
        return 0, {"error": f"{type(e).__name__}: {e}"}


DRY = "--dry-run" in sys.argv


def write(entry: dict) -> str | None:
    """Write one runtime entry; return its ledger id (for chaining precedents)."""
    entry.setdefault("team_id", TEAM)
    if DRY:
        print(f"  DRY {entry.get('runtime_kind') or 'stage_decision':16} "
              f"{entry.get('ambiguity_class') or '-':20} {entry['decision'][:50]}")
        return "dry-" + str(abs(hash(entry['decision'])) % 10**8)
    status, data = post("/tools/ledger.write_runtime", entry)
    if status not in (200, 201):
        print(f"  FAIL {status}: {json.dumps(data)[:200]}", file=sys.stderr)
        return None
    eid = data.get("id") or (data.get("entry") or {}).get("id")
    print(f"  ok  {eid}  {entry.get('ambiguity_class') or entry.get('runtime_kind') or '-':20} {entry['decision'][:46]}")
    return eid


AGENT = {"kind": "agent", "id": "assessor-agent@meridian", "display_name": "Assessor Agent"}
ARCHITECT = {"kind": "agent", "id": "architect-agent@meridian", "display_name": "Architect Agent"}
HUMAN = {"kind": "human", "id": "idan@contoso.com", "display_name": "Idan (Lead)"}


def stage_decision(run_id, cls, decision, actor, bundle_refs, rationale, precedent_refs=None):
    e = {
        "actor": actor, "decision": decision, "rationale": rationale,
        "run_id": run_id, "ambiguity_class": cls, "bundle_refs": bundle_refs,
        "runtime_kind": "stage_decision",
    }
    if precedent_refs:
        e["precedent_refs"] = precedent_refs
    return write(e)


def teaching(kind, ref_id, actor, decision, rationale, feedback_kind=None, paused_class=None):
    e = {
        "actor": actor, "decision": decision, "rationale": rationale,
        "runtime_kind": kind, "references_entry_id": ref_id,
        "run_id": "meridian-teaching",
    }
    if feedback_kind:
        e["feedback_kind"] = feedback_kind
    if paused_class:
        e["paused_class"] = paused_class
        e["ambiguity_class"] = paused_class
    return write(e)


def main():
    if not TOKEN and not DRY:
        sys.exit("LEDGER_MCP_TOKEN required (or pass --dry-run)")

    print(f"Seeding Meridian graph demo → {MCP_URL} team={TEAM} {'(DRY RUN)' if DRY else ''}")

    # ── RUN 1 — the FOUNDING run. Human makes the hard calls; these become
    #    the precedents everything else reuses. ─────────────────────────────
    run1 = "meridian-run-0001"
    print(f"\n[{run1}] founding run — human sets precedents")
    p_phi = stage_decision(
        run1, "phi-classification",
        "Portal messages classified PHI-high; encrypt at rest + field-level access log",
        HUMAN, [R_PHI],
        "Patient free-text messages can contain diagnoses. Lead call: treat as PHI-high.",
    )
    p_auth = stage_decision(
        run1, "auth-policy",
        "Patient auth via SMART-on-FHIR OAuth2 + step-up MFA for record export",
        HUMAN, [R_AUTH, R_PHI],
        "Export of a full record is the high-risk action; require step-up MFA there only.",
    )
    p_retain = stage_decision(
        run1, "data-retention",
        "Message retention 7 years to match clinical record policy, soft-delete + purge job",
        HUMAN, [R_RETAIN],
        "Align portal retention with the underlying clinical record; no shorter.",
    )
    p_naming = stage_decision(
        run1, "naming-convention",
        "REST resources kebab-case, FHIR resource names preserved verbatim",
        ARCHITECT, [R_NAMING], "Consistency with existing FHIR gateway conventions.",
    )

    # ── RUN 2 — Meridian appointments module. Autopilot REUSES run-1 precedents. ──
    run2 = "meridian-run-0002"
    print(f"\n[{run2}] appointments module — autopilot reuses precedents")
    d2_phi = stage_decision(
        run2, "phi-classification",
        "Appointment notes classified PHI-high (reused founding precedent)",
        AGENT, [R_PHI],
        "Auto-resolved from run-0001 human precedent: patient free-text is PHI-high.",
        precedent_refs=[p_phi] if p_phi else None,
    )
    stage_decision(
        run2, "auth-policy",
        "Appointment booking auth via SMART-on-FHIR OAuth2 (reused precedent)",
        AGENT, [R_AUTH],
        "Auto-resolved from run-0001 auth precedent.",
        precedent_refs=[p_auth] if p_auth else None,
    )
    stage_decision(
        run2, "naming-convention",
        "Appointment endpoints kebab-case (reused precedent)",
        AGENT, [R_NAMING], "Auto-resolved from architect naming precedent.",
        precedent_refs=[p_naming] if p_naming else None,
    )
    # A NEW ambiguity in run 2 the agent had to gate on (no precedent):
    d2_sla = stage_decision(
        run2, "sla-binding",
        "Appointment sync SLA 5min p99 — flagged for lead review",
        ARCHITECT, [R_SLA], "No precedent for sync latency; proposing 5min, needs lead sign-off.",
    )

    # ── RUN 3 — Meridian billing module. More reuse + one BAD decision. ──
    run3 = "meridian-run-0003"
    print(f"\n[{run3}] billing module — reuse + one decision the lead flags")
    stage_decision(
        run3, "phi-classification",
        "Billing records classified PHI-high (reused precedent)",
        AGENT, [R_PHI], "Auto-resolved from founding PHI precedent.",
        precedent_refs=[p_phi] if p_phi else None,
    )
    bad_retain = stage_decision(
        run3, "data-retention",
        "Billing data retention set to 3 years (SHORTER than clinical policy)",
        AGENT, [R_RETAIN],
        "Agent guessed 3y from generic finance norms — did NOT reuse the 7y precedent.",
    )
    stage_decision(
        run3, "auth-policy",
        "Billing export auth step-up MFA (reused precedent)",
        AGENT, [R_AUTH], "Auto-resolved from founding auth precedent.",
        precedent_refs=[p_auth] if p_auth else None,
    )

    # ── TEACHING SIGNALS — the human→agent learning loop. ──
    print("\n[teaching] human corrects + reinforces")
    if bad_retain:
        teaching("decision_flagged", bad_retain, HUMAN,
                 "Flagged: billing retention must match 7y clinical policy, not 3y",
                 "This contradicts RETAIN-004 + the run-0001 precedent. Don't reuse it.")
    if p_phi:
        teaching("feedback_thumbs", p_phi, HUMAN,
                 "Endorsed the PHI-high founding call", "Correct and worth reusing.",
                 feedback_kind="thumbs_up")
    if d2_phi:
        teaching("feedback_thumbs", d2_phi, HUMAN,
                 "Endorsed the appointments PHI reuse", "Good auto-resolution.",
                 feedback_kind="thumbs_up")
    if d2_sla:
        teaching("replay_requested", d2_sla, HUMAN,
                 "Replay SLA decision against updated SLA-007 rule",
                 "SLA-007 was revised; re-evaluate the 5min p99 target.")
    # Pause a whole class the lead wants to own going forward:
    teaching("class_paused", p_retain or "meridian-run-0001", HUMAN,
             "Paused autopilot for data-retention across Meridian",
             "Retention has legal exposure; lead will decide each one until further notice.",
             paused_class="data-retention")

    print("\nDone. Re-query /decisions or open /decisions/graph to see the map.")


if __name__ == "__main__":
    main()
