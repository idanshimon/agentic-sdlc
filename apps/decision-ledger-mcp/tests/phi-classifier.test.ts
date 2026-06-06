import { describe, it, expect } from "vitest";
import { classifyPhi } from "../src/phi-classifier.js";

describe("classifyPhi", () => {
  it("flags raw MRN", () => {
    const r = classifyPhi("logger.info(`patient ${MRN} updated`)");
    expect(r.has_phi).toBe(true);
    expect(r.phi_class).toBe("high");
    expect(r.bundle_refs).toContain("security/v0.1.0/PHI-001");
  });

  it("flags raw patient_id", () => {
    const r = classifyPhi("SELECT * FROM patients WHERE patient_id = 12345");
    expect(r.has_phi).toBe(true);
    expect(r.phi_class).toBe("high");
  });

  it("flags raw DOB pattern", () => {
    const r = classifyPhi("# user DOB 1985");
    expect(r.has_phi).toBe(true);
  });

  it("does not flag redacted IDs", () => {
    const r = classifyPhi("logger.info(`patient ${redacted_id()} updated`)");
    expect(r.has_phi).toBe(false);
    expect(r.phi_class).toBe("none");
  });

  it("flags secret patterns separately", () => {
    const r = classifyPhi('client_secret = "abcDEF1234567890_XYZ"');
    expect(r.matched_patterns).toContain("Secret pattern");
    expect(r.bundle_refs).toContain("security/v0.1.0/SECRET-001");
  });

  it("does not flag short alphanumerics as secrets", () => {
    const r = classifyPhi('api_key = "short"');
    expect(r.matched_patterns).not.toContain("Secret pattern");
  });
});
