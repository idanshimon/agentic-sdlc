# Solution Architecture: Clinical Vital-Signs Ingestion Platform

---

## Components & Data Flow

- **Vendor Connector Layer** — Dedicated adapter pods (one per vendor model: Philips IntelliVue, GE CARESCAPE) terminate inbound device streams. Each pod enforces **mutual TLS** using client certificates issued by the internal CA, then exchanges an **OAuth2 `client_credentials` token** from the internal authorization server before any data is forwarded. No connector is provisioned without a signed BAA and Vendor Management approval on file. *(Decision: mTLS + OAuth2 + BAA requirement)*

- **WebSocket Ingest Gateway** — Stateless, horizontally scaled gateway (target: ≥3 AZs, N+2 redundancy) that accepts normalized device frames over persistent WebSocket connections. The **p95 ingest latency ≤ 100 ms** SLO is measured and alarmed at this boundary; upstream vendor latency is explicitly excluded from the budget. Autoscaling triggers at 70% connection saturation to preserve headroom. *(Decision: <100 ms p95 at WebSocket boundary)*

- **FHIR Normalization Service** — Transforms raw device frames into **FHIR R4 Observation resources** with full PHI intact. Operates exclusively inside the trus