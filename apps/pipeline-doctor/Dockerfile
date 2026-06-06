# syntax=docker/dockerfile:1.7
FROM python:3.11-slim AS builder
WORKDIR /build
RUN pip install --no-cache-dir build
COPY pyproject.toml ./
COPY pipeline_doctor ./pipeline_doctor
COPY templates ./templates
COPY README.md ./
# Install the local ledger-core wheel first (mounted at build time)
COPY --from=ledger-core / /ledger-core
RUN pip install --no-cache-dir /ledger-core
RUN pip install --no-cache-dir .

FROM python:3.11-slim AS runtime
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates gh \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python deps from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy templates + standards bundles (mounted at /app/standards-bundles by Container Job volume)
COPY templates /app/templates
ENV STANDARDS_BUNDLES_ROOT=/app/standards-bundles
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "-m", "pipeline_doctor"]
CMD ["--mode", "dry-run"]
