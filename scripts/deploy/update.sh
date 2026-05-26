#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
BRANCH="${LSITE_BRANCH:-${NAUTH_BRANCH:-main}}"
[[ -d .git ]] || { echo "Нет git — обновите файлы вручную"; exit 1; }
git fetch origin "$BRANCH"
git checkout -B "$BRANCH" "origin/$BRANCH"
git pull --ff-only origin "$BRANCH"
# shellcheck disable=SC1091
source venv/bin/activate
REQ="requirements-prod.txt"; [[ -f "$REQ" ]] || REQ="requirements.txt"
python -m pip install -r "$REQ"
python start/setup_env.py --sync-auto --skip-venv
echo "Перезапуск: ./scripts/deploy/run-server.sh"
