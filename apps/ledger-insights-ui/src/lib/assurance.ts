export type AssuranceStatus = "pass" | "fail" | "not_run" | "unknown";

export interface AssuranceDimensions {
  deterministicPolicy: AssuranceStatus;
  buildTests: AssuranceStatus;
  dependencySecurity: AssuranceStatus;
  semanticReview: AssuranceStatus;
  mandatoryHuman: AssuranceStatus;
  fullyVerified: boolean;
}

export function deriveAssurance(payload: Record<string, unknown>): AssuranceDimensions {
  const status = (value: unknown): AssuranceStatus =>
    value === "pass" || value === "fail" || value === "not_run" ? value : "unknown";
  const dimensions = {
    deterministicPolicy: status(payload.deterministic_policy),
    buildTests: status(payload.build_tests),
    dependencySecurity: status(payload.dependency_security),
    semanticReview: status(payload.semantic_review),
    mandatoryHuman: status(payload.mandatory_human),
  };
  return {
    ...dimensions,
    fullyVerified: Object.values(dimensions).every((value) => value === "pass"),
  };
}
