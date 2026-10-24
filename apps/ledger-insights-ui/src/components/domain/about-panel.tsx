"use client";
/* About — build and backend identity. Lives as the last Settings tab, out of
 * the way: no one needs it until they need to report a bug or check which
 * build is deployed. */
import { useEffect, useState } from "react";
import { Copy, Check } from "lucide-react";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const BUILD = {
  version: process.env.NEXT_PUBLIC_APP_VERSION ?? "unknown",
  sha: process.env.NEXT_PUBLIC_BUILD_SHA ?? "unknown",
  dirty: process.env.NEXT_PUBLIC_BUILD_DIRTY === "1",
  time: process.env.NEXT_PUBLIC_BUILD_TIME,
  demo: process.env.NEXT_PUBLIC_DEMO_MODE !== "0",
};
const REPO = "https://github.com/idanshimon/agentic-sdlc";

interface AboutResponse {
  orchestrator: {
    host: string; reachable: boolean; latency_ms: number; status: string | null;
    api_title: string | null; api_version: string | null; endpoints: number | null; supports_settings: boolean | null;
  };
  ledger_mcp: { host: string | null; reachable: boolean; latency_ms?: number | null; note?: string };
  assistant_model: { configured: boolean; deployment?: string };
  server_time: string;
}

function Row({ k, children, mono }: { k: string; children: React.ReactNode; mono?: boolean }) {
  return (
    <div className="flex items-baseline gap-4 py-1.5">
      <dt className="w-36 shrink-0 text-[var(--text-tertiary)]">{k}</dt>
      <dd className={cn("min-w-0 flex-1 text-[var(--text-secondary)]", mono && "mono")}>{children}</dd>
    </div>
  );
}

function Dot({ ok }: { ok: boolean | null | undefined }) {
  return (
    <span
      className={cn("mr-1.5 inline-block h-1.5 w-1.5 rounded-full align-middle",
        ok ? "bg-[var(--success)]" : ok === false ? "bg-[var(--danger)]" : "bg-[var(--text-tertiary)]")}
    />
  );
}

/** Long container-app hostnames: truncate, full value on hover. */
function Host({ ok, host }: { ok: boolean; host: string }) {
  return (
    <div className="flex min-w-0 items-center">
      <Dot ok={ok} />
      <span className="mono truncate" title={host}>{host}</span>
    </div>
  );
}

export function AboutTab() {
  const [live, setLive] = useState<AboutResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    fetch("/api/about", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(setLive)
      .catch((e) => setErr(e instanceof Error ? e.message : String(e)));
  }, []);

  const builtAt = BUILD.time ? new Date(BUILD.time) : null;
  const summary = [
    `Ledger Insights UI ${BUILD.version} (${BUILD.sha}${BUILD.dirty ? "-dirty" : ""})`,
    builtAt && `built ${builtAt.toISOString()}`,
    live && `orchestrator ${live.orchestrator.api_version ?? "?"} @ ${live.orchestrator.host}`,
    live?.ledger_mcp.host && `ledger-mcp @ ${live.ledger_mcp.host}`,
  ].filter(Boolean).join("\n");

  return (
    <Card className="max-w-2xl space-y-4 p-5 text-xs">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold text-[var(--text)]">Agentic SDLC · Ledger Insights</h2>
          <p className="mt-0.5 text-[var(--text-tertiary)]">
            Operator console for the governed agentic SDLC demo. Read-only over the Decision Ledger.
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            navigator.clipboard.writeText(summary).then(() => {
              setCopied(true);
              setTimeout(() => setCopied(false), 1500);
            });
          }}
          className="inline-flex shrink-0 items-center gap-1 rounded-md border border-[var(--border-default)] px-2 py-1 text-[11px] text-[var(--text-secondary)] hover:bg-[var(--overlay)]"
        >
          {copied ? <Check className="h-3 w-3 text-[var(--success)]" /> : <Copy className="h-3 w-3" />}
          {copied ? "Copied" : "Copy for bug report"}
        </button>
      </div>

      <section>
        <h3 className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">This build</h3>
        <dl className="divide-y divide-[var(--border-muted)]">
          <Row k="Version" mono>{BUILD.version}</Row>
          <Row k="Commit" mono>
            {BUILD.sha !== "unknown" ? (
              <a href={`${REPO}/commit/${BUILD.sha}`} target="_blank" rel="noopener noreferrer" className="text-[var(--primary)] hover:underline">
                {BUILD.sha}
              </a>
            ) : "unknown"}
            {BUILD.dirty && <span className="ml-1.5 text-[var(--warning)]">+ uncommitted changes</span>}
          </Row>
          <Row k="Built">{builtAt ? builtAt.toLocaleString() : "not recorded"}</Row>
          <Row k="Mode">{BUILD.demo ? "Demo mode (no sign-in)" : "Signed-in (EasyAuth)"}</Row>
        </dl>
      </section>

      <section>
        <h3 className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">Connected services</h3>
        {err && <p className="text-[var(--danger)]">Could not probe backends: {err}</p>}
        {!live && !err && <p className="text-[var(--text-tertiary)]">Checking…</p>}
        {live && (
          <dl className="divide-y divide-[var(--border-muted)]">
            <Row k="Orchestrator">
              <Host ok={live.orchestrator.reachable} host={live.orchestrator.host} />
              {live.orchestrator.reachable && (
                <div className="text-[var(--text-tertiary)]">
                  API {live.orchestrator.api_version ?? "version not reported"} · {live.orchestrator.endpoints ?? "?"} endpoints · {live.orchestrator.latency_ms} ms
                </div>
              )}
              {live.orchestrator.supports_settings === false && (
                <div className="mt-0.5 text-[var(--warning)]">
                  Older than this UI — Settings is assembled from the endpoints it serves.
                </div>
              )}
            </Row>
            <Row k="Ledger MCP">
              {live.ledger_mcp.host ? (
                <>
                  <Host ok={live.ledger_mcp.reachable} host={live.ledger_mcp.host} />
                  {live.ledger_mcp.latency_ms != null && <div className="text-[var(--text-tertiary)]">{live.ledger_mcp.latency_ms} ms</div>}
                </>
              ) : (
                <><Dot ok={null} /><span className="text-[var(--text-tertiary)]">{live.ledger_mcp.note}</span></>
              )}
            </Row>
            <Row k="Assistant model">
              <Dot ok={live.assistant_model.configured ? true : null} />
              {live.assistant_model.configured ? (
                <span className="mono">{live.assistant_model.deployment}</span>
              ) : (
                <span className="text-[var(--text-tertiary)]">not configured · offline composer</span>
              )}
            </Row>
          </dl>
        )}
      </section>

      <p className="text-[var(--text-tertiary)]">
        Source:{" "}
        <a href={REPO} target="_blank" rel="noopener noreferrer" className="text-[var(--primary)] hover:underline">
          {REPO.replace("https://", "")}
        </a>
      </p>
    </Card>
  );
}
