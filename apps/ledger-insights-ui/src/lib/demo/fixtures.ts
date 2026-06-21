/* AUTO-GENERATED — do not edit by hand.
 * Source: experiments/results/phase-a-fixed/run-1/
 * Re-generate: python experiments/extract_demo_fixture.py
 *
 * This file contains the full pre-canned Phase-A-fixed output for
 * the Patient Vitals Streaming PRD. Demo Mode replays this verbatim
 * so the dashboard renders a real, audit-grade pipeline run with
 * no LLM calls and no network risk during demos.
 *
 * RIP-OUT: deleting this file + src/lib/demo/ + the four guards under
 * `if (isDemoMode())` removes Demo Mode entirely. See DEMO-MODE.md.
 */

export const VITALS_PRD = "# Patient Vitals Streaming API — Sample PRD\n\n**Title:** Patient Vitals Streaming API\n\n**Goal:** Ingest patient vital signs from bedside monitors, forward normalized\nevents to a clinical event bus. Cardiology team owns the consumer.\n\n**In-scope:** HL7 FHIR Observation resources for heart rate, SpO2, blood\npressure, temperature. WebSocket transport.\n\n**Out-of-scope:** ICU workflows, predictive analytics, alert routing.\n\n**Compliance:** PHI in transit. HIPAA minimum-necessary. PII redaction at egress.\n\n**SLA:** <100ms ingest latency, 99.95% uptime.\n\n**External integrations:** Ingest may need to consume vitals from third-party\nSaaS bedside-monitoring vendors (Philips IntelliVue, GE CARESCAPE).\nAuthorization model and egress policy for vendor connectors are TBD — some\nteams have been connecting to unapproved external tools without formal review.\n\n**Stakeholders:**\n- Cardiology engineering team (consumer)\n- Privacy office (review)\n- Security architecture (review)\n- Vendor management (egress policy)\n\n**Estimated launch:** Q3 FY26.\n";

export const VITALS_CARDS = [
  {
    "card_id": "3e38807e-a9b4-4a71-8364-055907dab944",
    "ambiguity_class": "auth-policy",
    "slot_value_hash": "61f002960993",
    "title": "Vendor Connector Authorization Model Undefined",
    "detail": "No concrete authentication/authorization mechanism is specified for Philips IntelliVue and GE CARESCAPE connectors, leaving the trust boundary and credential management approach undefined.",
    "prd_quote": "Authorization model and egress policy for vendor connectors are TBD — some teams have been connecting to unapproved external tools without formal review.",
    "prd_section": "External integrations",
    "gap_description": "No concrete authentication/authorization mechanism is specified for Philips IntelliVue and GE CARESCAPE connectors, leaving the trust boundary and credential management approach undefined.",
    "options": [
      {
        "label": "Mutual TLS + OAuth 2.0 Client Credentials per Vendor",
        "resolution": "Each vendor connector must authenticate via mutual TLS (client certificate issued by internal PKI) combined with OAuth 2.0 client_credentials grant scoped to read:vitals only. Credentials must be rotated every 90 days and reviewed by Security Architecture before activation.",
        "rationale": "HIPAA §164.312(d) requires entity authentication; mTLS + OAuth 2.0 satisfies both transport-layer and application-layer identity, and aligns with ONC HTI-1 API security requirements.",
        "downstream_impact": "Architect will design a certificate provisioning workflow and token introspection endpoint; CodeGen will implement mTLS handshake and OAuth middleware in the WebSocket upgrade path.",
        "recommended": true
      },
      {
        "label": "API Key per Vendor with IP Allowlist",
        "resolution": "Each vendor connector is issued a long-lived API key stored in a secrets manager, restricted to a pre-approved IP CIDR range maintained by Vendor Management.",
        "rationale": "Lower implementation complexity; some legacy Philips IntelliVue firmware versions do not support OAuth flows natively.",
        "downstream_impact": "Architect will design IP allowlist enforcement at the API gateway layer; CodeGen will implement API key header validation and secrets manager integration, but will not build certificate infrastructure.",
        "recommended": false
      }
    ],
    "team_occurrence_count": 0,
    "blast_radius_cost_usd": 450.0,
    "re_run_cost_usd": 0.0652,
    "is_gating": true,
    "is_eligible_for_promotion": false
  },
  {
    "card_id": "01e02d86-10dd-4bc9-8358-d9c3dfd3cf8d",
    "ambiguity_class": "phi-classification",
    "slot_value_hash": "6fc5f766f52e",
    "title": "Egress PHI Redaction Scope Ambiguous",
    "detail": "The PRD states 'PII redaction at egress' but does not specify which FHIR Observation fields constitute PHI/PII requiring redaction, nor whether patient identifiers in resource references (e.g., subject.reference) are included.",
    "prd_quote": "PII redaction at egress.",
    "prd_section": "Compliance",
    "gap_description": "The PRD states 'PII redaction at egress' but does not specify which FHIR Observation fields constitute PHI/PII requiring redaction, nor whether patient identifiers in resource references (e.g., subject.reference) are included.",
    "options": [
      {
        "label": "Redact All Direct Identifiers per HIPAA Safe Harbor §164.514(b)",
        "resolution": "At egress, strip or tokenize all 18 HIPAA Safe Harbor identifiers present in FHIR Observation resources, including subject.reference (replace with internal pseudonym token), performer, and any contained Patient resource. A field-level redaction manifest must be approved by the Privacy Office before launch.",
        "rationale": "HIPAA §164.514(b) Safe Harbor method provides a defined, auditable list of 18 identifier categories; applying it prevents inadvertent PHI leakage to the clinical event bus consumers.",
        "downstream_impact": "Architect will design a tokenization service mapping MRN/patient IDs to pseudonyms; CodeGen will implement a FHIR resource transformer that strips/replaces fields per the manifest before publishing to the event bus.",
        "recommended": true
      },
      {
        "label": "Redact Only Free-Text Fields Using Regex NLP Filter",
        "resolution": "Apply a regex and NLP-based de-identification filter only to free-text fields (Observation.note, Observation.text) at egress, leaving structured identifiers intact for downstream clinical use.",
        "rationale": "Cardiology engineering team may require patient identifiers in the event bus to correlate vitals with EHR records, making full Safe Harbor redaction operationally disruptive.",
        "downstream_impact": "CodeGen will implement a lighter NLP filter pipeline; Architect will document that structured PHI fields remain in the event bus and require downstream consumers to maintain BAAs and access controls.",
        "recommended": false
      }
    ],
    "team_occurrence_count": 0,
    "blast_radius_cost_usd": 400.0,
    "re_run_cost_usd": 0.0652,
    "is_gating": true,
    "is_eligible_for_promotion": false
  },
  {
    "card_id": "5952e4fa-87ce-4d93-ba83-dc70256bb0ae",
    "ambiguity_class": "data-retention",
    "slot_value_hash": "c59873c2ca91",
    "title": "Data Retention Period for Ingested Vitals Not Defined",
    "detail": "The PRD does not specify how long raw or normalized vitals data (containing PHI) is retained in the ingest pipeline, event bus, or any intermediate store before deletion or archival.",
    "prd_quote": "PHI in transit. HIPAA minimum-necessary.",
    "prd_section": "Compliance",
    "gap_description": "The PRD does not specify how long raw or normalized vitals data (containing PHI) is retained in the ingest pipeline, event bus, or any intermediate store before deletion or archival.",
    "options": [
      {
        "label": "6-Year Retention with Encrypted Archival per HIPAA §164.530(j)",
        "resolution": "Raw and normalized FHIR Observation records containing PHI are retained in encrypted cold storage for 6 years from creation date, then automatically purged. Event bus messages are deleted after consumer acknowledgment or 72 hours, whichever is sooner. Retention schedule must be documented in the organization's HIPAA policies.",
        "rationale": "HIPAA §164.530(j) requires covered entities to retain documentation for 6 years; applying the same window to PHI-bearing records is the conservative, audit-defensible default.",
        "downstream_impact": "Architect will design a tiered storage strategy (hot event bus → cold encrypted archive); CodeGen will implement TTL policies on the event bus and an archival job with AES-256 encryption at rest.",
        "recommended": true
      },
      {
        "label": "Retain Only in Event Bus for 24 Hours, No Long-Term Storage",
        "resolution": "The ingest pipeline treats itself as a pure transit layer; PHI-bearing messages are deleted from the event bus after 24 hours or consumer ACK. No archival store is maintained by this service; downstream consumers own retention.",
        "rationale": "Minimizes PHI exposure surface consistent with HIPAA minimum-necessary principle; appropriate if Cardiology's EHR system is the system of record for vitals.",
        "downstream_impact": "Architect will not design archival infrastructure for this service; CodeGen will implement 24-hour TTL only, but Architect must document that audit log reconstruction depends entirely on downstream consumer retention.",
        "recommended": false
      }
    ],
    "team_occurrence_count": 0,
    "blast_radius_cost_usd": 350.0,
    "re_run_cost_usd": 0.0652,
    "is_gating": true,
    "is_eligible_for_promotion": false
  },
  {
    "card_id": "7961407e-14a2-4ed3-ad8f-cff8df970c0e",
    "ambiguity_class": "phi-classification",
    "slot_value_hash": "6f5399a309f4",
    "title": "Minimum-Necessary Scope for Cardiology Event Bus Consumer Not Defined",
    "detail": "The PRD does not define which specific FHIR Observation fields the Cardiology consumer is authorized to receive, leaving the minimum-necessary determination required by HIPAA §164.502(b) unresolved.",
    "prd_quote": "HIPAA minimum-necessary. PII redaction at egress. Cardiology team owns the consumer.",
    "prd_section": "Compliance / Stakeholders",
    "gap_description": "The PRD does not define which specific FHIR Observation fields the Cardiology consumer is authorized to receive, leaving the minimum-necessary determination required by HIPAA §164.502(b) unresolved.",
    "options": [
      {
        "label": "Privacy Office Approves Explicit Cardiology Field Allowlist Before Launch",
        "resolution": "Before Q3 FY26 launch, the Privacy Office must produce and sign off on a field-level allowlist specifying exactly which FHIR Observation elements (e.g., valueQuantity, effectiveDateTime, code) the Cardiology event bus consumer may receive. The API enforces this allowlist as a projection filter at egress.",
        "rationale": "HIPAA §164.502(b)(1) requires minimum-necessary access to be defined per role/use-case; a Privacy Office-approved allowlist creates the required documentation and technical enforcement.",
        "downstream_impact": "Architect will design a projection/filter layer between the event bus and Cardiology consumer topic; CodeGen will implement configurable field-level filtering driven by the allowlist, with the Privacy Office as the configuration authority.",
        "recommended": true
      },
      {
        "label": "Cardiology Team Self-Declares Minimum-Necessary Fields",
        "resolution": "Cardiology engineering team submits a self-attested list of required FHIR fields to Security Architecture for logging purposes, without formal Privacy Office approval, before launch.",
        "rationale": "Faster path to launch; Cardiology has clinical context to determine what data they need without Privacy Office bottleneck.",
        "downstream_impact": "CodeGen may implement filtering based on Cardiology's declaration, but the organization bears audit risk if the self-attested scope is later found to exceed minimum-necessary under a HIPAA review.",
        "recommended": false
      }
    ],
    "team_occurrence_count": 0,
    "blast_radius_cost_usd": 300.0,
    "re_run_cost_usd": 0.0652,
    "is_gating": true,
    "is_eligible_for_promotion": false
  },
  {
    "card_id": "77fb03a9-da88-4aff-b1fc-c6bd3fd34682",
    "ambiguity_class": "auth-policy",
    "slot_value_hash": "4908dab38c8c",
    "title": "WebSocket Session Authentication Mechanism Not Specified",
    "detail": "The PRD specifies WebSocket as the transport but does not define how WebSocket sessions are authenticated for either inbound (bedside monitor → API) or outbound (API → Cardiology consumer) connections.",
    "prd_quote": "WebSocket transport.",
    "prd_section": "In-scope",
    "gap_description": "The PRD specifies WebSocket as the transport but does not define how WebSocket sessions are authenticated for either inbound (bedside monitor → API) or outbound (API → Cardiology consumer) connections.",
    "options": [
      {
        "label": "JWT Bearer Token in WebSocket Upgrade Header, Short-Lived (15-Min TTL)",
        "resolution": "WebSocket connections (both inbound from monitors and outbound to Cardiology consumer) must present a signed JWT (RS256) in the HTTP Upgrade request Authorization header. Tokens have a 15-minute TTL and are issued by the internal identity provider. Connections are terminated on token expiry and must re-authenticate.",
        "rationale": "HIPAA §164.312(d) requires unique user/entity authentication; short-lived JWTs in the Upgrade header are the IETF-recommended pattern for WebSocket auth (RFC 6455 §10.5) and limit PHI exposure window on compromised tokens.",
        "downstream_impact": "Architect will design token refresh flows for long-lived monitor connections; CodeGen will implement JWT validation middleware at the WebSocket upgrade handler and connection termination on expiry.",
        "recommended": true
      },
      {
        "label": "Session Cookie with HTTPS-Only Flag on WebSocket Upgrade",
        "resolution": "WebSocket connections authenticate via an HttpOnly, Secure, SameSite=Strict session cookie established during an initial HTTPS handshake, valid for the duration of the WebSocket session.",
        "rationale": "Cookie-based auth is simpler to implement for browser-based Cardiology dashboard consumers and avoids token refresh complexity for long-lived connections.",
        "downstream_impact": "Architect will design a session establishment endpoint; CodeGen will implement cookie validation at the WebSocket upgrade, but long-lived sessions increase PHI exposure risk if a session is hijacked.",
        "recommended": false
      }
    ],
    "team_occurrence_count": 0,
    "blast_radius_cost_usd": 250.0,
    "re_run_cost_usd": 0.0652,
    "is_gating": true,
    "is_eligible_for_promotion": false
  },
  {
    "card_id": "3a76c2b5-d7f5-4e3a-af1a-f82f35e9730e",
    "ambiguity_class": "sla-binding",
    "slot_value_hash": "c8b34210f891",
    "title": "99.95% Uptime SLA Measurement Window Not Defined",
    "detail": "The PRD does not specify the measurement window (monthly vs. annual), exclusion criteria (planned maintenance, vendor outages), or the consequence/remedy for SLA breach.",
    "prd_quote": "<100ms ingest latency, 99.95% uptime.",
    "prd_section": "SLA",
    "gap_description": "The PRD does not specify the measurement window (monthly vs. annual), exclusion criteria (planned maintenance, vendor outages), or the consequence/remedy for SLA breach.",
    "options": [
      {
        "label": "Monthly Rolling Window, 22-Minute Downtime Budget, Planned Maintenance Excluded",
        "resolution": "99.95% uptime is measured on a rolling calendar month (≤21.9 minutes downtime/month). Planned maintenance windows pre-approved by Cardiology engineering are excluded. SLA breach triggers a post-incident review within 48 hours and is tracked in the service reliability dashboard.",
        "rationale": "Monthly measurement windows are standard in clinical SaaS contracts and align with NIST SP 800-53 AU-6 continuous monitoring; 21.9 minutes/month is a concrete, testable budget.",
        "downstream_impact": "Architect will design redundancy and failover targets to meet the 21.9-minute budget; CodeGen will instrument uptime metrics with the defined exclusion logic in the observability stack.",
        "recommended": true
      },
      {
        "label": "Annual Window, 4.38-Hour Downtime Budget",
        "resolution": "99.95% uptime is measured annually (≤4.38 hours downtime/year), inclusive of all maintenance windows, with no formal breach remedy defined at this stage.",
        "rationale": "Annual windows reduce operational pressure during early post-launch stabilization and are common in internal service agreements.",
        "downstream_impact": "Architect may design less aggressive redundancy; CodeGen will implement simpler uptime tracking without monthly rollover logic, but breach accountability is weaker.",
        "recommended": false
      }
    ],
    "team_occurrence_count": 0,
    "blast_radius_cost_usd": 200.0,
    "re_run_cost_usd": 0.0652,
    "is_gating": false,
    "is_eligible_for_promotion": false
  },
  {
    "card_id": "9850f131-8e15-464b-827b-27344b915846",
    "ambiguity_class": "sla-binding",
    "slot_value_hash": "3030351468e6",
    "title": "Ingest Latency SLA Measurement Point Undefined",
    "detail": "The PRD does not define where the 100ms latency is measured — whether from bedside monitor transmission, WebSocket frame receipt, FHIR normalization completion, or event bus publish acknowledgment.",
    "prd_quote": "<100ms ingest latency",
    "prd_section": "SLA",
    "gap_description": "The PRD does not define where the 100ms latency is measured — whether from bedside monitor transmission, WebSocket frame receipt, FHIR normalization completion, or event bus publish acknowledgment.",
    "options": [
      {
        "label": "Measure from WebSocket Frame Receipt to Event Bus Publish ACK at P99",
        "resolution": "The <100ms latency SLA is defined as the P99 duration from WebSocket frame receipt at the API gateway to confirmed publish acknowledgment on the clinical event bus, excluding network transit from bedside monitor to gateway. Measured continuously via distributed tracing.",
        "rationale": "Measuring from the system boundary the team controls (WebSocket receipt) to the handoff point (event bus ACK) creates an accountable, instrumentable SLA; P99 is standard for clinical real-time systems per HL7 FHIR performance guidance.",
        "downstream_impact": "Architect will instrument trace spans at WebSocket receipt and event bus publish; CodeGen will add OpenTelemetry spans at both boundaries and configure P99 alerting thresholds.",
        "recommended": true
      },
      {
        "label": "Measure End-to-End from Monitor Transmission to Event Bus ACK",
        "resolution": "The <100ms latency SLA covers the full path from bedside monitor data transmission to event bus publish acknowledgment, including network transit, measured at P95.",
        "rationale": "End-to-end measurement better reflects clinical utility — a 100ms SLA that excludes network transit may still result in unacceptably delayed vitals reaching Cardiology consumers.",
        "downstream_impact": "Architect must account for network topology and vendor connector latency budgets; CodeGen will need timestamp injection at the monitor-side connector, increasing integration complexity with Philips/GE hardware.",
        "recommended": false
      }
    ],
    "team_occurrence_count": 0,
    "blast_radius_cost_usd": 150.0,
    "re_run_cost_usd": 0.0652,
    "is_gating": false,
    "is_eligible_for_promotion": false
  },
  {
    "card_id": "26f50b6d-8b64-45d2-b5c4-ac3c94654cc6",
    "ambiguity_class": "identifier-format",
    "slot_value_hash": "34c5d71295e7",
    "title": "FHIR Observation Resource Identifier Format Not Specified",
    "detail": "The PRD does not define the identifier scheme for FHIR Observation resources (e.g., UUID v4, OID-based, vendor-native ID passthrough), which affects deduplication, idempotency, and audit trail integrity.",
    "prd_quote": "HL7 FHIR Observation resources for heart rate, SpO2, blood pressure, temperature.",
    "prd_section": "In-scope",
    "gap_description": "The PRD does not define the identifier scheme for FHIR Observation resources (e.g., UUID v4, OID-based, vendor-native ID passthrough), which affects deduplication, idempotency, and audit trail integrity.",
    "options": [
      {
        "label": "System-Generated UUID v4 as Canonical Observation.id",
        "resolution": "All ingested FHIR Observation resources are assigned a system-generated UUID v4 as Observation.id at ingest time. Vendor-native device IDs are preserved in Observation.identifier with a vendor-specific system URI (e.g., 'urn:philips:intellivue:id'). This is the authoritative ID on the event bus.",
        "rationale": "UUID v4 ensures global uniqueness without vendor dependency; preserving vendor IDs in Observation.identifier maintains traceability per HL7 FHIR R4 §8.1.3 identifier guidance.",
        "downstream_impact": "Architect will design an ID generation layer at ingest normalization; CodeGen will implement UUID assignment and vendor ID mapping in the FHIR transformer, enabling idempotent event bus publishing.",
        "recommended": true
      },
      {
        "label": "Pass Through Vendor-Native Device ID as Observation.id",
        "resolution": "The vendor-supplied device observation ID is used directly as Observation.id, prefixed with a vendor namespace (e.g., 'philips-' or 'ge-') to avoid collisions.",
        "rationale": "Preserves end-to-end traceability from device to event bus without an additional ID generation step, reducing transformation complexity.",
        "downstream_impact": "CodeGen will implement namespace-prefixed passthrough logic; Architect must document collision risk if vendor IDs are not globally unique, and deduplication logic becomes vendor-specific.",
        "recommended": false
      }
    ],
    "team_occurrence_count": 0,
    "blast_radius_cost_usd": 100.0,
    "re_run_cost_usd": 0.0652,
    "is_gating": false,
    "is_eligible_for_promotion": false
  }
] as const;

export const VITALS_DECISIONS = [
  {
    "card_id": "3e38807e-a9b4-4a71-8364-055907dab944",
    "decision_kind": "accept",
    "resolution_text": "Each vendor connector must authenticate via mutual TLS (client certificate issued by internal PKI) combined with OAuth 2.0 client_credentials grant scoped to read:vitals only. Credentials must be rotated every 90 days and reviewed by Security Architecture before activation.",
    "option_index": 0,
    "gate": null,
    "actor": "experiment@local",
    "confidence_source": "human"
  },
  {
    "card_id": "01e02d86-10dd-4bc9-8358-d9c3dfd3cf8d",
    "decision_kind": "accept",
    "resolution_text": "At egress, strip or tokenize all 18 HIPAA Safe Harbor identifiers present in FHIR Observation resources, including subject.reference (replace with internal pseudonym token), performer, and any contained Patient resource. A field-level redaction manifest must be approved by the Privacy Office before launch.",
    "option_index": 0,
    "gate": null,
    "actor": "experiment@local",
    "confidence_source": "human"
  },
  {
    "card_id": "5952e4fa-87ce-4d93-ba83-dc70256bb0ae",
    "decision_kind": "swap",
    "resolution_text": "99.95% monthly uptime; <100ms p95 ingest latency measured at the WebSocket boundary, excluding upstream vendor latency.",
    "option_index": null,
    "gate": null,
    "actor": "experiment@local",
    "confidence_source": "human"
  },
  {
    "card_id": "7961407e-14a2-4ed3-ad8f-cff8df970c0e",
    "decision_kind": "accept",
    "resolution_text": "Before Q3 FY26 launch, the Privacy Office must produce and sign off on a field-level allowlist specifying exactly which FHIR Observation elements (e.g., valueQuantity, effectiveDateTime, code) the Cardiology event bus consumer may receive. The API enforces this allowlist as a projection filter at egress.",
    "option_index": 0,
    "gate": null,
    "actor": "experiment@local",
    "confidence_source": "human"
  },
  {
    "card_id": "77fb03a9-da88-4aff-b1fc-c6bd3fd34682",
    "decision_kind": "accept",
    "resolution_text": "WebSocket connections (both inbound from monitors and outbound to Cardiology consumer) must present a signed JWT (RS256) in the HTTP Upgrade request Authorization header. Tokens have a 15-minute TTL and are issued by the internal identity provider. Connections are terminated on token expiry and must re-authenticate.",
    "option_index": 0,
    "gate": null,
    "actor": "experiment@local",
    "confidence_source": "human"
  }
] as const;

export const VITALS_LEDGER = [
  {
    "id": "85ab1832-8f83-4a96-8ca5-b99c261c52a2",
    "team_id": "experiment-phase-a-run-1",
    "run_id": "f6880b34-ad6b-47a8-80df-5769d84bda19",
    "card_id": "3e38807e-a9b4-4a71-8364-055907dab944",
    "ambiguity_class": "auth-policy",
    "slot_value_hash": "61f002960993",
    "resolution_text": "Each vendor connector must authenticate via mutual TLS (client certificate issued by internal PKI) combined with OAuth 2.0 client_credentials grant scoped to read:vitals only. Credentials must be rotated every 90 days and reviewed by Security Architecture before activation.",
    "decision_kind": "accept",
    "status": "suggest",
    "sample_count": 1,
    "accuracy_score": 0.0,
    "created_at": "2026-06-07T05:57:34.123889+00:00",
    "created_by": "experiment@local",
    "precedent_id": null,
    "confidence_source": "human"
  },
  {
    "id": "1dcb0070-2d60-4201-90d7-af01bb296dac",
    "team_id": "experiment-phase-a-run-1",
    "run_id": "f6880b34-ad6b-47a8-80df-5769d84bda19",
    "card_id": "01e02d86-10dd-4bc9-8358-d9c3dfd3cf8d",
    "ambiguity_class": "phi-classification",
    "slot_value_hash": "6fc5f766f52e",
    "resolution_text": "At egress, strip or tokenize all 18 HIPAA Safe Harbor identifiers present in FHIR Observation resources, including subject.reference (replace with internal pseudonym token), performer, and any contained Patient resource. A field-level redaction manifest must be approved by the Privacy Office before launch.",
    "decision_kind": "accept",
    "status": "suggest",
    "sample_count": 1,
    "accuracy_score": 0.0,
    "created_at": "2026-06-07T05:57:34.124573+00:00",
    "created_by": "experiment@local",
    "precedent_id": null,
    "confidence_source": "human"
  },
  {
    "id": "986a885a-cc9e-484a-9094-80b353d810a2",
    "team_id": "experiment-phase-a-run-1",
    "run_id": "f6880b34-ad6b-47a8-80df-5769d84bda19",
    "card_id": "5952e4fa-87ce-4d93-ba83-dc70256bb0ae",
    "ambiguity_class": "data-retention",
    "slot_value_hash": "c59873c2ca91",
    "resolution_text": "99.95% monthly uptime; <100ms p95 ingest latency measured at the WebSocket boundary, excluding upstream vendor latency.",
    "decision_kind": "swap",
    "status": "suggest",
    "sample_count": 1,
    "accuracy_score": 0.0,
    "created_at": "2026-06-07T05:57:34.129436+00:00",
    "created_by": "experiment@local",
    "precedent_id": null,
    "confidence_source": "human"
  },
  {
    "id": "1f8ea318-c379-4329-add3-b8ff04027d45",
    "team_id": "experiment-phase-a-run-1",
    "run_id": "f6880b34-ad6b-47a8-80df-5769d84bda19",
    "card_id": "7961407e-14a2-4ed3-ad8f-cff8df970c0e",
    "ambiguity_class": "phi-classification",
    "slot_value_hash": "6f5399a309f4",
    "resolution_text": "Before Q3 FY26 launch, the Privacy Office must produce and sign off on a field-level allowlist specifying exactly which FHIR Observation elements (e.g., valueQuantity, effectiveDateTime, code) the Cardiology event bus consumer may receive. The API enforces this allowlist as a projection filter at egress.",
    "decision_kind": "accept",
    "status": "suggest",
    "sample_count": 1,
    "accuracy_score": 0.0,
    "created_at": "2026-06-07T05:57:34.137657+00:00",
    "created_by": "experiment@local",
    "precedent_id": null,
    "confidence_source": "human"
  },
  {
    "id": "e39ea8fd-24c8-452e-b46e-246d74dfdc24",
    "team_id": "experiment-phase-a-run-1",
    "run_id": "f6880b34-ad6b-47a8-80df-5769d84bda19",
    "card_id": "77fb03a9-da88-4aff-b1fc-c6bd3fd34682",
    "ambiguity_class": "auth-policy",
    "slot_value_hash": "4908dab38c8c",
    "resolution_text": "WebSocket connections (both inbound from monitors and outbound to Cardiology consumer) must present a signed JWT (RS256) in the HTTP Upgrade request Authorization header. Tokens have a 15-minute TTL and are issued by the internal identity provider. Connections are terminated on token expiry and must re-authenticate.",
    "decision_kind": "accept",
    "status": "suggest",
    "sample_count": 1,
    "accuracy_score": 0.0,
    "created_at": "2026-06-07T05:57:34.143105+00:00",
    "created_by": "experiment@local",
    "precedent_id": null,
    "confidence_source": "human"
  },
  {
    // --- Teaching-loop cluster (demo of the closed loop) -------------------
    // A LATER run (phase-a-run-2) hits the SAME data-retention ambiguity
    // (slot c59873c2ca91) that the human SWAPPED above (5952e4fa). findPrecedent
    // returns that human resolution → autopilot AUTO-RESOLVES instead of gating.
    // This is what lights up the "taught · reused 1×" + "auto · from precedent"
    // lineage badges and the non-zero "Autonomy earned" KPI on /decisions.
    "id": "b1ee77a0-2c41-4d58-9f0a-7d2b6c9a1f30",
    "team_id": "experiment-phase-a-run-1",
    "run_id": "9d2a4f17-66b1-4e0c-9a3e-2f1c8e54aa02",
    "card_id": "c0ffee11-2222-4333-8444-555566667777",
    "ambiguity_class": "data-retention",
    "slot_value_hash": "c59873c2ca91",
    "resolution_text": "99.95% monthly uptime; <100ms p95 ingest latency measured at the WebSocket boundary, excluding upstream vendor latency.",
    "decision_kind": "accept",
    "status": "suggest",
    "sample_count": 1,
    "accuracy_score": 0.0,
    "created_at": "2026-06-09T14:12:08.500000+00:00",
    "created_by": "autopilot:experiment-phase-a-run-1",
    "precedent_id": "986a885a-cc9e-484a-9094-80b353d810a2",
    "confidence_source": "autopilot"
  }
] as const;

export const VITALS_ARCHITECTURE_MD = "# Solution Architecture: Vendor Vitals Ingest Platform\n\n## Components & Data Flow\n\n- **Vendor Connector Gateway (VCG):** Terminates all inbound vendor connections. Enforces dual-layer auth — mTLS certificate validation (vendor-issued, 90-day rotation, catalog-checked) AND OAuth 2.0 client-credentials token scoped to `vitals:ingest` before any data is accepted. *(Decision: mTLS + OAuth dual-auth)*\n\n- **WebSocket Ingest Layer:** Accepts FHIR Observation streams over WebSocket. Validates RS256 JWT (15-min expiry) on HTTP Upgrade; enforces sub-protocol token refresh heartbeat; hard-terminates connections where token has been expired >30 seconds without refresh. Latency SLO of <100ms p95 is measured at this boundary via embedded timing middleware. *(Decisions: WebSocket JWT auth; p95 latency SLO)*\n\n- **Service Catalog & Certificate Registry:** Authoritative store of registered vendor certificates and OAuth client IDs. VCG performs a synchronous catalog lookup at connection establishment; unregistered certificates are rejected before TLS handshake completes. Rotation expiry triggers automated alerts at T-14 days. *(Decision: mTLS + catalog registration)*\n\n- **PHI Redaction Pipeline:** Inline, pre-egress tokenization service. Applies HMAC-SHA256 pseudonymization to `subject.reference`, `performer`, `encounter.reference`, and `device.identifier`. Runs a full 18-identifier Safe Harbor scan across every FHIR Observation field using a policy engine backed by the canonical data dictionary. Redaction is synchronous and blocking — no data exits without a redaction receipt. *(Decision: canonical redaction manifest)*\n\n- **Canonical Data Dictionary Service:** Versioned registry documenting every FHIR Observation field, its Safe Harbor evaluation result, and tokenization disposition. Updated on schema change via CI gate; serves as the compliance audit artifact. *(Decision: redaction manifest / HIPAA §164.514(b)(2))*\n\n- **Downstream FHIR Store / Event Bus:** Receives only post-redaction, tokenized Observations. Separated from the ingest path by the redaction pipeline to enforce a hard PHI boundary. Internal consumers subscribe via the event bus; no raw PHI traverses this segment. *(Decision: redaction manifest egress rule)*\n\n## Security & PHI Handling\n\n- **Zero-Trust Auth Chain:** Every inbound connection must satisfy mTLS + OAuth token + JWT in strict sequence. Failure at any layer drops the connection with a structured error log (no PHI in error payloads). HMAC keys for pseudonymization are stored in a dedicated HSM-backed secrets manager, rotated independently of certificates. *(Decisions: mTLS/OAuth; WebSocket JWT)*\n\n- **Token Refresh Enforcement:** Server-side refresh watchdog runs per-connection; emits a `token_expiry_warning` sub-protocol message at T-60 seconds; escalates to connection termination at T+30 seconds post-expiry. State is tracked in an in-memory session store (Redis with TTL) co-located with the WebSocket layer to avoid cross-service latency. *(Decision: WebSocket JWT refresh)*\n\n## Scale Assumptions\n\n- **Ingest Layer Sizing:** Horizontally scaled WebSocket pods behind a Layer-4 load balancer (sticky sessions per vendor connection). Autoscaling triggered at 70% CPU/connection saturation. Redaction pipeline scales independently as a sidecar-adjacent service to keep the ingest-to-redaction hop sub-millisecond and protect the p95 budget. *(Decision: <100ms p95 at WebSocket boundary)*\n\n## Observability & SLO Enforcement\n\n- **SLO Instrumentation:** Rolling 30-day uptime window tracked via synthetic probes (1-minute interval) and real-user WebSocket connection success rates. Prometheus + Grafana dashboards surface error budget burn rate in real time. Planned maintenance is flagged in a maintenance calendar API; probe results during pre-announced windows (≥72h notice, ≤60 min/month) are excluded from SLO calculation automatically. *(Decision: 99.95% uptime definition)*\n\n- **Automated Incident Response:** A burn-rate alert fires at 2× budget consumption rate (fast-burn) and 5% budget consumed in 1 hour (slow-burn), both routing to PagerDuty as P1. Runbooks are linked directly in the alert payload. Certificate expiry, failed catalog lookups, and redaction pipeline failures each have dedicated alert channels to prevent P1 noise conflation. *(Decision: 99.95% uptime; PagerDuty P1 trigger)*";

export const VITALS_TEST_PLAN_MD = "## Test 1: mTLS + OAuth 2.0 client_credentials Scope Enforcement on Vendor Connector\n\n**Verifies decision:** \"Each vendor connector must authenticate via mutual TLS (client certificate issued by internal PKI) combined with OAuth 2.0 client_credentials grant scoped to read:vitals only.\"\n\n**Given** a Vendor Connector pod is running with a valid internal PKI client certificate and an OAuth 2.0 token issued with the `read:vitals` scope\n\n**When** a vendor monitor attempts to open a connection to the Vendor Connector Layer presenting (a) a valid PKI cert + `read:vitals` token, (b) a valid PKI cert + a token scoped to `write:vitals`, and (c) no client certificate at all\n\n**Then** case (a) is accepted and data flows to the WebSocket Ingest Gateway; case (b) is rejected at the OAuth scope validation step with a logged authorization failure citing scope mismatch; case (c) is rejected at the TLS handshake layer before any OAuth exchange occurs — the connector pod emits a structured log entry with `auth_failure_reason: missing_client_cert` and no FHIR payload reaches the Raw FHIR Observation Buffer\n\n---\n\n## Test 2: 90-Day Credential Rotation Gate Blocks Expired Vendor Credentials\n\n**Verifies decision:** \"Credentials must be rotated every 90 days and reviewed by Security Architecture before activation.\"\n\n**Given** a Vendor Connector pod whose internal PKI client certificate has a `notAfter` timestamp exactly 91 days in the past, and the credential rotation job has not issued a replacement approved by Security Architecture\n\n**When** the vendor monitor attempts to initiate a mutual TLS handshake with the Vendor Connector Layer using the expired certificate\n\n**Then** the TLS handshake is rejected; the credential rotation job emits a metric `vendor_cert_expired_total{vendor=<name>}` incremented by 1; no OAuth token exchange is attempted; and the connector pod logs a `SECURITY_GATE: cert_expired` event traceable to the Security Architecture review queue\n\n---\n\n## Test 3: RS256 JWT Validation and 15-Minute TTL Enforcement at WebSocket Ingest Gateway\n\n**Verifies decision:** \"WebSocket connections (both inbound from monitors and outbound to Cardiology consumer) must present a signed JWT (RS256) in the HTTP Upgrade request Authorization header. Tokens have a 15-minute TTL and are issued by the internal identity provider. Connections are terminated on token expiry and must re-authenticate.\"\n\n**Given** the WebSocket Ingest Gateway is running and the internal identity provider has issued an RS256-signed JWT with a 15-minute TTL\n\n**When** (a) a vendor monitor sends an HTTP Upgrade request with a valid RS256 JWT in the `Authorization` header, (b) a monitor sends an Upgrade request with a token signed using HS256, and (c) an established WebSocket connection's JWT TTL elapses (simulated by advancing clock past `exp` claim)\n\n**Then** case (a) upgrades successfully and data ingestion begins; case (b) is rejected at the Upgrade step — the gateway returns a `401` with body citing `invalid_token_algorithm` and no WebSocket session is created; case (c) results in the gateway tearing down the active WebSocket connection within one TTL-check interval, emitting a `ws_session_terminated_reason: token_expired` log entry, and requiring the client to present a fresh JWT before reconnection is accepted\n\n---\n\n## Test 4: p95 Ingest Latency SLO Measured at WebSocket Ingest Gateway Boundary\n\n**Verifies decision:** \"99.95% monthly uptime; <100ms p95 ingest latency measured at the WebSocket boundary, excluding upstream vendor latency.\"\n\n**Given** the WebSocket Ingest Gateway is instrumented with a latency histogram metric `ingest_latency_ms` timestamped at the moment a FHIR Observation frame is received at the WebSocket boundary (not at the vendor-side origination timestamp)\n\n**When** a sustained load of representative FHIR Observation messages is injected directly into the WebSocket Ingest Gateway at production-representative throughput for a 10-minute window, with upstream vendor jitter stripped from measurement by using gateway-local receipt timestamps\n\n**Then** the p95 value of `ingest_latency_ms` is below 100 ms; any breach causes an alert `slo_ingest_p95_breach` to fire; the measurement explicitly excludes the delta between vendor origination time and gateway receipt time, confirmed by comparing the two timestamp fields in the metric labels\n\n---\n\n## Test 5: HIPAA Safe Harbor PHI Redaction of All 18 Identifiers at Egress\n\n**Verifies decision:** \"At egress, strip or tokenize all 18 HIPAA Safe Harbor identifiers present in FHIR Observation resources, including subject.reference (replace with internal pseudonym token), performer, and any contained Patient resource.\"\n\n**Given** the Raw FHIR Observation Buffer contains a FHIR Observation resource with all 18 Safe Harbor identifiers populated, including `subject.reference` set to a real patient MRN URI, a `performer` array with a named practitioner reference, and a `contained` Patient resource with name, DOB, and address\n\n**When** the PHI Redaction / Tokenization Service consumes the record and produces the egress-safe payload\n\n**Then** `subject.reference` is replaced with an internal pseudonym token matching the format defined in the redaction manifest; `performer` is either stripped or tokenized per the manifest; the `contained` Patient resource is absent from the egress payload; no raw MRN, name, DOB, geographic data, or other Safe Harbor identifier appears in plaintext; and the service emits a `redaction_manifest_version` label on each processed record so auditors can confirm the Privacy Office-approved manifest version was applied\n\n---\n\n## Test 6: Cardiology Event Bus Allowlist Projection Filter Enforced at Egress\n\n**Verifies decision:** \"The API enforces this allowlist as a projection filter at egress. The Privacy Office must produce and sign off on a field-level allowlist specifying exactly which FHIR Observation elements (e.g., valueQuantity, effectiveDateTime, code) the Cardiolo";

export const VITALS_CODE_PY = "\n```python\n\"\"\"\nvendor_vitals_ingest.py\n\nContract tests for Vendor Vitals Ingest & Cardiology Event Bus.\nCovers:\n  - Test 1: mTLS + OAuth 2.0 client_credentials scope enforcement\n  - Test 2: 90-day credential rotation gate\n  - Test 3: RS256 JWT validation (WebSocket Ingest Gateway)\n\"\"\"\n\nfrom __future__ import annotations\n\nimport base64\nimport datetime\nimport hashlib\nimport json\nimport logging\nimport time\nfrom dataclasses import dataclass, field\nfrom typing import Any, Dict, List, Optional, Tuple\n\nimport pytest\n\n# ---------------------------------------------------------------------------\n# Logging\n# ---------------------------------------------------------------------------\nlogging.basicConfig(level=logging.DEBUG)\nlogger = logging.getLogger(\"vendor_vitals_ingest\")\n\n\n# ---------------------------------------------------------------------------\n# Minimal RSA / JWT helpers (pure-Python, no external crypto deps required\n# for the contract test harness — uses stdlib hmac/hashlib stubs so the\n# tests can run without cryptography installed; real production code would\n# use `cryptography` or `PyJWT`).\n# ---------------------------------------------------------------------------\n\ndef _b64url_encode(data: bytes) -> str:\n    return base64.urlsafe_b64encode(data).rstrip(b\"=\").decode()\n\n\ndef _b64url_decode(s: str) -> bytes:\n    padding = 4 - len(s) % 4\n    if padding != 4:\n        s += \"=\" * padding\n    return base64.urlsafe_b64decode(s)\n\n\nclass _FakeRSA256Signer:\n    \"\"\"\n    Deterministic fake RS256 signer for testing.\n    Signs with HMAC-SHA256 keyed on a secret so tests can verify\n    without a real RSA key pair.\n    \"\"\"\n\n    def __init__(self, secret: str = \"test-rsa-secret\") -> None:\n        self._secret = secret.encode()\n\n    def sign(self, message: bytes) -> bytes:\n        import hmac\n        return hmac.new(self._secret, message, hashlib.sha256).digest()\n\n    def verify(self, message: bytes, signature: bytes) -> bool:\n        import hmac\n        expected = self.sign(message)\n        return hmac.compare_digest(expected, signature)\n\n\n_DEFAULT_SIGNER = _FakeRSA256Signer()\n\n\ndef create_jwt(\n    payload: Dict[str, Any],\n    signer: _FakeRSA256Signer = _DEFAULT_SIGNER,\n    algorithm: str = \"RS256\",\n) -> str:\n    header = {\"alg\": algorithm, \"typ\": \"JWT\"}\n    header_b64 = _b64url_encode(json.dumps(header).encode())\n    payload_b64 = _b64url_encode(json.dumps(payload).encode())\n    signing_input = f\"{header_b64}.{payload_b64}\".encode()\n    signature = signer.sign(signing_input)\n    return f\"{header_b64}.{payload_b64}.{_b64url_encode(signature)}\"\n\n\ndef decode_jwt(\n    token: str,\n    signer: _FakeRSA256Signer = _DEFAULT_SIGNER,\n    verify_signature: bool = True,\n) -> Dict[str, Any]:\n    \"\"\"\n    Decode and optionally verify a JWT.\n\n    Raises:\n        ValueError: on malformed token, bad signature, or expiry.\n    \"\"\"\n    parts = token.split(\".\")\n    if len(parts) != 3:\n        raise ValueError(\"Malformed JWT: expected 3 parts\")\n\n    header_b64, payload_b64, sig_b64 = parts\n    header = json.loads(_b64url_decode(header_b64))\n    payload = json.loads(_b64url_decode(payload_b64))\n\n    if verify_signature:\n        signing_input = f\"{header_b64}.{payload_b64}\".encode()\n        signature = _b64url_decode(sig_b64)\n        if not signer.verify(signing_input, signature):\n            raise ValueError(\"JWT signature verification failed\")\n\n    now = time.time()\n    if \"exp\" in payload and payload[\"exp\"] < now:\n        raise ValueError(f\"JWT expired at {payload['exp']}\")\n    if \"nbf\" in payload and payload[\"nbf\"] > now:\n        raise ValueError(f\"JWT not yet valid (nbf={payload['nbf']})\")\n\n    return payload\n\n\n# ---------------------------------------------------------------------------\n# Domain models\n# ---------------------------------------------------------------------------\n\n@dataclass\nclass ClientCertificate:\n    \"\"\"Represents an internal PKI client certificate.\"\"\"\n    vendor_name: str\n    not_before: datetime.datetime\n    not_after: datetime.datetime";

export const VITALS_DECISIONS_MD = "# Decisions for run f6880b34-ad6b-47a8-80df-5769d84bda19\nTeam: experiment-phase-a-run-1\n\n- **3e38807e** accept: Each vendor connector must authenticate via mutual TLS (client certificate issued by internal PKI) combined with OAuth 2.0 client_credentials grant scoped to read:vitals only. Credentials must be rotated every 90 days and reviewed by Security Architecture before activation.\n- **01e02d86** accept: At egress, strip or tokenize all 18 HIPAA Safe Harbor identifiers present in FHIR Observation resources, including subject.reference (replace with internal pseudonym token), performer, and any contained Patient resource. A field-level redaction manifest must be approved by the Privacy Office before launch.\n- **5952e4fa** swap: 99.95% monthly uptime; <100ms p95 ingest latency measured at the WebSocket boundary, excluding upstream vendor latency.\n- **7961407e** accept: Before Q3 FY26 launch, the Privacy Office must produce and sign off on a field-level allowlist specifying exactly which FHIR Observation elements (e.g., valueQuantity, effectiveDateTime, code) the Cardiology event bus consumer may receive. The API enforces this allowlist as a projection filter at egress.\n- **77fb03a9** accept: WebSocket connections (both inbound from monitors and outbound to Cardiology consumer) must present a signed JWT (RS256) in the HTTP Upgrade request Authorization header. Tokens have a 15-minute TTL and are issued by the internal identity provider. Connections are terminated on token expiry and must re-authenticate.";

export const VITALS_SUMMARY = {
  "phase": "A",
  "run_idx": 1,
  "run_id": "f6880b34-ad6b-47a8-80df-5769d84bda19",
  "team_id": "experiment-phase-a-run-1",
  "started_at": "2026-06-07T05:59:54.308586+00:00",
  "wall_clock_seconds": 212.82,
  "stage_durations_seconds": {
    "ingest": 0.1,
    "assessor": 72.54,
    "architect": 23.55,
    "test_plan": 38.94,
    "codegen": 76.83,
    "review_scan": 0.2,
    "deliver": 0.01
  },
  "total_tokens": 18957,
  "total_cost_usd": 0.246,
  "card_count": 8,
  "gating_card_count": 5,
  "decisions_applied": 5,
  "model_routing": {
    "ingest": "databricks-claude-sonnet-4-6",
    "assessor": "databricks-claude-sonnet-4-6",
    "architect": "databricks-claude-sonnet-4-6",
    "test_plan": "databricks-claude-sonnet-4-6",
    "codegen": "databricks-claude-sonnet-4-6",
    "review_scan": "databricks-claude-sonnet-4-6"
  }
} as const;
