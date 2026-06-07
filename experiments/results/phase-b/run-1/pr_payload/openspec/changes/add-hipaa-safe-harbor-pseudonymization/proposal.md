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