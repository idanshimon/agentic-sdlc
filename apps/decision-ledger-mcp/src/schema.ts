import { z } from "zod";

// ------------ ledger entry shapes (mirror packages/ledger-core/models.py) -----
export const ActorSchema = z.object({
  kind: z.enum(["human", "agent"]),
  id: z.string(),
  display_name: z.string().optional().nullable(),
});

export const RuntimeKindSchema = z.enum([
  "stage_decision",
  "ide_session_summary",
  "ide_tool_call",
  "auto_fix",
  "delivered",
  "plan_proposed",
  "phi_block",
]);

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
}).refine(
  (e) => e.run_id != null || e.agent_session_id != null,
  { message: "runtime entry requires at least one of: run_id, agent_session_id" }
);

// ------------ tool input schemas ---------------------------------------------
export const LedgerQueryInputSchema = z.object({
  team_id: z.string(),
  limit: z.number().int().min(1).max(200).optional().default(25),
  entry_type: z.enum(["runtime", "meta"]).optional(),
  agent_session_id: z.string().optional(),
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
