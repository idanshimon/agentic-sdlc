import type { ClassifyPhiResult } from "./schema.js";

// Mirror of security/v0.1.0/PHI-001 pattern (raw identifier types)
const PHI_PATTERN = /(MRN|patient_id|SSN|DOB[\s_-]*[0-9]{4})/i;

// Mirror of security/v0.1.0/SECRET-001 pattern (secret-looking values inline)
const SECRET_PATTERN = /(client[\s_-]?secret|api[\s_-]?key|password)\s*[:=]\s*[\"\']?[A-Za-z0-9+/=_-]{16,}/i;

export function classifyPhi(text: string): ClassifyPhiResult {
  const matched: string[] = [];
  const bundleRefs: string[] = [];
  let hasPhi = false;
  let phiClass: "none" | "low" | "high" = "none";

  if (PHI_PATTERN.test(text)) {
    hasPhi = true;
    phiClass = "high";
    matched.push("PHI raw identifier pattern");
    bundleRefs.push("security/v0.1.0/PHI-001");
  }
  if (SECRET_PATTERN.test(text)) {
    matched.push("Secret pattern");
    bundleRefs.push("security/v0.1.0/SECRET-001");
  }

  return { has_phi: hasPhi, phi_class: phiClass, matched_patterns: matched, bundle_refs: bundleRefs };
}
