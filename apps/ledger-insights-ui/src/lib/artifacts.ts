import type { StageEvent } from "@/lib/types";

export interface ProjectedRunArtifacts {
  architecture: string;
  testPlan: string;
  implementation: string;
  tests: string;
  decisionsMd: string;
  decisionsMdUrl: string;
  prUrl: string;
  deliveryStatus: string;
  deliveryReason: string;
  artifactFiles: string[];
}

function nonEmptyString(value: unknown): string {
  return typeof value === "string" && value.trim() ? value : "";
}

/** Project the latest live artifacts from the event contract emitted by the orchestrator. */
export function projectArtifactsFromEvents(
  events: ReadonlyArray<StageEvent> | undefined | null,
): ProjectedRunArtifacts {
  const out: ProjectedRunArtifacts = {
    architecture: "",
    testPlan: "",
    implementation: "",
    tests: "",
    decisionsMd: "",
    decisionsMdUrl: "",
    prUrl: "",
    deliveryStatus: "",
    deliveryReason: "",
    artifactFiles: [],
  };

  for (const event of events ?? []) {
    const payload = event.payload ?? {};
    const architecture = nonEmptyString(payload.architecture);
    const testPlan = nonEmptyString(payload.test_plan);
    const implementation = nonEmptyString(payload.app_code) || nonEmptyString(payload.code);
    const tests = nonEmptyString(payload.test_code);
    const decisionsMd = nonEmptyString(payload.decisions_md);
    const decisionsMdUrl = nonEmptyString(payload.decisions_md_url);
    const prUrl = nonEmptyString(payload.pr_url);
    const deliveryStatus = nonEmptyString(payload.delivery_status);
    const deliveryReason = nonEmptyString(payload.delivery_reason);

    if (architecture) out.architecture = architecture;
    if (testPlan) out.testPlan = testPlan;
    if (implementation) out.implementation = implementation;
    if (tests) out.tests = tests;
    if (decisionsMd) out.decisionsMd = decisionsMd;
    if (decisionsMdUrl) out.decisionsMdUrl = decisionsMdUrl;
    if (prUrl) out.prUrl = prUrl;
    if (deliveryStatus) out.deliveryStatus = deliveryStatus;
    if (deliveryReason) out.deliveryReason = deliveryReason;
    if (Array.isArray(payload.artifact_files)) {
      out.artifactFiles = payload.artifact_files.filter((value): value is string => typeof value === "string");
    }
  }

  return out;
}

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
