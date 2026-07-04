/* API endpoint configuration. Reads from NEXT_PUBLIC_* env vars at build
   AND at runtime via window.__APP_CONFIG__ (so a single Docker image can
   target multiple environments by re-rendering a config script).

   CRITICAL — Next.js inlines NEXT_PUBLIC_* into the client bundle ONLY for
   STATIC, literal property accesses it can pattern-match at build time:

       process.env.NEXT_PUBLIC_ORCHESTRATOR_URL   ✅ inlined
       process.env[`NEXT_PUBLIC_${key}`]          ❌ NEVER inlined → undefined in browser

   The previous version used the dynamic computed form, so in the browser the
   build-time value was always `undefined` and the client silently fell back to
   the hardcoded URL below — meaning --build-arg NEXT_PUBLIC_ORCHESTRATOR_URL
   had NO effect on the shipped bundle. Keep these accesses static. */

declare global {
  interface Window {
    __APP_CONFIG__?: {
      ORCHESTRATOR_URL?: string;
      LEDGER_MCP_URL?: string;
    };
  }
}

// Default backends — the live VNET-integrated Container Apps (post 2026-06-10
// private-network cutover). The old *.whitewater-* apps are decommissioned:
// their Cosmos data path is firewalled (publicNetworkAccess Disabled), so any
// client pointed at them gets HTTP 400 / "Run not found". Never default to them.
const DEFAULT_ORCHESTRATOR_URL =
  "https://ca-orchestrator-vnet.thankfulflower-0a94d0d3.eastus2.azurecontainerapps.io";
const DEFAULT_LEDGER_MCP_URL =
  "https://ca-ledger-mcp-vnet.thankfulflower-0a94d0d3.eastus2.azurecontainerapps.io";

export const apiConfig = {
  get orchestratorUrl(): string {
    // Browser: prefer runtime config, then the build-time-inlined env, then default.
    if (typeof window !== "undefined") {
      return (
        window.__APP_CONFIG__?.ORCHESTRATOR_URL ||
        process.env.NEXT_PUBLIC_ORCHESTRATOR_URL ||
        DEFAULT_ORCHESTRATOR_URL
      );
    }
    // Server (Node / RSC / route handlers): unprefixed wins, then public, then default.
    return (
      process.env.ORCHESTRATOR_URL ||
      process.env.NEXT_PUBLIC_ORCHESTRATOR_URL ||
      DEFAULT_ORCHESTRATOR_URL
    );
  },
  get ledgerMcpUrl(): string {
    if (typeof window !== "undefined") {
      return (
        window.__APP_CONFIG__?.LEDGER_MCP_URL ||
        process.env.NEXT_PUBLIC_LEDGER_MCP_URL ||
        DEFAULT_LEDGER_MCP_URL
      );
    }
    return (
      process.env.LEDGER_MCP_URL ||
      process.env.NEXT_PUBLIC_LEDGER_MCP_URL ||
      DEFAULT_LEDGER_MCP_URL
    );
  },
};
