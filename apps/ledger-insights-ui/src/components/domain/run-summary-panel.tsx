/**
 * RunSummaryPanel — dense, fact-dump panel for the per-run drilldown.
 *
 * The previous 3-card row (Spend / Decisions / Created) didn't say WHICH
 * model produced the run, didn't show stage durations, didn't surface the
 * harness provenance (namespace, source_run_dir). Operators couldn't tell
 * if they were looking at a sonnet run or a haiku run without leaving
 * the page.
 *
 * This panel surfaces:
 *   - Cost / tokens / wall clock at the top
 *   - Stage duration mini-bars (visual proportion of each stage)
 *   - Per-stage model routing (provider + model)
 *   - Output artifact sizes (chars per artifact)
 *   - Experiment-namespace provenance when present
 *
 * Defensive: every field falls back gracefully when missing.
 */
"use client";

import { Card } from "@/components/ui/card";
import type { RunState } from "@/lib/types";
import { fmtUsd, cn } from "@/lib/utils";

const STAGE_ORDER = [
  "ingest", "assessor", "architect", "test_plan",
  "codegen", "review_scan", "deliver",
];

export function RunSummaryPanel({ run }: { run: RunState }) {
  const totalCost = run.total_cost_usd ?? run.cost_usd ?? 0;
  const totalTokens = run.total_tokens ?? 0;
  const wallClock = run.wall_clock_seconds;

  const durations = run.stage_durations_seconds ?? {};
  const totalDuration = Object.values(durations).reduce((s, v) => s + v, 0);
  const stageRows = STAGE_ORDER
    .map((s) => ({ stage: s, secs: durations[s] ?? 0 }))
    .filter((r) => r.secs > 0);

  const routing = run.model_routing ?? {};
  const routingRows = Object.entries(routing).filter(
    ([, v]) => v && (v.provider || v.model),
  );

  const artifactSizes = run.artifact_sizes ?? {};

  return (
    <div className="space-y-3">
      {/* Top KPI row — cost, tokens, wall clock, decisions */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="Spend" value={fmtUsd(totalCost)} accent="primary" />
        <Stat
          label="Tokens"
          value={totalTokens.toLocaleString()}
          sub={totalTokens > 0 ? `${(totalCost / Math.max(1, totalTokens) * 1000).toFixed(2)} ¢/1k` : undefined}
        />
        <Stat
          label="Wall clock"
          value={wallClock != null ? `${wallClock.toFixed(0)}s` : "—"}
          sub={
            wallClock && totalTokens
              ? `${Math.round(totalTokens / Math.max(1, wallClock))} tok/s`
              : undefined
          }
        />
        <Stat label="Decisions" value={String(run.decisions_count ?? 0)} />
      </div>

      {/* Stage durations as horizontal proportional bars. Visual instead of
          a numeric table — operator instantly sees that assessor takes 80%
          of the wall clock or whatever the actual story is. */}
      {stageRows.length > 0 && (
        <Card className="p-4 space-y-2">
          <h3 className="text-[10px] font-medium uppercase tracking-wider text-[var(--text-tertiary)]">
            Stage durations
          </h3>
          <div className="space-y-1.5">
            {stageRows.map(({ stage, secs }) => {
              const pct = totalDuration > 0 ? (secs / totalDuration) * 100 : 0;
              return (
                <div key={stage} className="flex items-center gap-2 text-xs">
                  <span className="w-24 shrink-0 capitalize text-[var(--text-secondary)]">
                    {stage.replace(/_/g, " ")}
                  </span>
                  <div className="flex-1 h-2 rounded bg-[var(--overlay)] relative overflow-hidden">
                    <div
                      className="absolute inset-y-0 left-0 rounded bg-[var(--primary)]/70"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <span className="w-16 shrink-0 text-right tabular text-[var(--text-secondary)]">
                    {secs.toFixed(1)}s
                  </span>
                  <span className="w-12 shrink-0 text-right tabular text-[10px] text-[var(--text-tertiary)]">
                    {pct.toFixed(0)}%
                  </span>
                </div>
              );
            })}
          </div>
        </Card>
      )}

      <div className="grid gap-3 md:grid-cols-2">
        {/* Model routing — which provider+model carried which stage. The
            most useful piece of information for empirical model A/B work. */}
        {routingRows.length > 0 && (
          <Card className="p-4 space-y-2">
            <h3 className="text-[10px] font-medium uppercase tracking-wider text-[var(--text-tertiary)]">
              Model routing
            </h3>
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-[11px]">
              {routingRows.map(([stage, m]) => (
                <RoutingRow key={stage} stage={stage} provider={m.provider} model={m.model} />
              ))}
            </dl>
          </Card>
        )}

        {/* Artifact sizes — chars per artifact. Truncation regression
            indicator (a 1200-char architecture is the smoking gun for
            the [:1200] bug we fixed earlier). */}
        {Object.keys(artifactSizes).length > 0 && (
          <Card className="p-4 space-y-2">
            <h3 className="text-[10px] font-medium uppercase tracking-wider text-[var(--text-tertiary)]">
              Output artifacts
            </h3>
            <dl className="grid grid-cols-[1fr_auto] gap-x-3 gap-y-1 text-[11px]">
              {Object.entries(artifactSizes).map(([k, v]) => (
                <RowKV
                  key={k}
                  k={k.replace(/_/g, " ")}
                  v={`${v.toLocaleString()} chars`}
                  flag={v > 0 && v < 1500 && k.includes("chars") ? "warn" : undefined}
                  flagTitle={v < 1500 ? "suspiciously short — may indicate prompt cap or upstream truncation" : undefined}
                />
              ))}
            </dl>
          </Card>
        )}
      </div>

      {/* Experiment-namespace provenance: only renders when the run came
          from a harness seeder (carries namespace + model + source_run_dir).
          Keeps the dashboard honest about which entries are live-pipeline
          vs which are seeded historical artifacts. */}
      {(run.namespace || run.model || run.source_run_dir || run.original_team_id) && (
        <Card className="p-4 space-y-2">
          <h3 className="text-[10px] font-medium uppercase tracking-wider text-[var(--text-tertiary)]">
            Experiment provenance
          </h3>
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-[11px]">
            {run.namespace && <RowKV k="Namespace" v={run.namespace} />}
            {run.model && <RowKV k="Model" v={run.model} mono />}
            {run.model_slug && <RowKV k="Model slug" v={run.model_slug} mono />}
            {run.source_run_dir && <RowKV k="Source run dir" v={run.source_run_dir} mono />}
            {run.original_team_id && <RowKV k="Original team_id" v={run.original_team_id} mono />}
          </dl>
        </Card>
      )}
    </div>
  );
}

function Stat({
  label, value, sub, accent,
}: {
  label: string;
  value: string;
  sub?: string;
  accent?: "primary";
}) {
  return (
    <Card className="p-3 space-y-0.5">
      <div className="text-[10px] uppercase tracking-wider text-[var(--text-tertiary)]">
        {label}
      </div>
      <div className={cn(
        "text-xl font-semibold tabular",
        accent === "primary" ? "text-[var(--primary)]" : "text-[var(--text)]",
      )}>
        {value}
      </div>
      {sub && (
        <div className="text-[10px] text-[var(--text-tertiary)] tabular truncate">
          {sub}
        </div>
      )}
    </Card>
  );
}

function RoutingRow({
  stage, provider, model,
}: {
  stage: string;
  provider?: string;
  model?: string;
}) {
  return (
    <>
      <dt className="capitalize text-[var(--text-tertiary)]">
        {stage.replace(/_/g, " ")}
      </dt>
      <dd className="text-[var(--text)] mono break-all">
        {provider && (
          <span className="text-[var(--text-tertiary)]">{provider}</span>
        )}
        {provider && model && (
          <span className="text-[var(--text-tertiary)]"> · </span>
        )}
        {model && <span>{model}</span>}
        {!provider && !model && <span className="text-[var(--text-tertiary)]">—</span>}
      </dd>
    </>
  );
}

function RowKV({
  k, v, mono, flag, flagTitle,
}: {
  k: string;
  v: string;
  mono?: boolean;
  flag?: "warn";
  flagTitle?: string;
}) {
  return (
    <>
      <dt className="capitalize text-[var(--text-tertiary)] truncate">{k}</dt>
      <dd
        className={cn(
          "text-right break-all",
          mono && "mono",
          flag === "warn" ? "text-[var(--warning)]" : "text-[var(--text)]",
        )}
        title={flagTitle}
      >
        {v}
        {flag === "warn" && <span className="ml-1" aria-label="warning">⚠</span>}
      </dd>
    </>
  );
}
