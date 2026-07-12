import { CosmosClient, Container } from "@azure/cosmos";
import { DefaultAzureCredential } from "@azure/identity";
import { randomUUID } from "node:crypto";

import type { LedgerEntry } from "./schema.js";

let client: CosmosClient | null = null;
let ledgerContainer: Container | null = null;

export function getCosmos(): { ledger: Container } {
  if (ledgerContainer == null) {
    const endpoint = process.env.COSMOS_ENDPOINT;
    if (!endpoint) throw new Error("COSMOS_ENDPOINT not set");
    const dbName = process.env.COSMOS_DB ?? "agentic-sdlc";
    const containerName = process.env.COSMOS_LEDGER_CONTAINER ?? "decision-ledger";

    client = new CosmosClient({
      endpoint,
      aadCredentials: new DefaultAzureCredential(),
    });
    ledgerContainer = client.database(dbName).container(containerName);
  }
  return { ledger: ledgerContainer };
}

export async function writeRuntimeEntry(entry: LedgerEntry): Promise<{ id: string }> {
  const { ledger } = getCosmos();
  const id = randomUUID();
  const created_at = new Date().toISOString();
  const doc = {
    id,
    entry_type: "runtime",
    created_at,
    ...entry,
  };
  await ledger.items.upsert(doc);
  return { id };
}

export async function queryEntries(opts: {
  team_id: string;
  limit?: number;
  entry_type?: string;
  agent_session_id?: string;
  run_id?: string;
  bundle_ref_prefix?: string;
}): Promise<unknown[]> {
  const { ledger } = getCosmos();
  const limit = opts.limit ?? 25;
  const params: Array<{ name: string; value: string | number }> = [
    { name: "@n", value: limit },
    { name: "@t", value: opts.team_id },
  ];
  let query = "SELECT TOP @n * FROM c WHERE c.team_id=@t";
  if (opts.entry_type) {
    query += " AND c.entry_type=@et";
    params.push({ name: "@et", value: opts.entry_type });
  }
  if (opts.agent_session_id) {
    query += " AND c.agent_session_id=@s";
    params.push({ name: "@s", value: opts.agent_session_id });
  }
  if (opts.run_id) {
    query += " AND c.run_id=@run";
    params.push({ name: "@run", value: opts.run_id });
  }
  if (opts.bundle_ref_prefix) {
    query += " AND EXISTS(SELECT VALUE r FROM r IN c.bundle_refs WHERE STARTSWITH(r, @br))";
    params.push({ name: "@br", value: opts.bundle_ref_prefix });
  }
  query += " ORDER BY c.created_at DESC";

  const { resources } = await ledger.items
    .query({ query, parameters: params }, { partitionKey: opts.team_id })
    .fetchAll();
  return resources;
}

export async function findPrecedent(opts: {
  team_id: string;
  ambiguity_class: string;
  slot_value_hash: string;
}): Promise<unknown | null> {
  const { ledger } = getCosmos();

  // Track B: class-pause check. If any class_paused entry exists for this
  // ambiguity_class on this team, return null — the operator has explicitly
  // disabled auto-precedent for this category until they clear it.
  const { resources: paused } = await ledger.items
    .query(
      {
        query:
          "SELECT TOP 1 c.id FROM c " +
          "WHERE c.team_id=@t AND c.runtime_kind='class_paused' AND c.paused_class=@k " +
          "ORDER BY c.created_at DESC",
        parameters: [
          { name: "@t", value: opts.team_id },
          { name: "@k", value: opts.ambiguity_class },
        ],
      },
      { partitionKey: opts.team_id }
    )
    .fetchAll();
  if (paused.length > 0) return null;

  // Track B: flag-skip. Pull a small window of candidate precedents (most
  // recent first) and exclude any that have been flagged. We cap the
  // candidate set so a heavily-flagged class doesn't degenerate into a full
  // table scan; if the top 5 are all flagged the operator should pause the
  // class anyway.
  const { resources: candidates } = await ledger.items
    .query(
      {
        query:
          "SELECT TOP 5 * FROM c " +
          "WHERE c.team_id=@t AND c.ambiguity_class=@k AND c.slot_value_hash=@s " +
          "AND c.entry_type='runtime' " +
          "AND (NOT IS_DEFINED(c.runtime_kind) OR c.runtime_kind='stage_decision') " +
          "ORDER BY c.created_at DESC",
        parameters: [
          { name: "@t", value: opts.team_id },
          { name: "@k", value: opts.ambiguity_class },
          { name: "@s", value: opts.slot_value_hash },
        ],
      },
      { partitionKey: opts.team_id }
    )
    .fetchAll();

  if (candidates.length === 0) return null;

  // Pull the set of flagged ids for this team in one query and exclude
  // matching candidates. Done in two queries instead of one nested EXISTS to
  // keep partition-scoped cost predictable.
  const { resources: flagged } = await ledger.items
    .query(
      {
        query:
          "SELECT VALUE c.references_entry_id FROM c " +
          "WHERE c.team_id=@t AND c.runtime_kind='decision_flagged' " +
          "AND IS_DEFINED(c.references_entry_id)",
        parameters: [{ name: "@t", value: opts.team_id }],
      },
      { partitionKey: opts.team_id }
    )
    .fetchAll();
  const flaggedIds = new Set<string>(flagged.filter((x): x is string => typeof x === "string"));

  for (const candidate of candidates) {
    const id = (candidate as { id?: string }).id;
    if (id && flaggedIds.has(id)) continue;
    return candidate;
  }
  return null;
}
