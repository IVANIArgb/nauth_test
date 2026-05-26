#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
[[ -d venv ]] || { echo "Сначала: ./scripts/deploy/setup-ubuntu.sh"; exit 1; }
# shellcheck disable=SC1091
source venv/bin/activate
[[ -f .env ]] && set -a && source .env && set +a
export HOST="${HOST:-0.0.0.0}"
export PORT="${PORT:-8000}"
export FLASK_ENV="${FLASK_ENV:-development}"
export RUN_WITH_GUNICORN="${RUN_WITH_GUNICORN:-true}"
echo "[run] http://${HOST}:${PORT}/"
exec python run.py
