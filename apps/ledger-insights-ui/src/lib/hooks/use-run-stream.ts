"use client";
import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { orchestrator } from "@/lib/api/orchestrator";
import { isDemoMode, isDemoRun, subscribeDemoRun } from "@/lib/demo";
import type { StageEvent } from "@/lib/types";

export function streamGenerationAfterError(generation: number): number {
  return generation + 1;
}

export function reconnectDelayMs(attempt: number, random: () => number = Math.random): number {
  const base = Math.min(30_000, 1_000 * 2 ** Math.max(0, attempt));
  const jitter = Math.floor(base * 0.2 * random());
  return Math.min(30_000, base + jitter);
}

/** Subscribe to live stage events via SSE.
 *
 * Phase 4 (2026-06-16): when a new SSE event arrives, also invalidate
 * the run query so React Query refetches /api/runs/<id> and the
 * stage-progress pills + status badge update in real time. Without
 * this, operators had to manually refresh after every gate approval
 * to see the architect stage light up — defeating the whole point
 * of the SSE pipe.
 *
 * Also: dedup by (stage, status, ts) so events that the run-state
 * polling already brought down don't get re-appended on top of the
 * same events coming through SSE. (The page combines server events +
 * live SSE events into a single render list; without dedup, every
 * stage transition rendered twice.)
 */
export function useRunStream(runId: string | undefined) {
  const [events, setEvents] = useState<StageEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [streamGeneration, setStreamGeneration] = useState(0);
  const [reconnectAttempt, setReconnectAttempt] = useState(0);
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!runId) return;
    // Demo Mode: pull events from the local replay engine instead of SSE.
    if (isDemoMode() && isDemoRun(runId)) {
      const unsub = subscribeDemoRun(runId, (evs) => setEvents(evs));
      // Defer setConnected to the next microtask so we don't trigger a
      // cascading render inside the effect body (react-hooks/set-state-in-effect).
      const handle = queueMicrotask(() => setConnected(true));
      return () => {
        void handle;
        unsub();
        setConnected(false);
      };
    }
    const src = new EventSource(orchestrator.streamUrl(runId));
    let reconnectTimer: number | undefined;
    let disposed = false;
    src.onopen = () => {
      setConnected(true);
      setReconnectAttempt(0);
    };
    src.onmessage = (e) => {
      try {
        const ev = JSON.parse(e.data) as StageEvent;
        setEvents((prev) => {
          // Dedup by (stage, status, ts) — server-side run.events may
          // already contain this exact event from the last polling tick,
          // and React Query refetch below will bring more down. Without
          // dedup the event stream renders duplicates on every stage
          // transition.
          const key = `${ev.stage}|${ev.status}|${ev.ts ?? ""}`;
          if (prev.some((p) => `${p.stage}|${p.status}|${p.ts ?? ""}` === key)) {
            return prev;
          }
          return [...prev, ev];
        });
        // Phase 4: any new event means the run state may have changed
        // (status flipped, current_stage advanced, decisions count grew).
        // Invalidate the run query so React Query refetches and the
        // stage pills + status badge update without a manual refresh.
        queryClient.invalidateQueries({ queryKey: ["run", runId] });
      } catch {
        /* ignore */
      }
    };
    src.onerror = () => {
      setConnected(false);
      src.close();
      const delay = reconnectDelayMs(reconnectAttempt);
      reconnectTimer = window.setTimeout(() => {
        if (disposed) return;
        setReconnectAttempt((attempt) => attempt + 1);
        setStreamGeneration(streamGenerationAfterError);
      }, delay);
    };
    return () => {
      disposed = true;
      if (reconnectTimer !== undefined) window.clearTimeout(reconnectTimer);
      src.close();
      setConnected(false);
    };
  }, [runId, queryClient, streamGeneration, reconnectAttempt]);

  return { events, connected };
}
