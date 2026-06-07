import { cn } from "@/lib/utils";

const planes = [
  { id: "standards", label: "Standards", color: "var(--plane-standards)", items: ["Bundles (sec/privacy/architect/finops)", "Reviewer rosters", "Versioned + signed"] },
  { id: "pipeline", label: "Pipeline", color: "var(--plane-pipeline)", items: ["Orchestrator", "7-stage graph", "Native GH PR delivery"] },
  { id: "ledger", label: "Ledger + Doctor", color: "var(--plane-ledger)", items: ["Decision Ledger (Cosmos)", "Doctor cron job", "Drift + bounded auto-fix"] },
  { id: "agenthq", label: "Agent HQ", color: "var(--plane-agenthq)", items: ["5 lifecycle hooks", "6 custom agents", "Ledger MCP server"] },
];

export function ArchitectureMini({ className }: { className?: string }) {
  return (
    <div className={cn("grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3", className)}>
      {planes.map((p, i) => (
        <div
          key={p.id}
          className="relative rounded-lg border border-[var(--border-default)] bg-[var(--surface)] p-3 overflow-hidden"
        >
          <div
            className="absolute inset-x-0 top-0 h-0.5"
            style={{ background: p.color, opacity: 0.7 }}
          />
          <div className="flex items-center gap-2 mb-2">
            <span className="h-2 w-2 rounded-full" style={{ background: p.color }} />
            <span className="text-[10px] font-medium uppercase tracking-wider text-[var(--text-tertiary)]">
              Plane {i + 1}
            </span>
          </div>
          <h3 className="text-sm font-semibold mb-2" style={{ color: p.color }}>
            {p.label}
          </h3>
          <ul className="space-y-1">
            {p.items.map((item) => (
              <li key={item} className="text-[11px] text-[var(--text-secondary)] flex items-start gap-1.5">
                <span className="text-[var(--text-tertiary)] mt-1">•</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
