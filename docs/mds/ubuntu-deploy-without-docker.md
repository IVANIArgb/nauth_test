# Развёртывание на Ubuntu без Docker

Скрипты: **`scripts/deploy/`**

| Файл | Назначение |
|------|------------|
| `setup-ubuntu.sh` | Первая установка (apt, git, venv, `.env`) |
| `run-server.sh` | Запуск |
| `update.sh` | `git pull` + pip |

Короткие обёртки в корне: `./setup-ubuntu.sh`, `./run-server.sh`, `./update.sh` → вызывают `scripts/deploy/`.

Windows: только **`update.bat`** в корне (делегирует в `scripts/deploy/update.bat`).

## Авто `.env`

При установке создаётся/дополняется `.env`:

- `TEST_MODE=true` — админ-роли в API, seed БД, терминал
- `TEST_MODE_AUTH_BYPASS=false` — **без** подмены логина (нужен Kerberos/Windows/LDAP)
- `ROOT_TEST_AUTH_ENABLED=false`, `DOCKER_AUTH_FALLBACK=false`
- `DB_SEED_ON_START=true`, `TERMINAL_ROLE_COMMANDS_ENABLED=true`

Повторная синхронизация ключей: `python start/setup_env.py --sync-auto --skip-venv`

## Быстрый старт

```bash
chmod +x setup-ubuntu.sh run-server.sh update.sh
./setup-ubuntu.sh
./run-server.sh
```
