#!/usr/bin/env bash
# Полная установка на Ubuntu без Docker.
set -euo pipefail

REPO_URL="${LSITE_REPO:-${NAUTH_REPO:-https://github.com/IVANIArgb/LSiteSV.git}}"
BRANCH="${LSITE_BRANCH:-${NAUTH_BRANCH:-main}}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
if [[ -n "${LSITE_INSTALL_DIR:-}" ]]; then
  INSTALL_DIR="$LSITE_INSTALL_DIR"
elif [[ -n "${NAUTH_INSTALL_DIR:-}" ]]; then
  INSTALL_DIR="$NAUTH_INSTALL_DIR"
elif [[ -f "$PROJECT_ROOT/run.py" ]]; then
  INSTALL_DIR="$PROJECT_ROOT"
else
  INSTALL_DIR="${HOME}/LSiteSV"
fi

log() { printf '\n[setup] %s\n' "$*"; }
die() { printf '\n[setup] ОШИБКА: %s\n' "$*" >&2; exit 1; }

if [[ "$(id -u)" -eq 0 ]]; then SUDO=""; else SUDO="sudo"; fi

log "Системные пакеты..."
$SUDO apt-get update -qq
$SUDO apt-get install -y -qq git ca-certificates curl python3 python3-venv python3-pip \
  python3-dev build-essential libldap2-dev libsasl2-dev libssl-dev

if [[ ! -d "$INSTALL_DIR/.git" ]]; then
  if [[ -f "$INSTALL_DIR/run.py" ]]; then
    log "Проект без .git — установка в $INSTALL_DIR"
  else
    log "Клонирование $REPO_URL ($BRANCH)..."
    git clone --branch "$BRANCH" --depth 1 "$REPO_URL" "$INSTALL_DIR"
  fi
else
  git -C "$INSTALL_DIR" fetch origin "$BRANCH" --depth 1 || true
  git -C "$INSTALL_DIR" checkout -B "$BRANCH" "origin/$BRANCH" 2>/dev/null || true
  git -C "$INSTALL_DIR" pull --ff-only origin "$BRANCH" 2>/dev/null || true
fi

cd "$INSTALL_DIR"
REQ="requirements-prod.txt"
[[ -f "$REQ" ]] || REQ="requirements.txt"

[[ -d venv ]] || python3 -m venv venv
# shellcheck disable=SC1091
source venv/bin/activate
python -m pip install --upgrade pip wheel
python -m pip install -r "$REQ"
python start/setup_env.py --sync-auto

chmod +x scripts/deploy/*.sh 2>/dev/null || true
log "Готово. Запуск: ./scripts/deploy/run-server.sh"
