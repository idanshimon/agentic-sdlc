/**
 * TeachingSignalBar — the four-button row that appears on every DecisionCard.
 *
 * Per design discussion: NO umbrella label on the card. Buttons speak for
 * themselves. Aggregate "teaching signals" view lives in the sidebar at
 * /feedback.
 *
 * Buttons:
 *   👍 / 👎  — thumbs sentiment (cheap, no rationale required)
 *   Flag    — kills future precedent reuse on THIS entry (rationale required)
 *   Replay  — request re-run against current rules (rationale optional)
 *   Pause autopilot — gates the whole class (rationale required)
 *
 * Self-only signals (don't render on entries that ARE teaching signals — you
 * shouldn't be able to flag a flag).
 */

"use client";

import { useState } from "react";
import { ThumbsUp, ThumbsDown, Flag, RotateCcw, PauseCircle } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import {
  useThumbsMutation,
  useFlagMutation,
  useReplayMutation,
  usePauseClassMutation,
} from "@/lib/hooks/use-feedback";
import type { LedgerEntry } from "@/lib/types";

const TEACHING_SIGNAL_KINDS = new Set([
  "feedback_thumbs",
  "decision_flagged",
  "replay_requested",
  "class_paused",
]);

const ACTOR_ID =
  typeof window !== "undefined"
    ? // Operator identity placeholder. In a real EasyAuth deploy this comes
      // from the Container Apps `X-MS-CLIENT-PRINCIPAL-NAME` header surfaced
      // via a /api/me route; for now we pin "operator@demo" so the audit
      // trail is honest about provenance.
      "operator@demo"
    : "operator@demo";

export function TeachingSignalBar({ entry }: { entry: LedgerEntry }) {
  // React rules-of-hooks: every hook below MUST run on every render. The
  // self-suppression check that hides the bar on entries which ARE teaching
  // signals (you can't flag a flag) MUST happen AFTER all hook calls — an
  // early return above the hooks would make the hook order render-dependent
  // (different number of hooks called when an entry is/isn't a teaching
  // signal) and React will throw "Rendered fewer hooks than expected" the
  // moment a teaching-signal entry renders next to a stage_decision entry
  // in the same list.
  const thumbs = useThumbsMutation();
  const flag = useFlagMutation();
  const replay = useReplayMutation();
  const pause = usePauseClassMutation();

  const [showFlag, setShowFlag] = useState(false);
  const [showPause, setShowPause] = useState(false);
  const [flagReason, setFlagReason] = useState("");
  const [pauseReason, setPauseReason] = useState("");

  if (entry.runtime_kind && TEACHING_SIGNAL_KINDS.has(entry.runtime_kind)) {
    return null;
  }

  const ambiguityClass = entry.ambiguity_class;

  const busy =
    thumbs.isPending || flag.isPending || replay.isPending || pause.isPending;

  return (
    <div className="pt-2 border-t border-[var(--border-muted)] space-y-2">
      <div className="flex items-center gap-1 flex-wrap">
        <SignalButton
          icon={ThumbsUp}
          label="Helpful"
          onClick={() =>
            thumbs.mutate(
              {
                references_entry_id: entry.id,
                feedback_kind: "thumbs_up",
                actor_id: ACTOR_ID,
              },
              {
                onSuccess: () => toast.success("Recorded 👍"),
                onError: (e) => toast.error(`Failed to record: ${String(e)}`),
              },
            )
          }
          disabled={busy}
          accent="success"
          loading={thumbs.isPending && thumbs.variables?.feedback_kind === "thumbs_up"}
        />
        <SignalButton
          icon={ThumbsDown}
          label="Not helpful"
          onClick={() =>
            thumbs.mutate(
              {
                references_entry_id: entry.id,
                feedback_kind: "thumbs_down",
                actor_id: ACTOR_ID,
              },
              {
                onSuccess: () => toast.success("Recorded 👎"),
                onError: (e) => toast.error(`Failed to record: ${String(e)}`),
              },
            )
          }
          disabled={busy}
          accent="danger"
          loading={thumbs.isPending && thumbs.variables?.feedback_kind === "thumbs_down"}
        />
        <span className="w-2" />
        <SignalButton
          icon={Flag}
          label="Flag"
          onClick={() => setShowFlag((s) => !s)}
          disabled={busy}
          accent="warning"
          active={showFlag}
        />
        <SignalButton
          icon={RotateCcw}
          label="Replay"
          onClick={() =>
            replay.mutate(
              {
                references_entry_id: entry.id,
                actor_id: ACTOR_ID,
                rationale: "Re-run requested from /decisions card",
              },
              {
                onSuccess: () => toast.success("Replay queued — Track C worker picks it up"),
                onError: (e) => toast.error(`Failed to queue replay: ${String(e)}`),
              },
            )
          }
          disabled={busy}
          accent="primary"
          loading={replay.isPending}
        />
        {ambiguityClass && (
          <SignalButton
            icon={PauseCircle}
            label="Pause autopilot"
            onClick={() => setShowPause((s) => !s)}
            disabled={busy}
            accent="danger"
            active={showPause}
          />
        )}
      </div>

      {showFlag && (
        <FormPanel
          label="Why is this decision wrong?"
          placeholder="e.g. cited the wrong PHI rule version"
          value={flagReason}
          onChange={setFlagReason}
          submitLabel={flag.isPending ? "Flagging…" : "Flag decision"}
          disabled={!flagReason.trim() || flag.isPending}
          onSubmit={() => {
            flag.mutate(
              {
                references_entry_id: entry.id,
                actor_id: ACTOR_ID,
                rationale: flagReason.trim(),
              },
              {
                onSuccess: () => {
                  setFlagReason("");
                  setShowFlag(false);
                  toast.success("Decision flagged — findPrecedent will skip it next time");
                },
                onError: (e) => toast.error(`Failed to flag: ${String(e)}`),
              },
            );
          }}
          error={flag.isError ? String(flag.error) : null}
        />
      )}

      {showPause && ambiguityClass && (
        <FormPanel
          label={`Pause autopilot for class '${ambiguityClass}'?`}
          placeholder="What about this class needs human re-teaching"
          value={pauseReason}
          onChange={setPauseReason}
          submitLabel={pause.isPending ? "Pausing…" : "Pause autopilot"}
          disabled={!pauseReason.trim() || pause.isPending}
          onSubmit={() => {
            pause.mutate(
              {
                paused_class: ambiguityClass,
                actor_id: ACTOR_ID,
                rationale: pauseReason.trim(),
              },
              {
                onSuccess: () => {
                  setPauseReason("");
                  setShowPause(false);
                  toast.warning(`Autopilot paused for '${ambiguityClass}'`);
                },
                onError: (e) => toast.error(`Failed to pause: ${String(e)}`),
              },
            );
          }}
          error={pause.isError ? String(pause.error) : null}
        />
      )}

      {/* Inline success/error duplicated by sonner toasts — removed.
          Errors still surface inside FormPanel for flag/pause. */}
    </div>
  );
}

function SignalButton({
  icon: Icon,
  label,
  onClick,
  disabled,
  accent,
  loading,
  active,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  onClick: () => void;
  disabled?: boolean;
  accent?: "success" | "danger" | "warning" | "primary";
  loading?: boolean;
  active?: boolean;
}) {
  const accentColor: Record<string, string> = {
    success: "var(--success)",
    danger: "var(--danger)",
    warning: "var(--warning)",
    primary: "var(--primary)",
  };
  const color = accent ? accentColor[accent] : "var(--text-tertiary)";
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "inline-flex items-center gap-1 px-1.5 py-1 rounded text-[11px]",
        "border border-transparent transition-colors",
        "hover:bg-[var(--overlay)] hover:border-[var(--border-default)]",
        active && "bg-[var(--overlay)] border-[var(--border-default)]",
        loading && "animate-pulse",
        disabled && !loading && "opacity-50 cursor-not-allowed",
      )}
      title={label}
    >
      <Icon className="h-3.5 w-3.5" />
      <span style={{ color }}>{label}</span>
    </button>
  );
}

function FormPanel({
  label,
  placeholder,
  value,
  onChange,
  onSubmit,
  submitLabel,
  disabled,
  error,
}: {
  label: string;
  placeholder: string;
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  submitLabel: string;
  disabled: boolean;
  error: string | null;
}) {
  return (
    <div className="space-y-1.5 p-2 rounded bg-[var(--overlay)]/50 border border-[var(--border-muted)]">
      <label className="text-[11px] text-[var(--text-secondary)] block">
        {label}
      </label>
      <textarea
        className="w-full text-xs rounded border border-[var(--border-default)] bg-[var(--surface)] px-2 py-1 text-[var(--text)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:border-[var(--primary)] resize-none"
        rows={2}
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] text-[var(--text-tertiary)]">
          Audit trail: a new ledger entry will be written under your operator id.
        </span>
        <button
          type="button"
          onClick={onSubmit}
          disabled={disabled}
          className={cn(
            "text-[11px] px-2 py-1 rounded font-medium",
            "bg-[var(--primary)] text-[var(--surface-inverted,#001018)]",
            "hover:bg-[var(--primary-hover,var(--primary))]",
            "disabled:opacity-50 disabled:cursor-not-allowed",
          )}
        >
          {submitLabel}
        </button>
      </div>
      {error && (
        <div className="text-[11px] text-[var(--danger)]">{error}</div>
      )}
    </div>
  );
}
