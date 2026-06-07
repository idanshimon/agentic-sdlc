# Solution Architecture: Clinical Vitals Ingest & Distribution Platform

---

## Components & Data Flow

- **Vendor Connector Layer** — Each vendor integration runs as an isolated sidecar/microservice that establishes inbound WebSocket connections to the API Gateway. Every connector authenticates via **mTLS (internal PKI-issued client cert, 90-day rotation) + OAuth 2.0 `client_credentials` grant scoped to `vitals:ingest`**; OCSP revocation checked on every handshake. *(Decision: mTLS + OAuth auth requirement)*

- **API Gateway (WebSocket Termination Point)** — Terminates TLS, validates OAuth bearer token scope, and stamps each frame with a monotonic receipt timestamp. This timestamp is the **official start of the <100ms p99 SLA clock** — measured to event bus publish acknowledgment, reported in 1-minute rolling windows via OpenTelemetry distributed traces. *(Decision: <100ms p99 SLA definition + OTel measurement)*

- **Redaction & Pseudonymization Service** — Synchronous, in-process pipeline stage executed *before any egress*. Applies the **canonical redaction manifest**: masks MRN, patient name, DOB, and device serial number; replaces patient identity with a pseudonymous encounter