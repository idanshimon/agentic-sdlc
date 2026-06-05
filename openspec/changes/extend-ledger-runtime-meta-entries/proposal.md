# Proposal: extend ledger with runtime/meta entry types

> **Status:** DRAFT
> **Capability:** ledger
> **Related:** master-v07-four-plane-architecture

## Why

The v0.6 Decision Ledger had ONE entry type: a record of an
orchestrator-stage decision. v0.7 needs to record TWO different kinds of
events at the same audit substrate:

1. **Runtime decisions** — what an agent (or human) decided during a pipeline
   run, IDE session, or coding-agent flow. "PHI gate APPROVED with redacted
   MRN logging."
2. **Meta decisions** — what got changed about the rules themselves.
   "PHI rule X relaxed for de-identified datasets, effective bundle v2.4.0."

Mixing these in one schema creates query nightmares for compliance auditors.
Q3 PHI handling audit wants runtime entries; "who approved relaxing the rule"
audit wants meta entries.

## What changes

Single discriminator field `entry_type: runtime | meta`, plus type-specific
required fields. Backward-compatible with v0.6 entries (default `entry_type`
= `runtime` on read, no migration needed for existing rows).

### Schema additions

```python
class LedgerEntry(BaseModel):
    # existing fields preserved (id, run_id, stage, actor_kind, actor_id,
    # decision, rationale, phi_class, cost_usd, model_used, created_at, team_id)

    entry_type: Literal["runtime", "meta"] = "runtime"

    # cross-runtime attribution
    agent_session_id: Optional[str] = None       # GH audit log xref
    bundle_refs: List[str] = []                  # ["security/v0.1.0/PHI-001", ...]
    precedent_refs: List[str] = []               # prior ledger entry IDs

    # meta-only fields (validated when entry_type == "meta")
    change_ticket_id: Optional[str] = None       # the standards-change ticket
    bundle_version_from: Optional[str] = None    # "security/v0.1.0"
    bundle_version_to: Optional[str] = None      # "security/v0.1.1"
    blast_class: Optional[Literal["LOW", "MED", "HIGH"]] = None
    reviewers: List[ReviewerAttribution] = []    # who approved
    canary_metrics: Optional[CanaryMetrics] = None
    pr_url: Optional[str] = None                 # standards-bundles PR
    
    # runtime-only fields (validated when entry_type == "runtime")
    run_id: Optional[str] = None                 # pipeline run id
    stage: Optional[str] = None
```

### Validation

A Pydantic model_validator enforces:
- if `entry_type == "meta"`: `change_ticket_id`, `bundle_version_from`,
  `bundle_version_to`, `blast_class`, `reviewers` ALL required;
  `run_id` and `stage` MUST be null.
- if `entry_type == "runtime"`: `run_id` required for orchestrator-source
  entries, `agent_session_id` required for Agent-HQ-source entries.

### Cosmos partition key strategy

Stays `/team_id` (preserves v0.6 partitioning). Both entry types live in
the same container — separation is by `entry_type` field, not by container.
Indexed paths added: `/entry_type/?`, `/bundle_refs/[]/?`,
`/blast_class/?`, `/agent_session_id/?`.

## Why this design

**One container, two entry types** beats two containers for two reasons:
- Compliance "show me everything affecting the patient_lookup module" query
  spans both types and needs to be one cross-partition read, not two.
- Precedent lookup for autopilot: a high-blast meta entry MUST surface in
  the precedent search next time a runtime decision touches the affected
  rule. Two-container design forces a JOIN; one-container is a simple
  equality on `bundle_refs`.

**`bundle_refs` as a list, not a single field** — many runtime decisions
apply rules from multiple bundles (a codegen decision touches `architect`
+ `security`). Tag every applicable bundle so the doctor's drift signal
is accurate per-bundle.

## Migration

v0.6 ledger entries are auto-promoted on read:
- `entry_type = "runtime"` (default)
- `bundle_refs = []` (will be backfilled by doctor on first scan)
- `agent_session_id = None`

No write-side migration. v0.6 readers stay compatible (new fields ignored).
