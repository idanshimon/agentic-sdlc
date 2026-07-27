# Proposal: stop conditions on ambiguity cards

> **Status:** DRAFT (proposed)
> **Capability:** pipeline / assessor · ledger
> **Related:**
>   - `add-graduated-autonomy-tier2` (defines which classes may be autopiloted;
>     this proposal bounds what an autopiloted resolution is allowed to touch)
>   - `add-replay-disagreement-metric` (measures whether the agent diverged from
>     a human; a breached stop condition is a divergence the agent can detect
>     for itself, before the work is done rather than after)

## Why

Every ambiguity card today answers **what to decide**. No card answers **when to
stop deciding**.

That gap is structural, not cosmetic. An autopiloted card is resolved from
precedent and confidence, and the resolution then flows downstream into
architecture and codegen with no declared boundary. If the resolution turns out
to be wrong — or right but wider in effect than anyone intended — nothing in the
pipeline notices. The first signal is a human reading a diff at review-scan, or
a BLOCK rule firing on the output.

This is the same class of problem `requires_mechanism` solved for BLOCK rules.
A rule that asserts enforcement without naming what enforces it is an audit
artifact pretending to be a control. A card that authorizes autonomous
resolution without naming the condition under which the agent must stop is the
same shape of claim: the agent is trusted to know when it has gone too far,
with nothing checking.

Invariants already express the strongest form of "the agent must not proceed":
`phi-classification` and `auth-policy` are hard-gated and can never be
autopiloted. But an invariant is a *class-level* prohibition declared in
advance. A stop condition is *card-level* and situational — it bounds a decision
the agent IS permitted to make.

**Concretely, three failure modes today have no representation:**

1. **Scope drift.** The agent resolves "use FHIR-compliant UUIDs for patient
   identifiers" and, downstream, applies that ruling to identifiers it was never
   asked about. Nothing on the card says which surfaces the ruling covers.
2. **Silent over-reach.** A resolution is technically correct but touches more
   than the PRD authorized (new external dependency, new data store, a schema
   migration). The card licensed a decision, not a blast radius.
3. **Stale precedent applied past its shelf life.** Precedent is reused by
   `card_id`; nothing on the reused card states the conditions under which that
   precedent stops being applicable.

## What changes

Add an optional, structured **stop condition** to `AmbiguityCard`, populated by
the Assessor and carried through resolution into the ledger.

```python
class StopCondition(BaseModel):
    """A testable boundary on an autonomous resolution."""
    statement: str            # human-readable: "stop if this requires a schema migration"
    kind: StopKind            # scope | dependency | data | cost | confidence
    detectable: bool          # can the pipeline actually evaluate this?
    mechanism: str = ""       # WHAT evaluates it — required when detectable is True
```

### The rule that makes this real

Mirroring `requires_mechanism` on BLOCK rules:

> **A stop condition marked `detectable: true` MUST name a `mechanism`.**
> A stop condition with no mechanism is advisory only, MUST be rendered as
> advisory in the UI, and MUST NOT be counted as a control in any compliance
> view.

This is the whole point of the change. Without that constraint, stop conditions
become free-text intentions that make the system *look* better governed while
enforcing nothing — the exact failure `SBOM-001` shipped with for two versions.

### Where it binds

| Stage | Behaviour |
|---|---|
| **assess** | Assessor emits `stop_conditions` per card. Zero is legal; the field is optional. |
| **resolve** | A card whose stop condition is breached MUST NOT be autopiloted — it gates to a human regardless of earned autonomy. |
| **architect / codegen** | Detectable conditions are evaluated against the produced artifact; a breach fails the stage with the condition cited. |
| **ledger** | The resolution entry records which conditions were declared and which were evaluated. |

### Not in scope

- **No new autonomy.** A stop condition can only ever *narrow* what the agent
  may do autonomously; it can never widen it. An invariant class stays
  human-only whatever its stop conditions say.
- **No retro-fitting.** Existing cards without stop conditions keep working
  unchanged. The field is additive and optional.
- **No LLM-evaluated conditions in v1.** `detectable: true` requires a
  deterministic mechanism. A model asked "did you overstep?" is not a control.

## Why this is worth doing now

The system's central claim is that autonomy is *earned per class, on evidence*.
Earned autonomy answers "may the agent decide this?" — it does not answer "how
far does that decision reach?" Stop conditions close that gap, and they close it
in the same shape as every other control here: declared by a human, cited by id,
backed by a mechanism, recorded in the ledger.

It is also the cheapest honest strengthening available. The schema change is
additive, the assessor prompt change is small, and the enforcement point already
exists (the resolve gate). The expensive half — deterministic evaluators for
each `StopKind` — can land incrementally, because an undetectable condition is
explicitly permitted and explicitly labelled advisory.

## Open questions

1. Should a breached stop condition **retract the precedent** that produced the
   resolution, or only gate the current card? Retraction is the stronger signal
   but risks over-correcting on one incident.
2. Should `StopKind: cost` reuse the existing `blast_radius_cost_usd` on the
   card, or is a per-condition threshold clearer?
3. Do stop conditions belong in bundles as reusable, versioned definitions
   (`security/v0.2.0/STOP-001`) rather than free-form per card? That would make
   them governable law rather than per-run text — likely the right end state,
   but a larger change.
