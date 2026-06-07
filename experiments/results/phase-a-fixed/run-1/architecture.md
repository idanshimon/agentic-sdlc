# Solution Architecture: Vendor Vitals Ingest & Cardiology Event Bus

---

## Components & Data Flow

- **Vendor Connector Layer** — One connector pod per vendor; authenticates inbound monitor streams via **mutual TLS (internal PKI client cert) + OAuth 2.0 `client_credentials` / `read:vitals` scope** before any data is accepted. Credential rotation job enforces 90-day expiry with Security Architecture gate. *(Decision: mTLS + OAuth)*

- **WebSocket Ingest Gateway** — Terminates vendor WebSocket connections. Validates **RS256 signed JWT (15-min TTL) in the HTTP Upgrade `Authorization` header** at connection establishment; tears down and forces re-auth on expiry. Exposes the p95 <100 ms ingest latency SLO measurement point here — all latency budgets are scoped to this boundary, excluding upstream vendor jitter. *(Decisions: JWT WebSocket auth; 99.95% uptime / <100 ms p95)*

- **Raw FHIR Observation Buffer** — Short-lived, encrypted-at-rest internal Kafka topic (retention ≤ 5 min). Holds unredacted FHIR payloads **inside the PHI trust boundary**; never exposed externally. *(Decision: Safe Harbor strip/tokenize at egress)*

- **PHI Redaction / Tokenization Service** — Consumes from the