=== PROPOSAL ===
# Real-Time Vitals Ingest Pipeline: Privacy, Security, and SLA Hardening

## Why
The PRD requires a compliant, low-latency vitals ingest pipeline that protects patient identity under HIPAA Safe Harbor, enforces vendor authentication, and delivers measurable uptime and latency guarantees to downstream clinical consumers. Without these changes, the system cannot be approved for production use by the Privacy Office or Vendor Management, and SLA commitments remain untestable.

## What Changes
- Introduce a deterministic HMAC-SHA256 pseudonymization transform at egress that replaces FHIR Observation subject and encounter references and removes all 18 HIPAA Safe Harbor identifiers, keyed by a Privacy-office-managed secret
- Require mutual TLS plus short-lived OAuth 2.0 client_credentials tokens scoped to `vitals:ingest` for all third-party vendor connectors (Philips IntelliVue, GE CARESCAPE), with signed BAA and Vendor Management approval as onboarding prerequisites
- Enforce 99.95% monthly uptime and p99 <100ms ingest latency measured from WebSocket frame receipt at the API gateway to broker publish acknowledgment, captured in the observability dashboard and monthly SLA reports
- Restrict Cardiology consumer access to a dedicated event bus topic containing only the minimum-necessary field set, enforced via topic-level ACL and a pre-launch Data Use Agreement

## Capabilities
### New Capabilities
- `hipaa-safe-harbor-pseudonymization`: Deterministic HMAC-SHA256 egress transform that pseudonymizes FHIR subject/encounter references and removes all 18 HIPAA Safe Harbor identifiers before publishing to the clinical event bus

## Impact
- Affected components: API Gateway (WebSocket boundary), Vitals Ingest Service, Egress Transform Layer, Clinical Event Bus (topic ACLs), Vendor Connector Onboarding, Observability Dashboard, SLA Reporting Pipeline
- Migration: Existing vendor connectors must be re-onboarded with mTLS certificates and new OAuth client credentials; Cardiology consumer must migrate to the restricted topic; Privacy Office must approve field inventory before launch

=== DESIGN ===
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

=== SPEC ===
## ADDED Requirements

### Requirement: HIPAA Safe Harbor Egress Pseudonymization
The system MUST replace FHIR Observation.subject.reference and Observation.encounter.reference with a deterministic HMAC-SHA256 pseudonym keyed by the Privacy-office-managed secret, and MUST remove or pseudonymize all 18 HIPAA Safe Harbor identifiers (45 CFR §164.514(b)(2)) present in any resource before publishing to the clinical event bus. [decision: bfb13536]

#### Scenario: Subject and encounter references are pseudonymized at egress
- **WHEN** a FHIR Observation resource containing a raw patient subject reference and encounter reference is processed by the egress transform
- **THEN** the published event contains HMAC-SHA256 pseudonyms in place of both references, and no raw patient or encounter identifiers are present in the published payload

#### Scenario: All 18 HIPAA Safe Harbor identifiers are absent from published events
- **WHEN** an inbound FHIR Observation contains any of the 18 HIPAA Safe Harbor identifier fields (e.g., name, address, date of birth, phone number, geographic subdivisions smaller than state)
- **THEN** the egress transform removes or pseudonymizes every such field before the event is published, and a post-transform audit log entry records which field categories were acted upon

---

### Requirement: Vendor Connector Mutual TLS and OAuth Authentication
The system MUST require all third-party vendor connectors (Philips IntelliVue, GE CARESCAPE) to authenticate via mutual TLS for transport-layer identity and MUST present a valid short-lived OAuth 2.0 client_credentials token scoped to `vitals:ingest` on every ingest session; credential issuance SHALL be blocked until a signed BAA and a Vendor Management approval ticket are on record. [decision: 16709c4d]

#### Scenario: Connector without valid mTLS certificate is rejected
- **WHEN** a vendor connector attempts to establish a WebSocket ingest session without presenting a valid mTLS client certificate signed by the approved CA
- **THEN** the API gateway terminates the TLS handshake with a certificate-required alert and logs the rejection event; no data is accepted

#### Scenario: Connector without valid vitals:ingest scoped token is rejected
- **WHEN** a vendor connector presents a valid mTLS certificate but provides an OAuth 2.0 token that is expired, missing, or lacks the `vitals:ingest` scope
- **THEN** the ingest service returns HTTP 401 Unauthorized, closes the WebSocket connection, and emits a security audit log entry identifying the connector and failure reason

#### Scenario: Credential issuance blocked without BAA and Vendor Management ticket
- **WHEN** a new vendor connector onboarding request is submitted without a signed BAA or without a resolved Vendor Management approval ticket
- **THEN** the credential issuance workflow rejects the request, records the blocking reason, and does not generate mTLS certificates or OAuth client credentials

---

### Requirement: Ingest Pipeline Uptime and Latency SLA
The system MUST achieve 99.95% monthly uptime and MUST deliver p99 ingest latency of less than 100 milliseconds, measured from WebSocket frame receipt at the API gateway to confirmed publish acknowledgment from the clinical event bus broker, excluding vendor-side network transit. [decision: c46cef1f]

#### Scenario: p99 latency is within SLA under normal load
- **WHEN** the ingest pipeline is operating under normal production load
- **THEN** the p99 latency from WebSocket frame receipt at the API gateway to broker publish acknowledgment is less than 100 milliseconds, as recorded in the observability dashboard

#### Scenario: Monthly uptime meets 99.95% threshold
- **WHEN** the monthly SLA report is generated
- **THEN** the calculated uptime percentage for the ingest pipeline is at or above 99.95%, computed from availability metrics captured at the WebSocket boundary

---

### Requirement: Ingest Latency Observability and SLA Reporting
The system MUST capture the p99 ingest latency metric — defined as elapsed time from WebSocket frame receipt at the API gateway to confirmed broker publish acknowledgment — in the observability dashboard and MUST include this metric in monthly SLA reports. [decision: 3c0d577b]

#### Scenario: p99 latency metric is visible in the observability dashboard
- **WHEN** an operator opens the observability dashboard during or after an ingest session
- **THEN** the dashboard displays the current and historical p99 latency values measured at the WebSocket-to-broker boundary, with per-minute granularity at minimum

#### Scenario: Monthly SLA report includes p99 latency measurement
- **WHEN** the automated monthly SLA report is generated
- **THEN** the report contains a section showing the p99 ingest latency distribution for the reporting period, the measurement point definition, and a pass/fail indicator against the 100ms threshold

---

### Requirement: Cardiology Consumer Minimum-Necessary Topic Access
The system MUST grant the Cardiology consumer read access only to a dedicated event bus topic containing the minimum-necessary field set (vital-sign code, value, unit, effectiveDateTime, pseudonymized subject ID), and MUST enforce this restriction via topic-level ACL; access SHALL NOT be provisioned until a Data Use Agreement signed by Cardiology engineering and the Privacy Office is on record. [decision: b438868f]

#### Scenario: Cardiology consumer cannot read non-minimum-necessary fields
- **WHEN** the Cardiology consumer subscribes to the dedicated vitals topic
- **THEN** each event delivered contains only vital-sign code, value, unit, effectiveDateTime, and pseudonymized subject ID; all other FHIR Observation fields are absent from the topic payload

#### Scenario: Cardiology consumer is denied access to unrestricted topics
- **WHEN** the Cardiology consumer's service identity attempts to subscribe to any event bus topic other than its designated minimum-necessary vitals topic
- **THEN** the broker rejects the subscription with an authorization error and emits an access-denied audit log entry

#### Scenario: Access provisioning blocked without signed DUA
- **WHEN** a request is made to provision Cardiology consumer credentials or topic ACL entries before a signed Data Use Agreement is recorded
- **THEN** the provisioning workflow rejects the request and records the missing DUA as the blocking reason; no ACL entries are created