#!/usr/bin/env sh
# Подготовка файлов Kerberos для docker-compose.kerberos.yml (Linux/macOS).
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -f kerberos/krb5.conf ]; then
  cp kerberos/krb5.conf.example kerberos/krb5.conf
  echo "Создан kerberos/krb5.conf из примера — отредактируйте realm и KDC."
fi

if [ ! -f kerberos/http.keytab ]; then
  : > kerberos/http.keytab
  echo "Создан пустой kerberos/http.keytab — замените на реальный keytab."
fi

echo "Готово. Заполните .env (см. kerberos/env.kerberos.example), затем:"
echo "  docker compose -f docker-compose.yml -f docker-compose.kerberos.yml --env-file .env up -d --build"
