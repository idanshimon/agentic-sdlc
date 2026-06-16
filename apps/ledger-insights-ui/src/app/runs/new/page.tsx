"use client";
import { useState, useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  Upload, FileText, Loader2, Sparkles, Settings2, ChevronDown, ChevronRight,
  AlertCircle, Play, Bot, Hand,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/layout/page-header";
import { orchestrator, fetchSample } from "@/lib/api/orchestrator";
import { isDemoMode, getScenario, startDemoRun } from "@/lib/demo";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

type Sample = {
  id: string;
  title: string;
  subtitle: string;
  url: string;
  filename: string;
  size_kb: number;
  badge: "FAST" | "RECOMMENDED" | "FULL" | "WORKLOAD";
  badge_tone: "ok" | "primary" | "secondary" | "warning";
};

const SAMPLES: Sample[] = [
  {
    id: "eligibility",
    title: "Patient Eligibility Check",
    subtitle: "Tiny PRD with 4 deliberate ambiguities — perfect for the resolver flow",
    url: "/api/samples/eligibility-check.md",
    filename: "eligibility-check.md",
    size_kb: 1,
    badge: "FAST",
    badge_tone: "ok",
  },
  {
    id: "vitals",
    title: "Patient Vitals Streaming",
    subtitle: "FHIR HL7 streaming, cardiology workload, real PHI surface to classify",
    url: "/api/samples/patient-vitals-streaming.md",
    filename: "patient-vitals-streaming.md",
    size_kb: 1,
    badge: "WORKLOAD",
    badge_tone: "warning",
  },
  {
    id: "labs",
    title: "Lab Result Notifications",
    subtitle: "HL7 v2 ORU pipeline, multi-region, KEK encryption — heavy compliance",
    url: "/api/samples/lab-notifications.md",
    filename: "lab-notifications.md",
    size_kb: 2,
    badge: "RECOMMENDED",
    badge_tone: "primary",
  },
  {
    id: "pci-clean",
    title: "PCI Clean — Real PRD",
    subtitle: "63KB enterprise-scale PRD with deep compliance surface. Realistic enterprise workload.",
    url: "/api/samples/pci-clean.md",
    filename: "pci-clean.md",
    size_kb: 63,
    badge: "FULL",
    badge_tone: "secondary",
  },
];

const TEAMS = ["cardiology", "finance", "compliance", "platform"] as const;

const MODES = [
  {
    id: "manual" as const,
    label: "Manual",
    icon: Hand,
    desc: "Pause at every gate, you decide each resolution.",
    tone: "info" as const,
  },
  {
    id: "hybrid" as const,
    label: "Hybrid",
    icon: Sparkles,
    desc: "Autopilot routine classes, page you for the gnarly ones.",
    tone: "secondary" as const,
  },
  {
    id: "autopilot" as const,
    label: "Autopilot",
    icon: Bot,
    desc: "Resolve every ambiguity from precedent. End-to-end run.",
    tone: "warning" as const,
  },
];

const STAGES = ["ingest", "assessor", "architect", "test_plan", "codegen", "review_scan"] as const;
type Stage = (typeof STAGES)[number];

const STAGE_LABELS: Record<Stage, string> = {
  ingest: "Ingest",
  assessor: "Assessor",
  architect: "Architect",
  test_plan: "Test Plan",
  codegen: "CodeGen",
  review_scan: "Review · Scan",
};

const PROVIDERS = [
  { value: "default", label: "Server default", models: [] as string[] },
  { value: "openai-apim", label: "OpenAI (via APIM)", models: ["gpt-4-1", "gpt-4-1-mini", "o3-mini"] },
  { value: "anthropic", label: "Anthropic", models: ["claude-sonnet-4-6", "claude-opus-4-7", "claude-haiku-4-5"] },
  { value: "databricks", label: "Databricks (Claude)", models: ["databricks-claude-sonnet-4-6", "databricks-claude-opus-4-7"] },
  { value: "google", label: "Google Gemini", models: ["gemini-2-5-pro", "gemini-2-5-flash"] },
];

type StageOverride = { provider: string; model: string };

export default function NewRunPage() {
  const router = useRouter();
  const demo = isDemoMode();

  const [prdText, setPrdText] = useState("");
  const [filename, setFilename] = useState("untitled.md");
  const [team, setTeam] = useState<string>("cardiology");
  const [mode, setMode] = useState<"manual" | "autopilot" | "hybrid">("manual");
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [overrides, setOverrides] = useState<Record<Stage, StageOverride>>({
    ingest: { provider: "default", model: "" },
    assessor: { provider: "default", model: "" },
    architect: { provider: "default", model: "" },
    test_plan: { provider: "default", model: "" },
    codegen: { provider: "default", model: "" },
    review_scan: { provider: "default", model: "" },
  });

  const buildStageProviders = useCallback(() => {
    const out: Record<string, { provider: string; model: string }> = {};
    for (const stage of STAGES) {
      const o = overrides[stage];
      if (o.provider !== "default" && o.model) {
        out[stage] = { provider: o.provider, model: o.model };
      }
    }
    return out;
  }, [overrides]);

  const submit = useCallback(
    async (text: string, file: string, busyKey: string) => {
      setBusy(busyKey);
      setError(null);
      try {
        const sp = buildStageProviders();
        const { run_id } = await orchestrator.createRun({
          prd_text: text,
          filename: file,
          team_id: team,
          mode,
          ...(Object.keys(sp).length > 0 ? { stage_providers: sp } : {}),
        });
        toast.success("Run started", {
          description: `${file} · ${team} · ${mode}`,
        });
        router.push(`/runs/${run_id}`);
      } catch (e) {
        const msg = e instanceof Error ? e.message : "Failed to start run";
        setError(msg);
        setBusy(null);
        toast.error("Failed to start run", { description: msg });
      }
    },
    [router, team, mode, buildStageProviders],
  );

  const onFile = useCallback(async (file: File) => {
    const text = await file.text();
    setPrdText(text);
    setFilename(file.name);
  }, []);

  const onSample = useCallback(
    async (s: Sample) => {
      // Demo Mode short-circuit: replay pre-canned fixtures, no LLM call.
      if (demo) {
        const scenario = getScenario(s.id);
        if (!scenario) {
          toast.error("No demo fixture for this sample", {
            description: `Demo Mode currently ships fixtures for: ${
              ["vitals"].join(", ")
            }. Try "Patient Vitals Streaming".`,
          });
          return;
        }
        setBusy(s.id);
        setError(null);
        try {
          const runId = startDemoRun(s.id);
          toast.success("Demo run started", {
            description: `${s.title} · replaying audit-grade pipeline`,
          });
          router.push(`/runs/${runId}`);
        } catch (e) {
          const msg = e instanceof Error ? e.message : "Failed to start demo run";
          setError(msg);
          setBusy(null);
        }
        return;
      }

      setBusy(s.id);
      setError(null);
      try {
        const text = await fetchSample(s.url);
        setPrdText(text);
        setFilename(s.filename);
        await submit(text, s.filename, s.id);
      } catch (e) {
        const msg = e instanceof Error ? e.message : "Failed to load sample";
        setError(msg);
        setBusy(null);
      }
    },
    [demo, router, submit],
  );

  const onTextSubmit = useCallback(() => {
    if (!prdText.trim()) {
      setError("PRD body is empty");
      return;
    }
    submit(prdText, filename || "untitled.md", "text");
  }, [prdText, filename, submit]);

  useEffect(() => {
    if (!prdText.trim()) return;
    const lines = prdText.split("\n");
    const first = lines.find((l) => l.trim().startsWith("#"));
    if (first && filename === "untitled.md") {
      const slug = first
        .replace(/^#+\s*/, "")
        .toLowerCase()
        .trim()
        .replace(/[^a-z0-9-]+/g, "-")
        .replace(/^-+|-+$/g, "")
        .slice(0, 48);
      // Defer setState to next microtask to avoid the
      // react-hooks/set-state-in-effect cascade warning.
      if (slug) queueMicrotask(() => setFilename(`${slug}.md`));
    }
  }, [prdText, filename]);

  return (
    <div className="space-y-6">
      <PageHeader
        plane="pipeline"
        title={demo ? "Start a new demo run" : "Start a new run"}
        description={
          demo
            ? "Demo Mode — runs replay pre-canned audit-grade output from a real Phase-A-fixed pipeline run. Zero LLM calls, zero network. Click any sample tagged DEMO to begin."
            : "Drop in a PRD or pick a sample. The pipeline classifies ambiguities, resolves them (with you in the loop), generates code, runs the policy gates, and opens a PR."
        }
      />

      {error && (
        <Card className="p-3 border-[var(--danger)]/40 bg-[var(--danger)]/10 flex items-start gap-2">
          <AlertCircle className="h-4 w-4 text-[var(--danger)] mt-0.5 shrink-0" />
          <span className="text-xs text-[var(--danger)] leading-relaxed">{error}</span>
        </Card>
      )}

      {/* Sample chips */}
      <Card className="p-5 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold">Sample PRDs</h2>
            <p className="text-xs text-[var(--text-tertiary)]">
              {demo
                ? "Click a DEMO-tagged sample to replay a pre-canned audit-grade pipeline run."
                : "Click any sample to load + start a run immediately with your current mode/team."}
            </p>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {SAMPLES.map((s) => {
            const hasDemoFixture = !!getScenario(s.id);
            const disabledInDemo = demo && !hasDemoFixture;
            return (
              <button
                key={s.id}
                onClick={() => onSample(s)}
                disabled={busy !== null || disabledInDemo}
                title={disabledInDemo ? "No demo fixture for this sample yet" : undefined}
                className={cn(
                  "group text-left rounded-lg border border-[var(--border-default)] bg-[var(--bg)] p-4 hover:border-[var(--text-tertiary)] hover:bg-[var(--overlay)]/40 transition-colors relative overflow-hidden",
                  busy === s.id && "border-[var(--primary)] bg-[var(--primary)]/5",
                  busy && busy !== s.id && "opacity-50 cursor-not-allowed",
                  disabledInDemo && "opacity-40 cursor-not-allowed",
                )}
              >
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <FileText className="h-4 w-4 text-[var(--text-tertiary)] shrink-0" />
                    <h3 className="text-sm font-semibold truncate">{s.title}</h3>
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    {demo && hasDemoFixture && (
                      <Badge variant="warning" className="text-[10px]">
                        DEMO
                      </Badge>
                    )}
                    <Badge variant={s.badge_tone === "ok" ? "success" : s.badge_tone === "primary" ? "info" : s.badge_tone === "secondary" ? "secondary" : "warning"} className="text-[10px]">
                      {busy === s.id ? <Loader2 className="h-2.5 w-2.5 animate-spin" /> : s.badge}
                    </Badge>
                  </div>
                </div>
                <p className="text-xs text-[var(--text-secondary)] leading-relaxed mb-2">{s.subtitle}</p>
                <div className="flex items-center justify-between text-[10px] text-[var(--text-tertiary)]">
                  <span className="mono">{s.filename}</span>
                  <span className="tabular">
                    {disabledInDemo ? "no demo fixture" : s.size_kb >= 1 ? `~${s.size_kb} KB` : "<1 KB"}
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      </Card>

      {/* Paste / upload */}
      <Card className="p-5 space-y-3">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div>
            <h2 className="text-sm font-semibold">Paste or upload</h2>
            <p className="text-xs text-[var(--text-tertiary)]">
              Markdown or plain text. Drop a file, click to browse, or paste below.
            </p>
          </div>
          <label className="cursor-pointer">
            <input
              type="file"
              accept=".md,.txt,.markdown"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) onFile(f);
              }}
            />
            <span className="inline-flex items-center gap-1.5 h-8 px-3 text-xs font-medium text-[var(--text-secondary)] border border-[var(--border-default)] rounded-md hover:bg-[var(--overlay)] transition-colors">
              <Upload className="h-3.5 w-3.5" /> Upload file
            </span>
          </label>
        </div>
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            const f = e.dataTransfer.files?.[0];
            if (f) onFile(f);
          }}
          className={cn(
            "rounded-lg border-2 border-dashed transition-colors",
            dragging
              ? "border-[var(--primary)] bg-[var(--primary)]/5"
              : "border-[var(--border-default)]",
          )}
        >
          <Textarea
            value={prdText}
            onChange={(e) => setPrdText(e.target.value)}
            rows={14}
            placeholder="# Your PRD title&#10;&#10;## Goal&#10;...&#10;&#10;## Requirements&#10;1. ...&#10;2. ...&#10;&#10;## Out of scope&#10;..."
            className="border-0 bg-transparent mono text-xs resize-y focus-visible:ring-0"
          />
        </div>
        <div className="flex items-center justify-between gap-2 pt-1">
          <span className="text-[10px] text-[var(--text-tertiary)] tabular">
            {prdText.length} chars · {prdText.split(/\s+/).filter(Boolean).length} words
          </span>
          <Input
            value={filename}
            onChange={(e) => setFilename(e.target.value)}
            placeholder="filename.md"
            className="h-8 text-xs mono max-w-[240px]"
          />
        </div>
      </Card>

      {/* Run config */}
      <div className="grid gap-3 md:grid-cols-2">
        <Card className="p-4 space-y-3">
          <div>
            <h3 className="text-xs font-medium uppercase tracking-wider text-[var(--text-tertiary)] mb-1.5">
              Team
            </h3>
            <div className="grid grid-cols-2 gap-2">
              {TEAMS.map((t) => (
                <button
                  key={t}
                  onClick={() => setTeam(t)}
                  className={cn(
                    "h-9 text-xs font-medium rounded-md border transition-colors capitalize",
                    team === t
                      ? "border-[var(--primary)] bg-[var(--primary)]/10 text-[var(--primary)]"
                      : "border-[var(--border-default)] text-[var(--text-secondary)] hover:bg-[var(--overlay)]",
                  )}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>
        </Card>
        <Card className="p-4 space-y-3">
          <div>
            <h3 className="text-xs font-medium uppercase tracking-wider text-[var(--text-tertiary)] mb-1.5">
              Mode
            </h3>
            <div className="space-y-1.5">
              {MODES.map((m) => {
                const Icon = m.icon;
                const active = mode === m.id;
                return (
                  <button
                    key={m.id}
                    onClick={() => setMode(m.id)}
                    className={cn(
                      "w-full text-left flex items-start gap-2.5 p-2 rounded-md border transition-colors",
                      active
                        ? "border-[var(--primary)] bg-[var(--primary)]/10"
                        : "border-[var(--border-default)] hover:bg-[var(--overlay)]",
                    )}
                  >
                    <Icon className={cn("h-3.5 w-3.5 mt-0.5 shrink-0", active ? "text-[var(--primary)]" : "text-[var(--text-tertiary)]")} />
                    <div className="min-w-0">
                      <div className={cn("text-xs font-semibold", active && "text-[var(--primary)]")}>{m.label}</div>
                      <div className="text-[11px] text-[var(--text-secondary)] leading-tight">{m.desc}</div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </Card>
      </div>

      {/* Advanced — per-stage model overrides */}
      <Card className="overflow-hidden">
        <button
          onClick={() => setAdvancedOpen((p) => !p)}
          className="w-full flex items-center gap-3 p-4 text-left hover:bg-[var(--overlay)]/40 transition-colors"
        >
          {advancedOpen ? <ChevronDown className="h-4 w-4 text-[var(--text-tertiary)]" /> : <ChevronRight className="h-4 w-4 text-[var(--text-tertiary)]" />}
          <Settings2 className="h-4 w-4 text-[var(--text-tertiary)]" />
          <div className="flex-1">
            <div className="text-sm font-semibold">Advanced — per-stage model overrides</div>
            <div className="text-xs text-[var(--text-tertiary)]">
              Pin a specific provider/model per stage for this run only. Defaults to server-side config when left as &quot;Server default&quot;.
            </div>
          </div>
        </button>
        {advancedOpen && (
          <div className="px-4 pb-4 pt-1 border-t border-[var(--border-muted)] space-y-2">
            {STAGES.map((stage) => {
              const o = overrides[stage];
              const providerMeta = PROVIDERS.find((p) => p.value === o.provider);
              const models = providerMeta?.models ?? [];
              return (
                <div key={stage} className="grid grid-cols-12 items-center gap-2 py-1">
                  <div className="col-span-3 text-xs font-medium text-[var(--text-secondary)]">
                    {STAGE_LABELS[stage]}
                  </div>
                  <select
                    className="col-span-4 h-8 px-2 rounded-md border border-[var(--border-default)] bg-[var(--overlay)] text-xs"
                    value={o.provider}
                    onChange={(e) => setOverrides((p) => ({ ...p, [stage]: { provider: e.target.value, model: "" } }))}
                  >
                    {PROVIDERS.map((p) => (
                      <option key={p.value} value={p.value}>{p.label}</option>
                    ))}
                  </select>
                  <select
                    className="col-span-5 h-8 px-2 rounded-md border border-[var(--border-default)] bg-[var(--overlay)] text-xs mono disabled:opacity-50"
                    value={o.model}
                    disabled={models.length === 0}
                    onChange={(e) => setOverrides((p) => ({ ...p, [stage]: { ...p[stage], model: e.target.value } }))}
                  >
                    <option value="">{models.length === 0 ? "—" : "Pick a model"}</option>
                    {models.map((m) => (
                      <option key={m} value={m}>{m}</option>
                    ))}
                  </select>
                </div>
              );
            })}
          </div>
        )}
      </Card>

      {/* Submit */}
      <div className="flex items-center justify-end gap-2 pb-4">
        {demo && (
          <span className="text-[11px] text-[var(--text-tertiary)] mr-auto">
            Demo Mode is active — paste/upload submission disabled. Use a DEMO-tagged sample above.
          </span>
        )}
        <Button variant="ghost" onClick={() => { setPrdText(""); setFilename("untitled.md"); }}>
          Clear
        </Button>
        <Button
          variant="primary"
          size="lg"
          onClick={onTextSubmit}
          disabled={!prdText.trim() || busy !== null || demo}
          title={demo ? "Disabled in Demo Mode — use a sample" : undefined}
        >
          {busy === "text" ? (
            <><Loader2 className="h-4 w-4 animate-spin" /> Starting run…</>
          ) : (
            <><Play className="h-4 w-4" /> Start run</>
          )}
        </Button>
      </div>
    </div>
  );
}
