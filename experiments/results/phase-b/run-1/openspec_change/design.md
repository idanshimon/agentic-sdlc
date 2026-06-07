# Design

## Context
The vitals ingest pipeline receives real-time physiological data from bedside monitors (Philips IntelliVue, GE CARESCAPE) over WebSocket connections at the API gateway, transforms and publishes events to a clinical event bus, and fans out to downstream consumers including Cardiology. The pipeline handles Protected Health Information (PHI) and must comply with HIPAA Safe Harbor de-identification standards before any data leaves the ingest boundary. Current connectors lack standardized authentication, egress data contains raw patient identifiers, and latency and uptime SLAs are neither formally defined nor instrumented. These gaps block Privacy Office and Vendor Management approval for production launch.

## Goals
- Remove or pseudonymize all 18 HIPAA Safe Harbor identifiers at egress using a deterministic HMAC-SHA256 transform keyed by a Privacy-office-managed secret
- Enforce mTLS + OAuth 2.0 client_credentials (`vitals:ingest` scope) for all vendor connectors, with BAA and Vendor Management ticket as hard onboarding gates
- Achieve and measure 99.95% monthly uptime and p99 <100ms ingest latency from WebSocket frame receipt to broker publish acknowledgment
- Restrict Cardiology (and future) consumers to minimum-necessary fields via topic-level ACL and a signed Data Use Agreement

## Non-Goals
- Re-identification or reversal of pseudonyms at the ingest layer (key management and reversal is a Privacy Office concern)
- Support for vendor connectors beyond Philips IntelliVue and GE CARESCAPE in this change
- End-to-end latency SLA covering vendor-side network transit
- Defining the DUA template or BAA template content (owned by Legal/Privacy Office)

## Decisions
1. Egress pseudonymization via HMAC-SHA256 on subject/encounter references and removal of all 18 HIPAA Safe Harbor identifiers, with Privacy Office field-inventory approval before launch — [card_id: bfb13536]
2. Vendor connectors must authenticate with mTLS for transport identity and present a short-lived OAuth 2.0 client_credentials token scoped to `vitals:ingest`; signed BAA and Vendor Management approval ticket are prerequisites for credential issuance — [card_id: 16709c4d]
3. SLA targets set at 99.95% monthly uptime and p99 <100ms ingest latency measured at the WebSocket-to-broker boundary, excluding upstream vendor latency — [card_id: c46cef1f]
4. Cardiology consumer receives read-only access to a dedicated minimum-necessary topic (vital-sign code, value, unit, effectiveDateTime, pseudonymized subject ID) enforced by topic-level ACL; future consumers require separate DUA and Privacy Office review — [card_id: b438868f]
5. The p99 <100ms measurement point is defined as WebSocket frame receipt at the API gateway to confirmed broker publish acknowledgment; this metric MUST appear in the observability dashboard and monthly SLA reports — [card_id: 3c0d577b]

## Risks / Trade-offs
- **Risk**: HMAC key compromise exposes pseudonym linkability across all records — **Mitigation**: Key is managed exclusively by the Privacy Office with rotation policy and HSM storage; ingest service accesses key only via a secrets manager API
- **Risk**: mTLS certificate expiry causes vendor connector outages — **Mitigation**: Automated certificate rotation with alerting at 30-day and 7-day expiry thresholds; runbook required before launch
- **Risk**: p99 <100ms target may be breached under burst load — **Mitigation**: Load-test at 2× peak expected throughput before launch; autoscaling policy on ingest service tied to WebSocket connection count and broker lag
- **Risk**: Topic-level ACL misconfiguration could expose non-minimum-necessary fields to Cardiology — **Mitigation**: ACL configuration is code-reviewed and validated against the DUA field enumeration in CI before deployment