// Shared Meridian lineage data for all sketch variants (the real seeded scenario).
// Roots = human precedents; children reuse them; one flagged; teaching signals.
window.LINEAGE = {
  nodes: [
    { id: "phi-root",   rank: 0, actor: "human", role: "Idan (Lead)",       cls: "phi-classification", rule: "security/PHI-001",   text: "Portal messages classified PHI-high", root: true },
    { id: "auth-root",  rank: 0, actor: "human", role: "Idan (Lead)",       cls: "auth-policy",        rule: "security/AUTH-002",  text: "Patient auth via SMART-on-FHIR OAuth2 + step-up MFA", root: true },
    { id: "name-root",  rank: 0, actor: "agent", role: "Architect Agent",   cls: "naming-convention",  rule: "architect/NAMING-001", text: "REST resources kebab-case, FHIR names verbatim", root: true },

    { id: "phi-appt",   rank: 1, actor: "agent", role: "Assessor Agent",    cls: "phi-classification", rule: "security/PHI-001",  text: "Appointment notes classified PHI-high", reused: "phi-root" },
    { id: "phi-bill",   rank: 1, actor: "agent", role: "Assessor Agent",    cls: "phi-classification", rule: "security/PHI-001",  text: "Billing records classified PHI-high", reused: "phi-root" },
    { id: "auth-appt",  rank: 1, actor: "agent", role: "Assessor Agent",    cls: "auth-policy",        rule: "security/AUTH-002", text: "Appointment booking auth via SMART-on-FHIR", reused: "auth-root" },
    { id: "auth-bill",  rank: 1, actor: "agent", role: "Assessor Agent",    cls: "auth-policy",        rule: "security/AUTH-002", text: "Billing export step-up MFA", reused: "auth-root" },
    { id: "name-appt",  rank: 1, actor: "agent", role: "Assessor Agent",    cls: "naming-convention",  rule: "architect/NAMING-001", text: "Appointment endpoints kebab-case", reused: "name-root" },

    { id: "bill-retain",rank: 1, actor: "agent", role: "Assessor Agent",    cls: "data-retention",     rule: "privacy/RETAIN-004", text: "Billing retention set to 3 years", flagged: true },
  ],
  teaching: [
    { id: "t1", on: "phi-root",   kind: "endorsed", who: "Idan", label: "👍 endorsed" },
    { id: "t2", on: "phi-appt",   kind: "endorsed", who: "Idan", label: "👍 endorsed" },
    { id: "t3", on: "bill-retain",kind: "flagged",  who: "Idan", label: "🚩 flagged — won't reuse" },
  ],
  stats: { chains: 3, roots: 3, reuse: 5, flagged: 1 },
};
