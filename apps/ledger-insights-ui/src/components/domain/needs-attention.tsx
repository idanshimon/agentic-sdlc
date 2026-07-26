"use client";
/* NeedsAttention — the operator dashboard's first fold.
 *
 * Replaces the marketing hero. Answers exactly one question: "what needs me
 * right now?" Every row is a real record, states its consequence in plain
 * language, and clicks through. No decoration, no gradients, no fake data. */
import Link from "next/link";
import { AlertTriangle, ArrowRight, CheckCircle2, Clock, Flag, PauseCircle } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ago, type AttentionItem, type AttentionKind } from "@/lib/attention";
import { cn } from "@/lib/utils";

const KIND_META: Record<
  AttentionKind,
  { label: string; color: string; icon: typeof Flag }
> = {
  blocked: { label: "Blocked", color: "var(--warning)", icon: PauseCircle },
  failed: { label: "Failed", color: "var(--danger)", icon: AlertTriangle },
  flagged: { label: "Flagged", color: "var(--secondary)", icon: Flag },
  stalled: { label: "Stalled", color: "var(--text-tertiary)", icon: Clock },
};

export function NeedsAttention({
  items,
  loading,
  total,
}: {
  items: AttentionItem[];
  loading?: boolean;
  /** Full queue size — items may be capped for the fold. */
  total?: number;
}) {
  if (loading) {
    return (
      <section className="space-y-3">
        <SectionHeading count={null} />
        <div className="space-y-2">
          <div className="skeleton h-16 rounded-lg" />
          <div className="skeleton h-16 rounded-lg" />
        </div>
      </section>
    );
  }

  const queueSize = total ?? items.length;

  if (items.length === 0) {
    return (
      <section className="space-y-3">
        <SectionHeading count={0} />
        <Card className="p-6 flex items-center gap-3">
          <CheckCircle2 className="h-5 w-5 text-[var(--success)] shrink-0" />
          <div>
            <div className="text-sm font-medium text-[var(--text)]">Nothing is waiting on you</div>
            <div className="text-xs text-[var(--text-tertiary)]">
              No blocked gates, no recent failures, no flagged decisions.
            </div>
          </div>
        </Card>
      </section>
    );
  }

  return (
    <section className="space-y-3">
      <SectionHeading count={queueSize} />
      <div className="space-y-2">
        {items.map((item) => {
          const meta = KIND_META[item.kind];
          const Icon = meta.icon;
          return (
            <Card
              key={item.id}
              className={cn(
                "group relative flex items-start gap-3 p-4 pl-5 transition-colors",
                "hover:border-[var(--text-tertiary)]",
              )}
            >
              {/* Left accent rail encodes urgency without shouting. */}
              <span
                aria-hidden
                className="absolute left-0 top-0 h-full w-[3px] rounded-l-lg"
                style={{ background: meta.color }}
              />
              <Icon className="h-4 w-4 mt-0.5 shrink-0" style={{ color: meta.color }} />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium text-[var(--text)]">{item.title}</span>
                  <Badge variant="outline" className="shrink-0">
                    {meta.label}
                  </Badge>
                  {item.count && item.count > 1 && (
                    <Badge variant="default" className="shrink-0 tabular">
                      ×{item.count}
                    </Badge>
                  )}
                  <span className="text-[11px] text-[var(--text-tertiary)] tabular">
                    {ago(item.at)}
                  </span>
                </div>
                <p className="mt-0.5 text-xs text-[var(--text-secondary)] leading-relaxed">
                  {item.detail}
                </p>
              </div>
              <Button variant="secondary" size="sm" asChild className="shrink-0">
                <Link href={item.href}>
                  {item.action}
                  <ArrowRight className="h-3 w-3" />
                </Link>
              </Button>
            </Card>
          );
        })}
      </div>
      {queueSize > items.reduce((n, i) => n + (i.count ?? 1), 0) && (
        <Button variant="ghost" size="sm" asChild>
          <Link href="/runs?view=attention">
            {queueSize - items.reduce((n, i) => n + (i.count ?? 1), 0)} more need attention{" "}
            <ArrowRight className="h-3 w-3" />
          </Link>
        </Button>
      )}
    </section>
  );
}

function SectionHeading({ count }: { count: number | null }) {
  return (
    <div className="flex items-center gap-2">
      <h2 className="text-base font-semibold text-[var(--text)]">Needs attention</h2>
      {count !== null && count > 0 && (
        <Badge variant="warning" className="tabular">
          {count}
        </Badge>
      )}
    </div>
  );
}
