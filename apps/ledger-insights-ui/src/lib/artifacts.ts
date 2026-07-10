import type { StageEvent } from "@/lib/types";

/**
 * Extract the architecture markdown from a run's event stream.
 *
 * Fix A (2026-07-09): live runs never populated `run.artifacts.architecture`
 * — that field only exists on demo fixtures (getDemoArtifacts). But the
 * orchestrator DOES emit the full architecture on the ARCHITECT "Architecture
 * drafted" event (_pipeline_stages.py -> _ev(run, Stage.ARCHITECT, "completed",
 * ..., architecture=res.text)). So on a live run, the Design Review gate said
 * "Approve architecture" with nothing to read, and the artifacts panel showed
 * the Architecture tab as "(pending)". This reads the architecture where it
 * actually lands on the live path.
 *
 * Returns the last non-empty architecture payload seen (later ARCHITECT events
 * supersede earlier ones, e.g. after a reject + re-architect loop).
 */
export function architectureFromEvents(
  events: ReadonlyArray<StageEvent> | undefined | null,
): string {
  if (!events?.length) return "";
  let arch = "";
  for (const ev of events) {
    const val = (ev.payload as { architecture?: unknown } | undefined)?.architecture;
    if (typeof val === "string" && val.trim()) {
      arch = val;
    }
  }
  return arch;
}
