/* Model client for the assistant. Azure OpenAI, keyless (Entra ID):
 * DefaultAzureCredential resolves `az login` locally and the container's
 * user-assigned managed identity in Azure (AZURE_CLIENT_ID). No API keys.
 * Unconfigured → returns null and the caller falls back to the
 * deterministic composer, labelled as such. */
import { DefaultAzureCredential } from "@azure/identity";

const env = process.env;
let credential: DefaultAzureCredential | null = null;

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
  credential ??= new DefaultAzureCredential(env.AZURE_CLIENT_ID ? { managedIdentityClientId: env.AZURE_CLIENT_ID } : {});
  const token = await credential.getToken("https://cognitiveservices.azure.com/.default");
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 45_000);
  try {
    const res = await fetch(
      `${cfg.endpoint}/openai/deployments/${cfg.deployment}/chat/completions?api-version=${cfg.apiVersion}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token.token}` },
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
