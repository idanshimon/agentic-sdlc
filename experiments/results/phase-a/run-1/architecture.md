# Solution Architecture: Real-Time Vitals Ingestion Platform

---

## Components & Data Flow

- **WebSocket API Gateway** — Terminates WebSocket connections from downstream clinical consumers. Validates RS256-signed JWT (≤15 min TTL, `vitals:subscribe` scope, approved service-account subject) *before* completing the HTTP 101 handshake; rejects upgrades on any token failure. *(Decision: WebSocket JWT auth)*

- **Vendor Connector Layer** — One connector process per vendor, each authenticated via mTLS (internal PKI, 90-day cert rotation) + OAuth 2.0 `client_credentials` grant scoped to `vitals:ingest`. Connector activation is gated on a signed BAA and a Security Architecture approval ticket stored in the service registry. *(Decision: mTLS + OAuth vendor auth)*

- **PHI De-identification Sidecar** — Runs as an in-process or co-located sidecar on each connector. At egress, replaces `Observation.subject` and `Observation.encounter` with a deterministic HMAC-SHA256 token (rotating secret, managed via secrets manager). All remaining 18 HIPAA Safe Harbor identifiers are removed or tokenized before any message leaves the connector boundary. *(Decision: HMAC tokenization at egress)*

- **Toke