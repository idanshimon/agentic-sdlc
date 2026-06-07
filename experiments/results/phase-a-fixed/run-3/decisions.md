# Decisions for run 794a1818-a11d-40f5-b59a-24bf8ad3d9d1
Team: experiment-phase-a-run-3

- **50bea3ba** accept: Define a canonical redaction manifest: patient MRN, name, DOB, and device serial number are masked before publishing to the clinical event bus. Cardiology consumers receive a pseudonymous encounter token instead. Redaction applies to ALL egress points including vendor connectors.
- **720d3204** accept: Each vendor connector must authenticate via mutual TLS (client certificate issued by internal PKI) combined with OAuth 2.0 client_credentials grant scoped to 'vitals:ingest'. Certificates rotate every 90 days; revocation via OCSP is mandatory.
- **0b988942** swap: 99.95% monthly uptime; <100ms p95 ingest latency measured at the WebSocket boundary, excluding upstream vendor latency.
- **76b48106** accept: Prior to Q3 FY26 launch, the Privacy Office must approve a documented Data Access Matrix specifying exactly which FHIR Observation fields, patient identifiers, and vital sign types the Cardiology consumer may receive. This matrix is enforced as a filter in the event bus subscription configuration.
- **f19d3997** accept: The <100ms SLA is defined as the p99 latency from the timestamp of WebSocket frame receipt at the API gateway to the event bus publish acknowledgment. Measured via distributed tracing (OpenTelemetry) and reported in 1-minute rolling windows.