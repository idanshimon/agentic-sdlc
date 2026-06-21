# Proposal: graduated-autonomy tier-2 (hard-gate) + operator agency + teaching loop

> **Status:** DRAFT (2026-06-20)
> **Capability:** resolver-gate (operator decision surface) + ledger (precedent matching)
> **Related:**
>   - `add-teaching-signal-feedback` — the existing operator write path (thumbs/flag/replay/pause); this change adds the *gate-time* write path (swap → precedent) and the *autonomy tier* that governs it
>   - `add-slot-value-hash-to-runtime-schema` — defines slot_value_hash; this change fixes how it's KEYED so precedent matching actually works across runs
>   - `master-v07-four-plane-architecture` — the Pipeline/Ledger planes this spans
>   - `hca-agentic-sdlc-demo` skill — standing demo rules

## Why

The resolver gate had three operator-facing gaps and one silent correctness bug, all surfaced by live use (Idan, 2026-06-18..20):

1. **"Use this" gave a toast but nothing changed on the page.** Per-card approval persisted to the ledger but never updated the local view, so the operator couldn't tell a decision had landed. The card looked untouched.
2. **No way to edit a recommended resolution, or write your own.** The gate was a read-only approve-the-recommendation surface, even though the orchestrator's `/approve` already accepted `decision_kind: "swap"` + free-form `resolution_text`. Three backend capabilities (accept / swap / write-your-own) the operator couldn't reach.
3. **No way to block a rule class from being soft-approved.** PHI/auth cards could be swept into a one-click "Approve all" — a compliance hole. Autopilot already refused `INVARIANT_CLASSES`, but the *human bulk path* did not.
4. **The teaching loop was dead.** An operator's swap was supposed to become precedent that `findPrecedent` quotes back on the next run — closing the human→agent learning loop. It never fired, for two stacked reasons (see "What changes").

This completes the **3-tier graduated-autonomy model** the design always implied but never fully expressed:

| Tier | Who decides | Before | After |
|---|---|---|---|
| 0 — Autopilot | agent auto-resolves on high-confidence precedent | ✅ refuses INVARIANT_CLASSES | unchanged |
| 1 — Soft-approve | human one-click "Approve all recommended" | ✅ exists | now SKIPS hard-gated cards |
| 2 — **Hard-gate** | human MUST decide each card individually, explicitly, on the record | ❌ missing | ✅ server-enforced (409 on bulk) |

## What changes

### Tier-2 hard-gate (server-enforced)

- `apps/orchestrator/config.py` — `HARD_GATE_CLASSES`, defaults to `INVARIANT_CLASSES` (phi-classification, auth-policy). The `HARD_GATE_CLASSES` env **extends** the floor but can never shrink it — PHI/auth are immovable; un-gating them requires a standards-change, not an env flip. `reload_hard_gate_classes()` for test-time reload.
- `apps/orchestrator/models.py` — `GateDecision.approval_path: "bulk" | "individual"` (default `"individual"`, the safe value). `AmbiguityCard.is_hard_gated` stamped at assessor time.
- `apps/orchestrator/main.py::approve` — rejects `approval_path=="bulk"` on a hard-gated card with **409**, independent of the UI. A curl cannot rubber-stamp a PHI card.
- `GET /api/config/hard-gate-classes` — surfaces the posture (floor + extras + explainer) for a future Settings/Governance view.
- `apps/orchestrator/_pipeline_stages.py` — stamps `is_hard_gated` on every card from the resolved set.

### Operator agency (UI)

- `resolver-gate.tsx` — per-card `decided` state: "Use this" / "Use my version" visibly locks the card to a green "Decided: <label> — change" row; a header "N of M DECIDED" counter; finalize only when every gating card is decided.
- Edit-recommendation + write-your-own textarea (pre-filled with the recommended text, so editing IS the edit path) → sends `decision_kind: "swap"` + `resolution_text`. PHI soft-warn (SSN/MRN/DOB patterns) warns, never blocks.
- "Approve all recommended" uses `bulkApprovableCards()` to skip hard-gated + already-decided cards, sends `approval_path: "bulk"`, and shows "N cards need your explicit decision" when hard-gated cards remain. Hard-gated cards show a 🔒 EXPLICIT DECISION REQUIRED badge.

### Teaching loop (two stacked bug fixes)

The loop = operator swaps a resolution on run A → `findPrecedent` quotes it back on run B for the same (team, class, slot) → HYBRID autopilot auto-resolves instead of re-gating. It was dead for two reasons, fixed in order:

1. **Unstable slot_value_hash.** `slot_value_hash = _hash(title + detail)`, but title/detail come from the LLM assessor's prose, which varies run-to-run even for the SAME PRD. So run A and run B produced different hashes for the same ambiguity → `findPrecedent` (exact match on slot_value_hash) could never match. **Fix:** `_slot_key(class, prd_section)` keys on the stable semantic identity (class + normalized PRD section), not the LLM's wording. Verified: hashes now match across runs.
2. **`SELECT TOP 1 ... ORDER BY` returned empty.** `findPrecedent`'s query used `SELECT TOP 1 * ... ORDER BY created_at DESC` with a partition-scoped async `query_items`, which returned an EMPTY iterator even when matching rows existed (the identical query without `TOP 1` returned them). **Fix:** drop `TOP 1`, take the first ordered row in Python (identical semantics, no aggregation-pipeline bug).

### Decisions-page readability

- Teaching-signal rows (`feedback_thumbs`, `decision_flagged`, `replay_requested`, `class_paused`) rendered as "thumbs_up on <uuid>". `teachingSignalSummary()` now renders plain-English title + detail per kind.
- Removed the dead `↳ refers to <uuid>` line and the dead `<Link href="/prompts">` wrappers on `PromptChainBadge` (the catalog isn't deep-linkable; clicking dumped operators on a context-less page).

## Why this design

**Hard-gate reuses the existing INVARIANT_CLASSES set**, not a parallel mechanism — autopilot already refuses these (main.py:155 "Invariant override — always gates"); this extends the same set's reach to the human bulk path. **Server-enforced, not UI-only** — the 409 is the compliance guarantee; the lock badge is just the friendly surface. A reviewer cares about "the system makes it impossible," not "the dashboard discourages it."

**The swap is precedent-shaped by construction** — it writes a runtime LedgerEntry with the card's slot_value_hash + the operator's verbatim text + `decision_kind=swap`, no excluding `runtime_kind`. So once the two query bugs are fixed, the operator's wording IS the precedent findPrecedent returns. No separate "teaching" store.

## Out of scope / known issues

- **End-to-end teaching-loop proof is NOT yet green.** Both layer fixes are verified individually (stable hashes; find_precedent returns rows), but the run-A-teaches → run-B-quotes proof has not demonstrated `AUTO-RESOLVED` on a card that was actually taught. Last proof attempt was methodologically flawed (taught `data-retention`, checked `sla-binding`; run B did not contain a data-retention card — LLM varies WHICH classes it emits per run). Needs a correct test using a class present in both runs, with a confirmed-persisted precedent. There may be a third layer.
- **Settings/Governance view** (`GET /api/config/hard-gate-classes` consumer) — endpoint live, UI page deferred.
- **"Taught by operator" provenance badge** on decisions that reused a human swap — deferred.
- **LLM class-set variance** — the assessor emits a different SUBSET of classes per run, which makes deterministic teaching-loop demos fragile. A seeded/deterministic demo PRD path would make the loop reliably demonstrable.

## Receipts

- Commits: `0071b56` (hard-gate), `7550dfa` (operator agency UI), `97bcc45` (slot-hash), `ca56916` (find_precedent TOP-1 + debug cleanup), `4838231` (readable decisions), `2a20e72` (swap-precedent test)
- Images: `orchestrator:teaching-loop-v18` (rev 0000018), `ledger-insights-ui:4838231` (rev 0000024)
- Tests: orchestrator 179 passed; UI 9 (resolver-gate) + decision-card; tsc clean
