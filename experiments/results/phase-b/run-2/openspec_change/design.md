# Design

## Context
The vitals ingestion pipeline receives FHIR Observation resources from third-party vendor connectors over WebSocket connections and publishes them to an internal event bus for downstream processing. PHI flows across this boundary, creating HIPAA obligations for de-identification, access control, and audit. The system must meet strict latency and availability targets to support clinical use cases. Vendor connectors represent an external trust boundary that requires strong authentication and contractual controls before data may flow.

## Goals
- Ensure all PHI is de-identified at egress using a deterministic, reversible HMAC-SHA256 scheme compliant with HIPAA Safe Harbor
- Enforce mutual TLS and OAuth 2.0 client_credentials authentication for every vendor connector with automated certificate lifecycle management
- Bound WebSocket session lifetime to 15 minutes of inactivity with cryptographically bound re-authentication
- Formally specify and continuously measure ingest latency (p95 and p99) and monthly uptime SLAs
- Exclude vendor network transit time from internal SLA accounting while tracking it separately

## Non-Goals
- Re-identification workflows beyond providing a PHI-classified mapping store accessible to authorized services
- Management of vendor-side certificate infrastructure or OAuth authorization servers
- Modification of FHIR resource schemas beyond Safe Harbor identifier removal and reference tokenization
- End-to-end latency SLA inclusive of vendor network transit

## Decisions
1. At egress, replace FHIR Observation.subject.reference and Observation.encounter.reference with a deterministic HMAC-SHA256 token keyed per-deployment, remove all 18 HIPAA Safe Harbor identifiers, and retain a mapping table in a PHI-classified store. (card_id=0be92de1)
2. All vendor connectors must authenticate via mutual TLS (internal PKI, 90-day rotation) combined with OAuth 2.0 client_credentials scoped to read:vitals, and may not be activated without a signed BAA and vendor management approval ticket. (card_id=8035279b)
3. Monthly uptime target is 99.95%; p95 ingest latency must be <100ms measured at the WebSocket boundary, excluding upstream vendor latency. (card_id=c48f7fbe)
4. WebSocket sessions carrying PHI must terminate after 15 minutes of no data frames; clients must re-authenticate via a short-lived JWT (max 15-minute expiry) before reconnecting; session tokens are bound to the originating TLS session ID. (card_id=36cffec4)
5. The <100ms SLA is defined as p99 latency from the first TCP/WebSocket data frame at the API gateway NIC to event bus publish acknowledgment, measured continuously via distributed tracing; vendor network transit is excluded and tracked separately. (card_id=68b81a47)

## Risks / Trade-offs
- **Risk**: HMAC key compromise exposes all tokenized references to re-linkage — **Mitigation**: Per-deployment key storage in a secrets manager with envelope encryption; key rotation triggers re-tokenization of the mapping table
- **Risk**: 90-day certificate rotation may cause connector downtime if automation fails — **Mitigation**: Automated rotation with 14-day overlap validity window and alerting at 30 days before expiry
- **Risk**: 15-minute session timeout may cause data gaps if client re-authentication is slow — **Mitigation**: Clients must initiate JWT refresh before the timeout window closes; server sends a pre-expiry warning frame at 13 minutes
- **Risk**: p99 latency target is stricter than p95 SLA and may be breached under burst load — **Mitigation**: Continuous distributed tracing with alerting at p99 >80ms; auto-scaling triggers below SLA threshold