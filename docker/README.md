# Docker

Все файлы Docker лежат в этой папке. Команды выполняйте **из корня репозитория**.

## Базовый запуск

```bash
docker compose -f docker/docker-compose.yml build
docker compose -f docker/docker-compose.yml up -d
docker compose -f docker/docker-compose.yml logs -f web
```

## Шаблоны `.env`

| Файл | Назначение |
|------|------------|
| `docker.env.example` | Общий dev |
| `docker.env.sso.example` | SSO без keytab |
| `docker.env.sso-ad.example` | SSO + LDAP (AD) |
| `docker.env.hosting.example` | Продакшен на хостинге |

```bash
cp docker/docker.env.example .env
```

## Варианты compose

```bash
# Windows: монтирование C:/ и D:/
docker compose -f docker/docker-compose.yml -f docker/docker-compose.windows.yml up -d

# Flask dev server вместо gunicorn
docker compose -f docker/docker-compose.yml -f docker/docker-compose.dev.yml up --build

# Kerberos + keytab (см. ../kerberos/)
docker compose -f docker/docker-compose.yml -f docker/docker-compose.kerberos.yml --env-file .env up -d --build

# SSO-прокси (nginx)
docker compose -f docker/docker-compose.yml -f docker/docker-compose.sso.yml up -d --build

# Хостинг
docker compose -f docker/docker-compose.yml -f docker/docker-compose.hosting.yml up -d
```

Отдельный сервис Kerberos SSO: каталог `kerberos_ad_service/` (свой `Dockerfile` и `docker-compose.yml`).
