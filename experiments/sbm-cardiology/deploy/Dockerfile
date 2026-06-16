# Dockerfile for the SBM cardiology deterioration alert service.
# Built from the pipeline-emitted app.py + tests/test_app.py.
#
# Container Apps target: ca-sbm-cardiology-alerts on the existing
# acragenticsdlctj6c673gu6x5w.azurecr.io registry. Same naming convention as
# the other v0.7 services so the customer demo doesn't have a one-off.
FROM python:3.11-slim

WORKDIR /app

# Install runtime + test deps. Keep test deps in the image so we can run
# pytest against the deployed image (proof that the pipeline-emitted tests
# pass against the pipeline-emitted impl on the same artifact that Chen sees).
RUN pip install --no-cache-dir \
    fastapi==0.115.0 \
    uvicorn[standard]==0.32.0 \
    pydantic==2.9.2 \
    pytest==8.3.3 \
    httpx==0.27.2

COPY app.py /app/app.py
COPY tests/ /app/tests/

# Container Apps reads PORT from env; default 8000 for local docker run.
ENV PORT=8000
EXPOSE 8000

# Liveness probe surface — tested by Container Apps every 30s.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen(f'http://localhost:{__import__(\"os\").environ.get(\"PORT\", 8000)}/healthz').read()" || exit 1

CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT}"]
