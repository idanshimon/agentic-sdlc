# Agentic SDLC Orchestrator

FastAPI app implementing the 9-stage pipeline graph from
`openspec/changes/bootstrap-agentic-sdlc-foundation/design.md`.

Stages (design.md §2):
```
Ingest → Assessor → [Gate 1: Resolver — HITL] → Architect → [Gate 2: Design Review]
       → Test Plan → CodeGen → Review/Scan → [Gate 3: Policy] → Deliver
```

## Routes
- `POST /api/run` — multipart PRD upload, returns `{run_id, stream_url}`
- `GET  /api/runs/{run_id}/stream` — Server-Sent Events of stage progress
- `POST /api/runs/{run_id}/approve` — accept/swap a card (writes typed ledger entry, `suggest` status only — design.md §4)
- `POST /api/runs/{run_id}/reject` — reject-with-note (one-keystroke default — §3)
- `POST /api/runs/{run_id}/demote` — synchronous demote (§4); back-trace report is async
- `GET  /healthz` — liveness

## Files
| File | Purpose |
|---|---|
| `main.py` | FastAPI app + SSE + gate orchestration |
| `stages.py` | One async generator per stage |
| `providers/` | Multi-provider abstraction (AOAI, Foundry, Databricks, Anthropic direct). See `docs/PROVIDERS.md` |
| `ledger.py` | Cosmos client, team-partitioned, invariant write-block |
| `decisions_md.py` | Immutable per-run markdown to Blob `decisions` |
| `telemetry.py` | OTel → App Insights (re-run + human-attention cost) |
| `models.py` | Pydantic models |
| `config.py` | Env-var settings |

## Local dev

```bash
cd apps/orchestrator
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Auth for Cosmos / Blob / APIM via AAD; APIM sub key optional for local stub mode.
az login
export APIM_SUBSCRIPTION_KEY=...     # optional; absent → APIM call falls back to stub
export APPLICATIONINSIGHTS_CONNECTION_STRING="$(cat ../../logs/appi-conn.txt)"

uvicorn orchestrator.main:app --reload --port 8000
```

Smoke test:
```bash
curl -F prd=@sample-prd.md -F team_id=team-demo http://localhost:8000/api/run
# then in another shell:
curl -N http://localhost:8000/api/runs/<run_id>/stream
# approve the Resolver gate:
curl -X POST http://localhost:8000/api/runs/<run_id>/approve \
  -H 'Content-Type: application/json' \
  -d '{"card_id":"<card>","decision_kind":"accept","resolution_text":"care-team scope","actor":"alice@hca"}'
```

## Deploy (Azure Container Apps)

```bash
RG=<your resource group>
ACR=<your acr>      # or use az acr build with a workspace ACR
az acr build -r $ACR -t orchestrator:demo -f Dockerfile .

# Execution-plane targets are REQUIRED — the orchestrator refuses to start
# (validate_runtime_settings) if COSMOS_ENDPOINT or a storage account is unset,
# rather than falling back to a default and hanging on the first blob write.
# Storage accepts either STORAGE_ACCOUNT_URL (full URL) or STORAGE_ACCOUNT_NAME
# (bare name — the URL is derived as https://<name>.blob.core.windows.net).
az containerapp create \
  -g $RG -n orchestrator \
  --image $ACR.azurecr.io/orchestrator:demo \
  --ingress external --target-port 8000 \
  --env-vars \
    APIM_BASE_URL=https://<apim-name>.azure-api.net/openai/v1 \
    COSMOS_ENDPOINT=https://<cosmos-name>.documents.azure.com:443/ \
    STORAGE_ACCOUNT_NAME=<storage-account-name> \
    APPLICATIONINSIGHTS_CONNECTION_STRING="$(cat ../../logs/appi-conn.txt)" \
  --system-assigned
```

Grant the container app's managed identity:
- `Cosmos DB Built-in Data Contributor` on your Cosmos account
- `Storage Blob Data Contributor` on your storage account
- APIM subscription key in Key Vault `kv-agen-ab9963` (mount as `APIM_SUBSCRIPTION_KEY`)

## Design notes

- **Bootstrap Mode** (design.md §3) caps gating cards at K=5 by blast-radius cost for the first 30 days. Non-gating cards are logged as `auto-deferred`.
- **Invariant write-block** (design.md §4) refuses `swap` decisions on `phi-classification` / `auth-policy` classes when an org-layer precedent exists.
- **Suggest-only ledger writes** — promotion to `silent_apply` is FDE Phase 1 work, deliberately not in v1.
- **Cost telemetry** — `agentic.tokens.total` + `agentic.cost.usd` (re-run dim) and `agentic.gate.wall_clock_seconds` (human-attention dim).
