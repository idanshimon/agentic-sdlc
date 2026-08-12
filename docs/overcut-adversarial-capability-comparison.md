# Adversarial Capability Comparison: Overcut.ai vs. agentic-sdlc

**Question:** Which of our claimed governance advantages are *actually implemented in code* vs.
merely specified? Documentation is **not** evidence — every ✅ below cites an implementation
`file:line`; every ❌ is marked UNSHIPPED or SPEC-ONLY.

---

## Verdict table

| # | Claimed advantage | Overcut analog | Status | Evidence |
|---|---|---|---|---|
| 1 | Precedent citation (`precedent_refs`) drives autopilot | Memory injection (weight 0..1) | ✅ **WIRED** | `main.py:413,433` `find_precedent` gates autopilot; write at `main.py:2101,2174`; heal path `heal_runtime.py:165` |
| 2 | `bundle_refs` = real rule IDs at decision time | Bundle law (implicit) | ⚠️ **PARTIAL** | Stamped from stage subscription `main.py:475`, `deliver_github.py:161` — real IDs but *coarse* (per-stage, not per-rule-evaluated) |
| 3 | Per-run shared scratch store (inter-agent data) | scratchpad tier (append_scratchpad) | ❌ **NONE** | 0 hits for `scratchpad` in orchestrator. Everything rides the stage payload / ledger. |
| 4 | Cross-run memory / retrospective self-improvement | memory tier + 10-run retrospective | ❌ **SPEC-ONLY** | `accuracy_score` = `0.0` on all 229 live entries (`README.md:204`, `replay.py:26`); no compute site. `add-teaching-signal-feedback` 42/56, `add-replay-disagreement-metric` no tasks.md |
| 5 | Hard gate blocks **server-side**, independent of UI | Orchestration HumanGate | ✅ **ENFORCED** | `main.py:1861-1876` — `/approve` returns **409** on `approval_path=="bulk"` for `HARD_GATE_CLASSES`; floor is `INVARIANT_CLASSES` in `config.py:115`, env can extend never shrink |
| 6 | Records rejected alternatives at decision time | `OrchestrationDecision.proposals` (full candidate set) | ❌ **NONE** | LedgerEntry stores only `option_index`+`resolution_text` (chosen). No `alternatives`/`rejected`/`proposals` field. `redesign-decision-lifecycle` specs it (87%) but not on the persisted schema. |
| 7 | `gh_audit_xref` populated | onBehalfOf / GitHub xref | ✅ **WIRED** | `deliver_github.py:144` `gh_audit_xref=f"gh-pr-{pr_number}"`, written `:163` |
| 7b | `autonomy_ref` (WHY autopiloted/gated) populated | `decidedBy` + `pendingReason` | ✅ **WIRED** | `main.py:420-443,479` computed per-branch (`precedent>=t`, `autopilot-always`, `hybrid-precedent`); refusal path `:769`, gate path `:1918` |
| 8 | Governance-critical openspec changes shipped | Draft/committed versioning | ⚠️ **MIXED** — see below |

---

## Target-8 detail: shipped vs. draft (tasks.md checkbox state)

**SHIPPED (100%)** — governance-relevant:
- `add-autonomous-review-loop` (33/33), `add-bundle-ci-enforcement` (18/18),
  `add-config-editing-plane` (27/27), `add-decision-graph-views` (24/24),
  `harden-codegen-governance-quality` (15/15), `ship-operator-grade-pipeline-workflow` (48/48),
  `stabilize-run-lifecycle-execution` (14/14), `wire-real-llm-providers` (5/5)

**IN FLIGHT (partial)** — the teaching/learning loop is here and unfinished:
- `redesign-decision-lifecycle-control-plane` **87%** (34/39) — the alternatives+confidence lifecycle
- `add-graduated-autonomy-tier2` **86%** (31/36) — the tier-2 hard-gate (its enforced parts *are* live, target 5)
- `add-teaching-signal-feedback` **75%** (42/56) — cross-run learning (target 4)
- `add-self-heal-cowork` **47%** (20/43)

**DRAFT (0%)** — the biggest "advantage" claims are still paper:
- `add-pipeline-doctor` (0/36), `add-standards-bundles` (0/39),
  `add-agent-instructions-hierarchy` (0/34), `add-agent-hq-integration` (0/60),
  `extend-ledger-runtime-meta-entries` (0/18), `add-pipeline-eval-harness` (0/14),
  `master-v07-four-plane-architecture` **5%** (4/78)

> **Correction (post-audit verification).** An unchecked `tasks.md` is not proof a capability is
> absent — several of these shipped without their checkboxes being maintained. Verified against
> the filesystem:
>
> - **`add-standards-bundles` is NOT unshipped.** Four department bundles exist on disk with
>   `rules.yaml`, `envelope.yaml`, and `reviewers.yaml` (`standards-bundles/{architect,security,
>   privacy,finops}/v0.1.0/`, plus `security/v0.2.0/`), governed by `standards-bundles/PINS.yaml`
>   with per-team version pinning. `scripts/enforce_bundles.py:138-160` resolves PINS,
>   `:220-234` loads the CI-eligible rules per resolved version, and it **fails closed** on a
>   load error. `.github/workflows/bundle-enforce.yml` runs it on every PR with no repository
>   secret.
> - **`reviewers.yaml` already encodes N-of-M quorum policy** — per `blast_class`,
>   a `required_approvers` count plus `must_include_roles` (security `HIGH` = 3 approvers,
>   must include `security_lead` and `privacy_dpo`). This is the exact policy GitHub Environments
>   cannot express, and it exists as data today.
>
> The checkbox state is a documentation-hygiene defect, not a capability gap. Treat the 0% list as
> "needs verification per change," not "unshipped." The load-bearing finding of this audit —
> `accuracy_score` = 0.0 on all 229 live entries with no compute site — was separately verified
> and stands.

---

## Adversarial bottom line

**Where we genuinely beat Overcut (real code):**
- **Server-side, config-flooded hard gate** (target 5). Overcut's HumanGate is an orchestration
  policy object; ours is an HTTP 409 a `curl` cannot rubber-stamp, with a PHI/auth floor that env
  can extend but never shrink. This is our single strongest *implemented* differentiator.
- **`autonomy_ref` + `gh_audit_xref` as queryable audit facts** (targets 7/7b) — the WHY and the
  GitHub cross-ref are stamped on the persisted decision, not display-only. Overcut's `decidedBy`
  is comparable but lives in the orchestration runtime, not on an immutable ledger row.
- **Precedent-gated autopilot** (target 1) is wired end-to-end: `find_precedent` actually decides
  autopilot-vs-gate, not just a declared field.

**Where our pitch out-runs our code (Overcut is ahead in shipped substance):**
- **No inter-agent scratch tier (target 3).** Overcut's two-tier scratchpad/memory split is a real
  runtime primitive; we have exactly one channel (the stage payload) and zero shared scratch store.
- **No cross-run learning (target 4).** Overcut ships a weighted memory system with a 10-run
  retrospective. Our `accuracy_score` is `0.0` on all 229 live entries — the teaching loop is
  75% specced and **0% computing**. The "learning loop" claim is currently a schema, not a behavior.
- **No rejected-alternatives capture (target 6).** Overcut persists the *full weighed candidate
  set* (`proposals` JSON) on every `OrchestrationDecision`. We persist only the chosen option.
  The lifecycle that would add alternatives+confidence is 87% done but **not on the stored schema**.
- **`bundle_refs` is coarse (target 2):** real rule-namespace IDs, but stamped from the stage's
  static subscription list — not the specific rule *evaluated* for that decision. Defensible as
  "the governing bundle set," weaker than "the rule that decided this."

**One-line framing:** We win on *enforcement and auditability of a single decision* (hard gate,
autonomy_ref, gh xref — all real code). Overcut wins on *cross-decision memory and transparency of
the alternatives weighed* (scratch tier, weighted memory, `proposals`) — areas where our specs are
strong (75–87% tasks) but the code is 0% populated for the load-bearing fields.
