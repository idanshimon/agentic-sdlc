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
    description: "Read decision ledger entries by team, with optional filters on entry_type, session, bundle_ref prefix.",
    inputSchema: {
      type: "object",
      properties: {
        team_id: { type: "string" },
        limit: { type: "number", minimum: 1, maximum: 200 },
        entry_type: { type: "string", enum: ["runtime", "meta"] },
        agent_session_id: { type: "string" },
        bundle_ref_prefix: { type: "string" },
      },
      required: ["team_id"],
    },
    handler: async (input, authedTeamId) => {
      const args = LedgerQueryInputSchema.parse(input);
      if (args.team_id !== authedTeamId) {
        throw new Error(`Token scoped to '${authedTeamId}'; request targeted '${args.team_id}'`);
      }
      const entries = await queryEntries(args);
      return { entries };
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
};

export const toolList = Object.values(tools).map((t) => ({
  name: t.name,
  description: t.description,
  inputSchema: t.inputSchema,
}));
