/* Model client for the assistant. Azure OpenAI, keyless (Entra ID). No API
 * keys and no SDK:
 *   - In Azure Container Apps: the managed-identity endpoint the platform
 *     injects (IDENTITY_ENDPOINT + IDENTITY_HEADER), user-assigned via
 *     AZURE_CLIENT_ID.
 *   - Locally: `az account get-access-token` from the developer's az login.
 * (@azure/identity was dropped: every release pins a vulnerable msal-node,
 * GHSA-xcx6-jx8p-x3h5, and only a token is needed here.)
 * Unconfigured → returns null and the caller falls back to the deterministic
 * composer, labelled as such. */
import { execFile } from "node:child_process";
import { promisify } from "node:util";

const run = promisify(execFile);
const RESOURCE = "https://cognitiveservices.azure.com";

let cached: { token: string; expiresAt: number } | null = null;

async function getToken(): Promise<string> {
  if (cached && cached.expiresAt - Date.now() > 5 * 60_000) return cached.token;
  const idEndpoint = process.env.IDENTITY_ENDPOINT;
  const idHeader = process.env.IDENTITY_HEADER;
  if (idEndpoint && idHeader) {
    const q = new URLSearchParams({ "api-version": "2019-08-01", resource: RESOURCE });
    if (process.env.AZURE_CLIENT_ID) q.set("client_id", process.env.AZURE_CLIENT_ID);
    const res = await fetch(`${idEndpoint}?${q}`, { headers: { "X-IDENTITY-HEADER": idHeader }, cache: "no-store" });
    if (!res.ok) throw new Error(`managed identity token ${res.status}`);
    const j = (await res.json()) as { access_token: string; expires_on: string | number };
    cached = { token: j.access_token, expiresAt: Number(j.expires_on) * 1000 };
    return cached.token;
  }
  const { stdout } = await run("az", ["account", "get-access-token", "--resource", RESOURCE, "-o", "json"], {
    timeout: 20_000,
  });
  const j = JSON.parse(stdout) as { accessToken: string; expires_on?: number; expiresOn?: string };
  const exp = j.expires_on ? j.expires_on * 1000 : Date.parse(j.expiresOn ?? "") || Date.now() + 30 * 60_000;
  cached = { token: j.accessToken, expiresAt: exp };
  return cached.token;
}

const env = process.env;

export interface ModelConfig { endpoint: string; deployment: string; apiVersion: string }

export function modelConfig(): ModelConfig | null {
  const endpoint = env.ASSIST_AOAI_ENDPOINT ?? env.AOAI_ENDPOINT;
  if (!endpoint) return null;
  return {
    endpoint: endpoint.replace(/\/$/, ""),
    deployment: env.ASSIST_AOAI_DEPLOYMENT ?? "gpt-4-1-mini",
    apiVersion: env.ASSIST_AOAI_API_VERSION ?? "2024-10-21",
  };
}

export async function chatCompletion(
  cfg: ModelConfig,
  messages: Array<{ role: "system" | "user" | "assistant"; content: string }>,
): Promise<{ text: string; usage?: { prompt_tokens: number; completion_tokens: number } }> {
  const token = await getToken();
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 45_000);
  try {
    const res = await fetch(
      `${cfg.endpoint}/openai/deployments/${cfg.deployment}/chat/completions?api-version=${cfg.apiVersion}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ messages, temperature: 0.2, max_tokens: 700 }),
        signal: ctrl.signal,
      },
    );
    if (!res.ok) throw new Error(`model ${res.status}: ${(await res.text()).slice(0, 200)}`);
    const data = (await res.json()) as { choices: Array<{ message: { content: string } }>; usage?: { prompt_tokens: number; completion_tokens: number } };
    return { text: data.choices?.[0]?.message?.content ?? "", usage: data.usage };
  } finally {
    clearTimeout(timer);
  }
}
