#!/usr/bin/env sh
# Запуск на хостинге (Linux). Требуется .env из docker.env.hosting.example
set -eu
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "Create .env from docker.env.hosting.example"
  exit 1
fi

docker compose -f docker-compose.yml -f docker-compose.hosting.yml up -d --build
echo "Site: http://localhost:${WEB_PORT:-8080}/"
