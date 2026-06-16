import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function relativeTime(d: Date | string | number): string {
  const date = typeof d === "string" || typeof d === "number" ? new Date(d) : d;
  const diff = Date.now() - date.getTime();
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return date.toLocaleDateString();
}

export function shortId(id: string | null | undefined, len = 8): string {
  if (!id) return "—";
  return id.length <= len ? id : id.slice(0, len);
}

export function fmtUsd(value: number | null | undefined, digits = 4): string {
  if (value == null) return "—";
  return `$${value.toFixed(digits)}`;
}

export function fmtNumber(value: number | null | undefined): string {
  if (value == null) return "—";
  return new Intl.NumberFormat("en-US").format(value);
}

/**
 * Stage events come from two backends with two different field names for
 * the timestamp:
 *   - Orchestrator (apps/orchestrator/models.py::StageEvent) emits `ts`
 *   - Demo Mode + some legacy fixtures emit `timestamp`
 *
 * Reading `e.timestamp` directly on a real-orchestrator event produced
 * `Invalid Date` everywhere event timestamps were rendered. Caught
 * 2026-06-16 when seeded SBM runs landed in the dashboard — the bug had
 * been latent since the dashboard was first wired to the live pipeline.
 *
 * Always use this helper. Returns `null` when neither field is present
 * or both are unparseable so callers can render `—` instead of
 * `Invalid Date`.
 */
export function eventTimestamp(
  e: { ts?: string; timestamp?: string },
): Date | null {
  const raw = e?.ts ?? e?.timestamp;
  if (!raw) return null;
  const d = new Date(raw);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function eventTimeLabel(
  e: { ts?: string; timestamp?: string },
): string {
  const d = eventTimestamp(e);
  return d ? d.toLocaleTimeString() : "—";
}
