# Tasks — add-graduated-autonomy-tier2

> **Status:** DRAFT (2026-06-20). Tier-2 hard-gate + operator agency are SHIPPED
> and proven live. The teaching loop has two layer-fixes shipped but is NOT yet
> proven end-to-end (see section 4).

## 0 — Tier-2 hard-gate (server-enforced) — SHIPPED

- [x] 0.1 `HARD_GATE_CLASSES` config defaulting to `INVARIANT_CLASSES`, env extends-not-shrinks  *(config.py::_hard_gate_classes + reload_hard_gate_classes)*
- [x] 0.2 `GateDecision.approval_path` ("bulk" | "individual", default individual)  *(models.py)*
- [x] 0.3 `AmbiguityCard.is_hard_gated` stamped at assessor time  *(_pipeline_stages.py)*
- [x] 0.4 `/approve` rejects bulk on hard-gated card with 409, UI-independent  *(main.py::approve; references _config.HARD_GATE_CLASSES for test reload)*
- [x] 0.5 `GET /api/config/hard-gate-classes` surfaces the posture  *(main.py)*
- [x] 0.6 8 tests: defaults, env extends/can't-shrink, bulk→409, individual→200, default-path, endpoint  *(test_hard_gate.py)*
- [x] 0.7 Verified LIVE: bulk on PHI → 409, individual on PHI → 200 (rev 0000015..0000018)

## 1 — Operator agency (UI) — SHIPPED

- [x] 1.1 Per-card `decided` state: "Use this"/"Use my version" lock the card + "N of M decided" counter  *(resolver-gate.tsx)*
- [x] 1.2 Edit-recommendation + write-your-own textarea → `decision_kind: swap` + resolution_text  *(resolver-gate.tsx::approveCustom)*
- [x] 1.3 PHI soft-warn (SSN/MRN/DOB) on the free-text box — warns, never blocks  *(phiSoftWarn)*
- [x] 1.4 "Approve all" skips hard-gated + decided cards, sends approval_path:bulk, shows remaining-count notice  *(bulkApprovableCards)*
- [x] 1.5 Hard-gated cards show 🔒 EXPLICIT DECISION REQUIRED badge + excluded-from-bulk footer
- [x] 1.6 `ApproveBody.approval_path` on the orchestrator client  *(orchestrator.ts)*
- [x] 1.7 9 logic tests (phiSoftWarn + bulkApprovableCards), tsc clean  *(resolver-gate.test.ts)*
- [x] 1.8 Deployed live (rev 0000023)

## 2 — Decisions-page readability — SHIPPED

- [x] 2.1 `teachingSignalSummary()` — plain-English title+detail per runtime_kind  *(decision-card.tsx)*
- [x] 2.2 Removed dead `↳ refers to <uuid>` line; entry id is a muted footer ref
- [x] 2.3 Removed dead `<Link href="/prompts">` on PromptChainBadge (card + inline) → informational text  *(prompt-chain-badge.tsx)*
- [x] 2.4 tsc clean; deployed live (rev 0000024)

## 3 — Teaching loop: precedent-shaping + the two query bugs

- [x] 3.1 Operator swap writes a precedent-shaped entry (slot_value_hash + verbatim text + decision_kind=swap, no excluding runtime_kind)  *(main.py::approve; test_swap_precedent.py — 2 tests)*
- [x] 3.2 LAYER 1 FIX: stable `_slot_key(class, prd_section)` replaces `_hash(title + detail)`  *(_pipeline_stages.py; test_slot_key_stability.py — 6 tests)*
- [x] 3.3 LAYER 1 verified LIVE: same PRD → same slot_value_hash across runs
- [x] 3.4 LAYER 2 FIX: `find_precedent` drops `SELECT TOP 1` (partition-scoped async TOP+ORDER BY returned empty); takes first ordered row in Python  *(cosmos.py)*
- [x] 3.5 Removed the temporary `/api/debug/find-precedent` diagnostic endpoint  *(main.py; clean image teaching-loop-v18)*

## 4 — Teaching loop: end-to-end proof — NOT DONE

- [ ] 4.1 Run a CORRECT end-to-end test: teach a class present in BOTH runs (e.g. sla-binding or scope-resolution, which appear reliably), confirm the precedent persisted, then verify run B AUTO-RESOLVES that exact card
- [ ] 4.2 If still gating with v18 live + matching card + persisted precedent → there is a THIRD layer; re-diagnose (the find_precedent fix is necessary but maybe not sufficient)
- [x] 4.3 Add a regression test for find_precedent against a fake ledger that asserts a known row is returned + guards against TOP-1 reintroduction  *(packages/ledger-core/tests/test_find_precedent.py — 5 tests)*
- [ ] 4.4 Consider a seeded/deterministic demo PRD path so the LLM doesn't vary WHICH classes it emits per run (makes the loop reliably demonstrable)

## 5 — Deferred (not blocking)

- [ ] 5.1 Settings/Governance view consuming `GET /api/config/hard-gate-classes` (read-only; editing = standards-change)
- [ ] 5.2 "Taught by operator" provenance badge on decisions that reused a human swap
- [ ] 5.3 Make `HARD_GATE_CLASSES` bundle-declared (committee owns the posture, per four-plane model)

## Verification (definition of done)

- [ ] `openspec validate add-graduated-autonomy-tier2 --strict` → Valid
- [x] Tier-2 hard-gate proven live (bulk→409, individual→200)
- [x] Operator agency (decided-state, edit/write-your-own) deployed
- [x] Decisions-page readability deployed
- [ ] Teaching loop proven end-to-end (a taught card auto-resolves on the next run) — **OPEN**
