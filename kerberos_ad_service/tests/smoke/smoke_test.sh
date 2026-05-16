#!/usr/bin/env bash
set -euo pipefail

URL="${SMOKE_URL:-http://127.0.0.1:5000/health}"
status_code=$(curl -sS -o /tmp/smoke.out -w "%{http_code}" "$URL")

if [[ "$status_code" -ne 200 && "$status_code" -ne 503 ]]; then
  echo "Unexpected health status: $status_code"
  cat /tmp/smoke.out
  exit 1
fi

echo "Smoke test passed with status $status_code"
