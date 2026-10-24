"use client";
/* Orbital Mission Control cockpit.
 *
 * Hub = the human gate. Pipeline stages are sectors of the dial. Runs orbit on
 * rings ordered by consequence (blocked innermost — closest to the human who
 * must act). Agent personas are satellites on the outer rail, sized by their
 * real ledger activity. Pure SVG + theme tokens, so light/dark follow for free.
 */
import { useMemo, useState } from "react";
import Link from "next/link";
import {
  Bot, FileText, Wrench, Code, Search, ArrowRight, CircleDot, Hand, X,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { RunState } from "@/lib/types";
import {
  MISSION_STAGES, RINGS, orbitLayout, ringOf, runStage, stageOccupancy,
  AGENT_STAGES, type RingKind, type AgentActivityResult,
} from "@/lib/mission";
import { ago } from "@/lib/attention";
import { fmtUsd, shortId } from "@/lib/utils";
import { useHyperframe } from "@/lib/hyperframe";

const SIZE = 940;
const C = SIZE / 2;
const RADII: Record<RingKind, number> = { blocked: 128, failed: 186, active: 244, done: 302 };
const STAGE_LABEL_R = 362;
const AGENT_R = 420;
/* Satellites sit off the sector centre so their names never collide with the
 * stage label that occupies the centre of the same sector. */
const AGENT_OFFSET = 0.36;

const RING_META: Record<RingKind, { label: string; color: string; hint: string }> = {
  blocked: { label: "Waiting on a human", color: "var(--warning)", hint: "gate open — nothing proceeds" },
  failed: { label: "Failed or blocked by policy", color: "var(--danger)", hint: "needs triage" },
  active: { label: "In flight", color: "var(--primary)", hint: "agents working" },
  done: { label: "Delivered / complete", color: "var(--success)", hint: "history" },
};

export const AGENT_ICON: Record<string, React.ComponentType<{ className?: string }>> = {
  assessor: FileText,
  architect: Wrench,
  codegen: Code,
  "review-scan": Search,
};

const polar = (r: number, a: number) => ({ x: C + r * Math.sin(a), y: C - r * Math.cos(a) });

function arcPath(r: number, a0: number, a1: number) {
  const p0 = polar(r, a0);
  const p1 = polar(r, a1);
  const large = a1 - a0 > Math.PI ? 1 : 0;
  return `M ${p0.x} ${p0.y} A ${r} ${r} 0 ${large} 1 ${p1.x} ${p1.y}`;
}

type Selection = { kind: "run"; id: string } | { kind: "agent"; id: string } | null;

export function MissionCockpit({
  runs,
  activity,
  agents,
}: {
  runs: RunState[];
  activity: AgentActivityResult;
  agents: { id: string; display_name: string; description: string }[];
}) {
  const [sel, setSel] = useState<Selection>(null);
  const [hidden, setHidden] = useState<Set<RingKind>>(new Set());
  const [hover, setHover] = useState<string | null>(null);
  const svgRef = useHyperframe<SVGSVGElement>([runs.length]);

  const visibleRuns = useMemo(() => runs.filter((r) => !hidden.has(ringOf(r))), [runs, hidden]);
  const points = useMemo(() => orbitLayout(visibleRuns, RADII, { spacing: 13, laneGap: 12 }), [visibleRuns]);
  const occ = useMemo(() => stageOccupancy(runs), [runs]);
  const byId = useMemo(() => new Map(runs.map((r) => [r.run_id, r])), [runs]);
  const ringCounts = useMemo(() => {
    const c: Record<RingKind, number> = { blocked: 0, failed: 0, active: 0, done: 0 };
    runs.forEach((r) => (c[ringOf(r)] += 1));
    return c;
  }, [runs]);
  const maxDecisions = Math.max(1, ...Object.values(activity.agents).map((a) => a.decisions));
  const maxOcc = Math.max(1, ...occ.map((o) => o.total));

  const n = MISSION_STAGES.length;
  const sector = (2 * Math.PI) / n;
  const selRun = sel?.kind === "run" ? byId.get(sel.id) : undefined;
  const selAgent = sel?.kind === "agent" ? agents.find((a) => a.id === sel.id) : undefined;
  // stage(s) to highlight: the selected run's stage, or the selected agent's stages
  const hotStages = new Set<string>(
    selRun ? [runStage(selRun)] : selAgent ? AGENT_STAGES[selAgent.id] ?? [] : [],
  );

  const toggleRing = (k: RingKind) =>
    setHidden((h) => {
      const next = new Set(h);
      if (next.has(k)) next.delete(k);
      else next.add(k);
      return next;
    });

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">
      <Card className="relative overflow-hidden p-0">
        {/* ring legend = filters */}
        <div className="flex flex-wrap items-center gap-2 border-b border-[var(--border-muted)] px-4 py-2.5">
          {RINGS.map((k) => {
            const off = hidden.has(k);
            return (
              <button
                key={k}
                onClick={() => toggleRing(k)}
                aria-pressed={!off}
                className="inline-flex items-center gap-1.5 rounded-full border border-[var(--border-default)] px-2.5 py-1 text-[11px] transition-opacity hover:bg-[var(--overlay)]"
                style={{ opacity: off ? 0.4 : 1 }}
              >
                <span className="h-2 w-2 rounded-full" style={{ background: RING_META[k].color }} />
                <span className="text-[var(--text-secondary)]">{RING_META[k].label}</span>
                <span className="tabular font-semibold text-[var(--text)]">{ringCounts[k]}</span>
              </button>
            );
          })}
          <span className="ml-auto text-[11px] text-[var(--text-tertiary)]">
            Select a run or agent · empty space resets
          </span>
        </div>

        <svg
          ref={svgRef}
          viewBox={`0 0 ${SIZE} ${SIZE}`}
          className="mx-auto block h-auto w-full max-w-[820px] select-none"
          role="img"
          aria-label={`Mission control: ${runs.length} runs — ${ringCounts.blocked} waiting on a human, ${ringCounts.failed} failed, ${ringCounts.active} in flight, ${ringCounts.done} complete.`}
          onClick={() => setSel(null)}
        >
          <defs>
            <radialGradient id="mc-glow" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="var(--primary)" stopOpacity="0.14" />
              <stop offset="60%" stopColor="var(--primary)" stopOpacity="0.03" />
              <stop offset="100%" stopColor="var(--primary)" stopOpacity="0" />
            </radialGradient>
          </defs>
          <style>{`.mc-t{paint-order:stroke;stroke:var(--surface);stroke-width:4px;stroke-linejoin:round}`}</style>
          <circle cx={C} cy={C} r={AGENT_R + 30} fill="url(#mc-glow)" />

          {/* stage sectors: occupancy heat + highlight */}
          {MISSION_STAGES.map((s, i) => {
            const a0 = i * sector;
            const a1 = (i + 1) * sector;
            const o = occ[i];
            const hot = hotStages.has(s.id);
            const heat = o.total / maxOcc;
            const lab = polar(STAGE_LABEL_R, a0 + sector / 2);
            const div = polar(STAGE_LABEL_R - 14, a0);
            const divIn = polar(92, a0);
            return (
              <g key={s.id}>
                <path
                  d={`${arcPath(320, a0 + 0.02, a1 - 0.02)}`}
                  fill="none"
                  stroke={hot ? "var(--primary)" : "var(--border-default)"}
                  strokeWidth={hot ? 6 : 3 + heat * 5}
                  strokeOpacity={hot ? 0.9 : 0.35 + heat * 0.5}
                  strokeLinecap="round"
                  data-hf="draw"
                />
                {o.byRing.blocked > 0 && (
                  <path
                    d={arcPath(311, a0 + 0.05, a1 - 0.05)}
                    fill="none"
                    stroke="var(--warning)"
                    strokeWidth={2}
                    strokeDasharray="4 6"
                    className="mc-dash"
                  />
                )}
                <line x1={divIn.x} y1={divIn.y} x2={div.x} y2={div.y} stroke="var(--border-muted)" strokeWidth={1} />
                <text
                  x={lab.x}
                  y={lab.y - 4}
                  textAnchor="middle"
                  className="mc-t text-[13px] font-semibold"
                  fill={hot ? "var(--text)" : "var(--text-secondary)"}
                >
                  {s.label}
                </text>
                <text x={lab.x} y={lab.y + 12} textAnchor="middle" className="mc-t tabular text-[11px]" fill="var(--text-secondary)">
                  {o.total} run{o.total === 1 ? "" : "s"}
                  {o.byRing.blocked > 0 ? ` · ${o.byRing.blocked} gate` : ""}
                </text>
              </g>
            );
          })}

          {/* consequence rings */}
          {RINGS.map((k) => (
            <circle
              key={k}
              cx={C}
              cy={C}
              r={RADII[k]}
              fill="none"
              stroke={RING_META[k].color}
              strokeOpacity={hidden.has(k) ? 0.06 : 0.32}
              strokeWidth={1}
              strokeDasharray={k === "active" ? "2 6" : undefined}
              data-hf={k === "active" ? undefined : "draw"}
              className={k === "active" ? "mc-spin" : undefined}
              style={{ transformOrigin: `${C}px ${C}px` }}
            />
          ))}

          {/* agent satellites + beams to their stage sectors */}
          {agents.map((ag) => {
            const stages = AGENT_STAGES[ag.id] ?? [];
            const si = MISSION_STAGES.findIndex((s) => s.id === stages[0]);
            if (si < 0) return null;
            const angle = si * sector + sector / 2 + AGENT_OFFSET * sector;
            const p = polar(AGENT_R, angle);
            const act = activity.agents[ag.id];
            const weight = act ? act.decisions / maxDecisions : 0;
            const r = 16 + weight * 12;
            const selected = sel?.kind === "agent" && sel.id === ag.id;
            const beamEnd = polar(326, si * sector + sector / 2);
            const Icon = AGENT_ICON[ag.id] ?? Bot;
            return (
              <g
                key={ag.id}
                className="cursor-pointer"
                onClick={(e) => {
                  e.stopPropagation();
                  setSel({ kind: "agent", id: ag.id });
                }}
                onMouseEnter={() => setHover(`agent:${ag.id}`)}
                onMouseLeave={() => setHover(null)}
              >
                <line
                  x1={p.x} y1={p.y} x2={beamEnd.x} y2={beamEnd.y}
                  stroke="var(--plane-agenthq)"
                  strokeOpacity={selected ? 0.9 : 0.25 + weight * 0.4}
                  strokeWidth={selected ? 2.5 : 1.5}
                  strokeDasharray="3 4"
                  className={act && act.decisions > 0 ? "mc-dash" : undefined}
                />
                <circle cx={p.x} cy={p.y} r={r + 6} fill="var(--plane-agenthq)" fillOpacity={selected ? 0.22 : 0.08} />
                <circle
                  cx={p.x} cy={p.y} r={r}
                  fill="var(--elevated)"
                  stroke="var(--plane-agenthq)"
                  strokeWidth={selected || hover === `agent:${ag.id}` ? 2.5 : 1.5}
                />
                <foreignObject x={p.x - 9} y={p.y - 9} width={18} height={18} style={{ pointerEvents: "none" }}>
                  <div className="flex h-full w-full items-center justify-center text-[var(--plane-agenthq)]">
                    <Icon className="h-4 w-4" />
                  </div>
                </foreignObject>
                <text
                  x={p.x}
                  y={p.y + r + 15}
                  textAnchor="middle"
                  className="mc-t text-[12px] font-medium"
                  fill="var(--text)"
                >
                  {ag.display_name}
                </text>
                <text x={p.x} y={p.y + r + 28} textAnchor="middle" className="mc-t tabular text-[11px]" fill="var(--text-secondary)">
                  {act && act.decisions > 0 ? `${act.decisions} decisions` : "no activity"}
                </text>
              </g>
            );
          })}

          {/* run nodes */}
          {points.map((pt) => {
            const run = byId.get(pt.runId)!;
            const p = polar(pt.radius, pt.angle);
            const meta = RING_META[pt.ring];
            const selected = sel?.kind === "run" && sel.id === pt.runId;
            const dim = sel && !selected && !(sel.kind === "agent" && hotStages.has(pt.stage));
            const isHover = hover === pt.runId;
            return (
              <g
                key={pt.runId}
                className="cursor-pointer"
                data-hf="fade"
                opacity={dim ? 0.25 : 1}
                onClick={(e) => {
                  e.stopPropagation();
                  setSel({ kind: "run", id: pt.runId });
                }}
                onMouseEnter={() => setHover(pt.runId)}
                onMouseLeave={() => setHover(null)}
              >
                <title>{`${shortId(run.run_id)} · ${run.status} · ${pt.stage}`}</title>
                {pt.ring === "blocked" && (
                  <circle cx={p.x} cy={p.y} r={8} fill="none" stroke={meta.color} strokeWidth={1.2} className="mc-ping" style={{ transformOrigin: `${p.x}px ${p.y}px` }} />
                )}
                {selected && <line x1={C} y1={C} x2={p.x} y2={p.y} stroke={meta.color} strokeOpacity={0.6} strokeWidth={1.5} />}
                {/* generous invisible hit target — the visible dot is too small to tap */}
                <circle cx={p.x} cy={p.y} r={11} fill="transparent" />
                <circle
                  cx={p.x}
                  cy={p.y}
                  r={selected || isHover ? 7.5 : pt.ring === "done" ? 4 : 5}
                  fill={meta.color}
                  fillOpacity={pt.ring === "done" ? 0.7 : 1}
                  stroke={selected ? "var(--text)" : "var(--surface)"}
                  strokeWidth={1.5}
                />
              </g>
            );
          })}

          {/* hub: the human gate */}
          <circle cx={C} cy={C} r={86} fill="var(--surface)" stroke="var(--border-default)" />
          <circle cx={C} cy={C} r={78} fill="none" stroke="var(--warning)" strokeOpacity={ringCounts.blocked ? 0.6 : 0.15} strokeWidth={2} strokeDasharray="6 5" className={ringCounts.blocked ? "mc-spin-rev" : undefined} style={{ transformOrigin: `${C}px ${C}px` }} />
          <foreignObject x={C - 70} y={C - 54} width={140} height={108} style={{ pointerEvents: "none" }}>
            <div className="flex h-full flex-col items-center justify-center text-center">
              <Hand className="mb-1 h-4 w-4 text-[var(--warning)]" />
              <div className="tabular text-3xl font-semibold leading-none text-[var(--text)]">{ringCounts.blocked}</div>
              <div className="mt-1 text-[10px] leading-tight text-[var(--text-secondary)]">
                {ringCounts.blocked === 1 ? "run needs you" : "runs need you"}
              </div>
            </div>
          </foreignObject>
        </svg>

        {/* Phones: the orbit is a glance; this list is how you act. */}
        <NeedsYouList runs={runs} />

        {runs.length === 0 && (
          <div className="absolute inset-x-0 bottom-6 text-center text-xs text-[var(--text-tertiary)]">
            No runs recorded yet. <Link href="/runs/new" className="text-[var(--primary)] underline">Start one</Link>.
          </div>
        )}
      </Card>

      <Inspector
        run={selRun}
        agent={selAgent}
        activity={activity}
        runs={runs}
        onClose={() => setSel(null)}
      />
    </div>
  );
}

function Inspector({
  run, agent, activity, runs, onClose,
}: {
  run?: RunState;
  agent?: { id: string; display_name: string; description: string };
  activity: AgentActivityResult;
  runs: RunState[];
  onClose: () => void;
}) {
  if (run) {
    const ring = ringOf(run);
    const meta = RING_META[ring];
    const cost = run.total_cost_usd ?? run.cost_usd;
    const stageIdx = MISSION_STAGES.findIndex((s) => s.id === runStage(run));
    return (
      <Card className="space-y-4 p-4">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="text-[11px] text-[var(--text-tertiary)]">Run</div>
            <div className="mono truncate text-sm">{shortId(run.run_id, 14)}</div>
          </div>
          <button onClick={onClose} aria-label="Close" className="rounded p-1 hover:bg-[var(--overlay)]"><X className="h-4 w-4" /></button>
        </div>
        <div className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: meta.color }} />
          <span className="text-sm font-medium">{meta.label}</span>
        </div>
        {/* stage progress */}
        <div>
          <div className="mb-1.5 text-[11px] text-[var(--text-tertiary)]">Pipeline position</div>
          <div className="flex gap-1">
            {MISSION_STAGES.map((s, i) => (
              <div
                key={s.id}
                title={s.label}
                className="h-1.5 flex-1 rounded-full"
                style={{
                  background: i < stageIdx ? "var(--success)" : i === stageIdx ? meta.color : "var(--overlay)",
                }}
              />
            ))}
          </div>
          <div className="mt-1 text-xs text-[var(--text-secondary)]">at {MISSION_STAGES[stageIdx]?.label}</div>
        </div>
        <dl className="grid grid-cols-2 gap-2 text-xs">
          <Tile label="Team" value={run.team_id || "—"} />
          <Tile label="Mode" value={run.mode} />
          <Tile label="Spend" value={cost != null ? fmtUsd(cost, 2) : "not recorded"} />
          <Tile label="Decisions" value={run.decisions_count != null ? String(run.decisions_count) : "not recorded"} />
          <Tile label="Updated" value={ago(run.updated_at || run.created_at)} />
          <Tile label="Tokens" value={run.total_tokens != null ? run.total_tokens.toLocaleString() : "not recorded"} />
        </dl>
        {run.failure_reason && (
          <p className="rounded-md border border-[var(--border-muted)] bg-[var(--elevated)] p-2 text-xs text-[var(--text-secondary)]">
            {run.failure_kind === "policy_block" ? "Blocked by policy: " : ""}{run.failure_reason}
          </p>
        )}
        {(run.blocking_rules?.length ?? 0) > 0 && (
          <div className="flex flex-wrap gap-1">
            {run.blocking_rules!.map((r) => (
              <span key={r} className="mono rounded bg-[var(--overlay)] px-1.5 py-0.5 text-[10px] text-[var(--secondary)]">{r}</span>
            ))}
          </div>
        )}
        <Link
          href={`/runs/${run.run_id}`}
          className="inline-flex w-full items-center justify-center gap-1.5 rounded-md bg-[var(--primary)] px-3 py-2 text-xs font-medium text-[var(--on-primary)]"
        >
          {ring === "blocked" ? "Open gate" : ring === "failed" ? "Triage run" : "Open run"} <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </Card>
    );
  }

  if (agent) {
    const a = activity.agents[agent.id];
    const Icon = AGENT_ICON[agent.id] ?? Bot;
    const stages = AGENT_STAGES[agent.id] ?? [];
    const here = runs.filter((r) => stages.includes(runStage(r)) && ringOf(r) !== "done").length;
    return (
      <Card className="space-y-4 p-4">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-md bg-[color-mix(in_srgb,var(--plane-agenthq)_var(--tint),transparent)]">
              <Icon className="h-4 w-4 text-[var(--plane-agenthq)]" />
            </div>
            <div>
              <div className="text-sm font-semibold">{agent.display_name}</div>
              <div className="text-[11px] text-[var(--text-tertiary)]">agent persona</div>
            </div>
          </div>
          <button onClick={onClose} aria-label="Close" className="rounded p-1 hover:bg-[var(--overlay)]"><X className="h-4 w-4" /></button>
        </div>
        <p className="text-xs leading-relaxed text-[var(--text-secondary)]">{agent.description}</p>
        {a && a.decisions > 0 ? (
          <>
            <dl className="grid grid-cols-2 gap-2 text-xs">
              <Tile label="Decisions" value={String(a.decisions)} />
              <Tile label="Autonomous" value={`${Math.round((a.autonomous / a.decisions) * 100)}%`} />
              <Tile label="Flagged" value={String(a.flagged)} tone={a.flagged ? "danger" : undefined} />
              <Tile label="Spend" value={a.costed ? fmtUsd(a.costUsd, 2) : "not recorded"} />
            </dl>
            <Spark values={a.spark} />
            <div className="text-[11px] text-[var(--text-tertiary)]">Last active {ago(a.lastAt)} · {here} open run{here === 1 ? "" : "s"} at its stage</div>
          </>
        ) : (
          <p className="rounded-md border border-dashed border-[var(--border-default)] p-3 text-xs text-[var(--text-tertiary)]">
            No ledger activity recorded for this persona in the loaded window.
          </p>
        )}
        <Link href="/agents" className="inline-flex items-center gap-1 text-xs text-[var(--primary)]">
          Open agent roster <ArrowRight className="h-3 w-3" />
        </Link>
      </Card>
    );
  }

  // default: system summary
  const att = Object.values(activity.agents).reduce((s, a) => s + a.decisions, 0);
  return (
    <Card className="space-y-4 p-4">
      <div className="flex items-center gap-2">
        <CircleDot className="h-4 w-4 text-[var(--primary)]" />
        <h3 className="text-sm font-semibold">How to read this</h3>
      </div>
      <ul className="space-y-2.5 text-xs leading-relaxed text-[var(--text-secondary)]">
        <li><b className="text-[var(--text)]">Center</b> is you — the human gate. The number is runs waiting on a decision.</li>
        <li><b className="text-[var(--text)]">Sectors</b> are pipeline stages. A thicker arc means more runs are sitting there; an amber dashed arc means a gate is open.</li>
        <li><b className="text-[var(--text)]">Rings</b> order runs by consequence: waiting on you, failed, in flight, done.</li>
        <li><b className="text-[var(--text)]">Satellites</b> are agent personas, sized by decisions they wrote to the ledger.</li>
      </ul>
      <div className="flex flex-wrap gap-1.5 border-t border-[var(--border-muted)] pt-3">
        <Badge variant="info">{att} attributed decisions</Badge>
        {activity.unattributed > 0 && (
          <Badge variant="default" title="Ledger entries with no stage that maps to a persona. Counted, not guessed.">
            {activity.unattributed} unattributed
          </Badge>
        )}
      </div>
    </Card>
  );
}

function NeedsYouList({ runs }: { runs: RunState[] }) {
  const blocked = runs
    .filter((r) => ringOf(r) === "blocked")
    .sort((a, b) => (b.updated_at || "").localeCompare(a.updated_at || ""));
  if (!blocked.length) return null;
  return (
    <div className="border-t border-[var(--border-muted)] px-4 py-3 md:hidden">
      <div className="mb-2 text-xs font-semibold">Waiting on you ({blocked.length})</div>
      <ul className="divide-y divide-[var(--border-muted)]">
        {blocked.slice(0, 8).map((r) => (
          <li key={r.run_id}>
            <Link href={`/runs/${r.run_id}`} className="flex min-h-11 items-center gap-2 text-xs">
              <span className="h-2 w-2 shrink-0 rounded-full bg-[var(--warning)]" />
              <span className="mono truncate">{shortId(r.run_id)}</span>
              <span className="text-[var(--text-tertiary)]">at {MISSION_STAGES.find((s) => s.id === runStage(r))?.label}</span>
              <ArrowRight className="ml-auto h-3.5 w-3.5 text-[var(--text-tertiary)]" />
            </Link>
          </li>
        ))}
      </ul>
      {blocked.length > 8 && (
        <Link href="/runs?view=attention" className="mt-1 flex min-h-11 items-center text-xs text-[var(--primary)]">
          {blocked.length - 8} more waiting <ArrowRight className="ml-1 h-3 w-3" />
        </Link>
      )}
    </div>
  );
}

function Tile({ label, value, tone }: { label: string; value: string; tone?: "danger" }) {
  return (
    <div className="rounded-md border border-[var(--border-muted)] bg-[var(--elevated)] px-2.5 py-2">
      <dt className="text-[10px] text-[var(--text-tertiary)]">{label}</dt>
      <dd className="tabular truncate text-sm font-medium" style={{ color: tone ? `var(--${tone})` : "var(--text)" }}>{value}</dd>
    </div>
  );
}

export function Spark({ values, color = "var(--plane-agenthq)", unit = "w" }: { values: number[]; color?: string; unit?: string }) {
  const max = Math.max(1, ...values);
  const total = values.reduce((s, v) => s + v, 0);
  return (
    <div>
      <div className="flex h-10 items-end gap-[3px]" role="img" aria-label={`${total} decisions over the last ${values.length} weeks`}>
        {values.map((v, i) => (
          <div
            key={i}
            className="flex-1 rounded-sm"
            title={`${v} decisions, ${values.length - 1 - i === 0 ? "this week" : `${values.length - 1 - i}w ago`}`}
            style={{
              height: v ? `${Math.max(12, (v / max) * 100)}%` : "3px",
              background: v ? color : "var(--overlay)",
              opacity: v ? 0.45 + 0.55 * (v / max) : 1,
            }}
          />
        ))}
      </div>
      <div className="mt-1 flex justify-between text-[10px] text-[var(--text-tertiary)]">
        <span>{values.length}{unit} ago</span><span>this week</span>
      </div>
    </div>
  );
}
