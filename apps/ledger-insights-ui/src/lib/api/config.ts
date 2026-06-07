/* API endpoint configuration. Reads from NEXT_PUBLIC_* env vars at build
   AND at runtime via window.__APP_CONFIG__ (so a single Docker image can
   target multiple environments by re-rendering a config script). */

declare global {
  interface Window {
    __APP_CONFIG__?: {
      ORCHESTRATOR_URL?: string;
      LEDGER_MCP_URL?: string;
    };
  }
}

function readEnv(key: string, fallback: string): string {
  // Server-side (Node): use process.env.
  if (typeof window === "undefined") {
    return process.env[key] ?? fallback;
  }
  // Browser: prefer runtime config, then build-time env.
  const runtime = window.__APP_CONFIG__?.[key as "ORCHESTRATOR_URL" | "LEDGER_MCP_URL"];
  if (runtime) return runtime;
  return process.env[`NEXT_PUBLIC_${key}`] ?? fallback;
}

export const apiConfig = {
  get orchestratorUrl() {
    return readEnv(
      "ORCHESTRATOR_URL",
      "https://ca-orchestrator.whitewater-f74a5db8.eastus2.azurecontainerapps.io",
    );
  },
  get ledgerMcpUrl() {
    return readEnv(
      "LEDGER_MCP_URL",
      "https://ca-ledger-mcp.whitewater-f74a5db8.eastus2.azurecontainerapps.io",
    );
  },
};
