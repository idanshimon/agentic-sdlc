"use client";
import { useEffect, useState } from "react";
import { orchestrator } from "@/lib/api/orchestrator";
import { isDemoMode, isDemoRun, subscribeDemoRun } from "@/lib/demo";
import type { StageEvent } from "@/lib/types";

/** Subscribe to live stage events via SSE. */
export function useRunStream(runId: string | undefined) {
  const [events, setEvents] = useState<StageEvent[]>([]);
  const [connected, setConnected] = useState(false);

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
    src.onopen = () => setConnected(true);
    src.onmessage = (e) => {
      try {
        const ev = JSON.parse(e.data) as StageEvent;
        setEvents((prev) => [...prev, ev]);
      } catch {
        /* ignore */
      }
    };
    src.onerror = () => setConnected(false);
    return () => {
      src.close();
      setConnected(false);
    };
  }, [runId]);

  return { events, connected };
}
