import {
  LedgerQueryInputSchema,
  FindPrecedentInputSchema,
  GetBundleInputSchema,
  ClassifyPhiInputSchema,
  RuntimeEntrySchema,
} from "./schema.js";
import { writeRuntimeEntry, queryEntries, findPrecedent } from "./cosmos-client.js";
import { getBundle } from "./bundle-loader.js";
import { classifyPhi } from "./phi-classifier.js";

export interface ToolDef {
  name: string;
  description: string;
  inputSchema: { type: "object"; properties: Record<string, unknown>; required?: string[] };
  handler: (input: unknown, authedTeamId: string) => Promise<unknown>;
}

export const tools: Record<string, ToolDef> = {
  "ledger.query": {
    name: "ledger.query",
    description: "Read decision ledger entries by team, with optional filters on entry_type, session, bundle_ref prefix. team_id defaults to the authed team when omitted.",
    inputSchema: {
      type: "object",
      properties: {
        team_id: { type: "string" },
        limit: { type: "number", minimum: 1, maximum: 200 },
        entry_type: { type: "string", enum: ["runtime", "meta"] },
        agent_session_id: { type: "string" },
        bundle_ref_prefix: { type: "string" },
      },
      // team_id is no longer "required" — defaults to the authed team
      required: [],
    },
    handler: async (input, authedTeamId) => {
      const args = LedgerQueryInputSchema.parse(input);
      // Default to the authed team when caller omits team_id (the common
      // dashboard read pattern). Cross-team requests are still rejected.
      const team_id = args.team_id ?? authedTeamId;
      if (team_id !== authedTeamId) {
        throw new Error(`Token scoped to '${authedTeamId}'; request targeted '${team_id}'`);
      }
      const entries = await queryEntries({
        team_id,
        limit: args.limit,
        entry_type: args.entry_type,
        agent_session_id: args.agent_session_id,
        bundle_ref_prefix: args.bundle_ref_prefix,
      });
      // Echo the team the query actually ran against so the dashboard can show
      // WHICH partition it read (KI-1: a run under a different team_id is
      // invisible to this token; surfacing the team makes that explicit instead
      // of a silent empty result).
      return { entries, team_id };
    },
  },

  "ledger.write_runtime": {
    name: "ledger.write_runtime",
    description: "Write a runtime decision ledger entry (validated against schema).",
    inputSchema: {
      type: "object",
      properties: {
        team_id: { type: "string" },
        actor: { type: "object" },
        decision: { type: "string" },
        rationale: { type: "string" },
        bundle_refs: { type: "array", items: { type: "string" } },
        run_id: { type: "string" },
        agent_session_id: { type: "string" },
        runtime_kind: { type: "string" },
      },
      required: ["team_id", "actor", "decision"],
    },
    handler: async (input, authedTeamId) => {
      const args = RuntimeEntrySchema.parse(input);
      if (args.team_id !== authedTeamId) {
        throw new Error(`Token scoped to '${authedTeamId}'; request targeted '${args.team_id}'`);
      }
      return await writeRuntimeEntry(args);
    },
  },

  "ledger.find_precedent": {
    name: "ledger.find_precedent",
    description: "Most recent precedent matching (team, ambiguity_class, slot_value_hash).",
    inputSchema: {
      type: "object",
      properties: {
        team_id: { type: "string" },
        ambiguity_class: { type: "string" },
        slot_value_hash: { type: "string" },
      },
      required: ["team_id", "ambiguity_class", "slot_value_hash"],
    },
    handler: async (input, authedTeamId) => {
      const args = FindPrecedentInputSchema.parse(input);
      if (args.team_id !== authedTeamId) {
        throw new Error(`Token scoped to '${authedTeamId}'; request targeted '${args.team_id}'`);
      }
      const entry = await findPrecedent(args);
      return { entry };
    },
  },

  "ledger.get_bundle": {
    name: "ledger.get_bundle",
    description: "Fetch a standards bundle by dept + version (rules + envelope + metadata).",
    inputSchema: {
      type: "object",
      properties: {
        dept: { type: "string", enum: ["architect", "security", "privacy", "finops"] },
        version: { type: "string" },
      },
      required: ["dept", "version"],
    },
    handler: async (input, _authedTeamId) => {
      const args = GetBundleInputSchema.parse(input);
      return getBundle(args.dept, args.version);
    },
  },

  "ledger.classify_phi": {
    name: "ledger.classify_phi",
    description: "Run the PHI classifier on text; returns has_phi + matched patterns + bundle refs.",
    inputSchema: {
      type: "object",
      properties: {
        text: { type: "string", maxLength: 8000 },
      },
      required: ["text"],
    },
    handler: async (input, _authedTeamId) => {
      const args = ClassifyPhiInputSchema.parse(input);
      return classifyPhi(args.text);
    },
  },

  // -------- Track B: teaching-signal write paths -------------------------
  // Each tool below writes a runtime entry of a specific runtime_kind.
  // The handlers all delegate to writeRuntimeEntry after building a
  // RuntimeEntrySchema-valid object — this keeps the audit trail uniform
  // (the /decisions page renders teaching signals alongside stage decisions
  // because they're all just runtime entries with different runtime_kind).

  "ledger.add_feedback": {
    name: "ledger.add_feedback",
    description: "Operator thumbs up/down on a past decision. Lightest-weight teaching signal — no rationale required, used for sentiment aggregation.",
    inputSchema: {
      type: "object",
      properties: {
        team_id: { type: "string" },
        actor: { type: "object" },
        references_entry_id: { type: "string" },
        feedback_kind: { type: "string", enum: ["thumbs_up", "thumbs_down"] },
        rationale: { type: "string" },
        agent_session_id: { type: "string" },
      },
      required: ["actor", "references_entry_id", "feedback_kind"],
    },
    handler: async (input, authedTeamId) => {
      const raw = input as Record<string, unknown>;
      const team_id = (raw.team_id as string | undefined) ?? authedTeamId;
      if (team_id !== authedTeamId) {
        throw new Error(`Token scoped to '${authedTeamId}'; request targeted '${team_id}'`);
      }
      // Validate at the handler boundary — the inputSchema `required` array is
      // advertised to MCP clients but NOT enforced server-side, and naively
      // coercing missing values via String(undefined) yields the literal
      // string "undefined" which the schema refine would happily accept.
      const refIdRaw = raw.references_entry_id;
      if (typeof refIdRaw !== "string" || refIdRaw.length === 0) {
        throw new Error("references_entry_id is required and must be a non-empty string");
      }
      const kindRaw = raw.feedback_kind;
      if (kindRaw !== "thumbs_up" && kindRaw !== "thumbs_down") {
        throw new Error("feedback_kind is required and must be 'thumbs_up' or 'thumbs_down'");
      }
      const args = RuntimeEntrySchema.parse({
        team_id,
        actor: raw.actor,
        decision: `${kindRaw} on ${refIdRaw}`,
        rationale: typeof raw.rationale === "string" ? raw.rationale : "",
        runtime_kind: "feedback_thumbs",
        references_entry_id: refIdRaw,
        feedback_kind: kindRaw,
        agent_session_id: (raw.agent_session_id as string | undefined) ?? `feedback-${Date.now()}`,
      });
      return await writeRuntimeEntry(args);
    },
  },

  "ledger.flag_decision": {
    name: "ledger.flag_decision",
    description: "Flag a past decision as wrong. Stops findPrecedent from returning it next time. Audit-preserving — original decision is NOT modified.",
    inputSchema: {
      type: "object",
      properties: {
        team_id: { type: "string" },
        actor: { type: "object" },
        references_entry_id: { type: "string" },
        rationale: { type: "string" },
        agent_session_id: { type: "string" },
      },
      required: ["actor", "references_entry_id", "rationale"],
    },
    handler: async (input, authedTeamId) => {
      const raw = input as Record<string, unknown>;
      const team_id = (raw.team_id as string | undefined) ?? authedTeamId;
      if (team_id !== authedTeamId) {
        throw new Error(`Token scoped to '${authedTeamId}'; request targeted '${team_id}'`);
      }
      const refIdRaw = raw.references_entry_id;
      if (typeof refIdRaw !== "string" || refIdRaw.length === 0) {
        throw new Error("references_entry_id is required and must be a non-empty string");
      }
      const rationaleRaw = raw.rationale;
      if (typeof rationaleRaw !== "string" || rationaleRaw.length === 0) {
        throw new Error("rationale is required when flagging a decision");
      }
      const args = RuntimeEntrySchema.parse({
        team_id,
        actor: raw.actor,
        decision: `Flagged decision ${refIdRaw} as wrong`,
        rationale: rationaleRaw,
        runtime_kind: "decision_flagged",
        references_entry_id: refIdRaw,
        agent_session_id: (raw.agent_session_id as string | undefined) ?? `flag-${Date.now()}`,
      });
      return await writeRuntimeEntry(args);
    },
  },

  "ledger.request_replay": {
    name: "ledger.request_replay",
    description: "Request a replay of a past decision against current bundles. Writes a durable request entry; the orchestrator-side worker that actually re-runs is Track C.",
    inputSchema: {
      type: "object",
      properties: {
        team_id: { type: "string" },
        actor: { type: "object" },
        references_entry_id: { type: "string" },
        rationale: { type: "string" },
        agent_session_id: { type: "string" },
      },
      required: ["actor", "references_entry_id"],
    },
    handler: async (input, authedTeamId) => {
      const raw = input as Record<string, unknown>;
      const team_id = (raw.team_id as string | undefined) ?? authedTeamId;
      if (team_id !== authedTeamId) {
        throw new Error(`Token scoped to '${authedTeamId}'; request targeted '${team_id}'`);
      }
      const refIdRaw = raw.references_entry_id;
      if (typeof refIdRaw !== "string" || refIdRaw.length === 0) {
        throw new Error("references_entry_id is required and must be a non-empty string");
      }
      const args = RuntimeEntrySchema.parse({
        team_id,
        actor: raw.actor,
        decision: `Requested replay of ${refIdRaw} against current rules`,
        rationale: typeof raw.rationale === "string" ? raw.rationale : "",
        runtime_kind: "replay_requested",
        references_entry_id: refIdRaw,
        agent_session_id: (raw.agent_session_id as string | undefined) ?? `replay-${Date.now()}`,
      });
      return await writeRuntimeEntry(args);
    },
  },

  "ledger.pause_class": {
    name: "ledger.pause_class",
    description: "Pause autopilot for an entire ambiguity class. findPrecedent returns null for any decision in the paused class until cleared. Most consequential teaching signal.",
    inputSchema: {
      type: "object",
      properties: {
        team_id: { type: "string" },
        actor: { type: "object" },
        paused_class: { type: "string" },
        rationale: { type: "string" },
        agent_session_id: { type: "string" },
      },
      required: ["actor", "paused_class", "rationale"],
    },
    handler: async (input, authedTeamId) => {
      const raw = input as Record<string, unknown>;
      const team_id = (raw.team_id as string | undefined) ?? authedTeamId;
      if (team_id !== authedTeamId) {
        throw new Error(`Token scoped to '${authedTeamId}'; request targeted '${team_id}'`);
      }
      const clsRaw = raw.paused_class;
      if (typeof clsRaw !== "string" || clsRaw.length === 0) {
        throw new Error("paused_class is required and must be a non-empty string");
      }
      const rationaleRaw = raw.rationale;
      if (typeof rationaleRaw !== "string" || rationaleRaw.length === 0) {
        throw new Error("rationale is required when pausing a class");
      }
      const args = RuntimeEntrySchema.parse({
        team_id,
        actor: raw.actor,
        decision: `Paused autopilot for class '${clsRaw}'`,
        rationale: rationaleRaw,
        runtime_kind: "class_paused",
        paused_class: clsRaw,
        ambiguity_class: clsRaw,
        agent_session_id: (raw.agent_session_id as string | undefined) ?? `pause-${Date.now()}`,
      });
      return await writeRuntimeEntry(args);
    },
  },
};

export const toolList = Object.values(tools).map((t) => ({
  name: t.name,
  description: t.description,
  inputSchema: t.inputSchema,
}));
