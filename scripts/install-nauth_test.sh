#!/usr/bin/env bash
# Установка nauth_test на Linux: curl -fsSL .../install-nauth_test.sh | bash
set -euo pipefail

REPO_URL="${NAUTH_REPO:-https://github.com/IVANIArgh/nauth_test.git}"
INSTALL_DIR="${NAUTH_INSTALL_DIR:-$HOME/nauth_test}"
SSO_USER="${NAUTH_SSO_USER:-testadmin}"
WEB_PORT="${NAUTH_WEB_PORT:-8080}"

command -v git >/dev/null || { echo "Установите git"; exit 1; }
command -v docker >/dev/null || { echo "Установите Docker"; exit 1; }

if [[ ! -d "$INSTALL_DIR/.git" ]]; then
  git clone "$REPO_URL" "$INSTALL_DIR"
else
  git -C "$INSTALL_DIR" pull --ff-only
fi
cd "$INSTALL_DIR"

if [[ ! -f .env ]]; then
  cp -f docker.env.sso.example .env 2>/dev/null || cp -f docker.env.example .env
fi

upsert_env() {
  local key="$1" val="$2"
  if grep -q "^${key}=" .env 2>/dev/null; then
    sed -i "s|^${key}=.*|${key}=${val}|" .env
  else
    echo "${key}=${val}" >> .env
  fi
}

upsert_env SSO_DEFAULT_USER "$SSO_USER"
upsert_env WEB_PORT "$WEB_PORT"
upsert_env TRUST_REMOTE_USER true
upsert_env DOCKER_AUTH_FALLBACK false

docker compose -f docker-compose.yml -f docker-compose.sso.yml up -d --build

echo ""
echo "Готово: http://localhost:${WEB_PORT}/user/info-test (логин: ${SSO_USER})"
