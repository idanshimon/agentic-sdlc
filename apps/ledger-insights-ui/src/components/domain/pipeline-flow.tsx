"use client";
/* Horizontal pipeline strip: one node per stage with live occupancy split by
 * consequence. Connectors animate only where work is actually moving. */
import Link from "next/link";
import { useMemo } from "react";
import { Card } from "@/components/ui/card";
import type { RunState } from "@/lib/types";
import { stageOccupancy } from "@/lib/mission";

const SEG = [
  { k: "blocked", c: "var(--warning)" },
  { k: "failed", c: "var(--danger)" },
  { k: "active", c: "var(--primary)" },
  { k: "done", c: "var(--success)" },
] as const;

export function PipelineFlow({ runs, href }: { runs: RunState[]; href?: string }) {
  const occ = useMemo(() => stageOccupancy(runs), [runs]);
  const max = Math.max(1, ...occ.map((o) => o.total));
  return (
    <Card className="p-4">
      {(
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold">Pipeline flow{href && <span className="ml-2 text-[11px] font-normal text-[var(--primary)]">Open Mission Control →</span>}</h2>
          <div className="flex gap-3 text-[11px] text-[var(--text-tertiary)]">
            {SEG.map((s) => (
              <span key={s.k} className="inline-flex items-center gap-1">
                <span className="h-2 w-2 rounded-full" style={{ background: s.c }} />
                {s.k === "blocked" ? "gate" : s.k === "active" ? "in flight" : s.k}
              </span>
            ))}
          </div>
        </div>
      )}
      <div className="flex items-stretch overflow-x-auto">
        {occ.map((o, i) => {
          const moving = o.byRing.active > 0;
          return (
            <div key={o.id} className="flex min-w-[96px] flex-1 items-center">
              <Tile
                href={href}
                className="group flex-1 rounded-md border border-[var(--border-default)] bg-[var(--elevated)] px-2.5 py-2 transition-colors hover:border-[var(--text-tertiary)]"
                style={o.byRing.blocked ? { borderColor: "var(--warning)" } : undefined}
              >
                <div className="flex items-baseline justify-between">
                  <span className="text-[11px] text-[var(--text-secondary)]">{o.label}</span>
                  <span className="tabular text-sm font-semibold">{o.total}</span>
                </div>
                <div className="mt-1.5 flex h-1.5 overflow-hidden rounded-full bg-[var(--overlay)]" style={{ width: `${Math.max(12, (o.total / max) * 100)}%` }}>
                  {SEG.map((s) =>
                    o.byRing[s.k] ? (
                      <div key={s.k} style={{ flex: o.byRing[s.k], background: s.c }} />
                    ) : null,
                  )}
                </div>
              </Tile>
              {i < occ.length - 1 && (
                <div className={`mx-1 h-[2px] w-4 shrink-0 ${moving ? "mc-flow" : "bg-[var(--border-default)]"}`} />
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
}

function Tile({ href, ...rest }: { href?: string } & React.HTMLAttributes<HTMLDivElement>) {
  return href ? <Link href={href} {...(rest as React.HTMLAttributes<HTMLAnchorElement>)} /> : <div {...rest} />;
}
