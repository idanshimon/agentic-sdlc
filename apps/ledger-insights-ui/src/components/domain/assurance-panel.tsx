import { Badge } from "@/components/ui/badge";
import type { AssuranceDimensions, AssuranceStatus } from "@/lib/assurance";

const LABELS: Array<[keyof Omit<AssuranceDimensions, "fullyVerified">, string]> = [
  ["deterministicPolicy", "Policy"],
  ["buildTests", "Build/tests"],
  ["dependencySecurity", "Dependency/security"],
  ["semanticReview", "Semantic review"],
  ["mandatoryHuman", "Human requirements"],
];

function variant(status: AssuranceStatus): "success" | "danger" | "warning" | "default" {
  if (status === "pass") return "success";
  if (status === "fail") return "danger";
  if (status === "not_run") return "warning";
  return "default";
}

export function AssurancePanel({ assurance }: { assurance: AssuranceDimensions }) {
  return (
    <section className="rounded-lg border p-3" style={{ borderColor: "var(--border)" }}>
      <div className="mb-2 text-xs font-medium">Independent assurance</div>
      <div className="flex flex-wrap gap-2">
        {LABELS.map(([key, label]) => (
          <Badge key={key} variant={variant(assurance[key])}>
            {label}: {assurance[key].replace("_", " ")}
          </Badge>
        ))}
      </div>
      {!assurance.fullyVerified && (
        <p className="mt-2 text-xs text-[var(--text-secondary)]">
          Partial evidence is not a fully verified result. Unknown and not-run checks remain visible.
        </p>
      )}
    </section>
  );
}
