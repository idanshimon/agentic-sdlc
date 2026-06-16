"use client";
import { useState } from "react";
import {
  Building2, FlaskConical, Code2, FileCheck, ScrollText, ExternalLink,
  ChevronRight, ChevronDown, Scale,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DecisionCard } from "@/components/domain/decision-card";
import { isDemoRun, getDemoArtifacts } from "@/lib/demo";
import { ledgerMcp } from "@/lib/api/ledger-mcp";
import { useQuery } from "@tanstack/react-query";
import type { LedgerEntry } from "@/lib/types";
import { cn } from "@/lib/utils";

interface Props {
  runId: string;
  status: string;
}

type TabKey = "decisions" | "architecture" | "test_plan" | "code" | "decisions_md";

const TABS: { key: TabKey; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { key: "decisions", label: "Decisions", icon: Scale },
  { key: "architecture", label: "Architecture", icon: Building2 },
  { key: "test_plan", label: "Test plan", icon: FlaskConical },
  { key: "code", label: "Code", icon: Code2 },
  { key: "decisions_md", label: "decisions.md", icon: ScrollText },
];

export function RunArtifactsPanel({ runId, status }: Props) {
  const [tab, setTab] = useState<TabKey>("decisions");
  const [expanded, setExpanded] = useState(true);

  const isDemo = isDemoRun(runId);
  const artifacts = isDemo ? getDemoArtifacts(runId) : null;

  // Pull ledger entries for this run (works in both demo and live mode —
  // demo branch goes through the ledgerMcp.query() guard).
  const { data: ledger } = useQuery({
    queryKey: ["ledger-run", runId, status],
    queryFn: () => ledgerMcp.query({ run_id: runId, limit: 50 }),
    enabled: !!runId,
    refetchInterval: status === "running" ? 3000 : false,
  });
  const entries: LedgerEntry[] = ledger?.entries ?? [];

  const hasArchitecture = !!artifacts?.architecture;
  const hasTestPlan = !!artifacts?.test_plan;
  const hasCode = !!artifacts?.code;
  const hasDecisionsMd = !!artifacts?.decisions_md;
  const hasDecisions = entries.length > 0;

  // Hide entirely until something is ready to show.
  const ready = hasDecisions || hasArchitecture || hasTestPlan || hasCode || hasDecisionsMd;
  if (!ready) return null;

  const tabAvailable: Record<TabKey, boolean> = {
    decisions: hasDecisions,
    architecture: hasArchitecture,
    test_plan: hasTestPlan,
    code: hasCode,
    decisions_md: hasDecisionsMd,
  };

  // If the active tab is not yet available, switch to first available tab.
  if (!tabAvailable[tab]) {
    const firstAvailable = TABS.find((t) => tabAvailable[t.key]);
    if (firstAvailable) {
      // Set after render to avoid setState-in-render warning.
      Promise.resolve().then(() => setTab(firstAvailable.key));
    }
  }

  return (
    <Card className="overflow-hidden">
      <button
        onClick={() => setExpanded((e) => !e)}
        className="w-full flex items-center gap-3 p-4 text-left hover:bg-[var(--overlay)]/40 transition-colors border-b border-[var(--border-muted)]"
      >
        {expanded ? (
          <ChevronDown className="h-4 w-4 text-[var(--text-tertiary)]" />
        ) : (
          <ChevronRight className="h-4 w-4 text-[var(--text-tertiary)]" />
        )}
        <div className="flex-1">
          <h3 className="text-sm font-semibold">Pipeline artifacts</h3>
          <p className="text-xs text-[var(--text-tertiary)]">
            Resolver decisions · architecture · test plan · code · audit trail
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {hasDecisions && (
            <Badge variant="info" className="text-[10px]">
              {entries.length} {entries.length === 1 ? "decision" : "decisions"}
            </Badge>
          )}
          {artifacts?.pr_url && (
            <Badge variant="success" className="text-[10px]">
              PR opened
            </Badge>
          )}
        </div>
      </button>

      {expanded && (
        <>
          {/* Tabs */}
          <div className="flex items-center gap-1 px-4 pt-3 border-b border-[var(--border-muted)] flex-wrap">
            {TABS.map((t) => {
              const Icon = t.icon;
              const isActive = tab === t.key;
              const isReady = tabAvailable[t.key];
              return (
                <button
                  key={t.key}
                  onClick={() => isReady && setTab(t.key)}
                  disabled={!isReady}
                  className={cn(
                    "flex items-center gap-1.5 h-8 px-3 text-xs font-medium rounded-t-md transition-colors -mb-px",
                    isActive
                      ? "bg-[var(--card)] text-[var(--text)] border-x border-t border-[var(--border-muted)]"
                      : "text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]",
                    !isReady && "opacity-40 cursor-not-allowed",
                  )}
                  title={!isReady ? "Not yet generated" : undefined}
                >
                  <Icon className="h-3 w-3" />
                  {t.label}
                  {!isReady && (
                    <span className="text-[9px] text-[var(--text-tertiary)]">
                      (pending)
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          {/* Body */}
          <div className="p-4">
            {tab === "decisions" && hasDecisions && (
              <div className="space-y-3">
                <p className="text-xs text-[var(--text-tertiary)]">
                  Audit trail — every meaningful decision the pipeline made,
                  with rationale, bundle citations, and PHI classification.
                </p>
                <div className="grid gap-3 md:grid-cols-2">
                  {entries.map((e) => (
                    <DecisionCard key={e.id} entry={e} />
                  ))}
                </div>
              </div>
            )}
            {tab === "architecture" && artifacts?.architecture && (
              <ArtifactView content={artifacts.architecture} kind="md" />
            )}
            {tab === "test_plan" && artifacts?.test_plan && (
              <ArtifactView content={artifacts.test_plan} kind="md" />
            )}
            {tab === "code" && artifacts?.code && (
              <ArtifactView content={artifacts.code} kind="py" />
            )}
            {tab === "decisions_md" && artifacts?.decisions_md && (
              <div className="space-y-3">
                <ArtifactView content={artifacts.decisions_md} kind="md" />
                {artifacts.pr_url && (
                  <a
                    href={artifacts.pr_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1.5 text-xs text-[var(--primary)] hover:underline"
                  >
                    <FileCheck className="h-3.5 w-3.5" />
                    View pull request
                    <ExternalLink className="h-2.5 w-2.5" />
                  </a>
                )}
              </div>
            )}
          </div>
        </>
      )}
    </Card>
  );
}

function ArtifactView({ content, kind }: { content: string; kind: "md" | "py" }) {
  const [copied, setCopied] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const lines = content.split("\n");

  // Phase 6 (2026-06-16): operator-grade artifact viewer.
  // Three improvements over the old plain <pre>:
  //   1. Line numbers — operator can reference specific lines in flag/replay
  //   2. Copy + Download buttons — no more "select all + paste into editor"
  //   3. Collapsible — long codegen output (>200 lines) hides by default
  //      with "show all N lines" affordance
  // Light syntax color (no external dep): Python keywords + comments,
  // markdown headers/quotes. Adding shiki/prism would be 100KB+ for very
  // marginal UX gain on this surface; the regex approach is good enough
  // for a 30-line FastAPI route handler glance-check.
  const PYTHON_KEYWORDS = new Set([
    "def","class","import","from","return","if","elif","else","for","while",
    "try","except","finally","with","as","in","not","and","or","is","None",
    "True","False","async","await","yield","raise","pass","break","continue",
    "lambda","global","nonlocal",
  ]);

  function highlightLine(line: string, idx: number): React.ReactNode {
    if (kind === "py") {
      // Comments first (rest of line)
      const hashIdx = line.indexOf("#");
      const inString = /['"]/.test(line.slice(0, hashIdx));
      if (hashIdx >= 0 && !inString) {
        return (
          <>
            {highlightPython(line.slice(0, hashIdx))}
            <span className="text-[var(--text-tertiary)] italic">{line.slice(hashIdx)}</span>
          </>
        );
      }
      return highlightPython(line);
    }
    if (kind === "md") {
      if (line.startsWith("# ")) return <span className="text-blue-500 dark:text-blue-300 font-semibold">{line}</span>;
      if (line.startsWith("## ")) return <span className="text-blue-500 dark:text-blue-300">{line}</span>;
      if (line.startsWith("### ")) return <span className="text-blue-500 dark:text-blue-300 opacity-80">{line}</span>;
      if (line.startsWith("> ")) return <span className="text-[var(--text-tertiary)] italic">{line}</span>;
      if (line.startsWith("- ") || line.startsWith("* ") || /^\d+\.\s/.test(line)) {
        return <><span className="text-[var(--success)]">{line.slice(0, line.indexOf(" ") + 1)}</span>{line.slice(line.indexOf(" ") + 1)}</>;
      }
    }
    return line || " "; // empty lines need a space to keep row height
  }

  function highlightPython(text: string): React.ReactNode {
    // Tokenize on word boundaries; preserve whitespace by splitting with capture
    const tokens = text.split(/(\s+|[(){}[\],:;.])/);
    return tokens.map((t, i) => {
      if (PYTHON_KEYWORDS.has(t)) {
        return <span key={i} className="text-purple-500 dark:text-purple-300">{t}</span>;
      }
      // String literals (very rough)
      if (/^["'].*["']$/.test(t)) {
        return <span key={i} className="text-green-500 dark:text-green-300">{t}</span>;
      }
      // Decorators
      if (t.startsWith("@") && t.length > 1 && /[a-zA-Z]/.test(t[1])) {
        return <span key={i} className="text-orange-500 dark:text-orange-300">{t}</span>;
      }
      return <span key={i}>{t}</span>;
    });
  }

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      /* ignore */
    }
  };
  const handleDownload = () => {
    const ext = kind === "py" ? "py" : "md";
    const filename = `artifact.${ext}`;
    const blob = new Blob([content], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const LONG_THRESHOLD = 200;
  const isLong = lines.length > LONG_THRESHOLD;
  const visibleLines = isLong && !expanded ? lines.slice(0, LONG_THRESHOLD) : lines;

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-3">
        <div className="text-[10px] tabular text-[var(--text-tertiary)] flex items-center gap-3 flex-1">
          <span>{lines.length} lines · {content.length.toLocaleString()} chars</span>
          <span className="mono">{kind}</span>
        </div>
        <button
          onClick={handleCopy}
          className="text-[10px] px-2 py-0.5 rounded border border-[var(--border-muted)] hover:bg-[var(--surface-2)] transition-colors"
        >
          {copied ? "✓ copied" : "Copy"}
        </button>
        <button
          onClick={handleDownload}
          className="text-[10px] px-2 py-0.5 rounded border border-[var(--border-muted)] hover:bg-[var(--surface-2)] transition-colors"
        >
          Download
        </button>
      </div>
      <div
        className={cn(
          "bg-[var(--bg)] border border-[var(--border-muted)] rounded overflow-auto",
          expanded ? "max-h-[1200px]" : "max-h-[500px]",
        )}
      >
        <table className="w-full text-[11px] mono leading-relaxed">
          <tbody>
            {visibleLines.map((line, i) => (
              <tr key={i} className="hover:bg-[var(--surface-2)]/40">
                <td className="text-[var(--text-tertiary)] tabular text-right pr-3 pl-2 select-none w-10 align-top">
                  {i + 1}
                </td>
                <td className="pr-3 pb-px whitespace-pre-wrap break-words">
                  {highlightLine(line, i)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {isLong && (
        <button
          onClick={() => setExpanded((v) => !v)}
          className="text-[11px] text-[var(--text-tertiary)] hover:text-[var(--text-primary)] underline"
        >
          {expanded
            ? `Collapse to first ${LONG_THRESHOLD} lines`
            : `Show all ${lines.length} lines (currently showing ${LONG_THRESHOLD})`}
        </button>
      )}
    </div>
  );
}
