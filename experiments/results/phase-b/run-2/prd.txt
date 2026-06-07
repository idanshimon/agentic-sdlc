# Patient Vitals Streaming API — Sample PRD

**Title:** Patient Vitals Streaming API

**Goal:** Ingest patient vital signs from bedside monitors, forward normalized
events to a clinical event bus. Cardiology team owns the consumer.

**In-scope:** HL7 FHIR Observation resources for heart rate, SpO2, blood
pressure, temperature. WebSocket transport.

**Out-of-scope:** ICU workflows, predictive analytics, alert routing.

**Compliance:** PHI in transit. HIPAA minimum-necessary. PII redaction at egress.

**SLA:** <100ms ingest latency, 99.95% uptime.

**External integrations:** Ingest may need to consume vitals from third-party
SaaS bedside-monitoring vendors (Philips IntelliVue, GE CARESCAPE).
Authorization model and egress policy for vendor connectors are TBD — some
teams have been connecting to unapproved external tools without formal review.

**Stakeholders:**
- Cardiology engineering team (consumer)
- Privacy office (review)
- Security architecture (review)
- Vendor management (egress policy)

**Estimated launch:** Q3 FY26.
