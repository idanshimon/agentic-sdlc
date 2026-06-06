#!/usr/bin/env node
/**
 * Decision Ledger MCP server.
 *
 * Two transports:
 *   - stdio (default): MCP over stdin/stdout — use from VS Code / Copilot CLI
 *   - http: REST-shaped wrapper for the hook scripts (curl-friendly)
 *
 * Both use the same tool handlers + same auth + same Cosmos backend.
 *
 * Auth: Bearer token in Authorization header (HTTP) or initialize params (stdio).
 * Each token maps to a single team_id; cross-team queries are refused.
 */
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import express from "express";
import { tools, toolList } from "./tools.js";
import { authenticate, loadTokenMap } from "./auth.js";

loadTokenMap();

// ---------- shared handler ----------
async function dispatchTool(name: string, args: unknown, authedTeamId: string) {
  const def = tools[name];
  if (!def) throw new Error(`Unknown tool: ${name}`);
  return await def.handler(args ?? {}, authedTeamId);
}

// ---------- stdio transport (MCP) ----------
async function runStdio() {
  const server = new Server(
    { name: "decision-ledger-mcp", version: "0.7.0" },
    { capabilities: { tools: {} } }
  );

  server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools: toolList }));

  server.setRequestHandler(CallToolRequestSchema, async (req) => {
    const teamFromEnv = process.env.LEDGER_TEAM_ID;
    if (!teamFromEnv) {
      throw new Error("LEDGER_TEAM_ID required for stdio transport (per-process scoping)");
    }
    const result = await dispatchTool(req.params.name, req.params.arguments, teamFromEnv);
    return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
  });

  const transport = new StdioServerTransport();
  await server.connect(transport);
}

// ---------- http transport (rest-shaped, for hook scripts) ----------
async function runHttp(port: number) {
  const app = express();
  app.use(express.json({ limit: "1mb" }));

  app.get("/healthz", (_req, res) => res.json({ status: "ok", version: "0.7.0" }));

  app.get("/tools", (_req, res) => res.json({ tools: toolList }));

  app.post("/tools/:name", async (req, res) => {
    try {
      const teamId = authenticate(req.header("Authorization"));
      const result = await dispatchTool(req.params.name, req.body, teamId);
      res.json(result);
    } catch (e) {
      const msg = (e as Error).message;
      const status = msg.includes("token") || msg.includes("Authorization") ? 401 :
                     msg.includes("Unknown tool") ? 404 : 400;
      res.status(status).json({ error: msg });
    }
  });

  await new Promise<void>((resolve) => {
    app.listen(port, () => {
      // eslint-disable-next-line no-console
      console.log(`decision-ledger-mcp HTTP listening on :${port}`);
      resolve();
    });
  });
}

// ---------- entrypoint ----------
async function main() {
  const args = process.argv.slice(2);
  const transportFlag = args.indexOf("--transport");
  const portFlag = args.indexOf("--port");
  const transport =
    transportFlag >= 0 ? args[transportFlag + 1] :
    process.env.MCP_TRANSPORT ?? "stdio";
  const port = parseInt(
    portFlag >= 0 ? args[portFlag + 1] : (process.env.MCP_PORT ?? "3001"),
    10
  );

  if (transport === "http") {
    await runHttp(port);
  } else {
    await runStdio();
  }
}

main().catch((e) => {
  // eslint-disable-next-line no-console
  console.error("Fatal:", e);
  process.exit(1);
});
