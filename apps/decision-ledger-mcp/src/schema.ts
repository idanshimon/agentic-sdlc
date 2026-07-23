import { z } from "zod";

// ------------ ledger entry shapes (mirror packages/ledger-core/models.py) -----
export const ActorSchema = z.object({
  kind: z.enum(["human", "agent"]),
  id: z.string(),
  display_name: z.string().optional().nullable(),
});

export const RuntimeKindSchema = z.enum([
  // Pipeline-internal kinds (orchestrator stages)
  "stage_decision",
  "ide_session_summary",
  "ide_tool_call",
  "auto_fix",
  "delivered",
  "plan_proposed",
  "phi_block",
  // Track B: teaching-signal kinds. These are operator-authored entries
  // that the system reads back to refine its future behavior. Every kind
  // here MUST set references_entry_id pointing at the decision being acted
  // upon (or, for class_paused, set paused_class to the affected ambiguity
  // class). The aggregator on /feedback reads these.
  "feedback_thumbs",      // T0 — thumbs up/down sentiment
  "decision_flagged",     // T1 — "this decision was wrong, don't reuse it as precedent"
  "replay_requested",     // T2 — "re-run the same inputs against current rules"
  "class_paused",         // T3 — "stop auto-deciding this whole ambiguity class"
  // Autonomous review loop (add-autonomous-review-loop). One hop per action;
  // each carries a reviewloop/<tier>/<repo>/<action>@attempt=N autonomy_ref.
  "review_remediation",   // one bounded codegen remediation attempt
  "loop_converged",       // terminal PASS (auto-merged or awaiting human merge)
  "loop_escalated",       // terminal escalation to a human (exhaustion / cost / PHI floor)
]);

/**
 * Track B: feedback_kind discriminates the thumbs subkind. Only meaningful
 * when runtime_kind === "feedback_thumbs". Other kinds ignore it.
 */
export const FeedbackKindSchema = z.enum(["thumbs_up", "thumbs_down"]);

export const PHIClassSchema = z.enum(["none", "low", "high"]);

export const RuntimeEntrySchema = z.object({
  team_id: z.string(),
  actor: ActorSchema,
  decision: z.string(),
  rationale: z.string().optional().default(""),
  cost_usd: z.number().optional().default(0),
  model_used: z.string().optional().nullable(),
  bundle_refs: z.array(z.string()).optional().default([]),
  precedent_refs: z.array(z.string()).optional().default([]),
  phi_class: PHIClassSchema.optional().default("none"),
  agent_session_id: z.string().optional().nullable(),
  gh_audit_xref: z.string().optional().nullable(),
  run_id: z.string().optional().nullable(),
  stage: z.string().optional().nullable(),
  runtime_kind: RuntimeKindSchema.optional().nullable(),
  ambiguity_class: z.string().optional().nullable(),
  // Track B teaching-signal fields. All optional and additive — pre-Track-B
  // entries that don't include them parse identically. Specific runtime_kinds
  // require specific subsets of these (enforced via .refine below):
  //
  //   feedback_thumbs   → references_entry_id REQUIRED, feedback_kind REQUIRED
  //   decision_flagged  → references_entry_id REQUIRED
  //   replay_requested  → references_entry_id REQUIRED
  //   class_paused      → paused_class REQUIRED
  references_entry_id: z.string().optional().nullable(),
  feedback_kind: FeedbackKindSchema.optional().nullable(),
  paused_class: z.string().optional().nullable(),
}).refine(
  (e) => e.run_id != null || e.agent_session_id != null,
  { message: "runtime entry requires at least one of: run_id, agent_session_id" }
).refine(
  (e) => {
    if (e.runtime_kind === "feedback_thumbs") {
      return e.references_entry_id != null && e.feedback_kind != null;
    }
    if (e.runtime_kind === "decision_flagged" || e.runtime_kind === "replay_requested") {
      return e.references_entry_id != null;
    }
    if (e.runtime_kind === "class_paused") {
      return e.paused_class != null && e.paused_class.length > 0;
    }
    return true;
  },
  { message: "teaching-signal entries require their associated reference: feedback_thumbs needs references_entry_id+feedback_kind; decision_flagged/replay_requested need references_entry_id; class_paused needs paused_class" }
);

// ------------ tool input schemas ---------------------------------------------
// `team_id` is optional in the SCHEMA; the handler defaults it to the authed
// team when absent. This keeps the partition-scoped query intact (no
// cross-tenant reads) while letting the dashboard call ledger.query without
// hard-coding a team id in the client. See openspec change
// fix-decisions-page-empty-on-cold-load for the full rationale.
export const LedgerQueryInputSchema = z.object({
  team_id: z.string().optional(),
  limit: z.number().int().min(1).max(2000).optional().default(25),
  entry_type: z.enum(["runtime", "meta"]).optional(),
  agent_session_id: z.string().optional(),
  run_id: z.string().optional(),
  bundle_ref_prefix: z.string().optional(),
});

export const FindPrecedentInputSchema = z.object({
  team_id: z.string(),
  ambiguity_class: z.string(),
  slot_value_hash: z.string(),
});

export const GetBundleInputSchema = z.object({
  dept: z.enum(["architect", "security", "privacy", "finops"]),
  version: z.string().regex(/^v\d+\.\d+\.\d+(-[a-z0-9]+)?$/),
});

export const ClassifyPhiInputSchema = z.object({
  text: z.string().max(8000),
});

// ------------ tool output shapes ---------------------------------------------
export type LedgerEntry = z.infer<typeof RuntimeEntrySchema>;

export interface ClassifyPhiResult {
  has_phi: boolean;
  phi_class: "none" | "low" | "high";
  matched_patterns: string[];
  bundle_refs: string[];
}

export interface BundleResult {
  metadata: Record<string, unknown>;
  rules: Array<Record<string, unknown>>;
  envelope: Record<string, unknown>;
}
