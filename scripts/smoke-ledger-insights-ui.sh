#!/usr/bin/env bash
# Smoke-test a deployed ledger-insights-ui Container App.
#
# Asserts (per openspec/changes/add-ledger-insights-ui-deploy/specs/ledger-insights-ui-deploy/spec.md REQ-5):
#   - /, /runs, /decisions, /reports, /changes all return HTTP 200
#   - Each route's Content-Length > 1024 (catches empty fallback pages)
#   - /changes body contains "OpenSpec" (catches filesystem-read regression)
#
# Usage:
#   bash scripts/smoke-ledger-insights-ui.sh https://ca-ledger-ui.foo.eastus2.azurecontainerapps.io
#   bash scripts/smoke-ledger-insights-ui.sh http://localhost:3005   # local Demo Mode

set -uo pipefail   # NOT -e — we collect failures

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <base-url>" >&2
    echo "Example: $0 https://ca-ledger-ui.example.eastus2.azurecontainerapps.io" >&2
    exit 64
fi

BASE_URL="${1%/}"   # strip trailing slash
ROUTES=("/" "/runs" "/decisions" "/reports" "/changes")
FAILURES=0
MIN_BODY_BYTES=1024

echo "== Smoke test: $BASE_URL ============================================"

for route in "${ROUTES[@]}"; do
    url="${BASE_URL}${route}"
    printf "%-12s " "$route"

    # -L follows redirects; -w writes status,size on a known line.
    response=$(curl -sSL -o /tmp/smoke-body.html -w "%{http_code} %{size_download}" --max-time 30 "$url" 2>&1) || {
        echo "FAIL (curl error: $response)"
        FAILURES=$((FAILURES + 1))
        continue
    }

    http_code=$(echo "$response" | awk '{print $1}')
    body_size=$(echo "$response" | awk '{print $2}')

    if [[ "$http_code" != "200" ]]; then
        echo "FAIL (status $http_code, expected 200)"
        FAILURES=$((FAILURES + 1))
        continue
    fi

    if [[ "$body_size" -lt "$MIN_BODY_BYTES" ]]; then
        echo "FAIL (body $body_size bytes, expected > $MIN_BODY_BYTES)"
        FAILURES=$((FAILURES + 1))
        continue
    fi

    if [[ "$route" == "/changes" ]]; then
        if ! grep -q "OpenSpec" /tmp/smoke-body.html; then
            echo "FAIL (status 200, body $body_size bytes, but missing 'OpenSpec' literal — filesystem-read regression)"
            FAILURES=$((FAILURES + 1))
            continue
        fi
        echo "PASS (status 200, body ${body_size}B, OpenSpec literal present)"
    else
        echo "PASS (status 200, body ${body_size}B)"
    fi
done

rm -f /tmp/smoke-body.html

echo "===================================================================="
if [[ $FAILURES -eq 0 ]]; then
    echo "All ${#ROUTES[@]} routes PASSED."
    exit 0
else
    echo "FAILURES: $FAILURES of ${#ROUTES[@]} routes failed."
    exit 1
fi
