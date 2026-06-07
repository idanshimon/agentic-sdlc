# Solution Architecture: Clinical Vitals Ingest Platform

## Components & Data Flow

- **Vendor WebSocket Gateway** — Terminates all inbound vendor WebSocket connections; enforces dual-factor auth (mTLS certificate validation + OAuth 2.0 `vitals:ingest` token introspection) before any session is established or PHI traverses the boundary. *(Decision: dual-factor auth requirement)* Horizontally scaled behind a Layer-4 load balancer to support the 99.95% uptime SLA; p95 latency budget is measured and emitted as a metric at this boundary. *(Decision: 99.95% / <100ms SLA)*

- **Internal Authorization Server** — Issues short-lived OAuth 2.0 client-credentials tokens scoped to `vitals:ingest`; validates vendor certificate CN/SAN against an approved-connector registry before token issuance. Acts as the single trust anchor for vendor identity. *(Decision: dual-factor auth requirement)*

- **PHI Tokenization Service** — Receives raw FHIR Observation resources from the Gateway before any downstream publication; deterministically replaces all 18 HIPAA Safe Harbor identifiers (name, MRN, dates beyond year, device IDs, geographic data, etc.) with reversible tokens keyed per-patient. Token mappin