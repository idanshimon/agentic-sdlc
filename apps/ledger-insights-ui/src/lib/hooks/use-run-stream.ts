"use client";
import { useEffect, useState } from "react";
import { orchestrator } from "@/lib/api/orchestrator";
import type { StageEvent } from "@/lib/types";

/** Subscribe to live stage events via SSE. */
export function useRunStream(runId: string | undefined) {
  const [events, setEvents] = useState<StageEvent[]>([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    if (!runId) return;
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
