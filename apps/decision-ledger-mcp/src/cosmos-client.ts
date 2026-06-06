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
  const { resources } = await ledger.items
    .query(
      {
        query:
          "SELECT TOP 1 * FROM c " +
          "WHERE c.team_id=@t AND c.ambiguity_class=@k AND c.slot_value_hash=@s " +
          "AND c.entry_type='runtime' ORDER BY c.created_at DESC",
        parameters: [
          { name: "@t", value: opts.team_id },
          { name: "@k", value: opts.ambiguity_class },
          { name: "@s", value: opts.slot_value_hash },
        ],
      },
      { partitionKey: opts.team_id }
    )
    .fetchAll();
  return resources[0] ?? null;
}
