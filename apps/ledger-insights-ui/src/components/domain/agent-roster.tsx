"use client";
/* Agent roster: each persona as a live operator card — what it is, what it
 * is allowed to touch, and what the ledger says it actually did. */
import { useMemo } from "react";
import Link from "next/link";
import { Bot, Pencil, Radar, ShieldAlert } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AGENT_SEEDS } from "@/lib/versioning/seeds";
import { useDecisions, useRuns } from "@/lib/hooks/use-runs";
import { agentActivity, AGENT_STAGES, MISSION_STAGES, ringOf, runStage } from "@/lib/mission";
import { ago } from "@/lib/attention";
import { fmtUsd } from "@/lib/utils";
import { AGENT_ICON, Spark } from "@/components/domain/mission-cockpit";

export function AgentRoster({ onSelect }: { onSelect: (id: string) => void }) {
  const { data: decisions, isLoading, isError } = useDecisions({ limit: 500 });
  const { data: runs } = useRuns({ limit: 200 });
  const entries = useMemo(() => decisions?.entries ?? [], [decisions]);
  const runList = useMemo(() => runs?.items ?? [], [runs]);
  const activity = useMemo(() => agentActivity(entries, AGENT_SEEDS.map((a) => a.id)), [entries]);
  const totals = Object.values(activity.agents).reduce(
    (t, a) => ({ d: t.d + a.decisions, auto: t.auto + a.autonomous, f: t.f + a.flagged, c: t.c + a.costUsd, k: t.k + a.costed }),
    { d: 0, auto: 0, f: 0, c: 0, k: 0 },
  );

  return (
    <div className="space-y-4">
      <Card className="flex flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3 text-xs">
        <Stat label="Personas" value={String(AGENT_SEEDS.length)} />
        <Stat label="Attributed decisions" value={isLoading ? "…" : String(totals.d)} />
        <Stat label="Autonomous" value={totals.d ? `${Math.round((totals.auto / totals.d) * 100)}%` : "no data"} />
        <Stat label="Flagged by humans" value={String(totals.f)} tone={totals.f ? "danger" : undefined} />
        <Stat label="Agent spend" value={totals.k ? fmtUsd(totals.c, 2) : "not recorded"} />
        {activity.unattributed > 0 && (
          <span className="text-[var(--text-tertiary)]" title="Entries without a stage that maps to a persona — counted, not guessed.">
            + {activity.unattributed} unattributed entries
          </span>
        )}
        <Link href="/mission" className="ml-auto inline-flex items-center gap-1 text-[var(--primary)]">
          <Radar className="h-3.5 w-3.5" /> See them in Mission Control
        </Link>
      </Card>
      {isError && (
        <p className="text-xs text-[var(--danger)]">Could not read the ledger — activity below is unavailable, not zero.</p>
      )}

      <div className="grid gap-3 md:grid-cols-2">
        {AGENT_SEEDS.map((a) => {
          const Icon = AGENT_ICON[a.id] ?? Bot;
          const act = activity.agents[a.id];
          const stages = AGENT_STAGES[a.id] ?? [];
          const stageLabels = stages.map((s) => MISSION_STAGES.find((m) => m.id === s)?.label ?? s);
          const open = runList.filter((r) => stages.includes(runStage(r)) && ringOf(r) !== "done");
          const waiting = open.filter((r) => ringOf(r) === "blocked").length;
          const has = act && act.decisions > 0;
          const autoPct = has ? Math.round((act.autonomous / act.decisions) * 100) : 0;
          const live = open.some((r) => ringOf(r) === "active");
          return (
            <Card key={a.id} className="group relative overflow-hidden p-0 transition-colors hover:border-[var(--text-tertiary)]">
              <div className="absolute inset-y-0 left-0 w-[3px] bg-[var(--plane-agenthq)]" />
              <div className="space-y-3 p-4 pl-5">
                <div className="flex items-start gap-3">
                  <div className="relative flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[color-mix(in_srgb,var(--plane-agenthq)_var(--tint),transparent)]">
                    <Icon className="h-5 w-5 text-[var(--plane-agenthq)]" />
                    {live && <span aria-label="run in flight at this stage" className="pulse-dot absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full border-2 border-[var(--surface)] bg-[var(--primary)]" title="a run is in flight at this stage" />}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-semibold">{a.display_name}</h3>
                      <span className="mono text-[11px] text-[var(--text-tertiary)]">{a.id}.agent.md</span>
                    </div>
                    <p className="mt-0.5 line-clamp-2 text-xs leading-relaxed text-[var(--text-secondary)]">{a.description}</p>
                  </div>
                  <button
                    onClick={() => onSelect(a.id)}
                    className="inline-flex shrink-0 items-center gap-1 rounded-md border border-[var(--border-default)] px-2 py-1 text-[11px] text-[var(--text-secondary)] hover:bg-[var(--overlay)]"
                  >
                    <Pencil className="h-3 w-3" /> Edit
                  </button>
                </div>

                {has ? (
                  <div className="grid grid-cols-[1fr_auto] items-end gap-4">
                    <div className="space-y-2">
                      <div className="flex gap-4 text-xs">
                        <Stat label="Decisions" value={String(act.decisions)} />
                        <Stat label="Spend" value={act.costed ? fmtUsd(act.costUsd, 2) : "not recorded"} />
                        <Stat label="Flagged" value={String(act.flagged)} tone={act.flagged ? "danger" : undefined} />
                        <Stat label="Last" value={ago(act.lastAt)} />
                      </div>
                      {/* autonomy split bar */}
                      <div>
                        <div className="flex h-1.5 overflow-hidden rounded-full bg-[var(--overlay)]">
                          <div style={{ width: `${autoPct}%`, background: "var(--plane-agenthq)" }} />
                          <div style={{ width: `${100 - autoPct}%`, background: "var(--warning)" }} />
                        </div>
                        <div className="mt-1 flex justify-between text-[10px] text-[var(--text-tertiary)]">
                          <span>{autoPct}% autonomous</span>
                          <span>{act.human} human-decided</span>
                        </div>
                      </div>
                    </div>
                    <div className="w-32"><Spark values={act.spark} /></div>
                  </div>
                ) : (
                  <p className="rounded-md border border-dashed border-[var(--border-default)] px-3 py-2 text-xs text-[var(--text-tertiary)]">
                    {isLoading ? "Reading the ledger…" : "No ledger activity recorded for this persona yet."}
                  </p>
                )}

                <div className="flex flex-wrap items-center gap-1.5 border-t border-[var(--border-muted)] pt-3">
                  <span className="text-[11px] text-[var(--text-tertiary)]">Stage</span>
                  {stageLabels.map((s) => <Badge key={s} variant="info">{s}</Badge>)}
                  <span className="ml-2 text-[11px] text-[var(--text-tertiary)]">Bundles</span>
                  {a.bundles.map((b) => <Badge key={b} variant="secondary">{b}</Badge>)}
                  {waiting > 0 && (
                    <Badge variant="warning" className="ml-auto">
                      <ShieldAlert className="h-3 w-3" /> {waiting} gate{waiting === 1 ? "" : "s"} open
                    </Badge>
                  )}
                </div>
                {act?.models.length ? (
                  <div className="mono truncate text-[10px] text-[var(--text-tertiary)]">models: {act.models.join(" · ")}</div>
                ) : null}
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: "danger" }) {
  return (
    <div>
      <div className="text-[10px] text-[var(--text-tertiary)]">{label}</div>
      <div className="tabular text-sm font-semibold" style={tone ? { color: `var(--${tone})` } : undefined}>{value}</div>
    </div>
  );
}
