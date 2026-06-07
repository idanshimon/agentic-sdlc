"use client";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { ShieldCheck, ShieldAlert, Loader2, Play } from "lucide-react";
import { ledgerMcp } from "@/lib/api/ledger-mcp";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/layout/page-header";

const examples = [
  {
    label: "Raw MRN in a log statement",
    text: 'logger.info(f"patient {MRN} updated record")',
    expectPhi: true,
  },
  {
    label: "Synthetic patient ID",
    text: 'patient_id = "PT-DEMO-0001"; dob = "1900-01-01"',
    expectPhi: false,
  },
  {
    label: "SSN in a string",
    text: 'ssn_match = re.match(r"(\\d{3}-\\d{2}-\\d{4})", text)',
    expectPhi: true,
  },
];

export default function PhiPage() {
  const [text, setText] = useState(examples[0].text);

  const m = useMutation({
    mutationFn: (t: string) => ledgerMcp.classifyPhi(t),
  });

  const result = m.data;
  const isHigh = result?.phi_class === "high";

  return (
    <div className="space-y-6">
      <PageHeader
        plane="agenthq"
        title="PHI Classifier"
        description="Hit the local hook-layer PHI guard. Same fast-path that runs in `PreToolUse` for every IDE Copilot session. Returns phi_class + matched patterns + bundle refs."
      />

      <div className="grid gap-4 md:grid-cols-2">
        <Card className="p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-medium uppercase tracking-wider text-[var(--text-tertiary)]">
              Input
            </h3>
            <span className="text-[10px] text-[var(--text-tertiary)] tabular">{text.length} chars</span>
          </div>
          <Textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={6}
            className="mono text-xs"
            placeholder='Try: logger.info(f"patient {MRN} updated")'
          />
          <div className="flex flex-wrap gap-1.5">
            {examples.map((ex) => (
              <button
                key={ex.label}
                onClick={() => setText(ex.text)}
                className="text-[11px] px-2 py-1 rounded bg-[var(--overlay)] text-[var(--text-secondary)] hover:bg-[var(--elevated)] transition-colors"
              >
                {ex.label}
              </button>
            ))}
          </div>
          <Button
            variant="primary"
            onClick={() => m.mutate(text)}
            disabled={m.isPending || !text.trim()}
            className="w-full"
          >
            {m.isPending ? (
              <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Classifying…</>
            ) : (
              <><Play className="h-3.5 w-3.5" /> Run classifier</>
            )}
          </Button>
        </Card>

        <Card className="p-4 space-y-3">
          <h3 className="text-xs font-medium uppercase tracking-wider text-[var(--text-tertiary)]">
            Result
          </h3>
          {m.isError ? (
            <div className="p-3 rounded border border-[var(--danger)]/40 bg-[var(--danger)]/10 text-xs text-[var(--danger)]">
              {String((m.error as Error)?.message ?? "Classifier failed")}
            </div>
          ) : !result ? (
            <div className="h-32 flex items-center justify-center text-xs text-[var(--text-tertiary)]">
              Run the classifier to see results.
            </div>
          ) : (
            <div className="space-y-3">
              <div className="flex items-center gap-2.5 p-3 rounded-md border" style={{
                background: isHigh ? "rgba(239,68,68,0.1)" : "rgba(34,197,94,0.1)",
                borderColor: isHigh ? "rgba(239,68,68,0.3)" : "rgba(34,197,94,0.3)",
              }}>
                {isHigh ? (
                  <ShieldAlert className="h-5 w-5 text-[var(--danger)]" />
                ) : (
                  <ShieldCheck className="h-5 w-5 text-[var(--success)]" />
                )}
                <div>
                  <div className="text-sm font-semibold">
                    {result.has_phi ? "PHI detected" : "Clean"}
                  </div>
                  <div className="text-[11px] text-[var(--text-secondary)]">
                    phi_class = <span className="mono">{result.phi_class}</span>
                  </div>
                </div>
              </div>
              {result.matched_patterns?.length > 0 && (
                <div>
                  <div className="text-[10px] font-medium uppercase tracking-wider text-[var(--text-tertiary)] mb-1">
                    Matched patterns
                  </div>
                  <div className="space-y-1">
                    {result.matched_patterns.map((p, i) => (
                      <div key={i} className="text-xs text-[var(--text-secondary)] mono p-2 bg-[var(--overlay)] rounded">{p}</div>
                    ))}
                  </div>
                </div>
              )}
              {result.bundle_refs?.length > 0 && (
                <div>
                  <div className="text-[10px] font-medium uppercase tracking-wider text-[var(--text-tertiary)] mb-1">
                    Bundle references
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {result.bundle_refs.map((ref) => (
                      <Badge key={ref} variant="secondary" className="mono text-[10px]">
                        {ref}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
